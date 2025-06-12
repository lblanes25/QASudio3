"""
Workflow State Manager for Progressive Disclosure UI
Manages the state transitions and visibility of UI sections in the validation workflow
"""

from enum import Enum, auto
from typing import Optional, Set, Callable
from PySide6.QtCore import QObject, Signal
import logging

logger = logging.getLogger(__name__)


class WorkflowState(Enum):
    """Enumeration of workflow states"""
    INITIAL = auto()                # No data loaded
    DATA_LOADED = auto()           # Data source loaded, show responsible party
    COLUMN_SELECTED = auto()       # Responsible party selected, show rules
    RULES_SELECTED = auto()        # Rules selected, show validation controls
    VALIDATION_READY = auto()      # Ready to start validation
    VALIDATION_RUNNING = auto()    # Validation in progress
    VALIDATION_COMPLETE = auto()   # Validation finished
    ERROR = auto()                 # Error state


class WorkflowStateManager(QObject):
    """
    Manages workflow state transitions and emits signals for UI updates
    """
    
    # Signals
    stateChanged = Signal(WorkflowState, WorkflowState)  # old_state, new_state
    sectionVisibilityChanged = Signal(str, bool)  # section_name, visible
    statusMessage = Signal(str, str)  # message, level (info/warning/error)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_state = WorkflowState.INITIAL
        self._previous_state = None
        self._locked_sections: Set[str] = set()
        
        # State transition rules
        self._valid_transitions = {
            WorkflowState.INITIAL: [WorkflowState.DATA_LOADED, WorkflowState.ERROR],
            WorkflowState.DATA_LOADED: [WorkflowState.COLUMN_SELECTED, WorkflowState.INITIAL, WorkflowState.ERROR],
            WorkflowState.COLUMN_SELECTED: [WorkflowState.RULES_SELECTED, WorkflowState.DATA_LOADED, WorkflowState.INITIAL, WorkflowState.ERROR],
            WorkflowState.RULES_SELECTED: [WorkflowState.VALIDATION_READY, WorkflowState.COLUMN_SELECTED, WorkflowState.DATA_LOADED, WorkflowState.INITIAL, WorkflowState.ERROR],
            WorkflowState.VALIDATION_READY: [WorkflowState.VALIDATION_RUNNING, WorkflowState.RULES_SELECTED, WorkflowState.COLUMN_SELECTED, WorkflowState.DATA_LOADED, WorkflowState.INITIAL, WorkflowState.ERROR],
            WorkflowState.VALIDATION_RUNNING: [WorkflowState.VALIDATION_COMPLETE, WorkflowState.ERROR],
            WorkflowState.VALIDATION_COMPLETE: [WorkflowState.INITIAL, WorkflowState.DATA_LOADED, WorkflowState.COLUMN_SELECTED, WorkflowState.RULES_SELECTED, WorkflowState.VALIDATION_READY],
            WorkflowState.ERROR: [WorkflowState.INITIAL, WorkflowState.DATA_LOADED]
        }
        
        # Section visibility rules
        self._section_visibility = {
            'data_source': [WorkflowState.INITIAL, WorkflowState.DATA_LOADED, WorkflowState.COLUMN_SELECTED, 
                          WorkflowState.RULES_SELECTED, WorkflowState.VALIDATION_READY, WorkflowState.VALIDATION_RUNNING, 
                          WorkflowState.VALIDATION_COMPLETE, WorkflowState.ERROR],
            'responsible_party': [WorkflowState.DATA_LOADED, WorkflowState.COLUMN_SELECTED, WorkflowState.RULES_SELECTED, 
                                WorkflowState.VALIDATION_READY, WorkflowState.VALIDATION_RUNNING, WorkflowState.VALIDATION_COMPLETE],
            'rule_selection': [WorkflowState.COLUMN_SELECTED, WorkflowState.RULES_SELECTED, WorkflowState.VALIDATION_READY, 
                             WorkflowState.VALIDATION_RUNNING, WorkflowState.VALIDATION_COMPLETE],
            'validation_controls': [WorkflowState.RULES_SELECTED, WorkflowState.VALIDATION_READY, WorkflowState.VALIDATION_RUNNING, 
                                  WorkflowState.VALIDATION_COMPLETE],
            'progress_tracking': [WorkflowState.VALIDATION_RUNNING, WorkflowState.VALIDATION_COMPLETE],
            'results_summary': [WorkflowState.VALIDATION_COMPLETE]
        }
        
    @property
    def current_state(self) -> WorkflowState:
        """Get current workflow state"""
        return self._current_state
    
    def can_transition_to(self, new_state: WorkflowState) -> bool:
        """Check if transition to new state is valid"""
        return new_state in self._valid_transitions.get(self._current_state, [])
    
    def transition_to(self, new_state: WorkflowState, message: Optional[str] = None) -> bool:
        """
        Transition to a new state if valid
        
        Args:
            new_state: Target state
            message: Optional status message for the transition
            
        Returns:
            True if transition was successful
        """
        if not self.can_transition_to(new_state):
            logger.warning(f"Invalid state transition: {self._current_state} -> {new_state}")
            return False
        
        old_state = self._current_state
        self._previous_state = old_state
        self._current_state = new_state
        
        logger.info(f"State transition: {old_state.name} -> {new_state.name}")
        
        # Emit state change signal
        self.stateChanged.emit(old_state, new_state)
        
        # Update section visibility
        self._update_section_visibility(old_state, new_state)
        
        # Emit status message if provided
        if message:
            level = "error" if new_state == WorkflowState.ERROR else "info"
            self.statusMessage.emit(message, level)
        
        # Handle special transitions
        self._handle_state_transition_effects(old_state, new_state)
        
        return True
    
    def _update_section_visibility(self, old_state: WorkflowState, new_state: WorkflowState):
        """Update visibility of UI sections based on state change"""
        for section, visible_states in self._section_visibility.items():
            was_visible = old_state in visible_states
            is_visible = new_state in visible_states
            
            if section in self._locked_sections:
                # Don't hide locked sections
                is_visible = is_visible or was_visible
            
            if was_visible != is_visible:
                self.sectionVisibilityChanged.emit(section, is_visible)
    
    def _handle_state_transition_effects(self, old_state: WorkflowState, new_state: WorkflowState):
        """Handle special effects of state transitions"""
        # Lock sections during validation
        if new_state == WorkflowState.VALIDATION_RUNNING:
            self._locked_sections = {'data_source', 'responsible_party', 'rule_selection', 'validation_controls'}
            self.statusMessage.emit("Validation in progress. Controls are locked.", "info")
        elif old_state == WorkflowState.VALIDATION_RUNNING:
            self._locked_sections.clear()
        
        # Cascade resets based on backward navigation
        if old_state == WorkflowState.DATA_LOADED and new_state == WorkflowState.INITIAL:
            self.statusMessage.emit("Data source changed. Workflow reset.", "info")
        elif old_state == WorkflowState.COLUMN_SELECTED and new_state == WorkflowState.DATA_LOADED:
            self.statusMessage.emit("Responsible party column changed. Rule selection cleared.", "info")
        elif old_state == WorkflowState.RULES_SELECTED and new_state == WorkflowState.COLUMN_SELECTED:
            self.statusMessage.emit("Rule selection modified. Validation state reset.", "info")
    
    def reset_to_initial(self):
        """Reset workflow to initial state"""
        self._locked_sections.clear()
        self.transition_to(WorkflowState.INITIAL, "Workflow reset to initial state")
    
    def handle_data_loaded(self):
        """Handle successful data loading"""
        if self._current_state == WorkflowState.INITIAL:
            self.transition_to(WorkflowState.DATA_LOADED, "Data loaded successfully")
        elif self._current_state in [WorkflowState.COLUMN_SELECTED, WorkflowState.RULES_SELECTED, 
                                    WorkflowState.VALIDATION_READY, WorkflowState.VALIDATION_COMPLETE]:
            # Data source changed - cascade reset
            self.transition_to(WorkflowState.DATA_LOADED, "Data source changed. Previous selections cleared.")
    
    def handle_column_selected(self, column_name: str):
        """Handle responsible party column selection"""
        if self._current_state == WorkflowState.DATA_LOADED:
            self.transition_to(WorkflowState.COLUMN_SELECTED, f"Responsible party column set: {column_name}")
        elif self._current_state in [WorkflowState.RULES_SELECTED, WorkflowState.VALIDATION_READY, 
                                    WorkflowState.VALIDATION_COMPLETE]:
            # Column changed - partial reset
            self.transition_to(WorkflowState.COLUMN_SELECTED, f"Column changed to: {column_name}. Rule selection cleared.")
    
    def handle_rules_selected(self, rule_count: int):
        """Handle rule selection"""
        if rule_count > 0 and self._current_state == WorkflowState.COLUMN_SELECTED:
            self.transition_to(WorkflowState.RULES_SELECTED, f"{rule_count} rules selected")
        elif rule_count > 0 and self._current_state in [WorkflowState.RULES_SELECTED, WorkflowState.VALIDATION_READY]:
            # Stay in current state but update message
            self.statusMessage.emit(f"{rule_count} rules selected", "info")
        elif rule_count == 0 and self._current_state in [WorkflowState.RULES_SELECTED, WorkflowState.VALIDATION_READY]:
            # No rules selected - go back
            self.transition_to(WorkflowState.COLUMN_SELECTED, "No rules selected")
    
    def handle_validation_ready(self):
        """Mark validation as ready to start"""
        if self._current_state == WorkflowState.RULES_SELECTED:
            self.transition_to(WorkflowState.VALIDATION_READY, "Ready to start validation")
    
    def handle_validation_started(self):
        """Handle validation start"""
        if self._current_state == WorkflowState.VALIDATION_READY:
            self.transition_to(WorkflowState.VALIDATION_RUNNING, "Validation started")
    
    def handle_validation_complete(self, success: bool, message: str):
        """Handle validation completion"""
        if self._current_state == WorkflowState.VALIDATION_RUNNING:
            if success:
                self.transition_to(WorkflowState.VALIDATION_COMPLETE, message)
            else:
                self.transition_to(WorkflowState.ERROR, message)
    
    def handle_error(self, error_message: str):
        """Handle error state"""
        self.transition_to(WorkflowState.ERROR, error_message)
    
    def is_section_visible(self, section_name: str) -> bool:
        """Check if a section should be visible in current state"""
        return self._current_state in self._section_visibility.get(section_name, [])
    
    def is_section_locked(self, section_name: str) -> bool:
        """Check if a section is locked"""
        return section_name in self._locked_sections
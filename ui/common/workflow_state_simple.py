"""
Simplified Workflow State Tracker
Only tracks state for logging and analytics - does not control UI visibility
"""

from enum import Enum, auto
from typing import Optional, Dict, List
from PySide6.QtCore import QObject, Signal
import logging
import datetime

logger = logging.getLogger(__name__)


class WorkflowState(Enum):
    """Simple workflow states for tracking"""
    INITIAL = "initial"
    DATA_LOADED = "data_loaded"
    RULES_SELECTED = "rules_selected"
    VALIDATION_READY = "validation_ready"
    VALIDATION_RUNNING = "validation_running"
    VALIDATION_COMPLETE = "validation_complete"
    ERROR = "error"


class WorkflowStateTracker(QObject):
    """
    Simple state tracker for analytics and logging.
    Does NOT control UI visibility - only tracks workflow progression.
    """
    
    # Signals
    stateChanged = Signal(str, str)  # old_state, new_state
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_state = WorkflowState.INITIAL.value
        self.state_history: List[Dict] = []
        self.session_start = datetime.datetime.now()
        self.validation_start = None
        self.validation_end = None
        
    def update_state(self, new_state: str, metadata: Optional[Dict] = None):
        """
        Update state for tracking purposes only.
        
        Args:
            new_state: New state name
            metadata: Optional metadata about the state change
        """
        old_state = self.current_state
        self.current_state = new_state
        
        # Record state change
        entry = {
            'timestamp': datetime.datetime.now(),
            'old_state': old_state,
            'new_state': new_state,
            'metadata': metadata or {},
            'elapsed_seconds': self.get_elapsed_time()
        }
        self.state_history.append(entry)
        
        # Special handling for validation timing
        if new_state == WorkflowState.VALIDATION_RUNNING.value:
            self.validation_start = datetime.datetime.now()
        elif new_state == WorkflowState.VALIDATION_COMPLETE.value:
            self.validation_end = datetime.datetime.now()
        
        # Log state change
        logger.info(f"Workflow state: {old_state} -> {new_state}")
        if metadata:
            logger.debug(f"State metadata: {metadata}")
        
        # Emit signal
        self.stateChanged.emit(old_state, new_state)
        
    def get_elapsed_time(self) -> float:
        """Get elapsed time since session start in seconds"""
        return (datetime.datetime.now() - self.session_start).total_seconds()
        
    def get_validation_duration(self) -> Optional[float]:
        """Get validation duration in seconds if available"""
        if self.validation_start and self.validation_end:
            return (self.validation_end - self.validation_start).total_seconds()
        elif self.validation_start:
            # Still running
            return (datetime.datetime.now() - self.validation_start).total_seconds()
        return None
        
    def get_session_summary(self) -> Dict:
        """Get summary of the current session"""
        return {
            'session_start': self.session_start.isoformat(),
            'current_state': self.current_state,
            'state_changes': len(self.state_history),
            'elapsed_time': self.get_elapsed_time(),
            'validation_duration': self.get_validation_duration(),
            'states_visited': list(set(entry['new_state'] for entry in self.state_history))
        }
        
    def reset(self):
        """Reset tracker for new session"""
        self.current_state = WorkflowState.INITIAL.value
        self.state_history = []
        self.session_start = datetime.datetime.now()
        self.validation_start = None
        self.validation_end = None
        logger.info("Workflow state tracker reset")
        
    def export_history(self) -> List[Dict]:
        """Export state history for analytics"""
        return self.state_history.copy()
        
    def log_error(self, error_message: str, error_details: Optional[Dict] = None):
        """Log an error state with details"""
        self.update_state(WorkflowState.ERROR.value, {
            'error_message': error_message,
            'error_details': error_details or {},
            'previous_state': self.current_state
        })
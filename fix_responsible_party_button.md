# Fix for Disappearing Validation Button

## Problem
When you reselect the responsible party dropdown after choosing tests, the validation button disappears because the workflow state is being reset backwards.

## Solution
Update the `_on_responsible_party_changed` method in `main_application.py` (around line 1665):

### Current Code (PROBLEMATIC):
```python
def _on_responsible_party_changed(self, index: int):
    """Handle responsible party column selection changes."""
    # Update leader packs warning visibility
    if self.leader_packs_checkbox.isChecked() and index == 0:  # "None" selected
        self.leader_packs_warning.setVisible(True)
    else:
        self.leader_packs_warning.setVisible(False)
    
    # Update workflow state
    if hasattr(self, 'workflow_state'):
        if index > 0:  # Not "None"
            column_name = self.responsible_party_combo.currentText()
            self.workflow_state.handle_column_selected(column_name)
        else:
            # Going backward - check if we need to reset state
            from ui.common.workflow_state import WorkflowState
            if self.workflow_state.current_state in [WorkflowState.COLUMN_SELECTED, WorkflowState.RULES_SELECTED, 
                                                   WorkflowState.VALIDATION_READY, WorkflowState.VALIDATION_COMPLETE]:
                self.workflow_state.transition_to(WorkflowState.DATA_LOADED)
```

### Fixed Code:
```python
def _on_responsible_party_changed(self, index: int):
    """Handle responsible party column selection changes."""
    # Update leader packs warning visibility
    if self.leader_packs_checkbox.isChecked() and index == 0:  # "None" selected
        self.leader_packs_warning.setVisible(True)
    else:
        self.leader_packs_warning.setVisible(False)
    
    # Update workflow state - but don't go backwards if we already have rules selected
    if hasattr(self, 'workflow_state'):
        from ui.common.workflow_state import WorkflowState
        current_state = self.workflow_state.current_state
        
        if index > 0:  # Not "None"
            column_name = self.responsible_party_combo.currentText()
            # Only advance state if we're in an earlier state
            if current_state in [WorkflowState.DATA_LOADED, WorkflowState.INITIAL]:
                self.workflow_state.handle_column_selected(column_name)
            # If we're already past this point, just log the change
            else:
                self.log_message(f"Updated responsible party column to: {column_name}")
        else:
            # Only reset if we're specifically at COLUMN_SELECTED with no rules
            # Don't reset if we already have rules selected
            if current_state == WorkflowState.COLUMN_SELECTED:
                # Check if any rules are selected
                selected_rules = self.get_selected_simple_rules()
                if not selected_rules:
                    # No rules selected, safe to go back
                    self.workflow_state.transition_to(WorkflowState.DATA_LOADED)
            # For any other state, don't change the workflow state
```

## Alternative Simpler Fix:
If you want to completely prevent the workflow from going backwards when changing the responsible party:

```python
def _on_responsible_party_changed(self, index: int):
    """Handle responsible party column selection changes."""
    # Update leader packs warning visibility
    if self.leader_packs_checkbox.isChecked() and index == 0:  # "None" selected
        self.leader_packs_warning.setVisible(True)
    else:
        self.leader_packs_warning.setVisible(False)
    
    # Log the change but don't affect workflow state if we're past initial selection
    if hasattr(self, 'workflow_state'):
        from ui.common.workflow_state import WorkflowState
        current_state = self.workflow_state.current_state
        
        if index > 0:  # Not "None"
            column_name = self.responsible_party_combo.currentText()
            # Only advance state if we're in an early state
            if current_state == WorkflowState.DATA_LOADED:
                self.workflow_state.handle_column_selected(column_name)
            else:
                # Just log the change without affecting state
                self.log_message(f"Updated responsible party column to: {column_name}")
```

## Why This Works:
1. The workflow state manager controls which UI sections are visible
2. The validation controls are only visible in states: RULES_SELECTED, VALIDATION_READY, VALIDATION_RUNNING, VALIDATION_COMPLETE
3. When you change the responsible party after selecting rules, the current code resets to DATA_LOADED state
4. The fix prevents backward state transitions when you already have rules selected
5. This keeps the validation button visible while still allowing you to change the responsible party column

## Additional Consideration:
If you're updating to remove the leader_packs_warning as suggested in the reporting update, you can simplify this further:

```python
def _on_responsible_party_changed(self, index: int):
    """Handle responsible party column selection changes."""
    # Just log the change if we're past initial setup
    if index > 0:
        column_name = self.responsible_party_combo.currentText()
        self.log_message(f"Responsible party column: {column_name}")
    
    # Only update workflow state if we're still in early stages
    if hasattr(self, 'workflow_state'):
        from ui.common.workflow_state import WorkflowState
        if self.workflow_state.current_state == WorkflowState.DATA_LOADED and index > 0:
            self.workflow_state.handle_column_selected(self.responsible_party_combo.currentText())
```
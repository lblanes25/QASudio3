# Analytics Runner Refactoring Migration Guide

## Step-by-Step Migration Process

### 1. Add New Dependencies

First, add the new imports to `main_application.py`:

```python
# Add at the top with other imports
from ui.analytics_runner.validation_requirements import ValidationRequirements
from ui.analytics_runner.section_styles import (
    SectionStyles, create_status_icon, create_section_header, update_section_header
)
from ui.common.workflow_state_simple import WorkflowStateTracker
```

### 2. Initialize New Components

In the `__init__` method, add:

```python
# After existing initialization
self.validation_requirements = ValidationRequirements()
self.workflow_tracker = WorkflowStateTracker()  # Replaces WorkflowStateManager
```

### 3. Remove Progressive Disclosure Calls

Search and remove/replace these patterns:

```python
# REMOVE these patterns:
section.hide()
section.show()
self.workflow_state.handle_*  # Any workflow state UI control
self.workflow_state.transition_to()  # When it affects UI

# REPLACE with:
section.setVisible(True)  # Only for progress/results sections
self.update_all_section_states()  # Update visual states instead
```

### 4. Update Section Creation

For each section (data source, rules, etc.), update the creation:

```python
# OLD:
def create_some_section(self):
    section = QWidget()
    # ... content ...
    section.hide()  # Remove this
    return section

# NEW:
def create_some_section(self):
    section = QWidget()
    section.setObjectName("unique_section_name")  # Add this
    layout = QVBoxLayout(section)
    
    # Add header with status
    header = create_section_header("Section Title", "incomplete")
    layout.addWidget(header)
    section.header = header  # Store reference
    
    # ... rest of content ...
    
    # Set initial style
    section.setStyleSheet(SectionStyles.SECTION_INCOMPLETE)
    return section
```

### 5. Update Event Handlers

Replace complex workflow state logic with simple data updates:

```python
# OLD event handler:
def _on_something_changed(self):
    # Complex workflow state management
    if self.workflow_state.current_state == X:
        self.workflow_state.transition_to(Y)
    # UI visibility changes
    self.some_section.show()
    
# NEW event handler:
def _on_something_changed(self):
    # Update data model
    self.validation_requirements.some_property = new_value
    
    # Update UI state
    self.update_all_section_states()
    
    # Log for tracking only
    self.workflow_tracker.update_state("descriptive_state_name")
```

### 6. Key Methods to Update

#### a. `_on_data_source_changed()`
```python
def _on_data_source_changed(self):
    # Update requirements
    self.validation_requirements.data_source_valid = self.data_source_panel.is_valid()
    self.validation_requirements.data_source_path = self.data_source_panel.get_current_file()
    
    # Update UI
    self.update_all_section_states()
    
    # Track state
    if self.validation_requirements.data_source_valid:
        self.workflow_tracker.update_state("data_loaded")
```

#### b. `_on_responsible_party_changed()`
```python
def _on_responsible_party_changed(self, index: int):
    # Update requirements
    if index > 0:
        self.validation_requirements.responsible_party_column = self.responsible_party_combo.currentText()
    else:
        self.validation_requirements.responsible_party_column = None
    
    # Update UI
    self.update_all_section_states()
```

#### c. `_on_rules_selection_changed()`
```python
def _on_rules_selection_changed(self):
    # Update requirements
    self.validation_requirements.selected_rules = self.get_selected_simple_rules()
    
    # Update UI
    self.update_all_section_states()
    
    # Track state
    if len(self.validation_requirements.selected_rules) > 0:
        self.workflow_tracker.update_state("rules_selected")
```

### 7. Replace WorkflowStateManager Usage

Find all references to `self.workflow_state` and update:

```python
# OLD:
if hasattr(self, 'workflow_state'):
    self.workflow_state.handle_data_loaded()

# NEW:
self.workflow_tracker.update_state("data_loaded", {
    'file': self.validation_requirements.data_source_path
})
```

### 8. Update Validation Button

Make it always visible but conditionally enabled:

```python
# In create_validation_controls:
self.start_button = QPushButton("Start Validation")
self.start_button.setEnabled(False)  # Will be updated by update_all_section_states
# Remove any hide() calls

# In update_all_section_states:
if self.validation_requirements.can_validate:
    self.start_button.setEnabled(True)
    self.start_button.setStyleSheet(SectionStyles.BUTTON_ENABLED)
else:
    self.start_button.setEnabled(False)
    self.start_button.setStyleSheet(SectionStyles.BUTTON_DISABLED)
```

### 9. Testing Checklist

After refactoring, test these workflows:

- [ ] Load data source - section turns green
- [ ] Select rules - section turns green, button enables
- [ ] Change responsible party - doesn't hide anything
- [ ] Change data source after selecting rules - rules stay selected
- [ ] Start validation - progress shows
- [ ] Complete validation - results show
- [ ] Start new validation - can change any setting

### 10. Cleanup

Remove unused code:
- Old WorkflowStateManager imports and usage
- Progressive disclosure methods
- Complex state transition logic
- Section visibility toggle methods

### Benefits After Refactoring

1. **Predictable UI** - Nothing disappears unexpectedly
2. **Visual feedback** - Clear indication of what's complete/incomplete  
3. **Flexible workflow** - Change settings in any order
4. **Simpler code** - Less state management complexity
5. **Better UX** - Users always know what options are available

### Common Issues and Solutions

**Issue**: Sections still hiding
**Solution**: Search for `.hide()` and `.setVisible(False)` calls, remove them

**Issue**: Button not enabling
**Solution**: Check `update_all_section_states()` is called in all event handlers

**Issue**: Styles not applying
**Solution**: Ensure sections have `setObjectName()` and stored header references

**Issue**: Old workflow state errors
**Solution**: Remove all `workflow_state` references, use `workflow_tracker` only for logging
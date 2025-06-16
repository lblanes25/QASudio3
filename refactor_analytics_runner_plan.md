# Analytics Runner Refactoring Plan: State-Aware UI Management

## Overview
Replace the progressive disclosure pattern with always-visible sections that use visual styling to indicate availability and completion status.

## Key Changes

### 1. Data Model for Validation Requirements
Create a simple data model to track what's needed for validation:

```python
class ValidationRequirements:
    """Track validation requirements independently of UI state"""
    def __init__(self):
        self.data_source_valid = False
        self.data_source_path = None
        self.selected_rules = []
        self.responsible_party_column = None  # Optional
        self.analytic_id = ""
        self.output_dir = "./output"
        
    @property
    def can_validate(self) -> bool:
        """Check if all requirements are met for validation"""
        return self.data_source_valid and len(self.selected_rules) > 0
        
    @property
    def has_responsible_party(self) -> bool:
        """Check if responsible party is configured"""
        return self.responsible_party_column is not None and self.responsible_party_column != "None"
```

### 2. Visual State Indicators
Define consistent styling for different states:

```python
class SectionStyles:
    """Consistent styling for section states"""
    
    # Section backgrounds
    SECTION_COMPLETE = """
        QWidget {
            background-color: #f0f8f0;  /* Light green */
            border: 2px solid #4CAF50;
            border-radius: 6px;
            padding: 12px;
        }
    """
    
    SECTION_INCOMPLETE = """
        QWidget {
            background-color: #f5f5f5;  /* Light gray */
            border: 2px solid #ddd;
            border-radius: 6px;
            padding: 12px;
        }
    """
    
    SECTION_ERROR = """
        QWidget {
            background-color: #fff0f0;  /* Light red */
            border: 2px solid #f44336;
            border-radius: 6px;
            padding: 12px;
        }
    """
    
    # Headers with status icons
    HEADER_COMPLETE = """
        QLabel {
            color: #2e7d32;  /* Dark green */
            font-weight: bold;
            background-color: transparent;
        }
    """
    
    HEADER_INCOMPLETE = """
        QLabel {
            color: #666;
            font-weight: bold;
            background-color: transparent;
        }
    """
    
    # Disabled controls
    CONTROL_DISABLED = """
        opacity: 0.6;
        background-color: #f0f0f0;
    """
```

### 3. Section Status Icons
Add visual indicators for section status:

```python
def create_status_icon(status: str) -> QLabel:
    """Create a status icon label"""
    icon_label = QLabel()
    icon_label.setFixedSize(20, 20)
    
    if status == "complete":
        icon_label.setText("✓")
        icon_label.setStyleSheet("color: #4CAF50; font-size: 16px; font-weight: bold;")
    elif status == "incomplete":
        icon_label.setText("○")
        icon_label.setStyleSheet("color: #999; font-size: 16px;")
    elif status == "error":
        icon_label.setText("✗")
        icon_label.setStyleSheet("color: #f44336; font-size: 16px; font-weight: bold;")
    
    return icon_label
```

### 4. Main UI Updates

#### Remove Progressive Disclosure
Replace all `section.hide()` and `section.show()` calls with style updates:

```python
# OLD:
section.hide()  # Remove this

# NEW:
self.update_section_visual_state(section, "incomplete")
```

#### Update Section Creation
Add status indicators to each section header:

```python
def create_section_with_status(title: str, content_widget: QWidget) -> QWidget:
    """Create a section with status indicator"""
    section = QWidget()
    layout = QVBoxLayout(section)
    
    # Header with status
    header_layout = QHBoxLayout()
    status_icon = create_status_icon("incomplete")
    header_label = QLabel(title)
    header_label.setFont(get_header_font())
    
    header_layout.addWidget(status_icon)
    header_layout.addWidget(header_label)
    header_layout.addStretch()
    
    layout.addLayout(header_layout)
    layout.addWidget(content_widget)
    
    # Store references for updates
    section.status_icon = status_icon
    section.header_label = header_label
    
    return section
```

#### Update Validation Button
Keep it always visible but update enabled state:

```python
def update_validation_button_state(self):
    """Update validation button based on requirements"""
    can_validate = self.validation_requirements.can_validate
    
    self.start_button.setEnabled(can_validate)
    
    if can_validate:
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
    else:
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #ccc;
                color: #666;
            }
        """)
        
    # Update tooltip to explain requirements
    if not self.validation_requirements.data_source_valid:
        self.start_button.setToolTip("Select a valid data source first")
    elif len(self.validation_requirements.selected_rules) == 0:
        self.start_button.setToolTip("Select at least one validation rule")
    else:
        self.start_button.setToolTip("Click to start validation")
```

### 5. Event Handler Updates

Update all event handlers to only update data model and refresh UI:

```python
def _on_responsible_party_changed(self, index: int):
    """Handle responsible party column selection changes."""
    # Update data model
    if index > 0:
        self.validation_requirements.responsible_party_column = self.responsible_party_combo.currentText()
    else:
        self.validation_requirements.responsible_party_column = None
    
    # Update UI state
    self.update_all_section_states()
    
    # Log the change
    if self.validation_requirements.responsible_party_column:
        self.log_message(f"Responsible party column: {self.validation_requirements.responsible_party_column}")

def _on_data_source_changed(self):
    """Handle data source changes."""
    # Update data model
    self.validation_requirements.data_source_valid = self.data_source_panel.is_valid()
    self.validation_requirements.data_source_path = self.data_source_panel.get_current_file()
    
    # Update UI state
    self.update_all_section_states()
    
def _on_rules_selection_changed(self):
    """Handle rule selection changes."""
    # Update data model
    self.validation_requirements.selected_rules = self.get_selected_simple_rules()
    
    # Update UI state
    self.update_all_section_states()
```

### 6. Unified State Update Method

```python
def update_all_section_states(self):
    """Update visual state of all sections based on current data"""
    
    # Data Source Section
    if self.validation_requirements.data_source_valid:
        self.update_section_visual_state(self.data_source_section, "complete")
    else:
        self.update_section_visual_state(self.data_source_section, "incomplete")
    
    # Rule Selection Section
    if len(self.validation_requirements.selected_rules) > 0:
        self.update_section_visual_state(self.rule_section, "complete")
        count = len(self.validation_requirements.selected_rules)
        self.rule_count_label.setText(f"{count} rules selected")
    else:
        self.update_section_visual_state(self.rule_section, "incomplete")
        self.rule_count_label.setText("No rules selected")
    
    # Responsible Party Section (optional, so always "complete" if configured)
    if self.validation_requirements.has_responsible_party:
        self.update_section_visual_state(self.party_section, "complete")
    else:
        self.update_section_visual_state(self.party_section, "incomplete")
    
    # Update validation button
    self.update_validation_button_state()
    
def update_section_visual_state(self, section: QWidget, state: str):
    """Update a section's visual appearance based on state"""
    if state == "complete":
        section.setStyleSheet(SectionStyles.SECTION_COMPLETE)
        if hasattr(section, 'status_icon'):
            section.status_icon.setText("✓")
            section.status_icon.setStyleSheet("color: #4CAF50; font-size: 16px; font-weight: bold;")
        if hasattr(section, 'header_label'):
            section.header_label.setStyleSheet(SectionStyles.HEADER_COMPLETE)
    
    elif state == "incomplete":
        section.setStyleSheet(SectionStyles.SECTION_INCOMPLETE)
        if hasattr(section, 'status_icon'):
            section.status_icon.setText("○")
            section.status_icon.setStyleSheet("color: #999; font-size: 16px;")
        if hasattr(section, 'header_label'):
            section.header_label.setStyleSheet(SectionStyles.HEADER_INCOMPLETE)
    
    elif state == "error":
        section.setStyleSheet(SectionStyles.SECTION_ERROR)
        if hasattr(section, 'status_icon'):
            section.status_icon.setText("✗")
            section.status_icon.setStyleSheet("color: #f44336; font-size: 16px; font-weight: bold;")
```

### 7. Simplified WorkflowStateManager

Transform it into a simple state tracker for analytics/logging only:

```python
class WorkflowStateTracker(QObject):
    """Simple state tracker for analytics and logging only"""
    
    stateChanged = Signal(str, str)  # old_state, new_state
    
    def __init__(self):
        super().__init__()
        self.current_state = "initial"
        self.state_history = []
        
    def update_state(self, new_state: str, metadata: dict = None):
        """Update state for tracking purposes only"""
        old_state = self.current_state
        self.current_state = new_state
        
        entry = {
            'timestamp': datetime.now(),
            'old_state': old_state,
            'new_state': new_state,
            'metadata': metadata or {}
        }
        self.state_history.append(entry)
        
        logger.info(f"State change: {old_state} -> {new_state}")
        self.stateChanged.emit(old_state, new_state)
```

## Benefits

1. **Predictable UI**: Sections don't disappear, reducing user confusion
2. **Non-linear workflow**: Users can change settings in any order
3. **Clear feedback**: Visual indicators show what's complete/incomplete
4. **Better accessibility**: All options remain accessible at all times
5. **Simpler code**: No complex state management for visibility

## Implementation Order

1. Create ValidationRequirements class
2. Add visual state styling constants
3. Update section creation to include status indicators
4. Replace all hide/show calls with style updates
5. Update event handlers to use data model
6. Implement unified state update method
7. Simplify WorkflowStateManager to just track state
8. Test all workflows to ensure proper visual feedback
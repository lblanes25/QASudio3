# Key refactoring changes for main_application.py
# This file shows the main changes needed - not a complete replacement

"""
REFACTORING GUIDE: State-Aware UI Management

Replace progressive disclosure with always-visible sections that update their visual state.
"""

# Add these imports at the top
from ui.analytics_runner.validation_requirements import ValidationRequirements
from ui.analytics_runner.section_styles import (
    SectionStyles, create_status_icon, create_section_header, update_section_header
)

# In the __init__ method, add:
def __init__(self):
    # ... existing init code ...
    
    # Initialize validation requirements model
    self.validation_requirements = ValidationRequirements()
    
    # Remove or simplify workflow state manager - only for tracking
    self.workflow_tracker = WorkflowStateTracker()  # Simplified version

# Replace create_simple_mode_ui method sections with always-visible versions:

def create_simple_mode_ui(self):
    """Create the simple mode UI with all sections visible"""
    simple_widget = QWidget()
    simple_layout = QVBoxLayout(simple_widget)
    simple_layout.setSpacing(16)
    
    # Data Source Section - Always visible
    data_source_section = self.create_data_source_section()
    simple_layout.addWidget(data_source_section)
    
    # Responsible Party Section - Always visible
    party_section = self.create_responsible_party_section()
    simple_layout.addWidget(party_section)
    
    # Rule Selection Section - Always visible
    rule_section = self.create_rule_selection_section()
    simple_layout.addWidget(rule_section)
    
    # Execution Options Section - Always visible
    execution_section = self.create_execution_options_section()
    simple_layout.addWidget(execution_section)
    
    # Report Generation Section - Always visible
    report_section = self.create_report_generation_section()
    simple_layout.addWidget(report_section)
    
    # Validation Controls - Always visible
    validation_section = self.create_validation_controls_section()
    simple_layout.addWidget(validation_section)
    
    # Progress Section - Shows during validation
    progress_section = self.create_progress_section()
    progress_section.setVisible(False)  # Only hidden during non-validation
    simple_layout.addWidget(progress_section)
    
    # Results Section - Shows after validation
    results_section = self.create_results_section()
    results_section.setVisible(False)  # Only hidden before first validation
    simple_layout.addWidget(results_section)
    
    simple_layout.addStretch()
    
    # Initial state update
    self.update_all_section_states()
    
    return simple_widget

# Create sections with status indicators:

def create_data_source_section(self) -> QWidget:
    """Create data source section with status indicator"""
    section = QWidget()
    section.setObjectName("data_source_section")
    layout = QVBoxLayout(section)
    
    # Header with status
    header = create_section_header("Data Source", "incomplete")
    layout.addWidget(header)
    section.header = header  # Store reference
    
    # Content frame
    content = QWidget()
    content.setStyleSheet("background-color: transparent;")
    content_layout = QVBoxLayout(content)
    
    # Add existing data source panel
    self.data_source_panel = DataSourcePanel(
        registry=self.data_source_registry,
        parent=self
    )
    
    # Connect signals to update requirements
    self.data_source_panel.fileChanged.connect(self._on_data_source_changed)
    self.data_source_panel.validationStateChanged.connect(self._on_data_source_changed)
    
    content_layout.addWidget(self.data_source_panel)
    layout.addWidget(content)
    
    # Set initial style
    section.setStyleSheet(SectionStyles.SECTION_INCOMPLETE)
    
    return section

def create_responsible_party_section(self) -> QWidget:
    """Create responsible party section with status indicator"""
    section = QWidget()
    section.setObjectName("responsible_party_section")
    layout = QVBoxLayout(section)
    
    # Header with status
    header = create_section_header("Responsible Party Column (Optional)", "incomplete")
    layout.addWidget(header)
    section.header = header
    
    # Content
    content = QWidget()
    content.setStyleSheet("background-color: transparent;")
    content_layout = QHBoxLayout(content)
    
    label = QLabel("Select Column:")
    content_layout.addWidget(label)
    
    self.responsible_party_combo = QComboBox()
    self.responsible_party_combo.addItem("None")
    self.responsible_party_combo.setToolTip("Select column for audit leader grouping (optional)")
    self.responsible_party_combo.currentIndexChanged.connect(self._on_responsible_party_changed)
    content_layout.addWidget(self.responsible_party_combo, 1)
    
    layout.addWidget(content)
    
    # Set initial style
    section.setStyleSheet(SectionStyles.SECTION_INCOMPLETE)
    
    return section

def create_validation_controls_section(self) -> QWidget:
    """Create validation controls that are always visible"""
    section = QWidget()
    section.setObjectName("validation_controls_section")
    layout = QVBoxLayout(section)
    
    # Header
    header = create_section_header("Validation Controls", "incomplete")
    layout.addWidget(header)
    section.header = header
    
    # Controls
    controls = QWidget()
    controls.setStyleSheet("background-color: transparent;")
    controls_layout = QHBoxLayout(controls)
    
    # Start button - always visible
    self.start_button = QPushButton("Start Validation")
    self.start_button.setEnabled(False)
    self.start_button.clicked.connect(self.start_validation)
    self.start_button.setStyleSheet(SectionStyles.BUTTON_DISABLED)
    controls_layout.addWidget(self.start_button)
    
    # Cancel button
    self.cancel_button = QPushButton("Cancel")
    self.cancel_button.setEnabled(False)
    self.cancel_button.clicked.connect(self.cancel_validation)
    controls_layout.addWidget(self.cancel_button)
    
    # Status label
    self.validation_status_label = QLabel("Not ready")
    self.validation_status_label.setStyleSheet("color: #666; background-color: transparent;")
    controls_layout.addWidget(self.validation_status_label)
    
    controls_layout.addStretch()
    
    layout.addWidget(controls)
    
    # Set initial style
    section.setStyleSheet(SectionStyles.SECTION_INCOMPLETE)
    
    return section

# Update event handlers to only update data model and refresh UI:

def _on_data_source_changed(self):
    """Handle data source changes - update model and UI"""
    # Update data model
    self.validation_requirements.data_source_valid = self.data_source_panel.is_valid()
    self.validation_requirements.data_source_path = self.data_source_panel.get_current_file()
    self.validation_requirements.sheet_name = self.data_source_panel.get_current_sheet()
    
    # Update column list if Excel
    if self.validation_requirements.data_source_valid:
        columns = self.data_source_panel.get_column_list()
        self.responsible_party_combo.clear()
        self.responsible_party_combo.addItem("None")
        self.responsible_party_combo.addItems(columns)
    
    # Update UI state
    self.update_all_section_states()
    
    # Log for tracking
    if self.validation_requirements.data_source_valid:
        self.log_message(f"Data source loaded: {self.validation_requirements.data_source_path}")
        self.workflow_tracker.update_state("data_loaded")

def _on_responsible_party_changed(self, index: int):
    """Handle responsible party selection - update model and UI"""
    # Update data model
    if index > 0:
        self.validation_requirements.responsible_party_column = self.responsible_party_combo.currentText()
        self.log_message(f"Responsible party column: {self.validation_requirements.responsible_party_column}")
    else:
        self.validation_requirements.responsible_party_column = None
    
    # Update UI state
    self.update_all_section_states()

def _on_rules_selection_changed(self):
    """Handle rule selection changes - update model and UI"""
    # Update data model
    if self.mode_tabs.currentIndex() == 0:  # Simple mode
        self.validation_requirements.selected_rules = self.get_selected_simple_rules()
    else:  # Advanced mode
        self.validation_requirements.selected_rules = self.rule_selector_panel.get_selected_rule_ids()
    
    # Update UI state
    self.update_all_section_states()
    
    # Log for tracking
    count = len(self.validation_requirements.selected_rules)
    self.log_message(f"Selected {count} validation rules")

# Main state update method:

def update_all_section_states(self):
    """Update visual state of all sections based on current data"""
    
    # Data Source Section
    data_section = self.findChild(QWidget, "data_source_section")
    if data_section:
        if self.validation_requirements.data_source_valid:
            data_section.setStyleSheet(SectionStyles.SECTION_COMPLETE)
            update_section_header(data_section.header, "complete", 
                                os.path.basename(self.validation_requirements.data_source_path or ""))
        else:
            data_section.setStyleSheet(SectionStyles.SECTION_INCOMPLETE)
            update_section_header(data_section.header, "incomplete", "No file selected")
    
    # Responsible Party Section (optional)
    party_section = self.findChild(QWidget, "responsible_party_section")
    if party_section:
        if self.validation_requirements.has_responsible_party:
            party_section.setStyleSheet(SectionStyles.SECTION_COMPLETE)
            update_section_header(party_section.header, "complete", 
                                self.validation_requirements.responsible_party_column)
        else:
            party_section.setStyleSheet(SectionStyles.SECTION_INCOMPLETE)
            update_section_header(party_section.header, "incomplete", "Not configured")
    
    # Rule Selection Section
    rule_section = self.findChild(QWidget, "rule_selection_section")
    if rule_section:
        rule_count = len(self.validation_requirements.selected_rules)
        if rule_count > 0:
            rule_section.setStyleSheet(SectionStyles.SECTION_COMPLETE)
            update_section_header(rule_section.header, "complete", f"{rule_count} rules selected")
        else:
            rule_section.setStyleSheet(SectionStyles.SECTION_INCOMPLETE)
            update_section_header(rule_section.header, "incomplete", "No rules selected")
    
    # Validation Controls Section
    control_section = self.findChild(QWidget, "validation_controls_section")
    if control_section:
        if self.validation_requirements.can_validate:
            control_section.setStyleSheet(SectionStyles.SECTION_COMPLETE)
            update_section_header(control_section.header, "complete", "Ready to validate")
            self.start_button.setEnabled(True)
            self.start_button.setStyleSheet(SectionStyles.BUTTON_ENABLED)
            self.validation_status_label.setText("Ready to validate")
            self.validation_status_label.setStyleSheet("color: #4CAF50; background-color: transparent;")
        else:
            control_section.setStyleSheet(SectionStyles.SECTION_INCOMPLETE)
            update_section_header(control_section.header, "incomplete", "Not ready")
            self.start_button.setEnabled(False)
            self.start_button.setStyleSheet(SectionStyles.BUTTON_DISABLED)
            self.validation_status_label.setText(self.validation_requirements.validation_ready_message)
            self.validation_status_label.setStyleSheet("color: #666; background-color: transparent;")
    
    # Update button tooltip
    self.start_button.setToolTip(self.validation_requirements.validation_ready_message)

# Simplified workflow state tracker (replaces WorkflowStateManager):

class WorkflowStateTracker(QObject):
    """Simple state tracker for analytics and logging only - no UI control"""
    
    stateChanged = Signal(str, str)  # old_state, new_state
    
    def __init__(self):
        super().__init__()
        self.current_state = "initial"
        self.state_history = []
        self.start_time = None
        
    def update_state(self, new_state: str, metadata: dict = None):
        """Update state for tracking purposes only"""
        import datetime
        
        old_state = self.current_state
        self.current_state = new_state
        
        entry = {
            'timestamp': datetime.datetime.now(),
            'old_state': old_state,
            'new_state': new_state,
            'metadata': metadata or {}
        }
        self.state_history.append(entry)
        
        # Log state change
        logger.info(f"Workflow state: {old_state} -> {new_state}")
        self.stateChanged.emit(old_state, new_state)
        
    def get_elapsed_time(self) -> float:
        """Get elapsed time since start"""
        if self.start_time:
            return (datetime.datetime.now() - self.start_time).total_seconds()
        return 0.0
        
    def reset(self):
        """Reset tracker"""
        self.current_state = "initial"
        self.state_history = []
        self.start_time = None

# Update start_validation to use the requirements model:

def start_validation(self):
    """Start validation using the requirements model"""
    # Check requirements
    if not self.validation_requirements.can_validate:
        QMessageBox.warning(self, "Cannot Validate", 
                          self.validation_requirements.validation_ready_message)
        return
    
    # Log start
    self.log_message("Starting validation...")
    self.workflow_tracker.update_state("validation_started", {
        'rules_count': len(self.validation_requirements.selected_rules),
        'has_party': self.validation_requirements.has_responsible_party
    })
    
    # Update UI for running state
    self.start_button.setEnabled(False)
    self.cancel_button.setEnabled(True)
    self.progress_section.setVisible(True)
    
    # Create worker with requirements
    self.validation_worker = CancellableValidationWorker(
        pipeline=None,
        data_source=self.validation_requirements.data_source_path,
        sheet_name=self.validation_requirements.sheet_name,
        analytic_id=self.validation_requirements.analytic_id or f"Validation_{datetime.now():%Y%m%d_%H%M%S}",
        rule_ids=self.validation_requirements.selected_rules,
        generate_reports=self.validation_requirements.generate_excel_report,
        report_formats=['json', 'iag_excel'] if self.validation_requirements.generate_excel_report else ['json'],
        output_dir=self.validation_requirements.output_dir,
        use_parallel=(self.validation_requirements.execution_mode == "Parallel"),
        responsible_party_column=self.validation_requirements.responsible_party_column,
        generate_leader_reports=self.validation_requirements.generate_leader_reports
    )
    
    # Connect signals and start...
    # (rest of the method remains similar)
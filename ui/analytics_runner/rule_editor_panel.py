"""
Integrated Rule Editor Panel for Analytics Runner
Real implementation that manipulates ValidationRule objects and persists to JSON
"""

import logging
import uuid
from typing import Optional, Dict, Any, List
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QLineEdit, 
    QTextEdit, QComboBox, QPushButton, QLabel, QFrame, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QCheckBox, QDoubleSpinBox, QTabWidget, QSplitter, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QSyntaxHighlighter, QTextCharFormat, QTextDocument, QColor

# Import backend components
from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
from core.rule_engine.rule_parser import ValidationRuleParser
from core.rule_engine.rule_evaluator import RuleEvaluator
from ui.common.stylesheet import AnalyticsRunnerStylesheet

logger = logging.getLogger(__name__)


class FormulaSyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Excel formula editing"""

    def __init__(self, document: QTextDocument, rule_parser: ValidationRuleParser):
        super().__init__(document)
        self.rule_parser = rule_parser

        # Define highlighting formats
        self.formats = {
            'column_ref': QTextCharFormat(),
            'function': QTextCharFormat(),
            'operator': QTextCharFormat(),
            'error': QTextCharFormat()
        }

        # Column references (e.g., [ColumnName])
        self.formats['column_ref'].setForeground(QColor(AnalyticsRunnerStylesheet.PRIMARY_COLOR))
        self.formats['column_ref'].setFontWeight(QFont.Bold)

        # Functions (e.g., IF, AND, OR)
        self.formats['function'].setForeground(QColor("#9C27B0"))  # Purple
        self.formats['function'].setFontWeight(QFont.Bold)

        # Operators
        self.formats['operator'].setForeground(QColor("#FF5722"))  # Orange

        # Errors
        self.formats['error'].setForeground(QColor(AnalyticsRunnerStylesheet.ERROR_COLOR))
        self.formats['error'].setUnderlineStyle(QTextCharFormat.WaveUnderline)
        self.formats['error'].setUnderlineColor(QColor(AnalyticsRunnerStylesheet.ERROR_COLOR))

    def highlightBlock(self, text: str):
        """Apply syntax highlighting to a block of text"""
        # Highlight column references [ColumnName]
        import re
        column_pattern = re.compile(r'\[([^\]]+)\]')
        for match in column_pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(),
                          self.formats['column_ref'])

        # Highlight common Excel functions
        function_pattern = re.compile(r'\b(IF|AND|OR|NOT|ISBLANK|ISNULL|LEN|TRIM|UPPER|LOWER|LEFT|RIGHT|MID)\b', re.IGNORECASE)
        for match in function_pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(),
                          self.formats['function'])

        # Highlight operators
        operator_pattern = re.compile(r'[=<>!]+|[\+\-\*/]')
        for match in operator_pattern.finditer(text):
            self.setFormat(match.start(), match.end() - match.start(),
                          self.formats['operator'])


class RuleEditorPanel(QWidget):
    """
    Integrated rule editor that works with real ValidationRule objects
    and persists changes to JSON using ValidationRuleManager
    """

    # Signals
    ruleUpdated = Signal(str)  # Emitted when a rule is updated (rule_id)
    ruleCreated = Signal(str)  # Emitted when a rule is created (rule_id)

    def __init__(self, rule_manager: ValidationRuleManager, parent=None):
        super().__init__(parent)

        # Backend connections
        self.rule_manager = rule_manager
        self.rule_parser = ValidationRuleParser()
        self.rule_evaluator = RuleEvaluator(rule_manager=rule_manager)

        # Current state
        self.current_rule: Optional[ValidationRule] = None
        self.is_editing_existing = False
        self.has_unsaved_changes = False
        self.available_columns: List[str] = []
        self.current_data_preview = None

        # UI components
        self.form_fields = {}

        # Setup validation timer (debounced) - Initialize BEFORE UI setup
        self.validation_timer = QTimer()
        self.validation_timer.setSingleShot(True)
        self.validation_timer.timeout.connect(self._validate_formula)

        # Setup UI
        self.init_ui()

        logger.info("RuleEditorPanel initialized with real backend integration")

    def init_ui(self):
        """Initialize the user interface"""
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        # Header with title and actions
        self.create_header_section(main_layout)

        # Main content in tabs
        self.create_tabbed_content(main_layout)

        # Action buttons
        self.create_action_buttons(main_layout)

        # Initialize with empty state
        self.reset_editor()

    def create_header_section(self, parent_layout):
        """Create header with title and mode indicator"""
        header_layout = QHBoxLayout()

        # Title
        self.title_label = QLabel("Rule Editor")
        self.title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        self.title_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR}; font-weight: bold;")
        header_layout.addWidget(self.title_label)

        # Status indicator
        self.status_label = QLabel("No rule selected")
        self.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; font-style: italic;")
        header_layout.addStretch()
        header_layout.addWidget(self.status_label)

        parent_layout.addLayout(header_layout)

    def create_tabbed_content(self, parent_layout):
        """Create tabbed content area"""
        self.tab_widget = QTabWidget()

        # Rule Details Tab
        self.create_rule_details_tab()

        # Formula Editor Tab
        self.create_formula_editor_tab()

        # Test Results Tab
        self.create_test_results_tab()

        parent_layout.addWidget(self.tab_widget)

    def create_rule_details_tab(self):
        """Create the rule details editing tab - FIXED: Text clipping issues"""
        details_widget = QWidget()
        layout = QVBoxLayout(details_widget)
        layout.setSpacing(16)

        # Create scroll area for form
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(16)  # Increased spacing between form rows
        form_layout.setVerticalSpacing(16)  # Explicit vertical spacing
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        # FIXED: Ensure adequate height for all form fields
        field_height = max(36, AnalyticsRunnerStylesheet.BUTTON_HEIGHT + 4)  # Increased from 32px to 36px

        # Rule Name - FIXED: Adequate height with proper styling
        self.form_fields['name'] = QLineEdit()
        self.form_fields['name'].setPlaceholderText("Enter rule name...")
        self.form_fields['name'].setMinimumHeight(field_height)
        self.form_fields['name'].setStyleSheet(f"""
            QLineEdit {{
                min-height: {field_height}px;
                padding: 8px 12px;
                font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            }}
        """)
        self.form_fields['name'].textChanged.connect(self._on_field_changed)
        form_layout.addRow("Rule Name *:", self.form_fields['name'])

        # Rule ID (read-only for existing rules) - FIXED: Adequate height
        self.form_fields['rule_id'] = QLineEdit()
        self.form_fields['rule_id'].setReadOnly(True)
        self.form_fields['rule_id'].setMinimumHeight(field_height)
        self.form_fields['rule_id'].setStyleSheet(f"""
            QLineEdit {{
                background-color: {AnalyticsRunnerStylesheet.DISABLED_COLOR}40;
                min-height: {field_height}px;
                padding: 8px 12px;
                font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            }}
        """)
        form_layout.addRow("Rule ID:", self.form_fields['rule_id'])

        # Title (display name) - FIXED: Adequate height
        self.form_fields['title'] = QLineEdit()
        self.form_fields['title'].setPlaceholderText("Display title for reports...")
        self.form_fields['title'].setMinimumHeight(field_height)
        self.form_fields['title'].setStyleSheet(f"""
            QLineEdit {{
                min-height: {field_height}px;
                padding: 8px 12px;
                font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            }}
        """)
        self.form_fields['title'].textChanged.connect(self._on_field_changed)
        form_layout.addRow("Title:", self.form_fields['title'])

        # Description - FIXED: Adequate height with proper padding
        self.form_fields['description'] = QTextEdit()
        self.form_fields['description'].setPlaceholderText("Describe what this rule validates...")
        self.form_fields['description'].setMinimumHeight(90)  # Increased from 80px
        self.form_fields['description'].setMaximumHeight(110)  # Increased from 100px
        self.form_fields['description'].setStyleSheet(f"""
            QTextEdit {{
                min-height: 90px;
                max-height: 110px;
                padding: 8px 12px;
                font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            }}
        """)
        self.form_fields['description'].textChanged.connect(self._on_field_changed)
        form_layout.addRow("Description:", self.form_fields['description'])

        # Category - FIXED: Adequate height
        self.form_fields['category'] = QComboBox()
        self.form_fields['category'].setEditable(True)
        self.form_fields['category'].setMinimumHeight(field_height)
        self.form_fields['category'].setStyleSheet(f"""
            QComboBox {{
                min-height: {field_height}px;
                padding: 8px 12px;
                font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            }}
        """)
        self.form_fields['category'].addItems([
            "data_quality", "compliance", "timing", "completeness",
            "consistency", "fraud", "regulatory", "custom"
        ])
        self.form_fields['category'].currentTextChanged.connect(self._on_field_changed)
        form_layout.addRow("Category:", self.form_fields['category'])

        # Severity - FIXED: Adequate height
        self.form_fields['severity'] = QComboBox()
        self.form_fields['severity'].setMinimumHeight(field_height)
        self.form_fields['severity'].setStyleSheet(f"""
            QComboBox {{
                min-height: {field_height}px;
                padding: 8px 12px;
                font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            }}
        """)
        self.form_fields['severity'].addItems(["critical", "high", "medium", "low", "info"])
        self.form_fields['severity'].setCurrentText("medium")
        self.form_fields['severity'].currentTextChanged.connect(self._on_field_changed)
        form_layout.addRow("Severity:", self.form_fields['severity'])

        # Threshold - FIXED: Percentage display + clear tooltip
        threshold_layout = QVBoxLayout()

        # Main threshold input
        threshold_input_layout = QHBoxLayout()
        self.form_fields['threshold'] = QDoubleSpinBox()
        self.form_fields['threshold'].setRange(0.0, 100.0)  # Changed to 0-100 range
        self.form_fields['threshold'].setSingleStep(1.0)  # 1% increments
        self.form_fields['threshold'].setValue(100.0)  # Default to 100%
        self.form_fields['threshold'].setDecimals(1)  # One decimal place
        self.form_fields['threshold'].setSuffix("%")  # Show percentage symbol
        self.form_fields['threshold'].setMinimumHeight(field_height)

        # CRITICAL FIX: Enable keyboard input
        self.form_fields['threshold'].setKeyboardTracking(True)
        self.form_fields['threshold'].lineEdit().setReadOnly(False)

        # Clear tooltip explanation
        self.form_fields['threshold'].setToolTip(
            "Compliance Rate: Minimum percentage of data that must pass this rule.\n"
            "• 100% = No failures allowed\n"
            "• 95% = Up to 5% failure rate allowed\n"
            "• 90% = Up to 10% failure rate allowed"
        )

        self.form_fields['threshold'].setStyleSheet(f"""
            QDoubleSpinBox {{
                min-height: {field_height}px;
                padding: 8px 12px;
                font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            }}
        """)
        self.form_fields['threshold'].valueChanged.connect(self._on_field_changed)
        threshold_input_layout.addWidget(self.form_fields['threshold'])

        threshold_layout.addLayout(threshold_input_layout)
        form_layout.addRow("Compliance Threshold:", threshold_layout)

        # Tags - FIXED: Adequate height
        self.form_fields['tags'] = QLineEdit()
        self.form_fields['tags'].setPlaceholderText("Comma-separated tags...")
        self.form_fields['tags'].setMinimumHeight(field_height)
        self.form_fields['tags'].setStyleSheet(f"""
            QLineEdit {{
                min-height: {field_height}px;
                padding: 8px 12px;
                font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            }}
        """)
        self.form_fields['tags'].textChanged.connect(self._on_field_changed)
        form_layout.addRow("Tags:", self.form_fields['tags'])

        # Responsible Party Column - FIXED: Adequate height
        self.form_fields['responsible_party_column'] = QComboBox()
        self.form_fields['responsible_party_column'].setEditable(True)
        self.form_fields['responsible_party_column'].setMinimumHeight(field_height)
        self.form_fields['responsible_party_column'].setStyleSheet(f"""
            QComboBox {{
                min-height: {field_height}px;
                padding: 8px 12px;
                font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            }}
        """)
        self.form_fields['responsible_party_column'].setPlaceholderText("Select or enter column name...")
        self.form_fields['responsible_party_column'].currentTextChanged.connect(self._on_field_changed)
        form_layout.addRow("Responsible Party Column:", self.form_fields['responsible_party_column'])

        scroll_area.setWidget(form_widget)
        layout.addWidget(scroll_area)

        self.tab_widget.addTab(details_widget, "Rule Details")

    def create_formula_editor_tab(self):
        """Create the formula editor tab with syntax highlighting"""
        formula_widget = QWidget()
        layout = QVBoxLayout(formula_widget)
        layout.setSpacing(12)

        # Formula editor with syntax highlighting
        formula_group = QGroupBox("Excel Formula")
        formula_group_layout = QVBoxLayout(formula_group)

        self.form_fields['formula'] = QTextEdit()
        self.form_fields['formula'].setFont(AnalyticsRunnerStylesheet.get_fonts()['mono'])
        self.form_fields['formula'].setPlaceholderText("Enter Excel formula (e.g., =[Column1]<>[Column2])")
        self.form_fields['formula'].setMaximumHeight(120)
        self.form_fields['formula'].textChanged.connect(self._on_formula_changed)

        # Apply syntax highlighting
        self.syntax_highlighter = FormulaSyntaxHighlighter(
            self.form_fields['formula'].document(),
            self.rule_parser
        )

        formula_group_layout.addWidget(self.form_fields['formula'])

        # Formula validation feedback
        self.formula_feedback = QLabel("")
        self.formula_feedback.setWordWrap(True)
        self.formula_feedback.hide()
        formula_group_layout.addWidget(self.formula_feedback)

        layout.addWidget(formula_group)

        # Column references helper
        columns_group = QGroupBox("Available Columns")
        columns_layout = QVBoxLayout(columns_group)

        self.columns_list_label = QLabel("Load data to see available columns")
        self.columns_list_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; font-style: italic;")
        columns_layout.addWidget(self.columns_list_label)

        layout.addWidget(columns_group)

        # Formula examples
        examples_group = QGroupBox("Formula Examples")
        examples_layout = QVBoxLayout(examples_group)

        examples_text = QLabel("""
• Check not null: NOT(ISBLANK([ColumnName]))
• Compare columns: [Column1]<>[Column2]
• Value validation: [Amount]>0
• Text validation: LEN(TRIM([Name]))>0
• Conditional: IF([Status]="Active",[Amount]>0,TRUE)
        """.strip())
        examples_text.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        examples_text.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};")
        examples_layout.addWidget(examples_text)

        layout.addWidget(examples_group)
        layout.addStretch()

        self.tab_widget.addTab(formula_widget, "Formula Editor")

    def create_test_results_tab(self):
        """Create the test results tab"""
        test_widget = QWidget()
        layout = QVBoxLayout(test_widget)
        layout.setSpacing(12)

        # Test controls
        test_controls_layout = QHBoxLayout()

        self.test_button = QPushButton("Test Rule Against Current Data")
        self.test_button.setMinimumHeight(AnalyticsRunnerStylesheet.BUTTON_HEIGHT)
        self.test_button.clicked.connect(self.test_current_rule)
        test_controls_layout.addWidget(self.test_button)

        test_controls_layout.addStretch()

        # Clear results button
        clear_button = QPushButton("Clear Results")
        clear_button.setProperty("buttonStyle", "secondary")
        clear_button.clicked.connect(self.clear_test_results)
        test_controls_layout.addWidget(clear_button)

        layout.addLayout(test_controls_layout)

        # Test results summary
        self.test_summary_label = QLabel("No test results yet")
        self.test_summary_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; font-style: italic;")
        layout.addWidget(self.test_summary_label)

        # Results table
        self.test_results_table = QTableWidget()
        self.test_results_table.setAlternatingRowColors(True)
        self.test_results_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.test_results_table.setStyleSheet(AnalyticsRunnerStylesheet.get_table_stylesheet())
        self.test_results_table.hide()  # Hidden until we have results
        layout.addWidget(self.test_results_table)

        layout.addStretch()

        self.tab_widget.addTab(test_widget, "Test Results")

    def create_action_buttons(self, parent_layout):
        """Create action buttons at the bottom - COMPLETELY REMOVED duplicate New Rule button"""
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        parent_layout.addWidget(separator)

        # Buttons layout
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(12)

        # Discard changes button (moved to left side)
        self.discard_button = QPushButton("Discard Changes")
        self.discard_button.setProperty("buttonStyle", "secondary")
        self.discard_button.clicked.connect(self.discard_changes)
        self.discard_button.setEnabled(False)
        buttons_layout.addWidget(self.discard_button)

        # Add stretch to push Save button to the right
        buttons_layout.addStretch()

        # Save button (remains on right side as primary action)
        self.save_button = QPushButton("Save Rule")
        self.save_button.setMinimumHeight(AnalyticsRunnerStylesheet.BUTTON_HEIGHT)
        self.save_button.clicked.connect(self.save_current_rule)
        self.save_button.setEnabled(False)
        buttons_layout.addWidget(self.save_button)

        parent_layout.addLayout(buttons_layout)

    def reset_editor(self):
        """Reset the editor to empty state - FIXED to not be called during new rule creation"""
        # This method should only be called when truly clearing everything
        self.current_rule = None
        self.is_editing_existing = False
        self.has_unsaved_changes = False

        # Clear all form fields
        self.form_fields['name'].clear()
        self.form_fields['rule_id'].clear()
        self.form_fields['title'].clear()
        self.form_fields['description'].clear()
        self.form_fields['category'].setCurrentText("data_quality")
        self.form_fields['severity'].setCurrentText("medium")
        self.form_fields['threshold'].setValue(1.0)
        self.form_fields['tags'].clear()
        self.form_fields['responsible_party_column'].clear()
        self.form_fields['formula'].clear()

        # Update UI state
        self.title_label.setText("Rule Editor")
        self.status_label.setText("No rule selected")
        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.test_button.setEnabled(False)

        # Clear validation feedback
        self.formula_feedback.hide()

        # Clear test results
        self.clear_test_results()

        logger.debug("Rule editor reset to empty state")

    def load_rule(self, rule_id: str):
        """Load an existing rule for editing"""
        try:
            # Get rule from rule manager
            rule = self.rule_manager.get_rule(rule_id)
            if not rule:
                QMessageBox.warning(self, "Rule Not Found", f"Rule with ID {rule_id} not found")
                return False

            self.current_rule = rule
            self.is_editing_existing = True
            self.has_unsaved_changes = False

            # Populate form fields from rule
            self.form_fields['name'].setText(rule.name or "")
            self.form_fields['rule_id'].setText(rule.rule_id or "")
            self.form_fields['title'].setText(rule.title or "")
            self.form_fields['description'].setPlainText(rule.description or "")
            self.form_fields['category'].setCurrentText(rule.category or "data_quality")
            self.form_fields['severity'].setCurrentText(rule.severity or "medium")
            self.form_fields['threshold'].setValue(rule.threshold or 1.0)

            # Handle tags
            if rule.tags:
                self.form_fields['tags'].setText(", ".join(rule.tags))
            else:
                self.form_fields['tags'].clear()

            # Handle responsible party column
            responsible_party = rule.responsible_party_column
            if responsible_party:
                self.form_fields['responsible_party_column'].setCurrentText(responsible_party)
            else:
                self.form_fields['responsible_party_column'].setCurrentText("")

            self.form_fields['formula'].setPlainText(rule.formula or "")

            # Update UI state
            self.title_label.setText(f"Editing: {rule.name}")
            self.status_label.setText(f"Loaded rule: {rule_id}")
            self.save_button.setEnabled(False)  # No changes yet
            self.discard_button.setEnabled(False)
            self.test_button.setEnabled(bool(rule.formula and self.current_data_preview is not None))

            # Clear test results
            self.clear_test_results()

            # Validate formula
            if rule.formula:
                self._validate_formula()

            logger.info(f"Loaded rule for editing: {rule.name} ({rule_id})")
            return True

        except Exception as e:
            error_msg = f"Error loading rule: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Load Error", error_msg)
            return False

    def create_new_rule(self):
        """
        Create a new rule - UPDATED: Now only called from parent rule selector panel
        This method is triggered by the "Create New Rule" button in the rule selector panel
        """
        if self.has_unsaved_changes:
            reply = QMessageBox.question(
                self, "Unsaved Changes",
                "You have unsaved changes. Do you want to discard them?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Generate new rule ID
        new_rule_id = str(uuid.uuid4())

        # CRITICAL FIX: Create new ValidationRule object BEFORE calling reset_editor()
        self.current_rule = ValidationRule(
            rule_id=new_rule_id,
            name="",
            formula="",
            description="",
            threshold=1.0,
            severity="medium",
            category="data_quality",
            tags=[]
        )

        # Set flags
        self.is_editing_existing = False
        self.has_unsaved_changes = False

        # Clear all form fields manually (don't use reset_editor which clears current_rule)
        self.form_fields['name'].clear()
        self.form_fields['rule_id'].setText(new_rule_id)  # Show the generated ID
        self.form_fields['title'].clear()
        self.form_fields['description'].clear()
        self.form_fields['category'].setCurrentText("data_quality")
        self.form_fields['severity'].setCurrentText("medium")
        self.form_fields['threshold'].setValue(1.0)
        self.form_fields['tags'].clear()
        self.form_fields['responsible_party_column'].setCurrentText("")
        self.form_fields['formula'].clear()

        # Update UI state
        self.title_label.setText("Creating New Rule")
        self.status_label.setText("Enter Rule Name and Formula to enable saving")
        self.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; font-style: italic;")

        # Set button states - NOTE: No new_button to manage anymore
        self.save_button.setEnabled(False)
        self.discard_button.setEnabled(False)
        self.test_button.setEnabled(False)

        # Clear validation feedback
        self.formula_feedback.hide()

        # Clear test results
        self.clear_test_results()

        # Focus on name field to guide user
        self.form_fields['name'].setFocus()

        logger.info(f"Created new rule with ID: {new_rule_id}")
        logger.debug(f"self.current_rule is now: {self.current_rule}")

    def save_current_rule(self):
        """Save the current rule to persistent storage - ENHANCED with debug logging"""
        logger.debug(f"save_current_rule called: current_rule={self.current_rule is not None}")

        if not self.current_rule:
            logger.error("No current rule to save")
            # Show more helpful error message
            QMessageBox.warning(
                self,
                "Save Error",
                "No rule to save. This might be a bug.\n\n"
                "Try clicking 'Create New Rule' again and fill out the form."
            )
            return False

        try:
            # Update rule object from form fields
            self.current_rule.name = self.form_fields['name'].text().strip()
            self.current_rule.description = self.form_fields['description'].toPlainText().strip()
            self.current_rule.formula = self.form_fields['formula'].toPlainText().strip()
            self.current_rule.category = self.form_fields['category'].currentText().strip()
            self.current_rule.severity = self.form_fields['severity'].currentText().strip()
            self.current_rule.threshold = self.form_fields['threshold'].value()

            # Handle title
            title_text = self.form_fields['title'].text().strip()
            if title_text:
                self.current_rule.title = title_text
            else:
                self.current_rule.title = self.current_rule.name  # Default to name

            # Handle tags
            tags_text = self.form_fields['tags'].text().strip()
            if tags_text:
                self.current_rule.tags = [tag.strip() for tag in tags_text.split(",") if tag.strip()]
            else:
                self.current_rule.tags = []

            # Handle responsible party column
            responsible_party = self.form_fields['responsible_party_column'].currentText().strip()
            if responsible_party:
                self.current_rule.responsible_party_column = responsible_party

            # CRITICAL FIX: Validate rule before saving
            is_valid, error = self.current_rule.validate()
            if not is_valid:
                logger.error(f"Rule validation failed: {error}")
                QMessageBox.warning(self, "Validation Error", f"Rule is not valid:\n{error}")
                return False

            # CRITICAL FIX: Save using rule manager with proper error handling
            try:
                if self.is_editing_existing:
                    # Update existing rule
                    self.rule_manager.update_rule(self.current_rule)
                    logger.info(f"Updated existing rule: {self.current_rule.name} ({self.current_rule.rule_id})")
                    success_msg = f"Rule '{self.current_rule.name}' updated successfully"

                    # EMIT SIGNAL to notify parent that rule was updated
                    self.ruleUpdated.emit(self.current_rule.rule_id)
                else:
                    # Add new rule - FIXED: Capture the returned rule_id
                    returned_rule_id = self.rule_manager.add_rule(self.current_rule)

                    # Update the rule object with the confirmed ID
                    self.current_rule.rule_id = returned_rule_id
                    self.is_editing_existing = True
                    logger.info(f"Created new rule: {self.current_rule.name} ({returned_rule_id})")
                    success_msg = f"Rule '{self.current_rule.name}' created successfully"

                    # EMIT SIGNAL to notify parent that rule was created
                    self.ruleCreated.emit(returned_rule_id)

            except Exception as save_error:
                logger.error(f"Error saving rule to manager: {str(save_error)}")
                QMessageBox.critical(self, "Save Error", f"Failed to save rule:\n{str(save_error)}")
                return False

            # Update UI state - FIXED: Clear the changed state properly
            self.has_unsaved_changes = False
            self.save_button.setEnabled(False)
            self.discard_button.setEnabled(False)

            # UPDATE STATUS with success feedback
            self.status_label.setText("✓ Saved successfully")
            self.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR}; font-weight: bold;")

            # Update title to reflect saved state (remove asterisk)
            self.title_label.setText(f"Editing: {self.current_rule.name}")

            # Enable test button if we have data
            self.test_button.setEnabled(bool(self.current_rule.formula and self.current_data_preview is not None))

            # SHOW SUCCESS MESSAGE temporarily
            QTimer.singleShot(3000, lambda: [
                self.status_label.setText(f"Loaded rule: {self.current_rule.rule_id}"),
                self.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; font-style: italic;")
            ])

            logger.info(success_msg)
            return True

        except Exception as e:
            error_msg = f"Error saving rule: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Save Error", error_msg)
            return False

    def discard_changes(self):
        """Discard unsaved changes"""
        if not self.has_unsaved_changes:
            return

        reply = QMessageBox.question(
            self, "Discard Changes",
            "Are you sure you want to discard your changes?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            if self.is_editing_existing and self.current_rule:
                # Reload the rule from storage
                self.load_rule(self.current_rule.rule_id)
            else:
                # Reset to empty state for new rule
                self.reset_editor()

    def test_current_rule(self):
        """Test the current rule against loaded data - ENHANCED"""
        # Allow testing even if not saved
        name = self.form_fields['name'].text().strip() or "Test Rule"
        formula = self.form_fields['formula'].toPlainText().strip()

        if not formula:
            QMessageBox.warning(self, "No Formula", "Please enter a formula to test")
            return

        if self.current_data_preview is None:
            QMessageBox.warning(self, "No Data", "Please load data in the Data Source panel to test the rule")
            return

        try:
            # Create a temporary rule for testing (doesn't need to be saved)
            temp_rule = ValidationRule(
                rule_id="temp_test_rule",
                name=name,
                formula=formula,
                description=self.form_fields['description'].toPlainText().strip(),
                threshold=self.form_fields['threshold'].value(),
                severity=self.form_fields['severity'].currentText(),
                category=self.form_fields['category'].currentText()
            )

            # Validate formula with current data
            is_valid, error = temp_rule.validate_with_dataframe(self.current_data_preview)
            if not is_valid:
                QMessageBox.warning(self, "Formula Error", f"Formula validation failed:\n{error}")
                return

            # Run evaluation
            self.test_summary_label.setText("Testing rule... Please wait")

            # Use rule evaluator to test
            result = self.rule_evaluator.evaluate_rule(temp_rule, self.current_data_preview)

            # Display results
            self._display_test_results(result)

            # Switch to test results tab
            self.tab_widget.setCurrentIndex(2)

            # Show helpful message about testing unsaved rule
            if not self.is_editing_existing or self.has_unsaved_changes:
                self.test_summary_label.setText(
                    self.test_summary_label.text() + " (Testing unsaved rule)"
                )

        except Exception as e:
            error_msg = f"Error testing rule: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Test Error", error_msg)
            self.test_summary_label.setText("Test failed - see error message")

    def _display_test_results(self, result):
        """Display test results in the results table"""
        try:
            # Update summary
            summary = result.summary
            compliance_rate = summary.get('compliance_rate', 0)
            total_items = summary.get('total_items', 0)
            dnc_count = summary.get('dnc_count', 0)
            status = summary.get('compliance_status', 'UNKNOWN')

            summary_text = f"Status: {status} | Compliance: {compliance_rate:.1%} | "
            summary_text += f"Total Items: {total_items} | Failed: {dnc_count}"

            if status == "GC":
                self.test_summary_label.setStyleSheet(AnalyticsRunnerStylesheet.get_success_style())
            elif status == "PC":
                self.test_summary_label.setStyleSheet(AnalyticsRunnerStylesheet.get_warning_style())
            else:
                self.test_summary_label.setStyleSheet(AnalyticsRunnerStylesheet.get_error_style())

            self.test_summary_label.setText(summary_text)

            # Show failing items in table
            failing_items = result.get_failing_items()

            if len(failing_items) > 0:
                # Setup table
                self.test_results_table.setRowCount(min(len(failing_items), 100))  # Limit to 100 rows
                self.test_results_table.setColumnCount(len(failing_items.columns))
                self.test_results_table.setHorizontalHeaderLabels(list(failing_items.columns))

                # Populate table with failing items
                for row in range(min(len(failing_items), 100)):
                    for col in range(len(failing_items.columns)):
                        value = failing_items.iloc[row, col]
                        item = QTableWidgetItem(str(value) if value is not None else "")
                        self.test_results_table.setItem(row, col, item)

                # Resize columns
                self.test_results_table.resizeColumnsToContents()

                # Show table
                self.test_results_table.show()

                # Add note if we limited results
                if len(failing_items) > 100:
                    note_text = self.test_summary_label.text() + f" (Showing first 100 of {len(failing_items)} failed items)"
                    self.test_summary_label.setText(note_text)
            else:
                # Hide table if no failures
                self.test_results_table.hide()

            logger.info(f"Test results displayed: {status}, {dnc_count} failures out of {total_items} items")

        except Exception as e:
            logger.error(f"Error displaying test results: {str(e)}")
            self.test_summary_label.setText(f"Error displaying results: {str(e)}")
            self.test_summary_label.setStyleSheet(AnalyticsRunnerStylesheet.get_error_style())

    def clear_test_results(self):
        """Clear test results"""
        self.test_summary_label.setText("No test results yet")
        self.test_summary_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; font-style: italic;")
        self.test_results_table.clear()
        self.test_results_table.setRowCount(0)
        self.test_results_table.setColumnCount(0)
        self.test_results_table.hide()

    def set_available_columns(self, columns: List[str]):
        """Update available columns for formula reference"""
        self.available_columns = columns

        # Update responsible party column dropdown
        current_value = self.form_fields['responsible_party_column'].currentText()
        self.form_fields['responsible_party_column'].clear()
        self.form_fields['responsible_party_column'].addItems([""] + columns)

        # Restore previous value if it exists
        if current_value in columns:
            self.form_fields['responsible_party_column'].setCurrentText(current_value)

        # Update columns display
        if columns:
            columns_text = ", ".join(columns[:10])  # Show first 10 columns
            if len(columns) > 10:
                columns_text += f" (+ {len(columns) - 10} more)"
            self.columns_list_label.setText(f"Available: {columns_text}")
            self.columns_list_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.TEXT_COLOR};")
        else:
            self.columns_list_label.setText("Load data to see available columns")
            self.columns_list_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; font-style: italic;")

        # Update test button state
        self._update_test_button_state()

    def set_current_data_preview(self, data_df):
        """Set current data preview for testing"""
        self.current_data_preview = data_df
        self._update_test_button_state()

        # Extract columns if we have data
        if data_df is not None:
            self.set_available_columns(list(data_df.columns))

    def _update_test_button_state(self):
        """Update test button enabled state - ENHANCED"""
        has_formula = bool(self.form_fields['formula'].toPlainText().strip())
        has_data = self.current_data_preview is not None
        formula_valid = False

        if has_formula:
            formula_valid = self.rule_parser.is_valid_formula(
                self.form_fields['formula'].toPlainText().strip()
            )

        # Enable test if we have valid formula and data (don't require save)
        self.test_button.setEnabled(has_formula and has_data and formula_valid)

        # Update button text to be more descriptive
        if not has_data:
            self.test_button.setText("Test Rule (No Data Loaded)")
        elif not has_formula:
            self.test_button.setText("Test Rule (No Formula)")
        elif not formula_valid:
            self.test_button.setText("Test Rule (Invalid Formula)")
        else:
            self.test_button.setText("Test Rule Against Current Data")

    def _on_field_changed(self):
        """Handle field changes to track unsaved changes - ENHANCED WITH BETTER FEEDBACK"""
        # Always enable change tracking, even for new rules
        self.has_unsaved_changes = True

        # Check if we can save (basic validation)
        can_save = self._can_save_rule()
        self.save_button.setEnabled(can_save)
        self.discard_button.setEnabled(True)

        # ENHANCED: Provide better status feedback
        if can_save:
            self.status_label.setText("✓ Ready to save")
            self.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR}; font-weight: bold;")

            # Make save button more prominent when ready
            self.save_button.setStyleSheet(f"""
                QPushButton {{
                    background-color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR};
                    color: white;
                    font-weight: bold;
                    min-height: {AnalyticsRunnerStylesheet.BUTTON_HEIGHT}px;
                }}
                QPushButton:hover {{
                    background-color: #45a049;
                }}
            """)
        else:
            missing_fields = self._get_missing_required_fields()
            self.status_label.setText(f"Missing: {', '.join(missing_fields)}")
            self.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.WARNING_COLOR}; font-style: italic;")

            # Reset save button styling
            self.save_button.setStyleSheet("")

        # Update title to show unsaved state
        name = self.form_fields['name'].text().strip() or "Untitled Rule"
        if self.is_editing_existing:
            self.title_label.setText(f"Editing: {name} *")
        else:
            self.title_label.setText(f"Creating: {name} *")

    def _can_save_rule(self) -> bool:
        """Check if rule can be saved - ENHANCED with debug logging"""
        # Check required fields
        name = self.form_fields['name'].text().strip()
        formula = self.form_fields['formula'].toPlainText().strip()

        logger.debug(
            f"_can_save_rule check: current_rule={self.current_rule is not None}, name='{name}', formula='{formula}'")

        if not self.current_rule:
            logger.debug("Cannot save: no current_rule")
            return False

        if not name:
            logger.debug("Cannot save: no name")
            return False

        if not formula:
            logger.debug("Cannot save: no formula")
            return False

        # Basic formula syntax check
        if not self.rule_parser.is_valid_formula(formula):
            logger.debug("Cannot save: invalid formula syntax")
            return False

        logger.debug("Can save: all requirements met")
        return True

    def _get_missing_required_fields(self) -> List[str]:
        """Get list of missing required fields - NEW METHOD"""
        missing = []

        if not self.form_fields['name'].text().strip():
            missing.append("Rule Name")

        if not self.form_fields['formula'].toPlainText().strip():
            missing.append("Formula")
        elif not self.rule_parser.is_valid_formula(self.form_fields['formula'].toPlainText().strip()):
            missing.append("Valid Formula")

        return missing

    def _on_formula_changed(self):
        """Handle formula changes with validation"""
        self._on_field_changed()  # Mark as changed

        # Debounced validation
        self.validation_timer.stop()
        self.validation_timer.start(500)  # Validate after 500ms of no changes

        # Update test button state
        self._update_test_button_state()

    def _validate_formula(self):
        """Validate the current formula"""
        formula = self.form_fields['formula'].toPlainText().strip()

        if not formula:
            self.formula_feedback.hide()
            return

        # Basic syntax validation
        is_valid = self.rule_parser.is_valid_formula(formula)

        if is_valid:
            # Check column references if we have data
            if self.current_data_preview is not None:
                is_valid, error = self.rule_parser.validate_formula_with_dataframe(
                    formula, self.current_data_preview
                )

                if is_valid:
                    self.formula_feedback.setText("✓ Formula syntax is valid")
                    self.formula_feedback.setStyleSheet(AnalyticsRunnerStylesheet.get_success_style())
                else:
                    self.formula_feedback.setText(f"⚠ Column reference error: {error}")
                    self.formula_feedback.setStyleSheet(AnalyticsRunnerStylesheet.get_warning_style())
            else:
                self.formula_feedback.setText("✓ Formula syntax is valid (load data to validate column references)")
                self.formula_feedback.setStyleSheet(AnalyticsRunnerStylesheet.get_success_style())
        else:
            self.formula_feedback.setText("✗ Invalid formula syntax - must start with '=' and have balanced parentheses/brackets")
            self.formula_feedback.setStyleSheet(AnalyticsRunnerStylesheet.get_error_style())

        self.formula_feedback.show()

    def get_current_rule_id(self) -> Optional[str]:
        """Get the ID of the currently loaded rule"""
        return self.current_rule.rule_id if self.current_rule else None

    def has_changes(self) -> bool:
        """Check if there are unsaved changes"""
        return self.has_unsaved_changes
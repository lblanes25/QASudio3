"""
Formula Editor Widget with real-time LOOKUP validation.
Part of Phase 2, Task 3 for Secondary Source File Integration.
Enhanced with LOOKUP Assistant integration (Phase 3, Task 1).
"""

from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit, QLabel, 
    QTextEdit, QFrame, QScrollArea, QPushButton
)
from PySide6.QtCore import Signal, QTimer
from PySide6.QtGui import QFont

from ui.common.stylesheet import AnalyticsRunnerStylesheet
from ui.common.widgets.formula_validator import FormulaValidator
from core.lookup.smart_lookup_manager import SmartLookupManager


class FormulaEditorWidget(QWidget):
    """Formula editor with real-time LOOKUP validation feedback."""
    
    # Signals
    formulaChanged = Signal(str)
    formulaValidated = Signal(bool)  # True if valid, False if has errors
    
    def __init__(self, lookup_manager: SmartLookupManager = None, 
                 session_manager=None, primary_columns: List[str] = None,
                 parent=None):
        """
        Initialize the formula editor widget.
        
        Args:
            lookup_manager: SmartLookupManager instance for validation
            session_manager: Optional session manager for recent files
            primary_columns: List of columns from primary data (for LOOKUP Assistant)
            parent: Parent widget
        """
        super().__init__(parent)
        self.lookup_manager = lookup_manager
        self.session_manager = session_manager
        self.primary_columns = primary_columns or []
        
        # Create validator
        self.validator = FormulaValidator(session_manager)
        self.validator.validationResult.connect(self._on_validation_result)
        
        # Validation timer for debouncing
        self.validation_timer = QTimer()
        self.validation_timer.timeout.connect(self._perform_validation)
        self.validation_timer.setSingleShot(True)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        
        # Formula input
        input_layout = QHBoxLayout()
        
        label = QLabel("Formula:")
        label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        input_layout.addWidget(label)
        
        self.formula_input = QLineEdit()
        self.formula_input.setPlaceholderText("Enter formula (e.g., LOOKUP([ID], 'Status') = 'Active')")
        self.formula_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 8px;
                font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
                font-family: 'Consolas', 'Monaco', monospace;
            }}
            QLineEdit:focus {{
                border-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            }}
        """)
        self.formula_input.textChanged.connect(self._on_formula_changed)
        input_layout.addWidget(self.formula_input, 1)
        
        # LOOKUP Assistant button
        self.assistant_button = QPushButton("LOOKUP Assistant")
        self.assistant_button.setToolTip("Open LOOKUP formula builder")
        self.assistant_button.clicked.connect(self._open_lookup_assistant)
        self.assistant_button.setEnabled(bool(self.lookup_manager))
        input_layout.addWidget(self.assistant_button)
        
        layout.addLayout(input_layout)
        
        # Validation feedback area
        self.feedback_frame = QFrame()
        self.feedback_frame.setVisible(False)
        self.feedback_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        
        feedback_layout = QVBoxLayout(self.feedback_frame)
        feedback_layout.setSpacing(4)
        
        # Feedback container (will be populated dynamically)
        self.feedback_container = QWidget()
        self.feedback_layout = QVBoxLayout(self.feedback_container)
        self.feedback_layout.setContentsMargins(0, 0, 0, 0)
        self.feedback_layout.setSpacing(4)
        
        # Scroll area for feedback
        scroll_area = QScrollArea()
        scroll_area.setWidget(self.feedback_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setMaximumHeight(150)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: transparent;
            }}
        """)
        
        feedback_layout.addWidget(scroll_area)
        layout.addWidget(self.feedback_frame)
    
    def _on_formula_changed(self, text: str):
        """Handle formula text changes."""
        # Emit immediate change signal
        self.formulaChanged.emit(text)
        
        # Only validate if LOOKUP is present
        if 'LOOKUP(' in text:
            # Start/restart the validation timer (debounce)
            self.validation_timer.stop()
            self.validation_timer.start(300)  # 300ms delay
        else:
            # Hide feedback if no LOOKUP
            self.feedback_frame.setVisible(False)
    
    def _perform_validation(self):
        """Perform the actual validation."""
        if self.lookup_manager:
            formula = self.formula_input.text()
            self.validator.validate_lookup_formula(formula, self.lookup_manager)
    
    def _on_validation_result(self, result: dict):
        """Handle validation results from the validator."""
        feedback_items = result.get('feedback', [])
        has_errors = result.get('has_errors', False)
        
        # Clear existing feedback
        while self.feedback_layout.count():
            child = self.feedback_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not feedback_items:
            self.feedback_frame.setVisible(False)
            return
        
        # Add feedback items
        for item in feedback_items:
            feedback_widget = self._create_feedback_widget(item)
            self.feedback_layout.addWidget(feedback_widget)
        
        self.feedback_layout.addStretch()
        self.feedback_frame.setVisible(True)
        
        # Emit validation status
        self.formulaValidated.emit(not has_errors)
    
    def _create_feedback_widget(self, feedback: dict) -> QWidget:
        """Create a widget for displaying a single feedback item."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(2)
        
        # Main message
        message_label = QLabel(feedback['message'])
        message_label.setWordWrap(True)
        
        if feedback['status'] == 'found':
            message_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR};
                    font-size: {AnalyticsRunnerStylesheet.SMALL_FONT_SIZE}px;
                }}
            """)
        else:
            message_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.ERROR_COLOR};
                    font-size: {AnalyticsRunnerStylesheet.SMALL_FONT_SIZE}px;
                    font-weight: bold;
                }}
            """)
        
        layout.addWidget(message_label)
        
        # Suggestion if present
        if 'suggestion' in feedback:
            suggestion_label = QLabel(f"💡 {feedback['suggestion']}")
            suggestion_label.setWordWrap(True)
            suggestion_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.INFO_COLOR};
                    font-size: {AnalyticsRunnerStylesheet.SMALL_FONT_SIZE}px;
                    padding-left: 16px;
                }}
            """)
            layout.addWidget(suggestion_label)
        
        # Warning if present
        if 'warning' in feedback:
            warning_label = QLabel(f"⚠️ {feedback['warning']}")
            warning_label.setWordWrap(True)
            warning_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.WARNING_COLOR};
                    font-size: {AnalyticsRunnerStylesheet.SMALL_FONT_SIZE}px;
                    padding-left: 16px;
                }}
            """)
            layout.addWidget(warning_label)
        
        return widget
    
    def set_formula(self, formula: str):
        """Set the formula text programmatically."""
        self.formula_input.setText(formula)
    
    def get_formula(self) -> str:
        """Get the current formula text."""
        return self.formula_input.text()
    
    def _open_lookup_assistant(self):
        """Open the LOOKUP Assistant dialog."""
        if not self.lookup_manager:
            return
        
        from ui.analytics_runner.dialogs.lookup_assistant_dialog import LookupAssistant
        
        dialog = LookupAssistant(
            primary_columns=self.primary_columns,
            lookup_manager=self.lookup_manager,
            parent=self
        )
        
        # Connect to handle generated formula
        dialog.formulaGenerated.connect(self._insert_lookup_formula)
        
        dialog.exec()
    
    def _insert_lookup_formula(self, formula: str):
        """Insert the generated LOOKUP formula at cursor position."""
        cursor_pos = self.formula_input.cursorPosition()
        current_text = self.formula_input.text()
        
        # Insert at cursor position
        new_text = current_text[:cursor_pos] + formula + current_text[cursor_pos:]
        self.formula_input.setText(new_text)
        
        # Move cursor to end of inserted formula
        self.formula_input.setCursorPosition(cursor_pos + len(formula))
    
    def set_lookup_manager(self, lookup_manager: SmartLookupManager):
        """Update the lookup manager for validation."""
        self.lookup_manager = lookup_manager
        self.assistant_button.setEnabled(bool(lookup_manager))
        # Revalidate if we have a formula
        if self.formula_input.text() and 'LOOKUP(' in self.formula_input.text():
            self._perform_validation()
    
    def set_primary_columns(self, columns: List[str]):
        """Update the primary data columns for LOOKUP Assistant."""
        self.primary_columns = columns or []
    
    def clear(self):
        """Clear the formula and feedback."""
        self.formula_input.clear()
        self.feedback_frame.setVisible(False)
"""
PreValidationWidget - Data Quality Pre-Validation Component
Provides fast structural validation before full validation pipeline execution
"""

import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QGroupBox, QTextEdit, QProgressBar,
    QSizePolicy, QTreeWidget, QTreeWidgetItem, QHeaderView
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QFont, QPalette

from ui.common.stylesheet import AnalyticsRunnerStylesheet

logger = logging.getLogger(__name__)


class PreValidationWorker(QThread):
    """Worker thread for running pre-validation checks without blocking UI."""
    
    # Signals
    validationComplete = Signal(dict)  # Validation results
    validationProgress = Signal(int, str)  # Progress value, status message
    validationError = Signal(str)  # Error message
    
    def __init__(self, df, data_type: str = "generic", custom_rules: Optional[Dict] = None):
        super().__init__()
        self.df = df
        self.data_type = data_type
        self.custom_rules = custom_rules
        self._should_stop = False
    
    def stop(self):
        """Request the worker to stop."""
        self._should_stop = True
    
    def run(self):
        """Run pre-validation in background thread."""
        try:
            self.validationProgress.emit(10, "Initializing data validator...")
            
            if self._should_stop:
                return
            
            # Import here to avoid thread import issues
            from data_integration.io.data_validator import DataValidator
            from data_integration.io.importer import DataImporter
            
            validator = DataValidator()
            
            self.validationProgress.emit(30, "Loading validation rules...")
            
            # Get validation rules
            if self.custom_rules:
                validation_rules = self.custom_rules
            else:
                validation_rules = DataImporter.get_standard_validation_rules(self.data_type)
            
            if self._should_stop:
                return
            
            self.validationProgress.emit(60, "Running validation checks...")
            
            # Run validation
            results = validator.validate(
                self.df,
                validation_rules,
                raise_exception=False,
                treat_warnings_as_errors=False
            )
            
            if self._should_stop:
                return
            
            self.validationProgress.emit(90, "Processing results...")
            
            # Add metadata for UI display
            results['data_type'] = self.data_type
            results['rules_applied'] = list(validation_rules.keys())
            results['rule_count'] = len(validation_rules)
            
            self.validationProgress.emit(100, "Validation complete")
            self.validationComplete.emit(results)
            
        except Exception as e:
            error_msg = f"Pre-validation error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.validationError.emit(error_msg)


class ValidationRuleItem(QTreeWidgetItem):
    """Custom tree widget item for validation rules with status styling."""
    
    def __init__(self, parent, rule_name: str, rule_result: Dict[str, Any]):
        super().__init__(parent)
        
        self.rule_name = rule_name
        self.rule_result = rule_result
        
        # Set item data
        self.setText(0, rule_name)
        self.setText(1, "PASSED" if rule_result.get('valid', False) else "FAILED")
        self.setText(2, str(rule_result.get('failure_count', 0)))
        
        # Add failure details as children if any
        failures = rule_result.get('failures', [])
        if failures:
            for i, failure in enumerate(failures[:10]):  # Limit to first 10
                failure_item = QTreeWidgetItem(self)
                failure_item.setText(0, f"Issue {i+1}")
                failure_item.setText(1, str(failure))
                failure_item.setText(2, "")

            # Add "more" item if there are additional failures
            if len(failures) > 10:
                more_item = QTreeWidgetItem(self)
                more_item.setText(0, "...")
                more_item.setText(1, f"and {len(failures) - 10} more issues")
                more_item.setText(2, "")


class PreValidationWidget(QWidget):
    """
    Pre-validation widget for data quality checks before full validation.

    Features:
    - Fast structural validation using DataValidator
    - Color-coded status indicators
    - Expandable validation rule details
    - Clean status-only display without action buttons
    """

    # Signals
    validationStatusChanged = Signal(bool, str)  # Is valid, status message

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        # State
        self._current_results = None
        self._is_valid = False
        self._has_warnings = False
        self._worker = None

        # Setup UI
        self._setup_ui()
        self._setup_connections()

        # Initially hidden
        self.setVisible(False)

        logger.debug("PreValidationWidget initialized")

    def _setup_ui(self):
        """Setup the user interface components."""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # Create main group box
        self.validation_group = QGroupBox("Data Quality Pre-Validation")
        self.validation_group.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        self.main_layout.addWidget(self.validation_group)

        # Group layout
        group_layout = QVBoxLayout(self.validation_group)
        group_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)

        # Status header
        self._create_status_header(group_layout)

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setTextVisible(True)
        group_layout.addWidget(self.progress_bar)

        # Results area
        self._create_results_area(group_layout)

    def _create_status_header(self, parent_layout):
        """Create the validation status header."""
        # Status frame
        self.status_frame = QFrame()
        self.status_frame.setFrameStyle(QFrame.StyledPanel)
        self.status_frame.setLineWidth(1)
        parent_layout.addWidget(self.status_frame)

        # Status layout
        status_layout = QHBoxLayout(self.status_frame)
        status_layout.setContentsMargins(12, 8, 12, 8)
        status_layout.setSpacing(12)

        # Status indicator
        self.status_indicator = QLabel("●")
        self.status_indicator.setFont(QFont("Arial", 16))
        self.status_indicator.setAlignment(Qt.AlignCenter)
        self.status_indicator.setFixedSize(24, 24)
        status_layout.addWidget(self.status_indicator)

        # Status text
        self.status_label = QLabel("Ready for validation")
        self.status_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        status_layout.addWidget(self.status_label, 1)

        # Summary stats
        self.stats_label = QLabel("")
        self.stats_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        self.stats_label.setAlignment(Qt.AlignRight)
        status_layout.addWidget(self.stats_label)

        # Initialize with neutral styling
        self._update_status_display("ready")

    def _create_results_area(self, parent_layout):
        """Create the validation results display area with better sizing."""
        # Results tree widget with improved sizing
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Rule", "Status", "Issues"])
        self.results_tree.setAlternatingRowColors(True)
        self.results_tree.setRootIsDecorated(True)

        # Set flexible height with reasonable bounds
        self.results_tree.setMinimumHeight(120)
        self.results_tree.setMaximumHeight(300)  # Increased max height

        # Set size policy to allow vertical expansion
        self.results_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Configure column widths
        header = self.results_tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)

        # Initially hidden
        self.results_tree.setVisible(False)
        parent_layout.addWidget(self.results_tree)

        # Error/warning summary text with better sizing
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(60)
        self.summary_text.setMaximumHeight(120)  # Increased max height
        self.summary_text.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        self.summary_text.setPlaceholderText("Validation summary will appear here...")
        self.summary_text.setVisible(False)

        # Set size policy for better resizing
        self.summary_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        parent_layout.addWidget(self.summary_text)

    def _setup_connections(self):
        """Setup signal connections."""
        # No connections needed since we removed the re-validate button
        pass

    def _update_status_display(self, status: str, message: str = "", stats: str = ""):
        """Update the status display based on validation state."""
        status_styles = {
            "ready": {
                "color": AnalyticsRunnerStylesheet.TEXT_COLOR,
                "bg_color": AnalyticsRunnerStylesheet.INPUT_BACKGROUND,
                "border_color": AnalyticsRunnerStylesheet.BORDER_COLOR,
                "icon": "●",
                "message": message or "Ready for validation"
            },
            "running": {
                "color": AnalyticsRunnerStylesheet.INFO_COLOR,
                "bg_color": f"{AnalyticsRunnerStylesheet.INFO_COLOR}20",
                "border_color": AnalyticsRunnerStylesheet.INFO_COLOR,
                "icon": "⟳",
                "message": message or "Running validation..."
            },
            "passed": {
                "color": AnalyticsRunnerStylesheet.SUCCESS_COLOR,
                "bg_color": f"{AnalyticsRunnerStylesheet.SUCCESS_COLOR}20",
                "border_color": AnalyticsRunnerStylesheet.SUCCESS_COLOR,
                "icon": "✓",
                "message": message or "All validation checks passed"
            },
            "warning": {
                "color": AnalyticsRunnerStylesheet.WARNING_COLOR,
                "bg_color": f"{AnalyticsRunnerStylesheet.WARNING_COLOR}20",
                "border_color": AnalyticsRunnerStylesheet.WARNING_COLOR,
                "icon": "⚠",
                "message": message or "Validation completed with warnings"
            },
            "failed": {
                "color": AnalyticsRunnerStylesheet.ERROR_COLOR,
                "bg_color": f"{AnalyticsRunnerStylesheet.ERROR_COLOR}20",
                "border_color": AnalyticsRunnerStylesheet.ERROR_COLOR,
                "icon": "✗",
                "message": message or "Validation failed"
            }
        }

        style_info = status_styles.get(status, status_styles["ready"])

        # Update indicator
        self.status_indicator.setText(style_info["icon"])
        self.status_indicator.setStyleSheet(f"""
            QLabel {{
                color: {style_info["color"]};
                background-color: {style_info["bg_color"]};
                border-radius: 12px;
                font-weight: bold;
            }}
        """)

        # Update status frame
        self.status_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {style_info["bg_color"]};
                border: 1px solid {style_info["border_color"]};
                border-radius: 6px;
            }}
        """)

        # Update labels
        self.status_label.setText(style_info["message"])
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {style_info["color"]};
                font-weight: 500;
            }}
        """)

        if stats:
            self.stats_label.setText(stats)
            self.stats_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                }}
            """)

    def validate_data(self, df, data_type: str = "generic", custom_rules: Optional[Dict] = None):
        """
        Start validation of the provided DataFrame.

        Args:
            df: DataFrame to validate
            data_type: Type of data for rule selection
            custom_rules: Optional custom validation rules
        """
        # Store parameters for potential future use
        self._last_df = df
        self._last_data_type = data_type
        self._last_custom_rules = custom_rules

        # Stop any existing validation
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.quit()
            self._worker.wait()

        # Show the widget and update UI
        self.setVisible(True)
        self._update_status_display("running", "Starting validation...")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        # Hide results until validation completes
        self.results_tree.setVisible(False)
        self.summary_text.setVisible(False)

        # Start validation worker
        self._worker = PreValidationWorker(df, data_type, custom_rules)
        self._worker.validationComplete.connect(self._on_validation_complete)
        self._worker.validationProgress.connect(self._on_validation_progress)
        self._worker.validationError.connect(self._on_validation_error)
        self._worker.start()

        logger.info(f"Started pre-validation for {data_type} data")

    def _on_validation_progress(self, value: int, message: str):
        """Handle validation progress updates."""
        self.progress_bar.setValue(value)
        self.progress_bar.setFormat(f"{value}% - {message}")
        self._update_status_display("running", message)

    def _on_validation_complete(self, results: Dict[str, Any]):
        """Handle validation completion."""
        self._current_results = results

        # Hide progress bar
        self.progress_bar.setVisible(False)

        # Analyze results
        is_valid = results.get('valid', False)
        errors = results.get('errors', [])
        warnings = results.get('warnings', [])
        rule_details = results.get('details', {})

        # Update state
        self._is_valid = is_valid
        self._has_warnings = len(warnings) > 0

        # Determine status
        if is_valid and not warnings:
            status = "passed"
            message = "All validation checks passed"
        elif is_valid and warnings:
            status = "warning"
            message = f"Validation passed with {len(warnings)} warnings"
        else:
            status = "failed"
            message = f"Validation failed with {len(errors)} errors"

        # Create stats summary
        total_rules = len(rule_details)
        passed_rules = sum(1 for r in rule_details.values() if r.get('valid', False))
        stats = f"{passed_rules}/{total_rules} rules passed"

        # Update display
        self._update_status_display(status, message, stats)

        # Update results tree
        self._update_results_tree(rule_details)

        # Update summary text
        self._update_summary_text(results)

        # Show results
        self.results_tree.setVisible(True)
        if errors or warnings:
            self.summary_text.setVisible(True)

        # Emit status signal
        self.validationStatusChanged.emit(is_valid, message)

        logger.info(f"Pre-validation complete: {status} - {stats}")

    def _on_validation_error(self, error_msg: str):
        """Handle validation error."""
        self.progress_bar.setVisible(False)
        self._update_status_display("failed", f"Error: {error_msg}")

        # Show error in summary
        self.summary_text.setPlainText(f"Validation Error:\n{error_msg}")
        self.summary_text.setVisible(True)

        # Emit status signal
        self.validationStatusChanged.emit(False, error_msg)

        logger.error(f"Pre-validation error: {error_msg}")

    def _update_results_tree(self, rule_details: Dict[str, Any]):
        """Update the results tree with validation details."""
        self.results_tree.clear()

        for rule_name, rule_result in rule_details.items():
            ValidationRuleItem(self.results_tree, rule_name, rule_result)

        # Expand failed items by default
        for i in range(self.results_tree.topLevelItemCount()):
            item = self.results_tree.topLevelItem(i)
            if not item.rule_result.get('valid', False):
                self.results_tree.expandItem(item)

    def _update_summary_text(self, results: Dict[str, Any]):
        """Update the summary text with error and warning details."""
        summary_lines = []

        errors = results.get('errors', [])
        warnings = results.get('warnings', [])

        if errors:
            summary_lines.append("=== ERRORS ===")
            for i, error in enumerate(errors, 1):
                summary_lines.append(f"{i}. {error.get('message', 'Unknown error')}")
            summary_lines.append("")

        if warnings:
            summary_lines.append("=== WARNINGS ===")
            for i, warning in enumerate(warnings, 1):
                summary_lines.append(f"{i}. {warning.get('message', 'Unknown warning')}")
            summary_lines.append("")

        if not errors and not warnings:
            summary_lines.append("All validation checks passed successfully!")

        self.summary_text.setPlainText('\n'.join(summary_lines))

    # Public interface
    def get_validation_results(self) -> Optional[Dict[str, Any]]:
        """Get the current validation results."""
        return self._current_results

    def is_valid(self) -> bool:
        """Check if current validation status is valid."""
        return self._is_valid

    def has_warnings(self) -> bool:
        """Check if current validation has warnings."""
        return self._has_warnings

    def clear_results(self):
        """Clear current validation results and hide widget."""
        self._current_results = None
        self._is_valid = False
        self._has_warnings = False

        # Clear displays
        self.results_tree.clear()
        self.summary_text.clear()

        # Reset UI
        self._update_status_display("ready")
        self.progress_bar.setVisible(False)
        self.results_tree.setVisible(False)
        self.summary_text.setVisible(False)

        # Hide widget
        self.setVisible(False)

    def cleanup(self):
        """Clean up resources before widget destruction."""
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            self._worker.quit()
            self._worker.wait()
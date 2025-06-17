"""
Example demonstrating FormulaValidator integration.
Shows how to add real-time LOOKUP validation to any formula input field.
"""

import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QPushButton, QLabel, QGroupBox
)
from PySide6.QtCore import Qt

# Add parent directory to path for imports
sys.path.insert(0, '..')

from ui.common.widgets import FormulaEditorWidget
from ui.analytics_runner.data_source_panel import DataSourcePanel
from core.lookup.smart_lookup_manager import SmartLookupManager
from ui.common.stylesheet import AnalyticsRunnerStylesheet


class FormulaValidatorExample(QMainWindow):
    """Example window showing formula validation in action."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Formula Validator Example")
        self.setGeometry(100, 100, 900, 700)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        layout = QVBoxLayout(central)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Title
        title = QLabel("LOOKUP Formula Validation Example")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 20px;
                font-weight: bold;
                color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                padding: 8px;
            }}
        """)
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "1. Load files using the data source panel below\n"
            "2. Type a formula containing LOOKUP in the formula editor\n"
            "3. See real-time validation feedback as you type"
        )
        instructions.setStyleSheet(f"""
            QLabel {{
                background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
                padding: 12px;
                border-radius: 4px;
                border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            }}
        """)
        layout.addWidget(instructions)
        
        # Data source panel (simplified)
        data_group = QGroupBox("Data Sources")
        data_layout = QVBoxLayout(data_group)
        
        self.data_panel = DataSourcePanel()
        data_layout.addWidget(self.data_panel)
        
        layout.addWidget(data_group)
        
        # Formula editor with validation
        formula_group = QGroupBox("Formula Editor with Validation")
        formula_layout = QVBoxLayout(formula_group)
        
        # Get lookup manager from data panel
        lookup_manager = self.data_panel.get_lookup_manager()
        
        # Example primary columns (in real app, these would come from loaded data)
        primary_columns = ['ReviewerID', 'SubmitterID', 'VendorID', 'ProductID', 
                          'EmployeeID', 'Department', 'Amount', 'Quantity']
        
        self.formula_editor = FormulaEditorWidget(
            lookup_manager=lookup_manager,
            session_manager=None,  # Could pass real session manager here
            primary_columns=primary_columns
        )
        
        # Connect signals
        self.formula_editor.formulaChanged.connect(self._on_formula_changed)
        self.formula_editor.formulaValidated.connect(self._on_formula_validated)
        
        formula_layout.addWidget(self.formula_editor)
        
        # Example formulas
        examples_label = QLabel("Example formulas to try:")
        examples_label.setStyleSheet("font-weight: bold;")
        formula_layout.addWidget(examples_label)
        
        examples = [
            "LOOKUP([ReviewerID], 'Level') > LOOKUP([SubmitterID], 'Level')",
            "LOOKUP([VendorID], 'Status') = 'Active'",
            "LOOKUP([EmployeeID], 'Department') = 'Finance'",
            "LOOKUP([ProductID], 'Price') * [Quantity]"
        ]
        
        for example in examples:
            btn = QPushButton(example)
            btn.clicked.connect(lambda checked, f=example: self.formula_editor.set_formula(f))
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 4px 8px;
                    font-family: 'Consolas', monospace;
                    font-size: 12px;
                }
            """)
            formula_layout.addWidget(btn)
        
        layout.addWidget(formula_group)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                padding: 8px;
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
            }}
        """)
        layout.addWidget(self.status_label)
        
        layout.addStretch()
        
        # Apply stylesheet
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())
    
    def _on_formula_changed(self, formula: str):
        """Handle formula changes."""
        if formula:
            self.status_label.setText(f"Formula: {formula}")
        else:
            self.status_label.setText("Ready")
    
    def _on_formula_validated(self, is_valid: bool):
        """Handle validation results."""
        if is_valid:
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    padding: 8px;
                    background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                    border: 1px solid {AnalyticsRunnerStylesheet.SUCCESS_COLOR};
                    border-radius: 4px;
                    color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR};
                }}
            """)
        else:
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    padding: 8px;
                    background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                    border: 1px solid {AnalyticsRunnerStylesheet.ERROR_COLOR};
                    border-radius: 4px;
                    color: {AnalyticsRunnerStylesheet.ERROR_COLOR};
                }}
            """)


def main():
    """Run the example application."""
    app = QApplication(sys.argv)
    
    # Create and show example
    window = FormulaValidatorExample()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
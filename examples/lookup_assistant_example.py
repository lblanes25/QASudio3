"""
Example demonstrating LOOKUP Assistant integration with Formula Editor.
Shows the complete workflow of using the LOOKUP Assistant to build formulas.
"""

import sys
import os
from pathlib import Path
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QGroupBox, QTextEdit, QSplitter
)
from PySide6.QtCore import Qt

# Add parent directory to path for imports
sys.path.insert(0, '..')

from ui.common.widgets import FormulaEditorWidget
from ui.analytics_runner.data_source_panel import DataSourcePanel
from core.lookup.smart_lookup_manager import SmartLookupManager
from ui.common.stylesheet import AnalyticsRunnerStylesheet


class LookupAssistantExample(QMainWindow):
    """Example window showing LOOKUP Assistant integration."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LOOKUP Assistant Example")
        self.setGeometry(100, 100, 1200, 800)
        
        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        
        # Main layout
        layout = QVBoxLayout(central)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Title
        title = QLabel("LOOKUP Assistant Integration Example")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet(f"""
            QLabel {{
                font-size: 24px;
                font-weight: bold;
                color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                padding: 8px;
            }}
        """)
        layout.addWidget(title)
        
        # Instructions
        instructions = QLabel(
            "This example demonstrates the complete LOOKUP Assistant workflow:\n"
            "1. Load secondary data files using the Data Source Panel\n"
            "2. Click 'LOOKUP Assistant' in the formula editor to build LOOKUP formulas\n"
            "3. See real-time validation as you type or modify formulas\n"
            "4. View the generated formula and use it in your validation rules"
        )
        instructions.setStyleSheet(f"""
            QLabel {{
                background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
                padding: 12px;
                border-radius: 4px;
                border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                font-size: 14px;
            }}
        """)
        layout.addWidget(instructions)
        
        # Create splitter for side-by-side layout
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Data source panel
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        data_group = QGroupBox("Step 1: Load Secondary Data Files")
        data_layout = QVBoxLayout(data_group)
        
        # Add helpful text
        data_help = QLabel(
            "Load Excel or CSV files containing lookup data.\n"
            "Examples: employee_data.xlsx, vendor_list.csv, product_catalog.xlsx"
        )
        data_help.setWordWrap(True)
        data_help.setStyleSheet("""
            QLabel {
                color: #666;
                font-size: 12px;
                padding: 4px;
            }
        """)
        data_layout.addWidget(data_help)
        
        self.data_panel = DataSourcePanel()
        data_layout.addWidget(self.data_panel)
        
        left_layout.addWidget(data_group)
        splitter.addWidget(left_widget)
        
        # Right side - Formula editor and results
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # Formula editor with validation
        formula_group = QGroupBox("Step 2: Build LOOKUP Formulas")
        formula_layout = QVBoxLayout(formula_group)
        
        # Get lookup manager from data panel
        lookup_manager = self.data_panel.get_lookup_manager()
        
        # Example primary columns (in real app, these would come from loaded data)
        primary_columns = [
            'ReviewerID', 'SubmitterID', 'VendorID', 'ProductID',
            'EmployeeID', 'Department', 'Amount', 'Quantity',
            'TransactionDate', 'ApprovalLevel', 'Status'
        ]
        
        self.formula_editor = FormulaEditorWidget(
            lookup_manager=lookup_manager,
            session_manager=None,
            primary_columns=primary_columns
        )
        
        # Connect signals
        self.formula_editor.formulaChanged.connect(self._on_formula_changed)
        self.formula_editor.formulaValidated.connect(self._on_formula_validated)
        
        formula_layout.addWidget(self.formula_editor)
        
        # Example formulas section
        examples_label = QLabel("Example LOOKUP formulas to try:")
        examples_label.setStyleSheet("font-weight: bold; margin-top: 8px;")
        formula_layout.addWidget(examples_label)
        
        examples = [
            ("Manager Level Check", "LOOKUP([ReviewerID], 'Level') > LOOKUP([SubmitterID], 'Level')"),
            ("Active Vendor Check", "LOOKUP([VendorID], 'Status') = 'Active'"),
            ("Department Match", "LOOKUP([EmployeeID], 'Department') = [Department]"),
            ("Price Calculation", "LOOKUP([ProductID], 'Price') * [Quantity] < 10000"),
            ("Manager Approval", "LOOKUP([ReviewerID], 'CanApprove') = 'Yes'")
        ]
        
        for desc, formula in examples:
            example_layout = QHBoxLayout()
            
            desc_label = QLabel(f"{desc}:")
            desc_label.setFixedWidth(150)
            example_layout.addWidget(desc_label)
            
            btn = QPushButton(formula)
            btn.clicked.connect(lambda checked, f=formula: self.formula_editor.set_formula(f))
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 4px 8px;
                    font-family: 'Consolas', monospace;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #e0e0e0;
                }
            """)
            example_layout.addWidget(btn)
            
            formula_layout.addLayout(example_layout)
        
        right_layout.addWidget(formula_group)
        
        # Results area
        results_group = QGroupBox("Formula Output")
        results_layout = QVBoxLayout(results_group)
        
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        self.result_display.setMaximumHeight(150)
        self.result_display.setPlaceholderText("Formula validation results will appear here...")
        results_layout.addWidget(self.result_display)
        
        right_layout.addWidget(results_group)
        
        # Status
        self.status_label = QLabel("Ready - Load some data files to begin")
        self.status_label.setStyleSheet(f"""
            QLabel {{
                padding: 8px;
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
            }}
        """)
        right_layout.addWidget(self.status_label)
        
        right_layout.addStretch()
        splitter.addWidget(right_widget)
        
        # Set splitter sizes (40% left, 60% right)
        splitter.setSizes([480, 720])
        
        layout.addWidget(splitter)
        
        # Create sample data button
        sample_button = QPushButton("Create Sample Data Files")
        sample_button.clicked.connect(self._create_sample_data)
        sample_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {AnalyticsRunnerStylesheet.PRIMARY_HOVER};
            }}
        """)
        layout.addWidget(sample_button)
        
        # Apply stylesheet
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())
        
        # Connect data panel signals
        self.data_panel.data_loaded.connect(self._on_data_loaded)
    
    def _on_formula_changed(self, formula: str):
        """Handle formula changes."""
        if formula:
            self.result_display.append(f"Formula entered: {formula}")
        
    def _on_formula_validated(self, is_valid: bool):
        """Handle validation results."""
        if is_valid:
            self.status_label.setText("✓ Formula is valid")
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
            self.status_label.setText("✗ Formula has errors - check validation feedback")
            self.status_label.setStyleSheet(f"""
                QLabel {{
                    padding: 8px;
                    background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                    border: 1px solid {AnalyticsRunnerStylesheet.ERROR_COLOR};
                    border-radius: 4px;
                    color: {AnalyticsRunnerStylesheet.ERROR_COLOR};
                }}
            """)
    
    def _on_data_loaded(self, file_info: dict):
        """Handle data loaded from data panel."""
        self.result_display.append(f"\nLoaded: {file_info.get('alias', 'Unknown')}")
        self.result_display.append(f"  Columns: {', '.join(file_info.get('columns', [])[:5])}")
        if len(file_info.get('columns', [])) > 5:
            self.result_display.append(f"  ... and {len(file_info['columns']) - 5} more columns")
        
        # Update formula editor with new lookup manager
        self.formula_editor.set_lookup_manager(self.data_panel.get_lookup_manager())
        
        self.status_label.setText(f"Loaded {file_info.get('alias')} - Ready to build LOOKUP formulas")
    
    def _create_sample_data(self):
        """Create sample data files for testing."""
        import pandas as pd
        
        # Create sample employee data
        employee_data = pd.DataFrame({
            'EmployeeID': ['E001', 'E002', 'E003', 'E004', 'E005'],
            'Name': ['John Smith', 'Jane Doe', 'Bob Johnson', 'Alice Brown', 'Charlie Davis'],
            'Department': ['Finance', 'IT', 'Finance', 'HR', 'IT'],
            'Level': [3, 2, 4, 3, 1],
            'CanApprove': ['Yes', 'No', 'Yes', 'Yes', 'No'],
            'Manager': ['E003', 'E004', None, None, 'E002']
        })
        
        # Create sample vendor data
        vendor_data = pd.DataFrame({
            'VendorID': ['V001', 'V002', 'V003', 'V004'],
            'VendorName': ['Acme Corp', 'TechSupply Inc', 'Office Depot', 'GlobalTech'],
            'Status': ['Active', 'Active', 'Inactive', 'Active'],
            'Category': ['Software', 'Hardware', 'Supplies', 'Services'],
            'CreditLimit': [50000, 100000, 25000, 75000]
        })
        
        # Create sample product data
        product_data = pd.DataFrame({
            'ProductID': ['P001', 'P002', 'P003', 'P004', 'P005'],
            'ProductName': ['Laptop', 'Mouse', 'Keyboard', 'Monitor', 'Printer'],
            'Price': [1200.00, 25.00, 75.00, 350.00, 450.00],
            'Category': ['Hardware', 'Accessories', 'Accessories', 'Hardware', 'Hardware'],
            'InStock': ['Yes', 'Yes', 'No', 'Yes', 'Yes']
        })
        
        # Save files
        data_dir = Path('./sample_lookup_data')
        data_dir.mkdir(exist_ok=True)
        
        employee_data.to_excel(data_dir / 'employee_data.xlsx', index=False)
        vendor_data.to_csv(data_dir / 'vendor_list.csv', index=False)
        product_data.to_excel(data_dir / 'product_catalog.xlsx', index=False)
        
        self.result_display.append("\n✓ Created sample data files in ./sample_lookup_data/")
        self.result_display.append("  - employee_data.xlsx")
        self.result_display.append("  - vendor_list.csv")
        self.result_display.append("  - product_catalog.xlsx")
        self.result_display.append("\nUse the Data Source Panel to load these files!")
        
        self.status_label.setText("Sample data created - Load them using the Data Source Panel")


def main():
    """Run the example application."""
    app = QApplication(sys.argv)
    
    # Create and show example
    window = LookupAssistantExample()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Fixed Integration Test: DataSourcePanel + PreValidationWidget with Real Backend
Uses actual DataValidator and DataImporter from your backend
"""

import sys
import os
import tempfile
import pandas as pd
import numpy as np
from pathlib import Path

# Fix path setup - add the project root where data_integration module lives
current_file = Path(__file__).resolve()
project_root = current_file.parent.parent.parent  # Go up to QAStudiov3 root

# Add both the project root and potential backend locations
backend_paths = [
    str(project_root),  # QAStudiov3 root
    str(project_root / "backend"),  # If backend is in a backend folder
    str(project_root / "src"),  # If backend is in a src folder
    str(project_root.parent),  # Parent directory
]

for path in backend_paths:
    if path not in sys.path:
        sys.path.insert(0, path)

print("Python path setup:")
for i, path in enumerate(sys.path[:5]):  # Show first 5 paths
    print(f"  {i}: {path}")

# Check if we can find the data_integration module
try:
    import data_integration

    print(f"✅ Found data_integration module at: {data_integration.__file__}")
except ImportError as e:
    print(f"❌ Cannot import data_integration: {e}")
    print("Available modules in current directory:")
    current_dir = Path.cwd()
    for item in current_dir.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            print(f"  📁 {item.name}")
            # Check if it contains data_integration
            data_int_path = item / "data_integration"
            if data_int_path.exists():
                print(f"    ✅ Contains data_integration!")
                sys.path.insert(0, str(item))
                break
    print("\nPlease run this script from the directory containing data_integration module")
    print("Or adjust the path setup above.")

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel, QPushButton
from PySide6.QtCore import QTimer, Qt

# Import our UI components
from ui.analytics_runner.analytics_runner_stylesheet import AnalyticsRunnerStylesheet

# Suppress CSS warnings
import warnings

warnings.filterwarnings("ignore", message="Unknown property transform")


# Add the missing stylesheet method
def get_table_stylesheet():
    """Stylesheet for data preview tables"""
    return f"""
        QTableWidget {{
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            alternate-background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            gridline-color: {AnalyticsRunnerStylesheet.BORDER_COLOR};
            selection-background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            selection-color: white;
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 4px;
        }}

        QTableWidget::item {{
            padding: 6px 8px;
            border: none;
        }}

        QTableWidget::item:selected {{
            background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            color: white;
        }}

        QHeaderView::section {{
            background-color: {AnalyticsRunnerStylesheet.PANEL_BACKGROUND};
            color: {AnalyticsRunnerStylesheet.DARK_TEXT};
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-left: none;
            padding: 8px 12px;
            font-weight: 600;
            text-align: left;
        }}

        QHeaderView::section:first {{
            border-left: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
        }}

        QHeaderView::section:hover {{
            background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
        }}
    """


AnalyticsRunnerStylesheet.get_table_stylesheet = staticmethod(get_table_stylesheet)

# Now import the UI components
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QGroupBox,
    QFrame, QMessageBox, QFileDialog, QHeaderView,
)
from PySide6.QtCore import Qt, Signal, QThread, QTimer
from PySide6.QtGui import QFont, QColor
import logging
from typing import Optional, Dict, Any, List

from ui.analytics_runner.pre_validation_widget import PreValidationWidget

logger = logging.getLogger(__name__)


class FilePreviewWorker(QThread):
    """Worker thread using real DataImporter"""

    previewLoaded = Signal(object, dict)
    error = Signal(str)

    def __init__(self, file_path: str, sheet_name: str = None, max_rows: int = 100):
        super().__init__()
        self.file_path = file_path
        self.sheet_name = sheet_name
        self.max_rows = max_rows
        self._should_stop = False

    def stop(self):
        self._should_stop = True

    def run(self):
        try:
            if self._should_stop:
                return

            # Use the real DataImporter
            from data_integration.io.importer import DataImporter

            data_importer = DataImporter()

            # Use the real preview_file method
            kwargs = {'max_rows': self.max_rows}
            if self.sheet_name:
                kwargs['sheet_name'] = self.sheet_name

            if self._should_stop:
                return

            preview_df, metadata = data_importer.preview_file(
                self.file_path,
                **kwargs
            )

            if self._should_stop:
                return

            self.previewLoaded.emit(preview_df, metadata)

        except Exception as e:
            error_msg = f"Error loading file preview: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.error.emit(error_msg)


class IntegratedDataSourcePanel(QWidget):
    """Integrated DataSourcePanel with PreValidation using real backend"""

    # Signals
    dataSourceChanged = Signal(str)
    dataSourceValidated = Signal(bool, str)
    sheetChanged = Signal(str)
    previewUpdated = Signal(object)
    proceedToValidation = Signal(bool)

    def __init__(self, session_manager=None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.session_manager = session_manager
        self._current_file = ""
        self._current_sheet = None
        self._preview_df = None
        self._file_metadata = {}
        self._is_excel_file = False

        # Worker threads
        self._preview_worker = None
        self._sheet_worker = None

        # Setup UI
        self._setup_ui()
        self._setup_connections()

        logger.debug("IntegratedDataSourcePanel initialized")

    def _setup_ui(self):
        """Setup the simplified user interface with pre-validation."""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(16)
        self.main_layout.setContentsMargins(12, 12, 12, 12)

        self._create_file_selection_section()
        self._create_preview_section()

        # Add pre-validation widget
        self.pre_validation_widget = PreValidationWidget()
        self.main_layout.addWidget(self.pre_validation_widget)

    def _create_file_selection_section(self):
        """Create simplified file selection section."""
        file_frame = QFrame()
        file_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 6px;
                padding: 12px;
            }}
        """)

        file_layout = QVBoxLayout(file_frame)
        file_layout.setSpacing(8)

        # Title
        title_label = QLabel("Data Source File")
        title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                font-weight: bold;
                border: none;
                padding: 0px;
            }}
        """)
        file_layout.addWidget(title_label)

        # File selection row
        selection_layout = QHBoxLayout()
        selection_layout.setSpacing(12)

        # Current file display
        self.file_display = QLabel("No file selected")
        self.file_display.setStyleSheet(f"""
            QLabel {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 8px 12px;
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                font-style: italic;
            }}
        """)
        selection_layout.addWidget(self.file_display, 1)

        # Browse button
        self.browse_button = QPushButton("Browse...")
        self.browse_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.browse_button.clicked.connect(self._browse_file)
        selection_layout.addWidget(self.browse_button)

        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.setProperty("buttonStyle", "secondary")
        self.clear_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.clear_button.clicked.connect(self.clear_selection)
        self.clear_button.setVisible(False)
        selection_layout.addWidget(self.clear_button)

        file_layout.addLayout(selection_layout)
        self.main_layout.addWidget(file_frame)

    def _create_preview_section(self):
        """Create data preview section."""
        preview_frame = QFrame()
        preview_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 6px;
                padding: 12px;
            }}
        """)

        preview_layout = QVBoxLayout(preview_frame)
        preview_layout.setSpacing(8)

        # Header
        header_layout = QHBoxLayout()
        preview_title = QLabel("Data Preview")
        preview_title.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        preview_title.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                font-weight: bold;
                border: none;
                padding: 0px;
            }}
        """)
        header_layout.addWidget(preview_title)
        header_layout.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setProperty("buttonStyle", "secondary")
        self.refresh_button.setEnabled(False)
        self.refresh_button.clicked.connect(self._refresh_preview)
        header_layout.addWidget(self.refresh_button)

        preview_layout.addLayout(header_layout)

        # Preview table
        self.preview_table = QTableWidget()
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.preview_table.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        self.preview_table.setMinimumHeight(200)
        self.preview_table.setStyleSheet(AnalyticsRunnerStylesheet.get_table_stylesheet())

        preview_layout.addWidget(self.preview_table)
        self.main_layout.addWidget(preview_frame)

    def _setup_connections(self):
        """Setup signal connections."""
        # Pre-validation connections
        self.pre_validation_widget.validationStatusChanged.connect(self._on_prevalidation_status_changed)
        self.pre_validation_widget.proceedRequested.connect(self._on_proceed_requested)

    def _browse_file(self):
        """Open file browser dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Data Source File",
            "",
            "Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if file_path:
            self._set_file(file_path)

    def _set_file(self, file_path: str):
        """Set current file and update UI."""
        self._current_file = file_path

        # Update display
        file_name = os.path.basename(file_path)
        self.file_display.setText(file_name)
        self.file_display.setStyleSheet(f"""
            QLabel {{
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                border-radius: 4px;
                padding: 8px 12px;
                color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
                font-style: normal;
            }}
        """)

        self.clear_button.setVisible(True)
        self.refresh_button.setEnabled(True)

        # Load preview using real backend
        self._load_file_preview()

        # Emit signals
        self.dataSourceChanged.emit(file_path)
        self.dataSourceValidated.emit(True, "File selected")

    def _refresh_preview(self):
        """Refresh preview."""
        if self._current_file:
            self._load_file_preview()

    def _load_file_preview(self):
        """Load file preview using real DataImporter."""
        if not self._current_file:
            return

        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.stop()
            self._preview_worker.quit()
            self._preview_worker.wait()

        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Loading...")

        self._preview_worker = FilePreviewWorker(self._current_file, max_rows=50)
        self._preview_worker.previewLoaded.connect(self._on_preview_loaded)
        self._preview_worker.error.connect(self._on_preview_error)
        self._preview_worker.start()

    def _on_preview_loaded(self, preview_df, metadata: Dict[str, Any]):
        """Handle successful preview loading with pre-validation trigger."""
        self._preview_df = preview_df
        self._file_metadata = metadata

        # Update preview table
        self._update_preview_table()

        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("Refresh")

        # Auto-run pre-validation when preview loads
        if preview_df is not None and not preview_df.empty:
            # Always use generic validation for fast structural checks
            self.pre_validation_widget.validate_data(preview_df, "generic")

        self.previewUpdated.emit(preview_df)
        logger.info(f"Preview loaded: {len(preview_df)} rows, {len(preview_df.columns)} columns")

    def _on_preview_error(self, error_msg: str):
        """Handle preview error."""
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("Refresh")

        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)

        logger.error(f"Preview error: {error_msg}")

    def _update_preview_table(self):
        """Update preview table with data."""
        if self._preview_df is None or self._preview_df.empty:
            return

        rows, cols = self._preview_df.shape
        self.preview_table.setRowCount(rows)
        self.preview_table.setColumnCount(cols)

        # Set headers
        column_names = [str(col) for col in self._preview_df.columns]
        self.preview_table.setHorizontalHeaderLabels(column_names)

        # Populate data
        for row in range(rows):
            for col in range(cols):
                try:
                    value = self._preview_df.iloc[row, col]
                    display_value = "" if pd.isna(value) else str(value)
                    item = QTableWidgetItem(display_value)
                    self.preview_table.setItem(row, col, item)
                except Exception as e:
                    item = QTableWidgetItem(f"Error: {str(e)}")
                    self.preview_table.setItem(row, col, item)

        # Auto-size columns
        self.preview_table.resizeColumnsToContents()

    def _on_prevalidation_status_changed(self, is_valid: bool, message: str):
        """Handle pre-validation status change."""
        logger.info(f"Pre-validation status: {'Valid' if is_valid else 'Invalid'} - {message}")
        self.dataSourceValidated.emit(is_valid, f"Pre-validation: {message}")

    def _on_proceed_requested(self, force: bool):
        """Handle proceed request."""
        if force:
            logger.info("User requested to proceed despite validation warnings/errors")
        else:
            logger.info("User requested to proceed with validation")

        self.proceedToValidation.emit(force)

    def clear_selection(self):
        """Clear selection."""
        self._current_file = ""
        self._preview_df = None

        self.file_display.setText("No file selected")
        self.file_display.setStyleSheet(f"""
            QLabel {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 8px 12px;
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                font-style: italic;
            }}
        """)

        self.clear_button.setVisible(False)
        self.refresh_button.setEnabled(False)

        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)

        # Clear pre-validation
        self.pre_validation_widget.clear_results()

        self.dataSourceChanged.emit("")

    def cleanup(self):
        """Clean up resources."""
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.stop()
            self._preview_worker.quit()
            self._preview_worker.wait()

        self.pre_validation_widget.cleanup()


def create_test_files():
    """Create test CSV files with different data types and quality issues."""
    temp_dir = Path(tempfile.mkdtemp())

    # 1. Employee data with validation issues
    employee_data = {
        'EmployeeID': ['E001', 'E002', 'E003', None, 'E005', 'E002'],  # Null and duplicate
        'Name': ['John Smith', 'Jane Doe', '', 'Alice Brown', 'David Lee', 'Sarah Wilson'],
        'Department': ['IT', 'HR', 'Finance', 'IT', 'HR', 'InvalidDept'],  # Invalid value
        'Salary': [75000, 65000, -5000, 72000, 68000, 150000],  # Negative value
        'HireDate': ['2020-01-15', '2019-05-20', 'invalid-date', '2018-11-30', '2022-03-01', '2021-07-15'],
        'Position': ['Developer', 'Manager', 'Analyst', 'Developer', None, 'Manager']  # Null value
    }

    employee_file = temp_dir / "employee_data.csv"
    pd.DataFrame(employee_data).to_csv(employee_file, index=False)

    # 2. Financial data with issues
    financial_data = {
        'TransactionID': ['T001', 'T002', 'T003', 'T004', 'T005'],
        'Amount': [1000.50, -250.75, 0, 999999.99, None],  # Null value
        'Date': ['2023-01-15', '2023-01-16', 'invalid', '2023-01-18', '2023-01-19'],
        'Account': ['ACC001', 'ACC002', '', 'ACC001', 'ACC003'],  # Empty value
        'Type': ['Credit', 'Debit', 'Credit', 'InvalidType', 'Debit']  # Invalid type
    }

    financial_file = temp_dir / "financial_data.csv"
    pd.DataFrame(financial_data).to_csv(financial_file, index=False)

    # 3. Clean data for comparison
    clean_data = {
        'ID': ['1', '2', '3', '4', '5'],
        'Name': ['Item A', 'Item B', 'Item C', 'Item D', 'Item E'],
        'Value': [100, 200, 300, 400, 500],
        'Status': ['Active', 'Active', 'Inactive', 'Active', 'Active']
    }

    clean_file = temp_dir / "clean_data.csv"
    pd.DataFrame(clean_data).to_csv(clean_file, index=False)

    return {
        'employee': str(employee_file),
        'financial': str(financial_file),
        'clean': str(clean_file),
        'temp_dir': temp_dir
    }


class TestWindow(QMainWindow):
    """Test window for integrated data source panel."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Real Backend Integration Test: DataSourcePanel + PreValidation")
        self.setGeometry(100, 100, 1000, 800)

        # Apply stylesheet
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())

        # Create test files
        self.test_files = create_test_files()

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Add test file buttons
        self._create_test_buttons(layout)

        # Create integrated data source panel
        self.data_source_panel = IntegratedDataSourcePanel()
        layout.addWidget(self.data_source_panel)

        # Connect signals
        self.data_source_panel.dataSourceChanged.connect(self.on_data_source_changed)
        self.data_source_panel.dataSourceValidated.connect(self.on_data_source_validated)
        self.data_source_panel.proceedToValidation.connect(self.on_proceed_to_validation)

        print("Test window created with test files:")
        for name, path in self.test_files.items():
            if name != 'temp_dir':
                print(f"  {name}: {path}")

    def _create_test_buttons(self, layout):
        """Create buttons to load test files."""
        button_layout = QHBoxLayout()

        # Test file buttons
        employee_btn = QPushButton("Load Employee Data (Issues Expected)")
        employee_btn.clicked.connect(lambda: self._load_test_file('employee'))
        button_layout.addWidget(employee_btn)

        financial_btn = QPushButton("Load Financial Data (Issues Expected)")
        financial_btn.clicked.connect(lambda: self._load_test_file('financial'))
        button_layout.addWidget(financial_btn)

        clean_btn = QPushButton("Load Clean Data (Should Pass)")
        clean_btn.clicked.connect(lambda: self._load_test_file('clean'))
        button_layout.addWidget(clean_btn)

        layout.addLayout(button_layout)

    def _load_test_file(self, file_type):
        """Load a specific test file."""
        file_path = self.test_files[file_type]
        print(f"\n🔄 Loading {file_type} test file: {os.path.basename(file_path)}")
        self.data_source_panel._set_file(file_path)

    def on_data_source_changed(self, file_path):
        """Handle data source change."""
        print(f"📁 Data source changed: {os.path.basename(file_path) if file_path else 'None'}")

    def on_data_source_validated(self, is_valid, message):
        """Handle validation status change."""
        status = "✅ VALID" if is_valid else "❌ INVALID"
        print(f"🔍 Validation status: {status} - {message}")

    def on_proceed_to_validation(self, force):
        """Handle proceed to validation request."""
        if force:
            print("🚨 FORCE PROCEED - User wants to continue despite validation issues")
        else:
            print("✅ PROCEED - Validation passed, ready for full validation")


def main():
    """Main test function."""
    app = QApplication(sys.argv)

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Test backend imports
    print("\n🧪 Testing backend imports...")
    try:
        from data_integration.io.data_validator import DataValidator
        from data_integration.io.importer import DataImporter
        print("✅ Successfully imported DataValidator and DataImporter")

        # Test basic functionality
        validator = DataValidator()
        importer = DataImporter()
        print("✅ Successfully created validator and importer instances")

    except ImportError as e:
        print(f"❌ Backend import failed: {e}")
        print("Please ensure the data_integration module is in your Python path")
        return 1

    # Create test window
    window = TestWindow()
    window.show()

    print("\n" + "=" * 60)
    print("🧪 REAL BACKEND INTEGRATION TEST")
    print("=" * 60)
    print("1. Click test file buttons to load different data scenarios")
    print("2. Watch data preview load using real DataImporter")
    print("3. Observe pre-validation using real DataValidator")
    print("4. Check validation results for different data types")
    print("5. Test proceed/force proceed functionality")
    print("=" * 60)

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
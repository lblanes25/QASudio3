#!/usr/bin/env python3
"""
Test Script for Save Data Source Dialog
Tests the dialog functionality with sample data
"""

import sys
import os
import tempfile
import pandas as pd
from pathlib import Path

# Add the project root to the path so we can import our modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget, QLabel

# Import our components
from save_data_source_dialog import SaveDataSourceDialog
from data_source_registry import DataSourceRegistry
from analytics_runner_stylesheet import AnalyticsRunnerStylesheet


class TestWindow(QWidget):
    """Simple test window to demonstrate the save dialog."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Save Data Source Dialog Test")
        self.setGeometry(100, 100, 400, 200)
        
        # Create test data
        self.test_file_path, self.test_df = self._create_test_data()
        
        # Setup UI
        layout = QVBoxLayout(self)
        
        # Info label
        info_label = QLabel(f"Test file created: {os.path.basename(self.test_file_path)}")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Data info
        data_info = QLabel(f"Data: {len(self.test_df)} rows, {len(self.test_df.columns)} columns")
        layout.addWidget(data_info)
        
        # Test button
        test_button = QPushButton("Open Save Data Source Dialog")
        test_button.clicked.connect(self._open_save_dialog)
        layout.addWidget(test_button)
        
        # Registry info button
        registry_button = QPushButton("Show Registry Contents")
        registry_button.clicked.connect(self._show_registry)
        layout.addWidget(registry_button)
        
        # Apply stylesheet
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())
        
        # Initialize registry
        self.registry = DataSourceRegistry("test_registry.json")
    
    def _create_test_data(self):
        """Create a temporary test CSV file with sample data."""
        # Create sample data
        data = {
            'EmployeeID': ['E001', 'E002', 'E003', 'E004', 'E005'],
            'Name': ['John Smith', 'Jane Doe', 'Bob Johnson', 'Alice Brown', 'David Lee'],
            'Department': ['IT', 'HR', 'Finance', 'IT', 'HR'],
            'Salary': [75000, 65000, 85000, 72000, 68000],
            'HireDate': ['2020-01-15', '2019-05-20', '2021-02-10', '2018-11-30', '2022-03-01'],
            'Performance': [4.2, 3.8, 4.5, 4.1, 3.9]
        }
        
        df = pd.DataFrame(data)
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(temp_dir, "test_employee_data.csv")
        
        # Save to CSV
        df.to_csv(temp_file, index=False)
        
        print(f"Created test file: {temp_file}")
        return temp_file, df
    
    def _open_save_dialog(self):
        """Open the save data source dialog with test data."""
        try:
            dialog = SaveDataSourceDialog(
                file_path=self.test_file_path,
                sheet_name=None,  # CSV file, no sheet
                preview_df=self.test_df,
                registry=self.registry,
                parent=self
            )
            
            # Connect to success signal
            dialog.dataSourceSaved.connect(self._on_save_success)
            
            # Show dialog
            result = dialog.exec()
            
            if result == dialog.Accepted:
                print("Dialog accepted")
            else:
                print("Dialog cancelled")
                
        except Exception as e:
            print(f"Error opening dialog: {e}")
            import traceback
            traceback.print_exc()
    
    def _on_save_success(self, source_id: str):
        """Handle successful save."""
        print(f"Data source saved successfully with ID: {source_id}")
    
    def _show_registry(self):
        """Show current registry contents."""
        sources = self.registry.list_data_sources()
        print(f"\nRegistry contains {len(sources)} data sources:")
        
        for source in sources:
            print(f"  - {source.name} ({source.source_type.value}) - {source.file_path}")
        
        if not sources:
            print("  (No data sources registered)")
    
    def closeEvent(self, event):
        """Clean up on close."""
        # Clean up test file
        try:
            if os.path.exists(self.test_file_path):
                os.remove(self.test_file_path)
                print(f"Cleaned up test file: {self.test_file_path}")
        except Exception as e:
            print(f"Error cleaning up test file: {e}")
        
        super().closeEvent(event)


def test_save_dialog():
    """Test the save data source dialog."""
    app = QApplication(sys.argv)
    
    # Create test window
    window = TestWindow()
    window.show()
    
    # Run application
    return app.exec()


if __name__ == "__main__":
    print("Testing Save Data Source Dialog...")
    print("=" * 50)
    
    # Run test
    exit_code = test_save_dialog()
    
    print("=" * 50)
    print("Test completed")
    
    sys.exit(exit_code)

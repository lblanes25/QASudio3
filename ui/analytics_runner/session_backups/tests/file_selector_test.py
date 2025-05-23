#!/usr/bin/env python3
"""
Test application for FileSelectorWidget
"""

import sys
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, 
    QLabel, QTextEdit, QPushButton, QHBoxLayout
)
from PySide6.QtCore import Qt

# Add parent directory to path for imports (development testing)
sys.path.insert(0, str(Path(__file__).parent))

from file_selector_widget import FileSelectorWidget
from analytics_runner_stylesheet import AnalyticsRunnerStylesheet


class FileSelectorTestWindow(QMainWindow):
    """Test window for FileSelectorWidget."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FileSelectorWidget Test")
        self.setMinimumSize(600, 500)
        
        # Apply global stylesheet
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("FileSelectorWidget Test")
        title.setFont(AnalyticsRunnerStylesheet.get_fonts()['title'])
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Test 1: Basic CSV file selector
        self.csv_selector = FileSelectorWidget(
            title="CSV Data Files",
            file_filters="CSV Files (*.csv);;All Files (*)",
            accepted_extensions=['.csv'],
            validation_callback=self.validate_csv_file
        )
        self.csv_selector.fileSelected.connect(self.on_csv_file_selected)
        layout.addWidget(self.csv_selector)
        
        # Test 2: Excel file selector with recent files
        self.excel_selector = FileSelectorWidget(
            title="Excel Files",
            file_filters="Excel Files (*.xlsx *.xls);;All Files (*)",
            accepted_extensions=['.xlsx', '.xls'],
            show_recent_files=True,
            max_recent_files=3
        )
        self.excel_selector.fileSelected.connect(self.on_excel_file_selected)
        layout.addWidget(self.excel_selector)
        
        # Log area
        log_label = QLabel("Event Log:")
        log_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        layout.addWidget(log_label)
        
        self.log_area = QTextEdit()
        self.log_area.setMaximumHeight(150)
        self.log_area.setFont(AnalyticsRunnerStylesheet.get_fonts()['mono'])
        layout.addWidget(self.log_area)
        
        # Control buttons
        button_layout = QHBoxLayout()
        
        clear_button = QPushButton("Clear All")
        clear_button.clicked.connect(self.clear_all)
        button_layout.addWidget(clear_button)
        
        test_button = QPushButton("Add Test Recent Files")
        test_button.clicked.connect(self.add_test_recent_files)
        button_layout.addWidget(test_button)
        
        layout.addLayout(button_layout)
        
        self.log("FileSelectorWidget test application started")
    
    def validate_csv_file(self, file_path: str) -> tuple[bool, str]:
        """Custom validation for CSV files."""
        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size == 0:
                return False, "File is empty"
            
            if file_size > 100 * 1024 * 1024:  # 100MB limit
                return False, "File is too large (>100MB)"
            
            # Try to read first few bytes to check if it looks like CSV
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                first_line = f.readline().strip()
                if not first_line:
                    return False, "File appears to be empty"
                
                # Simple check for CSV-like content
                if ',' in first_line or '\t' in first_line:
                    return True, f"Valid CSV file ({file_size:,} bytes)"
                else:
                    return False, "File doesn't appear to contain CSV data"
                    
        except Exception as e:
            return False, f"Error reading file: {str(e)}"
    
    def on_csv_file_selected(self, file_path: str):
        """Handle CSV file selection."""
        self.log(f"CSV file selected: {os.path.basename(file_path)}")
        is_valid, message = self.csv_selector.validation_status
        self.log(f"  Validation: {message}")
    
    def on_excel_file_selected(self, file_path: str):
        """Handle Excel file selection."""
        self.log(f"Excel file selected: {os.path.basename(file_path)}")
        is_valid, message = self.excel_selector.validation_status
        self.log(f"  Validation: {message}")
    
    def clear_all(self):
        """Clear all file selections."""
        self.csv_selector.clear_selection()
        self.excel_selector.clear_selection()
        self.log("All selections cleared")
    
    def add_test_recent_files(self):
        """Add some test recent files (for demo purposes)."""
        # Create some dummy recent files for testing
        test_files = [
            "C:/Users/test/Documents/data.csv",
            "C:/Users/test/Downloads/report.xlsx", 
            "C:/Projects/analytics/sample.csv"
        ]
        
        # Only add files that actually exist for the demo
        existing_files = [f for f in test_files if os.path.exists(f)]
        
        if existing_files:
            self.excel_selector.set_recent_files(existing_files)
            self.log(f"Added {len(existing_files)} test recent files")
        else:
            # If no test files exist, create a demo with current directory files
            current_dir = Path.cwd()
            py_files = list(current_dir.glob("*.py"))[:3]
            if py_files:
                self.excel_selector.set_recent_files([str(f) for f in py_files])
                self.log(f"Added {len(py_files)} Python files as demo recent files")
            else:
                self.log("No suitable files found for demo")
    
    def log(self, message: str):
        """Add a message to the log area."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")


def main():
    """Run the test application."""
    app = QApplication(sys.argv)
    
    window = FileSelectorTestWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

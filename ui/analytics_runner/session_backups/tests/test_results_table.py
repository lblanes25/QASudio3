#!/usr/bin/env python3
"""
Test script for ResultsTableWidget
"""

import sys
import random
from datetime import datetime, timedelta

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from results_table_widget import ResultsTableWidget
from analytics_runner_stylesheet import AnalyticsRunnerStylesheet


def generate_test_data(num_rows: int = 100):
    """Generate test data for the table."""
    statuses = ['GC', 'PC', 'DNC']
    departments = ['IT', 'HR', 'Finance', 'Marketing', 'Operations']
    rule_types = ['Data Quality', 'Compliance', 'Completeness', 'Accuracy']
    
    data = []
    base_date = datetime.now() - timedelta(days=30)
    
    for i in range(num_rows):
        row = {
            'Rule ID': f'RULE_{i+1:03d}',
            'Rule Name': f'Test Rule {i+1}',
            'Status': random.choice(statuses),
            'Department': random.choice(departments),
            'Rule Type': random.choice(rule_types),
            'Compliance Rate': round(random.uniform(0.5, 1.0), 3),
            'Items Tested': random.randint(10, 1000),
            'Failures': random.randint(0, 50),
            'Last Run': (base_date + timedelta(days=random.randint(0, 30))).strftime('%Y-%m-%d'),
            'Severity': random.choice(['Critical', 'High', 'Medium', 'Low'])
        }
        data.append(row)
    
    return data


class TestWindow(QMainWindow):
    """Test window for ResultsTableWidget."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ResultsTableWidget Test")
        self.setGeometry(100, 100, 1200, 800)
        
        # Apply stylesheet
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())
        
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Layout
        layout = QVBoxLayout(central_widget)
        
        # Create table widget
        self.table_widget = ResultsTableWidget(
            show_search=True,
            show_column_filters=True,
            show_export_buttons=True,
            enable_context_menu=True,
            max_display_rows=1000
        )
        
        # Connect signals
        self.table_widget.rowSelected.connect(self.on_row_selected)
        self.table_widget.rowDoubleClicked.connect(self.on_row_double_clicked)
        self.table_widget.dataFiltered.connect(self.on_data_filtered)
        self.table_widget.exportCompleted.connect(self.on_export_completed)
        
        layout.addWidget(self.table_widget)
        
        # Load test data
        test_data = generate_test_data(500)  # 500 rows for testing
        self.table_widget.set_data(test_data)
        
        print(f"Loaded {len(test_data)} test rows")
    
    def on_row_selected(self, row_index: int, row_data: dict):
        """Handle row selection."""
        print(f"Row selected: {row_index} - {row_data.get('Rule Name', '')}")
    
    def on_row_double_clicked(self, row_index: int, row_data: dict):
        """Handle row double click."""
        print(f"Row double-clicked: {row_index} - {row_data.get('Rule Name', '')}")
    
    def on_data_filtered(self, filtered_count: int):
        """Handle data filtering."""
        print(f"Data filtered: {filtered_count} rows visible")
    
    def on_export_completed(self, file_path: str):
        """Handle export completion."""
        print(f"Export completed: {file_path}")


def main():
    """Main test function."""
    app = QApplication(sys.argv)
    app.setApplicationName("ResultsTableWidget Test")
    
    window = TestWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

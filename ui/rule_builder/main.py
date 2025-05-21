from PySide6.QtWidgets import QApplication
import sys
from main_window import RuleBuilderMainWindow

# !/usr/bin/env python3
"""
Rule Builder for Audit QA Framework

A PySide6-based UI for creating, editing, and testing validation rules
that integrates with the existing QA Analytics Framework.
"""

import sys
import os
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox

# Import our rule builder components
from main_window import RuleBuilderMainWindow


def main():
    # Configure application
    app = QApplication(sys.argv)
    app.setApplicationName("Rule Builder")
    app.setOrganizationName("Audit QA Framework")

    # Set application style
    app.setStyle("Fusion")

    # Determine rule manager path
    rule_manager_path = None
    if len(sys.argv) > 1:
        # Use path provided as command line argument
        rule_manager_path = sys.argv[1]
    else:
        # Try to find rules directory in common locations
        possible_paths = [
            "./rules",  # Current directory
            "../rules",  # Parent directory
            os.path.expanduser("~/rules"),  # Home directory
        ]

        for path in possible_paths:
            if os.path.isdir(path):
                rule_manager_path = path
                break

    try:
        # Create main window
        window = RuleBuilderMainWindow(rule_manager_path)
        window.show()

        # Run application
        sys.exit(app.exec())

    except Exception as e:
        # Show error dialog for any uncaught exceptions
        error_text = f"An unexpected error occurred:\n\n{str(e)}\n\nTraceback has been printed to console."
        QMessageBox.critical(None, "Error", error_text)
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
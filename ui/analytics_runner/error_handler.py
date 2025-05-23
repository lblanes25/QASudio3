"""
Error Handler for Analytics Runner
Provides centralized error handling, user-friendly dialogs, and debug support
"""

import sys
import traceback
import logging
import datetime
from pathlib import Path
from typing import Optional, Dict, Any, Callable
from enum import Enum

from PySide6.QtWidgets import (
    QMessageBox, QDialog, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QCheckBox, QApplication
)
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QFont, QIcon

from analytics_runner_stylesheet import AnalyticsRunnerStylesheet


class ErrorSeverity(Enum):
    """Error severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DetailedErrorDialog(QDialog):
    """Dialog for showing detailed error information with option to report"""

    def __init__(self, error_info: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.error_info = error_info
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("Error Details")
        self.setModal(True)
        self.resize(600, 400)

        layout = QVBoxLayout(self)

        # Error summary
        summary_label = QLabel(self.error_info.get('user_message', 'An error occurred'))
        summary_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        summary_label.setWordWrap(True)
        layout.addWidget(summary_label)

        # Technical details (collapsible)
        details_text = QTextEdit()
        details_text.setFont(AnalyticsRunnerStylesheet.get_fonts()['mono'])
        details_text.setPlainText(self.error_info.get('technical_details', ''))
        details_text.setReadOnly(True)
        layout.addWidget(details_text)

        # Buttons
        button_layout = QHBoxLayout()

        copy_button = QPushButton("Copy Details")
        copy_button.clicked.connect(self.copy_details)
        button_layout.addWidget(copy_button)

        button_layout.addStretch()

        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

        # Apply styling
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())

    def copy_details(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.error_info.get('technical_details', ''))


class ErrorHandler(QObject):
    """
    Centralized error handling system for Analytics Runner.

    Features:
    - Global exception handling
    - User-friendly error messages
    - Debug mode controls
    - Error logging and reporting
    """

    # Signals
    errorOccurred = Signal(dict)  # Emitted when an error occurs
    debugModeChanged = Signal(bool)  # Emitted when debug mode changes

    def __init__(self, app_name: str = "Analytics Runner"):
        super().__init__()
        self.app_name = app_name
        self.debug_mode = False
        self.error_log_path = Path("logs")
        self.error_log_path.mkdir(exist_ok=True)

        # Error message mappings
        self.error_messages = {
            FileNotFoundError: "The requested file could not be found.",
            PermissionError: "Permission denied. Please check file permissions.",
            ConnectionError: "Could not connect to the specified resource.",
            ImportError: "A required component is missing or could not be loaded.",
            ValueError: "Invalid data or configuration was provided.",
            MemoryError: "Not enough memory to complete the operation.",
            OSError: "A system error occurred.",
        }

        # Setup logging
        self.setup_logging()

        # Install global exception handler
        sys.excepthook = self.handle_exception

        self.logger = logging.getLogger(__name__)
        self.logger.info("Error handler initialized")

    def setup_logging(self):
        """Setup enhanced logging configuration"""
        # Create logs directory
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)

        # Clear existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # File handler for all logs
        log_file = log_dir / f"{self.app_name.lower().replace(' ', '_')}.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # Error file handler for errors and above
        error_file = log_dir / f"{self.app_name.lower().replace(' ', '_')}_errors.log"
        error_handler = logging.FileHandler(error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        root_logger.addHandler(error_handler)

        # Console handler for debug mode
        if self.debug_mode:
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(levelname)s - %(name)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            root_logger.addHandler(console_handler)

    def set_debug_mode(self, enabled: bool):
        """Enable or disable debug mode"""
        if self.debug_mode != enabled:
            self.debug_mode = enabled
            self.setup_logging()  # Reconfigure logging
            self.debugModeChanged.emit(enabled)

            level = "DEBUG" if enabled else "INFO"
            self.logger.info(f"Debug mode {'enabled' if enabled else 'disabled'} - Log level: {level}")

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """Global exception handler"""
        if issubclass(exc_type, KeyboardInterrupt):
            # Handle Ctrl+C gracefully
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        # Create error info
        error_info = self.create_error_info(exc_type, exc_value, exc_traceback)

        # Log the error
        self.log_error(error_info)

        # Show user dialog
        self.show_error_dialog(error_info)

        # Emit signal
        self.errorOccurred.emit(error_info)

    def create_error_info(self, exc_type, exc_value, exc_traceback) -> Dict[str, Any]:
        """Create structured error information"""
        # Get user-friendly message
        user_message = self.error_messages.get(exc_type, str(exc_value))

        # Get technical details
        technical_details = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))

        # Determine severity
        severity = ErrorSeverity.CRITICAL
        if exc_type in [FileNotFoundError, ValueError]:
            severity = ErrorSeverity.ERROR
        elif exc_type in [ImportError, ConnectionError]:
            severity = ErrorSeverity.WARNING

        return {
            'timestamp': datetime.datetime.now().isoformat(),
            'exception_type': exc_type.__name__,
            'user_message': user_message,
            'technical_message': str(exc_value),
            'technical_details': technical_details,
            'severity': severity,
            'debug_mode': self.debug_mode
        }

    def log_error(self, error_info: Dict[str, Any]):
        """Log error information"""
        severity = error_info['severity']
        message = f"{error_info['exception_type']}: {error_info['technical_message']}"

        if severity == ErrorSeverity.CRITICAL:
            self.logger.critical(message)
        elif severity == ErrorSeverity.ERROR:
            self.logger.error(message)
        elif severity == ErrorSeverity.WARNING:
            self.logger.warning(message)
        else:
            self.logger.info(message)

        # Log technical details in debug mode
        if self.debug_mode:
            self.logger.debug(f"Technical details:\n{error_info['technical_details']}")

    def show_error_dialog(self, error_info: Dict[str, Any]):
        """Show user-friendly error dialog"""
        try:
            app = QApplication.instance()
            if not app:
                return

            severity = error_info['severity']

            # Choose appropriate icon
            if severity == ErrorSeverity.CRITICAL:
                icon = QMessageBox.Critical
            elif severity == ErrorSeverity.ERROR:
                icon = QMessageBox.Warning
            else:
                icon = QMessageBox.Information

            # Create message box
            msg_box = QMessageBox()
            msg_box.setIcon(icon)
            msg_box.setWindowTitle(f"{self.app_name} - Error")
            msg_box.setText(error_info['user_message'])

            # Add details button in debug mode
            if self.debug_mode:
                msg_box.setDetailedText(error_info['technical_details'])
                msg_box.addButton("Show Details", QMessageBox.ActionRole)

            msg_box.setStandardButtons(QMessageBox.Ok)
            msg_box.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())

            msg_box.exec()

        except Exception as e:
            # Fallback error handling
            print(f"Error showing error dialog: {e}")
            print(f"Original error: {error_info['technical_message']}")

    def report_error(self,
                     exception: Exception,
                     context: str = "",
                     severity: ErrorSeverity = ErrorSeverity.ERROR,
                     show_dialog: bool = True):
        """Manually report an error"""
        error_info = {
            'timestamp': datetime.datetime.now().isoformat(),
            'exception_type': type(exception).__name__,
            'user_message': self.error_messages.get(type(exception), str(exception)),
            'technical_message': str(exception),
            'technical_details': f"Context: {context}\n\n{traceback.format_exc()}",
            'severity': severity,
            'debug_mode': self.debug_mode
        }

        self.log_error(error_info)

        if show_dialog:
            self.show_error_dialog(error_info)

        self.errorOccurred.emit(error_info)

    def report_warning(self, message: str, details: str = ""):
        """Report a warning message"""
        warning_info = {
            'timestamp': datetime.datetime.now().isoformat(),
            'exception_type': 'Warning',
            'user_message': message,
            'technical_message': message,
            'technical_details': details,
            'severity': ErrorSeverity.WARNING,
            'debug_mode': self.debug_mode
        }

        self.log_error(warning_info)
        self.errorOccurred.emit(warning_info)

    def report_info(self, message: str, details: str = ""):
        """Report an informational message"""
        info = {
            'timestamp': datetime.datetime.now().isoformat(),
            'exception_type': 'Info',
            'user_message': message,
            'technical_message': message,
            'technical_details': details,
            'severity': ErrorSeverity.INFO,
            'debug_mode': self.debug_mode
        }

        self.log_error(info)
        self.errorOccurred.emit(info)


# Global error handler instance
_global_error_handler: Optional[ErrorHandler] = None


def initialize_error_handler(app_name: str = "Analytics Runner") -> ErrorHandler:
    """Initialize the global error handler"""
    global _global_error_handler
    _global_error_handler = ErrorHandler(app_name)
    return _global_error_handler


def get_error_handler() -> Optional[ErrorHandler]:
    """Get the global error handler instance"""
    return _global_error_handler


def report_error(exception: Exception, context: str = "", show_dialog: bool = True):
    """Convenience function to report errors"""
    if _global_error_handler:
        _global_error_handler.report_error(exception, context, show_dialog=show_dialog)


def report_warning(message: str, details: str = ""):
    """Convenience function to report warnings"""
    if _global_error_handler:
        _global_error_handler.report_warning(message, details)


def set_debug_mode(enabled: bool):
    """Convenience function to set debug mode"""
    if _global_error_handler:
        _global_error_handler.set_debug_mode(enabled)
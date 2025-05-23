#!/usr/bin/env python3
"""
Analytics Runner - Main Application
QA Analytics Framework GUI Application
"""

import sys
import os
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QSplitter, QTabWidget, QStatusBar, QMenuBar,
    QToolBar, QTextEdit, QLabel, QPushButton, QProgressBar,
    QMessageBox, QFileDialog, QCheckBox
)
from PySide6.QtCore import Qt, QSettings, QTimer, QThreadPool
from PySide6.QtGui import QAction, QIcon, QFont

# Import our components
from session_manager import SessionManager
from analytics_runner_stylesheet import AnalyticsRunnerStylesheet
from error_handler import initialize_error_handler, get_error_handler, set_debug_mode
from debug_panel import DebugPanel
from data_source_panel import DataSourcePanel

# Configure basic logging (will be enhanced by error handler)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AnalyticsRunnerApp(QMainWindow):
    """
    Main application window for the Analytics Runner.

    Provides the shell for data validation workflows with:
    - Menu system and toolbar
    - Multi-tab interface for different modes
    - Splitter layout for main content and results
    - Status bar with progress indication
    - Session state management
    - Centralized error handling and debug support
    """

    def __init__(self):
        super().__init__()

        # Initialize error handler first
        self.error_handler = initialize_error_handler("Analytics Runner")

        # Initialize core systems
        self.session = SessionManager()
        self.threadpool = QThreadPool()

        # Set maximum thread count to prevent resource exhaustion
        self.threadpool.setMaxThreadCount(4)

        # Debug panel (initially None)
        self.debug_panel = None

        try:
            # Initialize UI
            self.init_ui()
            self.restore_state()

            # Initialize backend connections (placeholder for now)
            self.init_backend()

            # Setup error handler connections
            self.setup_error_handler()

            logger.info("Analytics Runner application initialized successfully")

        except Exception as e:
            # Use error handler if available, otherwise fall back
            if self.error_handler:
                self.error_handler.report_error(e, "Application initialization")
            else:
                logger.critical(f"Failed to initialize application: {e}")
                raise

    def init_ui(self):
        """Initialize the user interface components."""
        self.setWindowTitle("Analytics Runner - QA Analytics Framework")
        self.setMinimumSize(1200, 800)

        # Apply global stylesheet
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())

        # Create central widget with splitter layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)

        # Create main splitter (horizontal)
        self.main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(self.main_splitter)

        # Left panel - Main workflow area
        self.create_main_panel()

        # Right panel - Results and logs
        self.create_results_panel()

        # Set initial splitter proportions (60% main, 40% results)
        self.main_splitter.setSizes([600, 400])

        # Create menu bar
        self.create_menu_bar()

        # Create toolbar
        self.create_toolbar()

        # Create status bar
        self.create_status_bar()

    def create_main_panel(self):
        """Create the main workflow panel with tabs."""
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)

        # Create tab widget for different modes
        self.mode_tabs = QTabWidget()
        self.main_layout.addWidget(self.mode_tabs)

        # Simple Mode tab (updated)
        self.create_simple_mode_tab()

        # Advanced Mode tab (unchanged)
        self.create_advanced_mode_tab()

        # Add main widget to splitter
        self.main_splitter.addWidget(self.main_widget)

    def create_simple_mode_tab(self):
        """Create the simple mode tab with DataSourcePanel integration."""
        self.simple_mode_widget = QWidget()
        simple_layout = QVBoxLayout(self.simple_mode_widget)
        simple_layout.setSpacing(AnalyticsRunnerStylesheet.SECTION_SPACING)
        simple_layout.setContentsMargins(24, 24, 24, 24)

        # Title section
        title_container = QWidget()
        title_layout = QVBoxLayout(title_container)
        title_layout.setSpacing(8)

        # Main title
        simple_label = QLabel("Simple Validation Mode")
        simple_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['title'])
        simple_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
                padding: 0px;
                border: none;
                margin-bottom: 8px;
            }}
        """)
        simple_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(simple_label)

        # Subtitle
        subtitle_label = QLabel("Quick validation with default settings")
        subtitle_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        subtitle_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                padding: 0px;
                border: none;
            }}
        """)
        subtitle_label.setAlignment(Qt.AlignCenter)
        title_layout.addWidget(subtitle_label)

        simple_layout.addWidget(title_container)

        # REPLACE: Enhanced data source section with DataSourcePanel
        self.data_source_panel = DataSourcePanel(session_manager=self.session)

        # Connect data source panel signals to main application methods
        self.data_source_panel.dataSourceChanged.connect(self._on_data_source_changed)
        self.data_source_panel.dataSourceValidated.connect(self._on_data_source_validated)
        self.data_source_panel.previewUpdated.connect(self._on_data_preview_updated)

        simple_layout.addWidget(self.data_source_panel)

        # Start validation section
        validation_section = QWidget()
        validation_layout = QVBoxLayout(validation_section)

        # Add some basic controls
        self.start_button = QPushButton("Start Validation")
        self.start_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        self.start_button.setEnabled(False)  # Disabled until data source selected
        self.start_button.clicked.connect(self.start_validation)
        self.start_button.setMinimumHeight(48)
        validation_layout.addWidget(self.start_button)

        simple_layout.addWidget(validation_section)
        simple_layout.addStretch()
        self.mode_tabs.addTab(self.simple_mode_widget, "Simple Mode")

    def create_advanced_mode_tab(self):
        """Create the advanced mode tab"""
        self.advanced_mode_widget = QWidget()
        advanced_layout = QVBoxLayout(self.advanced_mode_widget)
        advanced_layout.setSpacing(AnalyticsRunnerStylesheet.SECTION_SPACING)
        advanced_layout.setContentsMargins(24, 24, 24, 24)

        # Advanced mode title
        advanced_label = QLabel("Advanced Validation Mode")
        advanced_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['title'])
        advanced_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
                padding: 0px;
                border: none;
                margin-bottom: 8px;
            }}
        """)
        advanced_label.setAlignment(Qt.AlignCenter)
        advanced_layout.addWidget(advanced_label)

        # Advanced mode subtitle
        advanced_subtitle = QLabel("Full control over validation settings and rule selection")
        advanced_subtitle.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        advanced_subtitle.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                padding: 0px;
                border: none;
            }}
        """)
        advanced_subtitle.setAlignment(Qt.AlignCenter)
        advanced_layout.addWidget(advanced_subtitle)

        # Placeholder for advanced controls
        advanced_placeholder = QLabel("Advanced controls will be implemented in Phase 3")
        advanced_placeholder.setAlignment(Qt.AlignCenter)
        advanced_placeholder.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                font-style: italic;
                padding: 40px;
                border: 2px dashed {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 8px;
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            }}
        """)
        advanced_layout.addWidget(advanced_placeholder)

        advanced_layout.addStretch()

        self.mode_tabs.addTab(self.advanced_mode_widget, "Advanced Mode")

    def create_results_panel(self):
        """Create the results and logging panel."""
        self.results_widget = QWidget()
        results_layout = QVBoxLayout(self.results_widget)
        results_layout.setContentsMargins(12, 12, 12, 12)
        results_layout.setSpacing(8)

        # Results panel header
        results_header = QLabel("Results & Logs")
        results_header.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        results_header.setStyleSheet(AnalyticsRunnerStylesheet.get_header_stylesheet())
        results_layout.addWidget(results_header)

        # Create tab widget for results views
        self.results_tabs = QTabWidget()
        results_layout.addWidget(self.results_tabs)

        # Results tab
        self.results_view = QTextEdit()
        self.results_view.setReadOnly(True)
        self.results_view.setPlaceholderText("Validation results will appear here...")
        self.results_view.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.results_tabs.addTab(self.results_view, "Results")

        # Log tab
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("Application logs will appear here...")
        self.log_view.setFont(AnalyticsRunnerStylesheet.get_fonts()['mono'])
        self.log_view.setStyleSheet(f"""
            QTextEdit {{
                background-color: {AnalyticsRunnerStylesheet.DARK_TEXT};
                color: #00FF00;
                font-family: 'Consolas', 'Courier New', monospace;
                border-radius: 6px;
            }}
        """)
        self.results_tabs.addTab(self.log_view, "Logs")

        # Add results widget to splitter
        self.main_splitter.addWidget(self.results_widget)

    def create_menu_bar(self):
        """Create the application menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        # New session
        new_action = QAction("&New Session", self)
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_session)
        file_menu.addAction(new_action)

        # Open data source
        open_action = QAction("&Open Data Source", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_data_source)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        # Recent files submenu
        self.recent_menu = file_menu.addMenu("Recent Files")
        self.update_recent_files_menu()

        file_menu.addSeparator()

        # Exit
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        # Toggle results panel
        toggle_results_action = QAction("Toggle Results Panel", self)
        toggle_results_action.setShortcut("F9")
        toggle_results_action.triggered.connect(self.toggle_results_panel)
        view_menu.addAction(toggle_results_action)

        view_menu.addSeparator()

        # Debug panel
        toggle_debug_action = QAction("Toggle Debug Panel", self)
        toggle_debug_action.setShortcut("F12")
        toggle_debug_action.triggered.connect(self.toggle_debug_panel)
        view_menu.addAction(toggle_debug_action)

        # Tools menu
        tools_menu = menubar.addMenu("&Tools")

        # Debug mode toggle
        self.debug_mode_action = QAction("Debug Mode", self)
        self.debug_mode_action.setCheckable(True)
        self.debug_mode_action.triggered.connect(self.toggle_debug_mode)
        tools_menu.addAction(self.debug_mode_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        """Create the application toolbar."""
        toolbar = self.addToolBar("Main")
        toolbar.setMovable(False)

        # Open data source
        open_data_action = QAction("Open Data", self)
        open_data_action.setToolTip("Open data source for validation")
        open_data_action.triggered.connect(self.open_data_source)
        toolbar.addAction(open_data_action)

        toolbar.addSeparator()

        # Start validation
        self.start_validation_action = QAction("Start Validation", self)
        self.start_validation_action.setToolTip("Start validation process")
        self.start_validation_action.setEnabled(False)
        self.start_validation_action.triggered.connect(self.start_validation)
        toolbar.addAction(self.start_validation_action)

        # Stop validation
        self.stop_validation_action = QAction("Stop Validation", self)
        self.stop_validation_action.setToolTip("Stop validation process")
        self.stop_validation_action.setEnabled(False)
        self.stop_validation_action.triggered.connect(self.stop_validation)
        toolbar.addAction(self.stop_validation_action)

        toolbar.addSeparator()

        # Debug mode checkbox in toolbar
        self.debug_checkbox = QCheckBox("Debug")
        self.debug_checkbox.setToolTip("Toggle debug mode")
        self.debug_checkbox.toggled.connect(self.toggle_debug_mode)
        toolbar.addWidget(self.debug_checkbox)

    def create_status_bar(self):
        """Create the application status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Status label
        self.status_label = QLabel("Ready")
        self.status_bar.addWidget(self.status_label)

        # Progress bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(200)
        self.status_bar.addPermanentWidget(self.progress_bar)

        # Thread count indicator
        self.thread_label = QLabel(f"Threads: 0/{self.threadpool.maxThreadCount()}")
        self.status_bar.addPermanentWidget(self.thread_label)

        # Update thread count periodically
        self.thread_timer = QTimer()
        self.thread_timer.timeout.connect(self.update_thread_count)
        self.thread_timer.start(1000)  # Update every second

    def setup_error_handler(self):
        """Setup error handler connections"""
        if self.error_handler:
            # Connect error signals to UI updates
            self.error_handler.errorOccurred.connect(self.on_error_occurred)
            self.error_handler.debugModeChanged.connect(self.on_debug_mode_changed)

            # Sync initial debug mode state
            self.debug_checkbox.setChecked(self.error_handler.debug_mode)
            self.debug_mode_action.setChecked(self.error_handler.debug_mode)

    def init_backend(self):
        """Initialize backend connections."""
        # Placeholder for backend initialization
        # This will be expanded in Phase 2
        self.data_source_path = None
        self.validation_pipeline = None

        self.log_message("Backend systems initialized")

    def restore_state(self):
        """Restore application state from previous session."""
        # Restore window geometry
        geometry = self.session.get('window_geometry')
        if geometry:
            self.restoreGeometry(geometry)
        else:
            # Default size and center on screen
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - 1200) // 2
            y = (screen.height() - 800) // 2
            self.setGeometry(x, y, 1200, 800)

        # Restore splitter position
        splitter_state = self.session.get('splitter_state')
        if splitter_state:
            self.main_splitter.restoreState(splitter_state)

        # Restore active tab
        active_mode = self.session.get('active_mode', 0)
        self.mode_tabs.setCurrentIndex(active_mode)

        self.log_message("Application state restored")

    def save_state(self):
        """Save application state for next session."""
        self.session.set('window_geometry', self.saveGeometry())
        self.session.set('splitter_state', self.main_splitter.saveState())
        self.session.set('active_mode', self.mode_tabs.currentIndex())

        self.log_message("Application state saved")

    def update_recent_files_menu(self):
        """Update the recent files menu."""
        self.recent_menu.clear()

        recent_files = self.session.get('recent_files', [])
        if not recent_files:
            no_recent_action = QAction("No recent files", self)
            no_recent_action.setEnabled(False)
            self.recent_menu.addAction(no_recent_action)
        else:
            for file_path in recent_files:
                if os.path.exists(file_path):
                    action = QAction(os.path.basename(file_path), self)
                    action.setData(file_path)
                    action.setToolTip(file_path)
                    action.triggered.connect(self.load_recent_file)
                    self.recent_menu.addAction(action)

    def update_thread_count(self):
        """Update the thread count display."""
        active_threads = self.threadpool.activeThreadCount()
        max_threads = self.threadpool.maxThreadCount()
        self.thread_label.setText(f"Threads: {active_threads}/{max_threads}")

    def log_message(self, message: str, level: str = "INFO"):
        """Add a message to the log view."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        formatted_message = f"[{timestamp}] {level}: {message}"

        self.log_view.append(formatted_message)

        # Also log to file
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)

    def show_progress(self, visible: bool = True):
        """Show or hide the progress bar."""
        self.progress_bar.setVisible(visible)
        if not visible:
            self.progress_bar.setValue(0)

    def update_progress(self, value: int, message: str = ""):
        """Update progress bar and status message."""
        self.progress_bar.setValue(value)
        if message:
            self.status_label.setText(message)

    # Add new signal handler methods for DataSourcePanel
    def _on_data_source_changed(self, file_path: str):
        """Handle data source file change."""
        self.log_message(f"Data source changed: {os.path.basename(file_path)}")

        # Update the data_source_path attribute
        self.data_source_path = file_path

        # Update UI state
        is_valid = self.data_source_panel.is_valid()
        self.start_button.setEnabled(is_valid)
        self.start_validation_action.setEnabled(is_valid)

        # Update status bar
        if file_path:
            self.status_label.setText(f"Data source: {os.path.basename(file_path)}")
        else:
            self.status_label.setText("No data source selected")

    def _on_data_source_validated(self, is_valid: bool, message: str):
        """Handle data source validation status change."""
        if is_valid:
            self.log_message(f"Data source validation: {message}")
        else:
            self.log_message(f"Data source validation failed: {message}", "WARNING")

        # Update UI state
        self.start_button.setEnabled(is_valid)
        self.start_validation_action.setEnabled(is_valid)

    def _on_data_preview_updated(self, preview_df):
        """Handle data preview update."""
        if preview_df is not None and not preview_df.empty:
            rows, cols = preview_df.shape
            self.log_message(f"Data preview loaded: {rows} rows, {cols} columns")

            # Show preview summary in results view
            summary_text = f"Data Preview Summary:\n"
            summary_text += f"Rows: {rows}\n"
            summary_text += f"Columns: {cols}\n"
            summary_text += f"Column names: {', '.join(preview_df.columns[:10])}"
            if cols > 10:
                summary_text += f" (+ {cols - 10} more)"

            self.results_view.setPlainText(summary_text)
        else:
            self.log_message("Data preview cleared", "INFO")

    # Slot methods for menu actions
    def new_session(self):
        """Start a new session."""
        self.log_message("Starting new session")
        # Clear current state
        self.data_source_path = None
        self.results_view.clear()
        self.start_button.setEnabled(False)
        self.start_validation_action.setEnabled(False)
        self.status_label.setText("Ready - New session")

    def open_data_source(self):
        """Open a data source file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Data Source",
            self.session.get('last_data_directory', ''),
            "Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if file_path:
            self.load_data_source(file_path)

    def load_data_source(self, file_path: str):
        """Load a data source file."""
        self.log_message(f"Loading data source: {os.path.basename(file_path)}")

        # Update session
        self.session.add_recent_file(file_path)
        self.session.set('last_data_directory', os.path.dirname(file_path))
        self.update_recent_files_menu()

        # Store data source path
        self.data_source_path = file_path

        # Enable validation controls
        self.start_button.setEnabled(True)
        self.start_validation_action.setEnabled(True)

        # Update status
        self.status_label.setText(f"Data source loaded: {os.path.basename(file_path)}")

    def load_recent_file(self):
        """Load a recent file."""
        action = self.sender()
        if action:
            file_path = action.data()
            self.load_data_source(file_path)

    def start_validation(self):
        """Start the validation process."""
        # Get data source from panel
        data_source_file = self.data_source_panel.get_current_file()

        if not data_source_file:
            QMessageBox.warning(self, "No Data Source", "Please select a data source first.")
            return

        if not self.data_source_panel.is_valid():
            QMessageBox.warning(self, "Invalid Data Source", "The selected data source is not valid.")
            return

        self.log_message("Starting validation process")

        # Get sheet name for Excel files
        sheet_name = self.data_source_panel.get_current_sheet()
        if sheet_name:
            self.log_message(f"Using Excel sheet: {sheet_name}")

        # Update UI state
        self.start_button.setEnabled(False)
        self.start_validation_action.setEnabled(False)
        self.stop_validation_action.setEnabled(True)
        self.show_progress(True)
        self.update_progress(0, "Initializing validation...")

        # TODO: In Phase 4, we'll implement the actual validation worker here
        # For now, just simulate a process
        QTimer.singleShot(2000, self.validation_complete)

    def stop_validation(self):
        """Stop the validation process."""
        self.log_message("Stopping validation process")

        # TODO: Implement actual cancellation in Phase 4
        self.validation_complete()

    def validation_complete(self):
        """Handle validation completion."""
        self.log_message("Validation process completed")

        # Update UI state
        self.start_button.setEnabled(True)
        self.start_validation_action.setEnabled(True)
        self.stop_validation_action.setEnabled(False)
        self.show_progress(False)
        self.status_label.setText("Validation completed")

        # Show mock results
        self.results_view.setPlainText(
            "Validation Results:\n\nMock results - functionality will be implemented in later phases.")

    def toggle_results_panel(self):
        """Toggle visibility of the results panel."""
        if self.results_widget.isVisible():
            self.results_widget.hide()
        else:
            self.results_widget.show()

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Analytics Runner",
            "Analytics Runner v1.0\n\n"
            "QA Analytics Framework GUI Application\n\n"
            "Built with PySide6"
        )

    def closeEvent(self, event):
        """Handle application close event."""
        self.log_message("Application closing")

        # Clean up data source panel resources
        if hasattr(self, 'data_source_panel'):
            self.data_source_panel.cleanup()

        self.save_state()

        # Wait for active threads to complete
        if self.threadpool.activeThreadCount() > 0:
            reply = QMessageBox.question(
                self,
                "Active Operations",
                "There are active validation operations. Do you want to force close?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.No:
                event.ignore()
                return

        # Clean shutdown
        self.threadpool.waitForDone(3000)  # Wait up to 3 seconds
        event.accept()

    def toggle_debug_mode(self, enabled: bool = None):
        """Toggle debug mode"""
        if enabled is None:
            enabled = self.debug_checkbox.isChecked()

        # Update UI controls
        self.debug_checkbox.setChecked(enabled)
        self.debug_mode_action.setChecked(enabled)

        # Update error handler
        if self.error_handler:
            self.error_handler.set_debug_mode(enabled)

        self.log_message(f"Debug mode {'enabled' if enabled else 'disabled'}")

    def toggle_debug_panel(self):
        """Toggle debug panel visibility"""
        if self.debug_panel is None:
            # Create debug panel
            self.debug_panel = DebugPanel()
            self.debug_panel.setWindowTitle("Debug Panel")
            self.debug_panel.resize(800, 600)

            # Connect signals
            self.debug_panel.debugModeChanged.connect(self.toggle_debug_mode)

        if self.debug_panel.isVisible():
            self.debug_panel.hide()
        else:
            self.debug_panel.show()
            self.debug_panel.raise_()

    def on_error_occurred(self, error_info: dict):
        """Handle error occurrence"""
        severity = error_info.get('severity')
        message = error_info.get('user_message', 'An error occurred')

        # Add to log view
        self.log_message(f"ERROR: {message}", "ERROR")

        # Update status bar briefly
        original_status = self.status_label.text()
        self.status_label.setText(f"Error: {message}")
        QTimer.singleShot(5000, lambda: self.status_label.setText(original_status))

    def on_debug_mode_changed(self, enabled: bool):
        """Handle debug mode change from error handler"""
        self.debug_checkbox.setChecked(enabled)
        self.debug_mode_action.setChecked(enabled)


def main():
    """Main application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName("Analytics Runner")
    app.setApplicationVersion("1.0")
    app.setOrganizationName("QA Analytics Framework")

    # Set application icon (if available)
    # app.setWindowIcon(QIcon("icon.png"))

    # Create and show main window
    window = AnalyticsRunnerApp()
    window.show()

    # Start event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
#!/usr/bin/env python3
"""
Analytics Runner - Main Application
QA Analytics Framework GUI Application
"""

import sys
import os
import logging
import datetime
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QSplitter, QTabWidget, QStatusBar, QMenuBar,
    QToolBar, QTextEdit, QLabel, QPushButton, QProgressBar,
    QMessageBox, QFileDialog, QCheckBox, QScrollArea
)
from PySide6.QtCore import Qt, QTimer, QThreadPool, QObject, QRunnable, Signal
from PySide6.QtGui import QAction, QIcon, QFont

# Import our components
from ui.common.session_manager import SessionManager
from ui.common.stylesheet import AnalyticsRunnerStylesheet
from ui.common.error_handler import initialize_error_handler, get_error_handler, set_debug_mode
from ui.analytics_runner.dialogs.debug_panel import DebugPanel
from data_source_panel import DataSourcePanel
from data_source_registry import DataSourceRegistry
from ui.analytics_runner.dialogs.save_data_source_dialog import SaveDataSourceDialog
from rule_selector_panel import RuleSelectorPanel

# Configure basic logging (will be enhanced by error handler)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ValidationWorkerSignals(QObject):
    """Signals for ValidationWorker"""
    started = Signal()
    finished = Signal()
    error = Signal(str)
    result = Signal(dict)
    progress = Signal(int, str)


class ValidationWorker(QRunnable):
    """Worker thread for running validation operations"""

    def __init__(self, pipeline, data_source: str, sheet_name: str = None,
                 analytic_id: str = None, rule_ids: List[str] = None):
        super().__init__()
        self.pipeline = pipeline
        self.data_source = data_source
        self.sheet_name = sheet_name
        self.analytic_id = analytic_id or "Simple_Validation"
        self.rule_ids = rule_ids  # Add rule_ids parameter
        self.signals = ValidationWorkerSignals()

    def run(self):
        """Run the validation process."""
        try:
            self.signals.started.emit()

            # Prepare validation parameters
            validation_params = {
                'data_source': self.data_source,
                'analytic_id': self.analytic_id,
                'output_formats': ['json', 'excel'],
                'use_parallel': False
            }

            # Add rule_ids if specified
            if self.rule_ids:
                validation_params['rule_ids'] = self.rule_ids

            # Add sheet name for Excel files
            if self.sheet_name:
                validation_params['data_source_params'] = {'sheet_name': self.sheet_name}

            self.signals.progress.emit(25, "Preparing validation...")

            # Import here to avoid circular imports
            from services.validation_service import ValidationPipeline

            # Create pipeline if not provided
            if not self.pipeline:
                self.pipeline = ValidationPipeline(output_dir='./output')

            # Run validation
            results = self.pipeline.validate_data_source(**validation_params)

            self.signals.progress.emit(90, "Processing results...")
            self.signals.result.emit(results)

        except Exception as e:
            import traceback
            error_msg = f"Validation error: {str(e)}\n{traceback.format_exc()}"
            self.signals.error.emit(error_msg)
        finally:
            self.signals.finished.emit()


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
    - Scrollable content areas for better screen compatibility
    """

    def __init__(self):
        super().__init__()

        # Initialize error handler first
        self.error_handler = initialize_error_handler("Analytics Runner")

        # Initialize core systems
        self.session = SessionManager()
        self.threadpool = QThreadPool()

        # Initialize data source registry
        self.data_source_registry = DataSourceRegistry(session_manager=self.session)

        # Set maximum thread count to prevent resource exhaustion
        self.threadpool.setMaxThreadCount(4)

        # Debug panel (initially None)
        self.debug_panel = None

        try:
            # Initialize UI
            self.init_ui()
            self.restore_state()

            # Initialize backend connections
            self.init_backend()

            # Setup error handler connections
            self.setup_error_handler()

            logger.info("Analytics Runner application initialized successfully")

        except Exception as e:
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

        # Left panel - Main workflow area (now scrollable)
        self.create_main_panel()

        # Right panel - Results and logs
        self.create_results_panel()

        # Set initial splitter proportions (60% main, 40% results)
        self.main_splitter.setSizes([600, 400])
        self.results_widget.hide()

        # Create menu bar
        self.create_menu_bar()

        # Create toolbar
        self.create_toolbar()

        # Create status bar
        self.create_status_bar()

        # Connect data source to rule editor (moved here so both panels exist)
        self.data_source_panel.previewUpdated.connect(self.rule_selector_panel.set_current_data_preview)
        self.data_source_panel.previewUpdated.connect(self._update_rule_editor_columns)

    def create_main_panel(self):
        """Create the main workflow panel with tabs and scrolling support."""
        # Create scroll area for main content
        self.main_scroll_area = QScrollArea()
        self.main_scroll_area.setWidgetResizable(True)
        self.main_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.main_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # Set scroll area styling to minimize visual clutter
        self.main_scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: none;
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            }}
            QScrollArea > QWidget > QWidget {{
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            }}
        """)

        # Create the main content widget
        self.main_widget = QWidget()
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(8, 8, 8, 8)  # Reduced margins
        self.main_layout.setSpacing(12)  # Consistent spacing

        # Create tab widget for different modes
        self.mode_tabs = QTabWidget()
        self.main_layout.addWidget(self.mode_tabs)

        # Simple Mode tab (updated with better spacing)
        self.create_simple_mode_tab()

        # Advanced Mode tab (unchanged)
        self.create_advanced_mode_tab()

        # Rule Management tab
        self.create_rule_selection_mode_tab()

        # Add stretch to push content to top and allow natural expansion
        self.main_layout.addStretch()

        # Set the content widget in the scroll area
        self.main_scroll_area.setWidget(self.main_widget)

        # Add scroll area to splitter
        self.main_splitter.addWidget(self.main_scroll_area)

    def create_simple_mode_tab(self):
        """Create the simple mode tab with save data source integration."""
        self.simple_mode_widget = QWidget()
        simple_layout = QVBoxLayout(self.simple_mode_widget)

        # Reduced spacing and margins for tighter, more efficient layout
        simple_layout.setSpacing(16)  # Increased spacing between major sections
        simple_layout.setContentsMargins(16, 16, 16, 16)  # Balanced padding

        # Data source panel (with registry integration)
        self.data_source_panel = DataSourcePanel(session_manager=self.session)
        self.data_source_panel.dataSourceChanged.connect(self._on_data_source_changed)
        self.data_source_panel.dataSourceValidated.connect(self._on_data_source_validated)
        self.data_source_panel.previewUpdated.connect(self._on_data_preview_updated)

        # Connect to data source registry for integration
        self.data_source_panel.data_source_registry = self.data_source_registry

        simple_layout.addWidget(self.data_source_panel)

        # Validation section with cleaner layout
        validation_section = QWidget()
        validation_layout = QVBoxLayout(validation_section)
        validation_layout.setContentsMargins(0, 8, 0, 0)  # Minimal top margin only

        self.start_button = QPushButton("Select Data Source First")
        self.start_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_validation)
        self.start_button.setMinimumHeight(AnalyticsRunnerStylesheet.BUTTON_HEIGHT)
        validation_layout.addWidget(self.start_button)

        simple_layout.addWidget(validation_section)

        # Let content naturally size without forcing stretch
        self.mode_tabs.addTab(self.simple_mode_widget, "Simple Mode")

    def create_rule_selection_mode_tab(self):
        """Create the enhanced rule selection mode tab with integrated editor."""
        self.rule_selection_widget = QWidget()
        rule_selection_layout = QVBoxLayout(self.rule_selection_widget)
        rule_selection_layout.setContentsMargins(0, 0, 0, 0)
        rule_selection_layout.setSpacing(0)

        # Create rule selector panel with integrated editor
        self.rule_selector_panel = RuleSelectorPanel(session_manager=self.session)

        # Connect signals
        self.rule_selector_panel.rulesSelectionChanged.connect(self._on_rules_selection_changed)

        rule_selection_layout.addWidget(self.rule_selector_panel)

        # Add tab to mode tabs
        self.mode_tabs.addTab(self.rule_selection_widget, "Rule Management")

    def _update_rule_editor_columns(self, preview_df):
        """Update rule editor with available columns from data preview."""
        if preview_df is not None and not preview_df.empty:
            columns = list(preview_df.columns)
            self.rule_selector_panel.set_available_columns(columns)
            # Use log_message method instead of accessing log_view directly
            self.log_message(f"Updated rule editor with {len(columns)} columns", "DEBUG")

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
        """Create the application menu bar with data source menu."""
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

        # Save data source (NEW)
        self.save_source_action = QAction("&Save Current Data Source", self)
        self.save_source_action.setShortcut("Ctrl+S")
        self.save_source_action.setEnabled(False)  # Disabled until data is loaded
        self.save_source_action.triggered.connect(self.save_current_data_source)
        file_menu.addAction(self.save_source_action)

        file_menu.addSeparator()

        # Recent files submenu
        self.recent_menu = file_menu.addMenu("Recent Files")
        self.update_recent_files_menu()

        # Data sources submenu (NEW)
        self.data_sources_menu = file_menu.addMenu("Saved Data Sources")
        self.update_data_sources_menu()

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
        """Restore application state from previous session - FIXED: Default to Simple Mode"""
        import base64

        # Restore window geometry
        geometry = self.session.get('window_geometry')
        if geometry and isinstance(geometry, str):
            try:
                # Decode base64 string back to bytes
                geometry_bytes = base64.b64decode(geometry.encode('utf-8'))
                self.restoreGeometry(geometry_bytes)
            except Exception as e:
                self.log_message(f"Failed to restore window geometry: {e}", "WARNING")
                # Fall back to default size
                screen = QApplication.primaryScreen().geometry()
                x = (screen.width() - 1200) // 2
                y = (screen.height() - 800) // 2
                self.setGeometry(x, y, 1200, 800)
        else:
            # Default size and center on screen
            screen = QApplication.primaryScreen().geometry()
            x = (screen.width() - 1200) // 2
            y = (screen.height() - 800) // 2
            self.setGeometry(x, y, 1200, 800)

        # Restore splitter position
        splitter_state = self.session.get('splitter_state')
        if splitter_state and isinstance(splitter_state, str):
            try:
                # Decode base64 string back to bytes
                splitter_bytes = base64.b64decode(splitter_state.encode('utf-8'))
                self.main_splitter.restoreState(splitter_bytes)
            except Exception as e:
                self.log_message(f"Failed to restore splitter state: {e}", "WARNING")

        # FIXED: Always default to Simple Mode (tab 0) for better UX
        # Don't restore the last active tab - always start with Simple Mode
        self.mode_tabs.setCurrentIndex(0)  # Always start with Simple Mode

        # Optional: Only restore tab if user specifically wants it
        # active_mode = self.session.get('active_mode', 0)
        # self.mode_tabs.setCurrentIndex(active_mode)

        self.log_message("Application state restored - defaulted to Simple Mode")

    def save_state(self):
        """Save application state for next session."""
        import base64

        # Convert QByteArray to base64 strings for JSON serialization
        geometry = self.saveGeometry()
        splitter_state = self.main_splitter.saveState()

        self.session.set('window_geometry', base64.b64encode(bytes(geometry)).decode('utf-8'))
        self.session.set('splitter_state', base64.b64encode(bytes(splitter_state)).decode('utf-8'))
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

    def update_data_sources_menu(self):
        """Update the saved data sources menu."""
        self.data_sources_menu.clear()

        # Get saved data sources
        saved_sources = self.data_source_registry.list_data_sources(
            active_only=True,
            sort_by="last_used"
        )

        if not saved_sources:
            no_sources_action = QAction("No saved data sources", self)
            no_sources_action.setEnabled(False)
            self.data_sources_menu.addAction(no_sources_action)
        else:
            # Add favorites first
            favorites = [s for s in saved_sources if s.is_favorite]
            if favorites:
                for source in favorites[:5]:  # Limit to 5 favorites
                    action = QAction(f"★ {source.name}", self)
                    action.setData(source.source_id)
                    action.setToolTip(f"{source.description}\nFile: {source.file_path}")
                    action.triggered.connect(self.load_saved_data_source)
                    self.data_sources_menu.addAction(action)

                self.data_sources_menu.addSeparator()

            # Add recent sources
            for source in saved_sources[:10]:  # Limit to 10 recent
                if not source.is_favorite:  # Don't duplicate favorites
                    action = QAction(source.name, self)
                    action.setData(source.source_id)
                    action.setToolTip(f"{source.description}\nFile: {source.file_path}")
                    action.triggered.connect(self.load_saved_data_source)
                    self.data_sources_menu.addAction(action)

            if len(saved_sources) > 10:
                self.data_sources_menu.addSeparator()
                view_all_action = QAction("View All Saved Sources...", self)
                view_all_action.triggered.connect(self.show_data_source_manager)
                self.data_sources_menu.addAction(view_all_action)

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

    def _on_rules_selection_changed(self, rule_ids: List[str]):
        """Handle rule selection changes."""
        self.log_message(f"Rule selection changed: {len(rule_ids)} rules selected")

        # Store selected rules for validation
        self.selected_rule_ids = rule_ids

        # Update start button if we have both data and rules
        if hasattr(self, 'data_source_panel') and self.data_source_panel.is_valid() and rule_ids:
            self.start_button.setText("Start Validation with Selected Rules")
            self.start_button.setEnabled(True)
            self.start_validation_action.setEnabled(True)
        elif not rule_ids:
            if hasattr(self, 'data_source_panel') and self.data_source_panel.is_valid():
                self.start_button.setText("Select Rules First")
            else:
                self.start_button.setText("Select Data Source and Rules")
            self.start_button.setEnabled(False)
            self.start_validation_action.setEnabled(False)

    def _on_rule_edit_requested(self, rule_id: str):
        """Handle rule editing request."""
        self.log_message(f"Rule edit requested for: {rule_id}")
        # TODO: Implement rule editing in Phase 3.2
        QMessageBox.information(
            self,
            "Rule Editor",
            f"Rule editing will be available in Phase 3.2.\n\nRule ID: {rule_id}"
        )

    def save_current_data_source(self):
        """Save the current data source configuration."""
        # Get current data from the data source panel
        current_file = self.data_source_panel.get_current_file()
        current_sheet = self.data_source_panel.get_current_sheet()
        preview_data = self.data_source_panel.get_preview_data()

        if not current_file or preview_data is None or preview_data.empty:
            QMessageBox.warning(
                self,
                "No Data to Save",
                "Please load a valid data source before saving."
            )
            return

        try:
            # Open save dialog
            dialog = SaveDataSourceDialog(
                file_path=current_file,
                sheet_name=current_sheet,
                preview_df=preview_data,
                registry=self.data_source_registry,
                parent=self
            )

            # Connect to success signal
            dialog.dataSourceSaved.connect(self._on_data_source_saved)

            # Show dialog
            dialog.exec()

        except Exception as e:
            error_msg = f"Error saving data source: {str(e)}"
            self.log_message(error_msg, "ERROR")
            QMessageBox.critical(self, "Save Error", error_msg)

    def load_saved_data_source(self):
        """Load a saved data source and update the main panel."""
        action = self.sender()
        if not action:
            return

        source_id = action.data()
        if not source_id:
            return

        try:
            # Get source metadata from registry
            source = self.data_source_registry.get_data_source(source_id)
            if not source:
                QMessageBox.warning(self, "Source Not Found", f"Data source not found: {source_id}")
                return

            # Check if file still exists
            if not os.path.exists(source.file_path):
                reply = QMessageBox.question(
                    self,
                    "File Not Found",
                    f"The file for data source '{source.name}' no longer exists:\n{source.file_path}\n\n"
                    f"Would you like to remove this source from the registry?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )

                if reply == QMessageBox.Yes:
                    self.data_source_registry.delete_data_source(source_id)
                    self.update_data_sources_menu()
                    self.log_message(f"Removed invalid data source: {source.name}")
                return

            # Check if file has changed since registration
            if source.is_file_changed():
                reply = QMessageBox.question(
                    self,
                    "File Changed",
                    f"The file for data source '{source.name}' has been modified since registration.\n\n"
                    f"Do you want to continue loading it?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if reply == QMessageBox.No:
                    return

                # Update the file info in the registry
                source.update_file_info()

            self.log_message(f"Loading saved data source: {source.name}")

            # Use the enhanced data source panel method to load the saved source
            if hasattr(self, 'data_source_panel'):
                try:
                    self.data_source_panel.load_saved_data_source(source)
                except Exception as e:
                    # Fallback to basic file loading if enhanced method fails
                    self.log_message(f"Enhanced loading failed, using basic method: {str(e)}", "WARNING")
                    self.data_source_panel._set_file(source.file_path)

            # Update session with this file
            self.session.add_recent_file(source.file_path)
            self.session.set('last_data_directory', os.path.dirname(source.file_path))
            self.update_recent_files_menu()

            # Mark source as used in registry
            self.data_source_registry.mark_source_used(source_id)

            # Update data sources menu to reflect usage
            self.update_data_sources_menu()

            # Display source metadata in results area
            self._display_source_metadata(source)

            # Update status
            self.status_label.setText(f"Loaded saved source: {source.name}")

            self.log_message(f"Successfully loaded saved data source: {source.name}")

        except Exception as e:
            error_msg = f"Error loading saved data source: {str(e)}"
            self.log_message(error_msg, "ERROR")
            QMessageBox.critical(self, "Load Error", error_msg)

    def show_data_source_manager(self):
        """Show the data source manager dialog (placeholder for future implementation)."""
        QMessageBox.information(
            self,
            "Data Source Manager",
            "Data Source Manager will be implemented in a future update.\n\n"
            "For now, you can access saved data sources through the File menu."
        )

    def _display_source_metadata(self, source):
        """Display source metadata in the results area."""
        metadata_text = [
            f"=== LOADED DATA SOURCE ===",
            f"Name: {source.name}",
            f"Description: {source.description or '(none)'}",
            f"File: {os.path.basename(source.file_path)}",
            f"Full Path: {source.file_path}",
            f"Type: {source.source_type.value.upper()}",
            f"Data Type Hint: {source.data_type_hint}",
            ""
        ]

        # Add tags if present
        if source.tags:
            metadata_text.append(f"Tags: {', '.join(source.tags)}")
            metadata_text.append("")

        # Add connection parameters if present
        if source.connection_params:
            metadata_text.append("Connection Parameters:")
            for key, value in source.connection_params.items():
                metadata_text.append(f"  {key}: {value}")
            metadata_text.append("")

        # Add usage statistics
        metadata_text.extend([
            f"Use Count: {source.use_count}",
            f"Last Used: {source.last_used or 'Never'}",
            f"Registered: {source.created_date[:10] if source.created_date else 'Unknown'}",  # Just date part
        ])

        # Add file statistics if available
        if source.file_size:
            if source.file_size < 1024 * 1024:
                size_str = f"{source.file_size / 1024:.1f} KB"
            else:
                size_str = f"{source.file_size / (1024 * 1024):.1f} MB"
            metadata_text.append(f"File Size: {size_str}")

        if source.last_modified:
            # Format the timestamp nicely
            try:
                from datetime import datetime
                mod_time = datetime.fromisoformat(source.last_modified.replace('Z', '+00:00'))
                metadata_text.append(f"Last Modified: {mod_time.strftime('%Y-%m-%d %H:%M')}")
            except:
                metadata_text.append(f"Last Modified: {source.last_modified}")

        # Add validation rules info if present
        if source.validation_rules:
            metadata_text.append("")
            metadata_text.append(f"Custom Validation Rules: {len(source.validation_rules)} defined")

        # Display in results view
        self.results_view.setPlainText('\n'.join(metadata_text))

        # Switch to results tab to show the metadata
        if hasattr(self, 'results_tabs'):
            self.results_tabs.setCurrentIndex(0)

    def _on_data_source_saved(self, source_id: str):
        """Handle successful data source save."""
        self.log_message(f"Data source saved successfully: {source_id}")

        # Update data sources menu
        self.update_data_sources_menu()

        # Enable save action if it was disabled
        self.save_source_action.setEnabled(True)

    def _on_saved_source_sheets_loaded(self, sheet_names):
        """Handle sheet loading completion for saved data sources."""
        # Check if we have a pending sheet selection
        if hasattr(self, '_pending_sheet_selection') and self._pending_sheet_selection:
            target_sheet = self._pending_sheet_selection

            # Find the target sheet in the loaded sheets
            if target_sheet in sheet_names:
                # Set the sheet combo to the saved sheet
                sheet_index = sheet_names.index(target_sheet)
                if hasattr(self.data_source_panel, 'sheet_combo'):
                    self.data_source_panel.sheet_combo.setCurrentIndex(sheet_index)
                    self.data_source_panel._current_sheet = target_sheet

                self.log_message(f"Set Excel sheet to saved preference: {target_sheet}")
            else:
                self.log_message(f"Saved sheet '{target_sheet}' not found, using default", "WARNING")

            # Clear the pending selection
            self._pending_sheet_selection = None

    def _on_data_source_changed(self, file_path: str):
        """Handle data source file change - Enhanced to detect saved sources."""
        if file_path:
            file_name = os.path.basename(file_path)
            self.log_message(f"Data source changed: {file_name}")

            # Check if this is a saved data source
            saved_source = None
            if hasattr(self, 'data_source_panel'):
                saved_source = self.data_source_panel.get_current_source_metadata()

            if saved_source:
                self.log_message(f"Loaded from saved source: {saved_source.name}")

            self.data_source_path = file_path

            self.start_button.setText("Loading...")
            self.start_button.setEnabled(False)
            self.status_label.setText(f"Data source: {file_name}")

            # Enable save action when file is selected (but will be enabled when preview loads)
            self.save_source_action.setEnabled(False)
        else:
            self.start_button.setText("Select Data Source First")
            self.start_button.setEnabled(False)
            self.status_label.setText("No data source selected")
            self.save_source_action.setEnabled(False)

    def _on_data_source_validated(self, is_valid: bool, message: str):
        """Handle data source validation status change."""
        if is_valid:
            self.log_message(f"Data source validation: {message}")
            self.start_button.setText("Start Validation")
            self.start_button.setEnabled(True)
            self.start_validation_action.setEnabled(True)
        else:
            self.log_message(f"Data source validation failed: {message}", "WARNING")
            self.start_button.setText("Fix Data Issues First")
            self.start_button.setEnabled(False)
            self.start_validation_action.setEnabled(False)

    def _on_data_preview_updated(self, preview_df):
        """Handle data preview update."""
        if preview_df is not None and not preview_df.empty:
            rows, cols = preview_df.shape
            self.log_message(f"Data preview loaded: {rows} rows, {cols} columns")

            # Enable save action when valid preview is available
            self.save_source_action.setEnabled(True)

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

            # Disable save action when no valid preview
            self.save_source_action.setEnabled(False)

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
        """Start the validation process with selected rules."""
        # Get data source from panel
        data_source_file = self.data_source_panel.get_current_file()

        if not data_source_file:
            QMessageBox.warning(self, "No Data Source", "Please select a data source first.")
            return

        if not self.data_source_panel.is_valid():
            QMessageBox.warning(self, "Invalid Data Source", "The selected data source is not valid.")
            return

        # Get selected rules from enhanced rule selector
        selected_rules = []
        if hasattr(self, 'rule_selector_panel'):
            selected_rules = self.rule_selector_panel.get_selected_rule_ids()

        if not selected_rules:
            reply = QMessageBox.question(
                self,
                "No Rules Selected",
                "No validation rules are selected. Do you want to run with all available rules?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )

            if reply == QMessageBox.No:
                return
            else:
                # Use all rules if none selected
                selected_rules = None

        self.log_message(f"Starting validation with {len(selected_rules) if selected_rules else 'all'} rules")

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

        # Create and start validation worker
        self.validation_worker = ValidationWorker(
            pipeline=None,  # Will be created in worker
            data_source=data_source_file,
            sheet_name=sheet_name,
            analytic_id=f"Analytics_Validation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}",
            rule_ids=selected_rules  # Pass selected rules
        )

        # Connect worker signals
        self.validation_worker.signals.started.connect(self._on_validation_started)
        self.validation_worker.signals.progress.connect(self.update_progress)
        self.validation_worker.signals.result.connect(self._on_validation_complete)
        self.validation_worker.signals.error.connect(self._on_validation_error)
        self.validation_worker.signals.finished.connect(self._on_validation_finished)

        # Start worker
        self.threadpool.start(self.validation_worker)

    # ADD these new methods to the AnalyticsRunnerApp class:
    def _on_validation_started(self):
        """Handle validation start."""
        self.log_message("Validation started")

    def _on_validation_complete(self, results: dict):
        """Handle validation completion with results."""
        self.log_message("Validation completed successfully")

        # Format and display results
        result_text = self._format_validation_results(results)
        self.results_view.setPlainText(result_text)

        # Switch to results tab
        if hasattr(self, 'results_tabs'):
            self.results_tabs.setCurrentIndex(0)

    def _on_validation_error(self, error_message: str):
        """Handle validation error."""
        self.log_message(f"Validation failed: {error_message}", "ERROR")
        QMessageBox.critical(self, "Validation Error", f"Validation failed:\n\n{error_message}")
        self.results_view.setPlainText(f"Validation Error:\n{error_message}")

    def _on_validation_finished(self):
        """Handle validation worker finished (cleanup)."""
        self.start_button.setEnabled(True)
        self.start_validation_action.setEnabled(True)
        self.stop_validation_action.setEnabled(False)
        self.show_progress(False)
        self.status_label.setText("Validation completed")

    def _format_validation_results(self, results: dict) -> str:
        """Format validation results for text display."""
        lines = ["=== VALIDATION RESULTS ===", ""]

        status = results.get('status', 'UNKNOWN')
        lines.append(f"Overall Status: {status}")
        lines.append(f"Timestamp: {results.get('timestamp', 'N/A')}")
        lines.append("")

        summary = results.get('summary', {})
        if summary:
            lines.append("=== SUMMARY ===")
            lines.append(f"Total Rules: {summary.get('total_rules', 0)}")
            compliance_counts = summary.get('compliance_counts', {})
            lines.append(f"GC: {compliance_counts.get('GC', 0)}")
            lines.append(f"PC: {compliance_counts.get('PC', 0)}")
            lines.append(f"DNC: {compliance_counts.get('DNC', 0)}")
            lines.append(f"Compliance: {summary.get('compliance_rate', 0):.1%}")
            lines.append("")

        exec_time = results.get('execution_time', 0)
        lines.append(f"Execution Time: {exec_time:.2f} seconds")

        return "\n".join(lines)

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

        # Clean up rule selector panel - UPDATED
        if hasattr(self, 'rule_selector_panel'):
            self.rule_selector_panel.cleanup()

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
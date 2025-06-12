#!/usr/bin/env python3
"""
Analytics Runner - Main Application
QA Analytics Framework GUI Application
"""

import sys
import os
import logging
import datetime
import pandas as pd
from pathlib import Path
from typing import Optional, List

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
    QWidget, QSplitter, QTabWidget, QStatusBar, QMenuBar,
    QToolBar, QTextEdit, QLabel, QPushButton, QProgressBar,
    QMessageBox, QFileDialog, QCheckBox, QScrollArea, QLineEdit,
    QComboBox, QFrame, QTableWidget, QStackedWidget, QHeaderView, QTableWidgetItem
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
# from services.progress_tracking_pipeline import ProgressTrackingPipeline
from rule_selector_panel import RuleSelectorPanel
from ui.analytics_runner.cancellable_validation_worker import (
    CancellableValidationWorker, CancellableWorkerSignals, ExecutionStatus
)
from ui.common.widgets.results_tree_widget import ResultsTreeWidget

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
    # Report generation signals
    reportStarted = Signal()
    reportProgress = Signal(int, str)
    reportCompleted = Signal(dict)
    reportError = Signal(str)
    # Real-time progress tracking signals
    progressUpdated = Signal(int)  # Progress percentage (0-100, or -1 for error)
    statusUpdated = Signal(str)  # Status message
    ruleStarted = Signal(str, int, int)  # Rule name, current index, total count


class ValidationWorker(QRunnable):
    """Worker thread for running validation operations"""

    def __init__(self, pipeline, data_source: str, sheet_name: str = None,
                 analytic_id: str = None, rule_ids: List[str] = None,
                 generate_reports: bool = True, report_formats: List[str] = None,
                 output_dir: str = None):
        super().__init__()
        self.pipeline = pipeline
        self.data_source = data_source
        self.sheet_name = sheet_name
        self.analytic_id = analytic_id or "Simple_Validation"
        self.rule_ids = rule_ids  # Add rule_ids parameter
        self.generate_reports = generate_reports
        self.report_formats = report_formats or ['excel', 'html']
        self.output_dir = output_dir or './output'
        self.signals = ValidationWorkerSignals()

    def run(self):
        """Run the validation process."""
        try:
            self.signals.started.emit()

            # Define progress callback that emits signals
            def progress_callback(progress: int, status: str):
                self.signals.progressUpdated.emit(progress)
                self.signals.statusUpdated.emit(status)
                
                # Parse rule info from status if available
                if "Processing rule" in status and "/" in status:
                    # Extract rule number and name
                    parts = status.split(":")
                    if len(parts) > 1:
                        rule_info = parts[0].replace("Processing rule", "").strip()
                        rule_name = parts[1].split("(")[0].strip()
                        
                        # Extract current and total
                        if "/" in rule_info:
                            current, total = rule_info.split("/")
                            try:
                                current_idx = int(current)
                                total_count = int(total)
                                self.signals.ruleStarted.emit(rule_name, current_idx, total_count)
                            except ValueError:
                                pass

            # Prepare validation parameters
            validation_params = {
                'data_source_path': self.data_source,
                'source_type': 'excel' if self.data_source.endswith(('.xlsx', '.xls')) else 'csv',
                'rule_ids': self.rule_ids,
                'selected_sheet': self.sheet_name,
                'analytic_id': self.analytic_id,
                'output_formats': self.report_formats if self.generate_reports else ['json'],
                'use_parallel': False,
                'progress_callback': progress_callback
            }

            # Add use_all_rules flag if no specific rules selected
            if not self.rule_ids:
                validation_params['use_all_rules'] = True
                logger.info("No specific rules selected - will use all available rules")

            self.signals.progress.emit(25, "Preparing validation...")

            # Import here to avoid circular imports
            from services.validation_service import ValidationPipeline

            # Create pipeline if not provided
            if not self.pipeline:
                # Ensure output directory exists
                import os
                os.makedirs(self.output_dir, exist_ok=True)
                logger.info(f"Created/verified output directory: {self.output_dir}")
                
                # Import rule manager with correct rules directory
                from core.rule_engine.rule_manager import ValidationRuleManager
                rule_manager = ValidationRuleManager(rules_directory="./data/rules")
                
                self.pipeline = ValidationPipeline(
                    rule_manager=rule_manager,
                    output_dir=self.output_dir
                )

            # Run validation directly with the pipeline
            results = self.pipeline.validate_data_source(**validation_params)

            self.signals.progress.emit(90, "Processing results...")
            
            # Log validation results for debugging
            logger.info(f"Validation completed. Valid: {results.get('valid')}, Status: {results.get('status')}")
            logger.info(f"Generate reports: {self.generate_reports}, Report formats: {self.report_formats}")
            logger.info(f"Output files in results: {results.get('output_files', [])}")
            
            # Check if report generation occurred and emit appropriate signals
            # Note: Reports should be generated regardless of validation result
            if self.generate_reports and results.get('output_files'):
                self.signals.reportStarted.emit()
                self.signals.reportProgress.emit(95, "Reports generated successfully")
                
                # Emit report completion with file paths
                report_info = {
                    'output_files': results.get('output_files', []),
                    'output_dir': self.output_dir
                }
                self.signals.reportCompleted.emit(report_info)
            elif self.generate_reports:
                # Reports were requested but not generated
                logger.warning("Reports were requested but no output files were generated")
                self.signals.reportError.emit("No report files were generated. Check logs for details.")
            
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

        # Results & Reports tab
        self.create_results_reports_tab()

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

        # Report Generation Options section
        report_section = QWidget()
        report_section.setStyleSheet(f"""
            QWidget {{
                background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR}40;
                border-radius: 6px;
                padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
            }}
        """)
        report_layout = QVBoxLayout(report_section)
        report_layout.setContentsMargins(12, 12, 12, 12)
        report_layout.setSpacing(8)

        # Report options header
        report_header = QLabel("Report Generation")
        report_header.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        report_header.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.DARK_TEXT}; background-color: transparent;")
        report_layout.addWidget(report_header)

        # Checkbox frame for report formats
        checkbox_frame = QWidget()
        checkbox_frame.setStyleSheet("background-color: transparent;")
        checkbox_layout = QVBoxLayout(checkbox_frame)
        checkbox_layout.setContentsMargins(0, 0, 0, 0)
        checkbox_layout.setSpacing(6)

        # Excel report checkbox
        self.excel_report_checkbox = QCheckBox("Generate Excel Report")
        self.excel_report_checkbox.setChecked(True)
        self.excel_report_checkbox.setStyleSheet("background-color: transparent;")
        self.excel_report_checkbox.toggled.connect(self._on_report_option_changed)
        checkbox_layout.addWidget(self.excel_report_checkbox)

        # HTML report checkbox
        self.html_report_checkbox = QCheckBox("Generate HTML Report")
        self.html_report_checkbox.setChecked(True)
        self.html_report_checkbox.setStyleSheet("background-color: transparent;")
        self.html_report_checkbox.toggled.connect(self._on_report_option_changed)
        checkbox_layout.addWidget(self.html_report_checkbox)

        # Audit Leader-Specific Workbooks checkbox (always enabled for discoverability)
        self.leader_packs_checkbox = QCheckBox("Generate Audit Leader-Specific Workbooks")
        self.leader_packs_checkbox.setChecked(False)
        self.leader_packs_checkbox.setEnabled(True)  # Always enabled
        self.leader_packs_checkbox.setStyleSheet("background-color: transparent;")
        self.leader_packs_checkbox.setToolTip("Creates individual Excel workbooks for each responsible party. Requires a responsible party column to be selected.")
        self.leader_packs_checkbox.toggled.connect(self._on_leader_packs_changed)
        checkbox_layout.addWidget(self.leader_packs_checkbox)
        
        # Warning label for leader packs (hidden by default)
        self.leader_packs_warning = QLabel("⚠️ Select a responsible party column to enable this feature")
        self.leader_packs_warning.setStyleSheet(f"""
            color: {AnalyticsRunnerStylesheet.WARNING_COLOR};
            background-color: transparent;
            font-size: 12px;
            padding-left: 20px;
        """)
        self.leader_packs_warning.setVisible(False)
        checkbox_layout.addWidget(self.leader_packs_warning)

        report_layout.addWidget(checkbox_frame)

        # Output directory selection
        output_dir_frame = QWidget()
        output_dir_frame.setStyleSheet("background-color: transparent;")
        output_dir_layout = QHBoxLayout(output_dir_frame)
        output_dir_layout.setContentsMargins(0, 0, 0, 0)
        output_dir_layout.setSpacing(8)

        output_dir_label = QLabel("Output Directory:")
        output_dir_label.setStyleSheet("background-color: transparent;")
        output_dir_layout.addWidget(output_dir_label)

        self.output_dir_edit = QLineEdit("./output")
        self.output_dir_edit.setReadOnly(True)
        output_dir_layout.addWidget(self.output_dir_edit)

        self.output_dir_button = QPushButton("Browse")
        self.output_dir_button.setProperty("buttonStyle", "secondary")
        self.output_dir_button.clicked.connect(self.browse_output_directory)
        self.output_dir_button.setMaximumWidth(80)
        output_dir_layout.addWidget(self.output_dir_button)

        report_layout.addWidget(output_dir_frame)

        simple_layout.addWidget(report_section)

        # Progress tracking section
        progress_section = QWidget()
        progress_section.setStyleSheet(f"""
            QWidget {{
                background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR}40;
                border-radius: 6px;
                padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
            }}
        """)
        progress_layout = QVBoxLayout(progress_section)
        progress_layout.setContentsMargins(12, 12, 12, 12)
        progress_layout.setSpacing(8)
        
        # Progress header
        progress_header = QLabel("Validation Progress")
        progress_header.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        progress_header.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.DARK_TEXT}; background-color: transparent;")
        progress_layout.addWidget(progress_header)
        
        # Progress bar
        self.validation_progress_bar = QProgressBar()
        self.validation_progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                text-align: center;
                min-height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                border-radius: 3px;
            }}
        """)
        self.validation_progress_bar.setVisible(False)
        progress_layout.addWidget(self.validation_progress_bar)
        
        # Status message label
        self.validation_status_label = QLabel("")
        self.validation_status_label.setStyleSheet(f"""
            color: {AnalyticsRunnerStylesheet.DARK_TEXT}; 
            background-color: transparent;
            font-size: 13px;
        """)
        self.validation_status_label.setVisible(False)
        progress_layout.addWidget(self.validation_status_label)
        
        # Rule execution summary
        self.rule_summary_label = QLabel("")
        self.rule_summary_label.setStyleSheet(f"""
            color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; 
            background-color: transparent;
            font-size: 12px;
            font-style: italic;
        """)
        self.rule_summary_label.setVisible(False)
        progress_layout.addWidget(self.rule_summary_label)
        
        simple_layout.addWidget(progress_section)
        self.progress_section = progress_section
        self.progress_section.setVisible(False)  # Hidden by default

        # Execution Management section
        execution_section = QWidget()
        execution_section.setStyleSheet(f"""
            QWidget {{
                background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR}40;
                border-radius: 6px;
                padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
            }}
        """)
        execution_layout = QVBoxLayout(execution_section)
        execution_layout.setContentsMargins(12, 12, 12, 12)
        execution_layout.setSpacing(8)
        
        # Execution header with status
        execution_header_layout = QHBoxLayout()
        execution_header_layout.setSpacing(12)
        
        execution_header = QLabel("Execution Control")
        execution_header.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        execution_header.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.DARK_TEXT}; background-color: transparent;")
        execution_header_layout.addWidget(execution_header)
        
        # Status indicator
        self.execution_status_label = QLabel("Status: Ready")
        self.execution_status_label.setStyleSheet(f"""
            color: {AnalyticsRunnerStylesheet.DARK_TEXT}; 
            background-color: transparent;
            font-weight: bold;
            padding: 4px 8px;
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 4px;
        """)
        execution_header_layout.addStretch()
        execution_header_layout.addWidget(self.execution_status_label)
        
        execution_layout.addLayout(execution_header_layout)
        
        # Session info label
        self.session_info_label = QLabel("")
        self.session_info_label.setStyleSheet(f"""
            color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; 
            background-color: transparent;
            font-size: 12px;
            font-style: italic;
        """)
        self.session_info_label.setVisible(False)
        execution_layout.addWidget(self.session_info_label)
        
        # Execution parameters section
        params_widget = QWidget()
        params_widget.setStyleSheet("background-color: transparent;")
        params_layout = QVBoxLayout(params_widget)
        params_layout.setContentsMargins(0, 8, 0, 8)
        params_layout.setSpacing(8)
        
        # Row 1: Analytic ID and Execution Mode
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(12)
        
        # Analytic ID input
        analytic_id_label = QLabel("Analytic ID:")
        analytic_id_label.setStyleSheet("background-color: transparent;")
        row1_layout.addWidget(analytic_id_label)
        
        self.analytic_id_input = QLineEdit()
        self.analytic_id_input.setPlaceholderText(f"Analytics_Validation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}")
        self.analytic_id_input.setToolTip("Enter a custom Analytic ID or leave empty for auto-generated timestamp")
        self.analytic_id_input.setStyleSheet(f"""
            QLineEdit {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px 10px;
                min-height: 20px;
            }}
            QLineEdit:focus {{
                border-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            }}
        """)
        row1_layout.addWidget(self.analytic_id_input, 2)
        
        row1_layout.addSpacing(20)
        
        # Execution mode selector
        mode_label = QLabel("Execution Mode:")
        mode_label.setStyleSheet("background-color: transparent;")
        row1_layout.addWidget(mode_label)
        
        self.execution_mode_combo = QComboBox()
        self.execution_mode_combo.addItems(["Serial", "Parallel"])
        self.execution_mode_combo.setCurrentText("Serial")
        self.execution_mode_combo.setToolTip("Select execution mode for validation rules")
        self.execution_mode_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px 10px;
                min-height: 20px;
                min-width: 100px;
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
            }}
            QComboBox:hover {{
                border-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {AnalyticsRunnerStylesheet.DARK_TEXT};
                margin-right: 5px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                selection-background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                selection-color: white;
                outline: none;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 30px;
                padding: 4px 8px;
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            }}
        """)
        row1_layout.addWidget(self.execution_mode_combo, 1)
        
        params_layout.addLayout(row1_layout)
        
        # Row 2: Responsible Party Column
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(12)
        
        party_label = QLabel("Responsible Party Column:")
        party_label.setStyleSheet("background-color: transparent;")
        row2_layout.addWidget(party_label)
        
        self.responsible_party_combo = QComboBox()
        self.responsible_party_combo.addItem("None")
        self.responsible_party_combo.setEnabled(False)  # Disabled until data is loaded
        self.responsible_party_combo.setToolTip("Select column containing responsible party information")
        self.responsible_party_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px 10px;
                min-height: 20px;
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
            }}
            QComboBox:hover:enabled {{
                border-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            }}
            QComboBox:disabled {{
                background-color: {AnalyticsRunnerStylesheet.DISABLED_COLOR};
                color: #999999;
            }}
            QComboBox::drop-down {{
                border: none;
                padding-right: 8px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid {AnalyticsRunnerStylesheet.DARK_TEXT};
                margin-right: 5px;
            }}
            QComboBox::down-arrow:disabled {{
                border-top: 5px solid #999999;
            }}
            QComboBox QAbstractItemView {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                selection-background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                selection-color: white;
                outline: none;
                padding: 4px;
            }}
            QComboBox QAbstractItemView::item {{
                min-height: 30px;
                padding: 4px 8px;
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
            }}
            QComboBox QAbstractItemView::item:hover {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            }}
        """)
        self.responsible_party_combo.currentIndexChanged.connect(self._on_responsible_party_changed)
        row2_layout.addWidget(self.responsible_party_combo, 2)
        
        row2_layout.addStretch()
        
        params_layout.addLayout(row2_layout)
        
        execution_layout.addWidget(params_widget)
        
        # Control buttons layout
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(8)
        
        # Start/Run button
        self.start_button = QPushButton("Select Data Source First")
        self.start_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_validation)
        self.start_button.setMinimumHeight(AnalyticsRunnerStylesheet.BUTTON_HEIGHT)
        self.start_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }}
            QPushButton:hover:enabled {{
                background-color: {AnalyticsRunnerStylesheet.HOVER_COLOR};
            }}
            QPushButton:pressed {{
                background-color: #014A8F;
            }}
            QPushButton:disabled {{
                background-color: {AnalyticsRunnerStylesheet.DISABLED_COLOR};
                color: #999999;
            }}
        """)
        controls_layout.addWidget(self.start_button)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_validation)
        self.cancel_button.setMinimumHeight(AnalyticsRunnerStylesheet.BUTTON_HEIGHT)
        self.cancel_button.setProperty("buttonStyle", "danger")
        self.cancel_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {AnalyticsRunnerStylesheet.ERROR_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #C82333;
            }}
            QPushButton:pressed {{
                background-color: #A71D2A;
            }}
            QPushButton:disabled {{
                background-color: {AnalyticsRunnerStylesheet.DISABLED_COLOR};
                color: #999999;
            }}
        """)
        controls_layout.addWidget(self.cancel_button)
        
        # Pause/Resume button (disabled for MVP)
        self.pause_button = QPushButton("Pause")
        self.pause_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.pause_button.setEnabled(False)
        self.pause_button.setMinimumHeight(AnalyticsRunnerStylesheet.BUTTON_HEIGHT)
        self.pause_button.setProperty("buttonStyle", "secondary")
        self.pause_button.setToolTip("Pause/Resume functionality coming in future release")
        self.pause_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {AnalyticsRunnerStylesheet.DISABLED_COLOR};
                color: #999999;
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px 16px;
            }}
        """)
        controls_layout.addWidget(self.pause_button)
        
        execution_layout.addLayout(controls_layout)
        
        simple_layout.addWidget(execution_section)

        # Let content naturally size without forcing stretch
        self.mode_tabs.addTab(self.simple_mode_widget, "Validation")

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

    def create_results_reports_tab(self):
        """Create the Results & Reports tab with sub-tabs"""
        self.results_reports_widget = QWidget()
        results_layout = QVBoxLayout(self.results_reports_widget)
        results_layout.setSpacing(AnalyticsRunnerStylesheet.SECTION_SPACING)
        results_layout.setContentsMargins(24, 24, 24, 24)

        # Header section with title and controls
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setSpacing(16)
        
        # Left side: Title and status
        left_header = QWidget()
        left_header_layout = QVBoxLayout(left_header)
        left_header_layout.setSpacing(4)
        
        # Title
        results_title = QLabel("Results & Reports")
        results_title.setFont(AnalyticsRunnerStylesheet.get_fonts()['title'])
        results_title.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
                padding: 0px;
                border: none;
            }}
        """)
        left_header_layout.addWidget(results_title)
        
        # Status indicator
        self.results_status_label = QLabel("No results loaded")
        self.results_status_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.results_status_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                padding: 4px 8px;
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
            }}
        """)
        left_header_layout.addWidget(self.results_status_label)
        
        header_layout.addWidget(left_header)
        header_layout.addStretch()
        
        # Right side: Clear Results button
        self.clear_results_button = QPushButton("Clear Results")
        self.clear_results_button.setEnabled(False)
        self.clear_results_button.clicked.connect(self.clear_results)
        self.clear_results_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }}
            QPushButton:hover:enabled {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            }}
            QPushButton:pressed {{
                background-color: {AnalyticsRunnerStylesheet.BORDER_COLOR};
            }}
            QPushButton:disabled {{
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                background-color: {AnalyticsRunnerStylesheet.DISABLED_COLOR};
            }}
        """)
        header_layout.addWidget(self.clear_results_button)
        
        results_layout.addWidget(header_widget)
        
        # Create sub-tabs for different result views
        self.results_reports_tabs = QTabWidget()
        self.results_reports_tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border-radius: 4px;
                margin-top: -1px;
            }}
            QTabBar::tab {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
                padding: 8px 16px;
                margin-right: 2px;
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                font-weight: 500;
            }}
            QTabBar::tab:hover:!selected {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
        """)
        
        # Create Summary tab
        self.create_summary_tab()
        
        # Create Rule Details tab
        self.create_rule_details_tab()
        
        # Create Failed Items tab
        self.create_failed_items_tab()
        
        # Create Reports tab
        self.create_reports_tab()
        
        results_layout.addWidget(self.results_reports_tabs)
        
        # Add the tab to main tabs
        self.mode_tabs.addTab(self.results_reports_widget, "Results & Reports")
    
    def create_summary_tab(self):
        """Create the Summary sub-tab with compact layout"""
        self.summary_widget = QWidget()
        summary_layout = QVBoxLayout(self.summary_widget)
        summary_layout.setContentsMargins(16, 16, 16, 16)
        summary_layout.setSpacing(12)  # Reduced from 24
        
        # Compact Overview Card - combines compliance rate and status counts
        overview_card = QFrame()
        overview_card.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 8px;
                padding: 16px;
            }}
        """)
        overview_layout = QHBoxLayout(overview_card)
        overview_layout.setSpacing(24)
        
        # Left side: Compliance Rate
        rate_section = QWidget()
        rate_layout = QVBoxLayout(rate_section)
        rate_layout.setSpacing(4)
        rate_layout.setContentsMargins(0, 0, 0, 0)
        
        rate_title = QLabel("Compliance Rate")
        rate_title.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        rate_title.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};")
        rate_layout.addWidget(rate_title)
        
        self.compliance_rate_label = QLabel("--")
        self.compliance_rate_label.setFont(QFont("Arial", 32, QFont.Bold))
        self.compliance_rate_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};")
        rate_layout.addWidget(self.compliance_rate_label)
        
        overview_layout.addWidget(rate_section)
        
        # Vertical separator
        separator = QFrame()
        separator.setFrameShape(QFrame.VLine)
        separator.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.BORDER_COLOR};")
        overview_layout.addWidget(separator)
        
        # Right side: Status counts in horizontal layout
        counts_section = QWidget()
        counts_layout = QVBoxLayout(counts_section)
        counts_layout.setSpacing(8)
        counts_layout.setContentsMargins(0, 0, 0, 0)
        
        counts_title = QLabel("Status Breakdown")
        counts_title.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        counts_title.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};")
        counts_layout.addWidget(counts_title)
        
        # Status blocks in pill style
        status_row = QWidget()
        status_layout = QHBoxLayout(status_row)
        status_layout.setSpacing(12)
        status_layout.setContentsMargins(0, 0, 0, 0)
        
        # GC - Green pill
        self.gc_pill = self._create_status_pill("GC", "0", "#27ae60", "white")
        status_layout.addWidget(self.gc_pill)
        
        # PC - Amber pill
        self.pc_pill = self._create_status_pill("PC", "0", "#f39c12", "#2c3e50")
        status_layout.addWidget(self.pc_pill)
        
        # DNC - Red pill
        self.dnc_pill = self._create_status_pill("DNC", "0", "#e74c3c", "white")
        status_layout.addWidget(self.dnc_pill)
        
        status_layout.addStretch()
        counts_layout.addWidget(status_row)
        
        overview_layout.addWidget(counts_section)
        overview_layout.addStretch()
        
        summary_layout.addWidget(overview_card)
        
        # Execution Details - Horizontal layout
        details_card = QFrame()
        details_card.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 8px;
                padding: 12px 16px;
            }}
        """)
        
        # Grid layout for details
        details_grid = QHBoxLayout(details_card)
        details_grid.setSpacing(24)
        
        # Left column
        left_details = QVBoxLayout()
        left_details.setSpacing(6)
        
        self.timestamp_label = self._create_detail_label("Timestamp", "--")
        left_details.addWidget(self.timestamp_label)
        
        self.rules_count_label = self._create_detail_label("Rules Applied", "--")
        left_details.addWidget(self.rules_count_label)
        
        details_grid.addLayout(left_details)
        
        # Right column
        right_details = QVBoxLayout()
        right_details.setSpacing(6)
        
        self.execution_time_label = self._create_detail_label("Execution Time", "--")
        right_details.addWidget(self.execution_time_label)
        
        self.data_source_label = self._create_detail_label("Data Source", "--")
        self.data_source_label.setWordWrap(True)
        right_details.addWidget(self.data_source_label)
        
        details_grid.addLayout(right_details)
        details_grid.addStretch()
        
        summary_layout.addWidget(details_card)
        
        # Add placeholder for when no results
        self.summary_placeholder = QLabel("No validation results to display")
        self.summary_placeholder.setAlignment(Qt.AlignCenter)
        self.summary_placeholder.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                font-style: italic;
                padding: 40px;
            }}
        """)
        self.summary_placeholder.hide()
        summary_layout.addWidget(self.summary_placeholder)
        
        summary_layout.addStretch()
        
        self.results_reports_tabs.addTab(self.summary_widget, "Summary")
    
    def _create_status_pill(self, label: str, count: str, bg_color: str, text_color: str) -> QLabel:
        """Create a pill-style status block"""
        pill = QLabel(f"{label} {count}")
        pill.setObjectName(f"{label.lower()}_pill")
        pill.setAlignment(Qt.AlignCenter)
        font = AnalyticsRunnerStylesheet.get_fonts()['regular']
        font.setBold(True)
        pill.setFont(font)
        pill.setStyleSheet(f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                border-radius: 14px;
                padding: 6px 16px;
                min-width: 70px;
                font-weight: bold;
                font-size: 14px;
            }}
            QLabel:hover {{
                background-color: {bg_color}dd;
            }}
        """)
        
        # Set tooltip with full status name
        tooltips = {
            "GC": "Generally Conforms",
            "PC": "Partially Conforms",
            "DNC": "Does Not Conform"
        }
        pill.setToolTip(tooltips.get(label, label))
        
        # Store the label and count parts for easy updates
        pill.label_text = label
        pill.count_text = count
        
        return pill
    
    def _create_detail_label(self, title: str, value: str) -> QLabel:
        """Create a compact detail label"""
        label = QLabel(f"<b>{title}:</b> {value}")
        label.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};")
        return label
    
    def _create_status_frame(self, title: str, count: str, color: str) -> QFrame:
        """Create a status count frame"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 2px solid {color};
                border-radius: 8px;
                padding: 16px;
                min-width: 150px;
            }}
        """)
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(8)
        
        title_label = QLabel(title)
        title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        title_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};")
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        count_label = QLabel(count)
        count_label.setObjectName(f"{title.lower().replace(' ', '_')}_count")
        count_label.setFont(QFont("Arial", 24, QFont.Bold))
        count_label.setStyleSheet(f"color: {color};")
        count_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(count_label)
        
        return frame
    
    def create_rule_details_tab(self):
        """Create the Rule Details sub-tab"""
        self.rule_details_widget = QWidget()
        rule_details_layout = QVBoxLayout(self.rule_details_widget)
        rule_details_layout.setContentsMargins(16, 16, 16, 16)
        rule_details_layout.setSpacing(12)
        
        # Header with filter controls
        header_layout = QHBoxLayout()
        
        # Title
        title = QLabel("Rule Execution Details")
        title.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        title.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.DARK_TEXT};")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Filter by status
        filter_label = QLabel("Filter by Status:")
        filter_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};")
        header_layout.addWidget(filter_label)
        
        self.rule_status_filter = QComboBox()
        self.rule_status_filter.addItems(["All", "Passed", "Failed", "Error"])
        self.rule_status_filter.setMinimumWidth(120)
        self.rule_status_filter.currentTextChanged.connect(self._filter_rule_details)
        header_layout.addWidget(self.rule_status_filter)
        
        rule_details_layout.addLayout(header_layout)
        
        # Scrollable area for rule cards
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet(f"""
            QScrollArea {{
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            }}
            QScrollBar:vertical {{
                width: 12px;
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
                border-radius: 6px;
            }}
            QScrollBar::handle:vertical {{
                background-color: {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 6px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background-color: {AnalyticsRunnerStylesheet.HOVER_COLOR};
            }}
        """)
        
        # Container for rule cards
        self.rule_cards_container = QWidget()
        self.rule_cards_layout = QVBoxLayout(self.rule_cards_container)
        self.rule_cards_layout.setSpacing(8)
        self.rule_cards_layout.setContentsMargins(8, 8, 8, 8)
        
        # Placeholder when no results
        self.rule_details_placeholder = QLabel("No validation results to display")
        self.rule_details_placeholder.setAlignment(Qt.AlignCenter)
        self.rule_details_placeholder.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                font-style: italic;
                padding: 40px;
            }}
        """)
        self.rule_cards_layout.addWidget(self.rule_details_placeholder)
        
        scroll_area.setWidget(self.rule_cards_container)
        rule_details_layout.addWidget(scroll_area)
        
        self.results_reports_tabs.addTab(self.rule_details_widget, "Rule Details")
    
    def create_failed_items_tab(self):
        """Create the Failed Items sub-tab"""
        self.failed_items_widget = QWidget()
        failed_items_layout = QVBoxLayout(self.failed_items_widget)
        failed_items_layout.setContentsMargins(16, 16, 16, 16)
        failed_items_layout.setSpacing(12)
        
        # Header with controls
        header_layout = QHBoxLayout()
        
        # Title
        title = QLabel("Failed Validation Items")
        title.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        title.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.DARK_TEXT};")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Export button
        export_button = QPushButton("Export to CSV")
        export_button.setIcon(QIcon.fromTheme("document-save"))
        export_button.clicked.connect(self._export_failed_items)
        export_button.setEnabled(False)  # Disabled until we have results
        self.failed_items_export_btn = export_button
        header_layout.addWidget(export_button)
        
        failed_items_layout.addLayout(header_layout)
        
        # Table for failed items
        self.failed_items_table = QTableWidget()
        self.failed_items_table.setAlternatingRowColors(True)
        self.failed_items_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.failed_items_table.setSortingEnabled(True)
        self.failed_items_table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
            }}
            QTableWidget::item {{
                padding: 4px 8px;
                border: none;
            }}
            QTableWidget::item:selected {{
                background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                color: white;
            }}
            QHeaderView::section {{
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
                padding: 6px;
                border: none;
                border-bottom: 2px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                font-weight: bold;
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
            }}
            QTableWidget::item:alternate {{
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            }}
        """)
        
        # Set default columns
        self.failed_items_table.setColumnCount(5)
        self.failed_items_table.setHorizontalHeaderLabels([
            "Rule Name", "Column", "Row", "Value", "Reason"
        ])
        
        # Configure column widths
        header = self.failed_items_table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Fixed)
        header.setSectionResizeMode(3, QHeaderView.Interactive)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        
        self.failed_items_table.setColumnWidth(2, 80)  # Row column
        
        # Placeholder when no failures
        self.failed_items_placeholder = QLabel("No failed items to display")
        self.failed_items_placeholder.setAlignment(Qt.AlignCenter)
        self.failed_items_placeholder.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                font-style: italic;
                padding: 40px;
            }}
        """)
        
        # Stack widget to switch between table and placeholder
        self.failed_items_stack = QStackedWidget()
        self.failed_items_stack.addWidget(self.failed_items_placeholder)
        self.failed_items_stack.addWidget(self.failed_items_table)
        self.failed_items_stack.setCurrentIndex(0)  # Show placeholder initially
        
        failed_items_layout.addWidget(self.failed_items_stack)
        
        self.results_reports_tabs.addTab(self.failed_items_widget, "Failed Items")
    
    def create_reports_tab(self):
        """Create the Reports sub-tab"""
        self.reports_widget = QWidget()
        reports_layout = QVBoxLayout(self.reports_widget)
        reports_layout.setContentsMargins(20, 20, 20, 20)
        reports_layout.setSpacing(16)
        
        # Title
        reports_title = QLabel("Generated Reports")
        reports_title.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        reports_title.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
                padding: 0px;
                border: none;
                margin-bottom: 8px;
            }}
        """)
        reports_layout.addWidget(reports_title)
        
        # Reports container
        self.reports_container = QWidget()
        self.reports_container_layout = QVBoxLayout(self.reports_container)
        self.reports_container_layout.setSpacing(12)
        
        # Placeholder for no reports
        self.no_reports_label = QLabel("No reports generated yet")
        self.no_reports_label.setAlignment(Qt.AlignCenter)
        self.no_reports_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                font-style: italic;
                padding: 40px;
                border: 2px dashed {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 8px;
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            }}
        """)
        self.reports_container_layout.addWidget(self.no_reports_label)
        
        reports_layout.addWidget(self.reports_container)
        reports_layout.addStretch()
        
        self.results_reports_tabs.addTab(self.reports_widget, "Reports")
    
    def _create_report_card(self, file_path: str, file_type: str) -> QFrame:
        """Create a card widget for a report file"""
        import os
        
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 8px;
                padding: 16px;
            }}
            QFrame:hover {{
                border-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            }}
        """)
        
        card_layout = QHBoxLayout(card)
        card_layout.setSpacing(12)
        
        # Icon based on file type
        icon_label = QLabel()
        icon_label.setFixedSize(48, 48)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setStyleSheet(f"""
            QLabel {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border-radius: 8px;
                font-size: 24px;
            }}
        """)
        
        if file_type == "Excel":
            icon_label.setText("📊")
        elif file_type == "HTML":
            icon_label.setText("🌐")
        elif file_type == "JSON":
            icon_label.setText("📄")
        elif file_type == "ZIP":
            icon_label.setText("📦")
        else:
            icon_label.setText("📁")
            
        card_layout.addWidget(icon_label)
        
        # File info
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        file_name = os.path.basename(file_path)
        name_label = QLabel(file_name)
        name_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        name_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.DARK_TEXT};")
        info_layout.addWidget(name_label)
        
        # File size
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.1f} MB"
            size_label = QLabel(f"{file_type} • {size_str}")
        else:
            size_label = QLabel(f"{file_type}")
            
        size_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        size_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};")
        info_layout.addWidget(size_label)
        
        card_layout.addLayout(info_layout)
        card_layout.addStretch()
        
        # Action buttons
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        
        # Open button
        open_btn = QPushButton("Open")
        open_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {AnalyticsRunnerStylesheet.HOVER_COLOR};
            }}
        """)
        # Store file path as a property to avoid lambda capture issues
        open_btn.file_path = file_path
        open_btn.clicked.connect(lambda checked, path=file_path: self._open_report_file(path))
        button_layout.addWidget(open_btn)
        
        # Show in folder button
        folder_btn = QPushButton("Show in Folder")
        folder_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            }}
        """)
        # Store file path as a property to avoid lambda capture issues
        folder_btn.file_path = file_path
        folder_btn.clicked.connect(lambda checked, path=file_path: self._show_in_folder(path))
        button_layout.addWidget(folder_btn)
        
        card_layout.addLayout(button_layout)
        
        return card
    
    def _disconnect_widget_signals(self, widget):
        """Recursively disconnect all signals from a widget and its children to prevent orphaned connections"""
        try:
            # Disconnect signals from the widget itself if it has any
            if hasattr(widget, 'clicked'):
                widget.clicked.disconnect()
            if hasattr(widget, 'textChanged'):
                widget.textChanged.disconnect()
            if hasattr(widget, 'currentIndexChanged'):
                widget.currentIndexChanged.disconnect()
            if hasattr(widget, 'toggled'):
                widget.toggled.disconnect()
            
            # Recursively disconnect signals from all children
            for child in widget.findChildren(QPushButton):
                if hasattr(child, 'clicked'):
                    child.clicked.disconnect()
            
            for child in widget.findChildren(QComboBox):
                if hasattr(child, 'currentIndexChanged'):
                    child.currentIndexChanged.disconnect()
                if hasattr(child, 'currentTextChanged'):
                    child.currentTextChanged.disconnect()
            
            for child in widget.findChildren(QCheckBox):
                if hasattr(child, 'toggled'):
                    child.toggled.disconnect()
                    
        except Exception as e:
            # If disconnection fails, just log it but don't crash
            logger.debug(f"Signal disconnection warning: {e}")
    
    def _update_summary_tab(self, results: dict):
        """Update the Summary tab with validation results"""
        # Hide placeholder, show actual content
        if hasattr(self, 'summary_placeholder'):
            self.summary_placeholder.hide()
            
        # Update compliance rate
        summary = results.get('summary', {})
        compliance_rate = summary.get('compliance_rate', 0)
        self.compliance_rate_label.setText(f"{compliance_rate:.1%}")
        
        # Update status color based on rate
        if compliance_rate >= 0.95:
            color = AnalyticsRunnerStylesheet.SUCCESS_COLOR
        elif compliance_rate >= 0.8:
            color = AnalyticsRunnerStylesheet.WARNING_COLOR
        else:
            color = AnalyticsRunnerStylesheet.ERROR_COLOR
        self.compliance_rate_label.setStyleSheet(f"color: {color}; font-size: 32px; font-weight: bold;")
        
        # Update compliance counts
        compliance_counts = summary.get('compliance_counts', {})
        
        # Update GC pill
        gc_count = compliance_counts.get('GC', 0)
        self.gc_pill.setText(f"GC {gc_count}")
        self.gc_pill.count_text = str(gc_count)
            
        # Update PC pill
        pc_count = compliance_counts.get('PC', 0)
        self.pc_pill.setText(f"PC {pc_count}")
        self.pc_pill.count_text = str(pc_count)
            
        # Update DNC pill
        dnc_count = compliance_counts.get('DNC', 0)
        self.dnc_pill.setText(f"DNC {dnc_count}")
        self.dnc_pill.count_text = str(dnc_count)
            
        # Update execution details using the compact format
        timestamp = results.get('timestamp', 'N/A')
        if timestamp != 'N/A':
            try:
                dt = datetime.datetime.fromisoformat(timestamp)
                timestamp = dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        self.timestamp_label.setText(f"<b>Timestamp:</b> {timestamp}")
        
        # Rules count
        rules_applied = len(results.get('rules_applied', []))
        self.rules_count_label.setText(f"<b>Rules Applied:</b> {rules_applied}")
        
        # Execution time
        exec_time = results.get('execution_time', 0)
        if exec_time > 60:
            time_str = f"{exec_time/60:.1f} minutes"
        else:
            time_str = f"{exec_time:.1f} seconds"
        self.execution_time_label.setText(f"<b>Execution Time:</b> {time_str}")
        
        # Data source
        data_source = results.get('data_source', 'Unknown')
        data_source_name = os.path.basename(data_source) if data_source != 'Unknown' else data_source
        self.data_source_label.setText(f"<b>Data Source:</b> {data_source_name}")
        self.data_source_label.setToolTip(data_source)
        
    def _update_reports_tab(self, results: dict):
        """Update the Reports tab with generated files"""
        # Clear existing report cards - properly disconnect signals first
        while self.reports_container_layout.count():
            item = self.reports_container_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                # Disconnect all signals from buttons in the widget to prevent orphaned connections
                self._disconnect_widget_signals(widget)
                widget.deleteLater()
                
        output_files = results.get('output_files', [])
        
        if output_files:
            # Hide no reports label
            self.no_reports_label.hide()
            
            # Add report cards
            for file_path in output_files:
                # Determine file type
                if file_path.endswith('.xlsx'):
                    file_type = "Excel"
                elif file_path.endswith('.html'):
                    file_type = "HTML"
                elif file_path.endswith('.json'):
                    file_type = "JSON"
                elif file_path.endswith('.zip'):
                    file_type = "ZIP"
                else:
                    file_type = "File"
                    
                card = self._create_report_card(file_path, file_type)
                self.reports_container_layout.addWidget(card)
                
            # Check for leader packs
            leader_packs = results.get('leader_packs', {})
            if leader_packs.get('success') and leader_packs.get('zip_path'):
                card = self._create_report_card(
                    leader_packs['zip_path'], 
                    "ZIP"
                )
                self.reports_container_layout.addWidget(card)
        else:
            # Show no reports label
            self.no_reports_label.show()
            
        # Add stretch at the end
        self.reports_container_layout.addStretch()
        
    def _update_rule_details_tab(self, results: dict):
        """Update the Rule Details tab with rule execution information"""
        # Clear existing rule cards - properly disconnect signals first
        while self.rule_cards_layout.count():
            item = self.rule_cards_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                # Disconnect all signals from buttons in the widget to prevent orphaned connections
                self._disconnect_widget_signals(widget)
                widget.deleteLater()
        
        # Get rule details from results
        rule_details = results.get('rule_details', [])
        rules_applied = results.get('rules_applied', [])
        
        if rule_details or rules_applied:
            # Hide placeholder
            self.rule_details_placeholder.hide()
            
            # Create a card for each rule
            for i, rule_detail in enumerate(rule_details if rule_details else rules_applied):
                if isinstance(rule_detail, dict):
                    rule_name = rule_detail.get('name', f'Rule {i+1}')
                    status = rule_detail.get('status', 'Unknown')
                    passed = rule_detail.get('passed', 0)
                    failed = rule_detail.get('failed', 0)
                    errors = rule_detail.get('errors', 0)
                else:
                    # If we only have rule names, create minimal cards
                    rule_name = str(rule_detail)
                    status = 'Applied'
                    passed = 0
                    failed = 0
                    errors = 0
                
                card = self._create_rule_detail_card(rule_name, status, passed, failed, errors)
                self.rule_cards_layout.addWidget(card)
        else:
            # Show placeholder
            self.rule_details_placeholder.show()
            self.rule_cards_layout.addWidget(self.rule_details_placeholder)
        
        # Add stretch at the end
        self.rule_cards_layout.addStretch()
    
    def _create_rule_detail_card(self, rule_name: str, status: str, passed: int, failed: int, errors: int) -> QFrame:
        """Create a card widget for rule details"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 8px;
                padding: 12px;
            }}
            QFrame:hover {{
                border-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            }}
        """)
        
        layout = QHBoxLayout(card)
        layout.setSpacing(16)
        
        # Rule info section
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        
        # Rule name
        name_label = QLabel(rule_name)
        name_font = AnalyticsRunnerStylesheet.get_fonts()['regular']
        name_font.setBold(True)
        name_label.setFont(name_font)
        name_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.DARK_TEXT};")
        info_layout.addWidget(name_label)
        
        # Status
        status_color = {
            'Passed': AnalyticsRunnerStylesheet.SUCCESS_COLOR,
            'Failed': AnalyticsRunnerStylesheet.ERROR_COLOR,
            'Error': AnalyticsRunnerStylesheet.ERROR_COLOR,
            'Applied': AnalyticsRunnerStylesheet.PRIMARY_COLOR
        }.get(status, AnalyticsRunnerStylesheet.LIGHT_TEXT)
        
        status_label = QLabel(f"Status: {status}")
        status_label.setStyleSheet(f"color: {status_color}; font-weight: bold;")
        info_layout.addWidget(status_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # Stats section
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(24)
        
        # Passed
        passed_label = QLabel(f"✓ {passed:,}")
        passed_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR}; font-weight: bold;")
        stats_layout.addWidget(passed_label)
        
        # Failed
        failed_label = QLabel(f"✗ {failed:,}")
        failed_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.ERROR_COLOR}; font-weight: bold;")
        stats_layout.addWidget(failed_label)
        
        # Errors
        if errors > 0:
            error_label = QLabel(f"⚠ {errors:,}")
            error_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.WARNING_COLOR}; font-weight: bold;")
            stats_layout.addWidget(error_label)
        
        layout.addLayout(stats_layout)
        
        return card
    
    def _update_failed_items_tab(self, results: dict):
        """Update the Failed Items tab with validation failures"""
        # Clear existing items
        self.failed_items_table.setRowCount(0)
        
        # Get failed items from results
        failed_items = results.get('failed_items', [])
        
        if failed_items:
            # Show table
            self.failed_items_stack.setCurrentIndex(1)
            self.failed_items_export_btn.setEnabled(True)
            
            # Add rows
            self.failed_items_table.setRowCount(len(failed_items))
            
            for row, item in enumerate(failed_items):
                # Rule Name
                self.failed_items_table.setItem(row, 0, QTableWidgetItem(item.get('rule_name', '')))
                
                # Column
                self.failed_items_table.setItem(row, 1, QTableWidgetItem(item.get('column', '')))
                
                # Row
                self.failed_items_table.setItem(row, 2, QTableWidgetItem(str(item.get('row', ''))))
                
                # Value
                self.failed_items_table.setItem(row, 3, QTableWidgetItem(str(item.get('value', ''))))
                
                # Reason
                self.failed_items_table.setItem(row, 4, QTableWidgetItem(item.get('reason', '')))
        else:
            # Show placeholder
            self.failed_items_stack.setCurrentIndex(0)
            self.failed_items_export_btn.setEnabled(False)
    
    def _filter_rule_details(self, filter_text: str):
        """Filter rule detail cards based on status"""
        # This will be implemented when we have actual rule details
        pass
    
    def _export_failed_items(self):
        """Export failed items to CSV"""
        if self.failed_items_table.rowCount() == 0:
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Failed Items",
            "failed_items.csv",
            "CSV Files (*.csv)"
        )
        
        if file_path:
            try:
                # Create data for export
                data = []
                for row in range(self.failed_items_table.rowCount()):
                    row_data = []
                    for col in range(self.failed_items_table.columnCount()):
                        item = self.failed_items_table.item(row, col)
                        row_data.append(item.text() if item else '')
                    data.append(row_data)
                
                # Create DataFrame and export
                df = pd.DataFrame(data, columns=[
                    "Rule Name", "Column", "Row", "Value", "Reason"
                ])
                df.to_csv(file_path, index=False)
                
                self.log_message(f"Failed items exported to: {file_path}")
                QMessageBox.information(self, "Export Complete", "Failed items exported successfully!")
                
            except Exception as e:
                self.log_message(f"Error exporting failed items: {str(e)}", "ERROR")
                QMessageBox.critical(self, "Export Error", f"Failed to export: {str(e)}")
        
    def _open_report_file(self, file_path: str):
        """Open a report file with the default application"""
        import subprocess
        import platform
        
        try:
            if platform.system() == 'Windows':
                os.startfile(file_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', file_path])
            else:  # Linux
                subprocess.run(['xdg-open', file_path])
        except Exception as e:
            QMessageBox.warning(
                self, 
                "Error Opening File", 
                f"Could not open file: {str(e)}"
            )
            
    def _show_in_folder(self, file_path: str):
        """Show file in folder/explorer"""
        import subprocess
        import platform
        
        try:
            if platform.system() == 'Windows':
                subprocess.run(['explorer', '/select,', os.path.normpath(file_path)])
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', '-R', file_path])
            else:  # Linux
                folder = os.path.dirname(file_path)
                subprocess.run(['xdg-open', folder])
        except Exception as e:
            QMessageBox.warning(
                self, 
                "Error", 
                f"Could not open folder: {str(e)}"
            )
    
    def clear_results(self):
        """Clear all results from the Results & Reports tab"""
        # Update status
        self.results_status_label.setText("No results loaded")
        self.results_status_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                padding: 4px 8px;
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
            }}
        """)
        
        # Disable clear button
        self.clear_results_button.setEnabled(False)
        
        # Clear Summary tab
        self.compliance_rate_label.setText("--")
        self.compliance_rate_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR}; font-size: 32px; font-weight: bold;")
        
        # Reset status pills
        self.gc_pill.setText("GC 0")
        self.gc_pill.count_text = "0"
        self.pc_pill.setText("PC 0")
        self.pc_pill.count_text = "0"
        self.dnc_pill.setText("DNC 0")
        self.dnc_pill.count_text = "0"
            
        # Reset execution details
        self.timestamp_label.setText("<b>Timestamp:</b> --")
        self.rules_count_label.setText("<b>Rules Applied:</b> --")
        self.execution_time_label.setText("<b>Execution Time:</b> --")
        self.data_source_label.setText("<b>Data Source:</b> --")
        self.data_source_label.setToolTip("")
        
        # Clear Rule Details tab
        while self.rule_cards_layout.count():
            item = self.rule_cards_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                self._disconnect_widget_signals(widget)
                widget.deleteLater()
        self.rule_details_placeholder.show()
        self.rule_cards_layout.addWidget(self.rule_details_placeholder)
        
        # Clear Failed Items tab
        self.failed_items_table.setRowCount(0)
        self.failed_items_stack.setCurrentIndex(0)
        self.failed_items_export_btn.setEnabled(False)
        
        # Clear Reports tab
        while self.reports_container_layout.count():
            item = self.reports_container_layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                self._disconnect_widget_signals(widget)
                widget.deleteLater()
        self.no_reports_label.show()
        
        # Clear the side panel results view
        if hasattr(self, 'results_view'):
            self.results_view.tree_widget.clear()
            self.results_view.failing_items_cache.clear()
        
        self.log_message("Results cleared", "INFO")

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

        # Results tab with interactive tree widget
        self.results_view = ResultsTreeWidget()
        self.results_view.ruleSelected.connect(self._on_result_rule_selected)
        self.results_view.exportRequested.connect(self._on_result_export_requested)
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

            # Sync initial debug mode state only if UI elements exist
            if hasattr(self, 'debug_checkbox') and self.debug_checkbox:
                self.debug_checkbox.setChecked(self.error_handler.debug_mode)
            if hasattr(self, 'debug_mode_action') and self.debug_mode_action:
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

        # Only append to log_view if it exists
        if hasattr(self, 'log_view') and self.log_view is not None:
            self.log_view.append(formatted_message)

        # Always log to file/console
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

        # Display metadata in results tree widget
        metadata_results = {
            'status': 'METADATA',
            'timestamp': datetime.datetime.now().isoformat(),
            'message': '\n'.join(metadata_text),
            'summary': {
                'total_rules': 0,
                'compliance_counts': {}
            }
        }
        self.results_view.load_results(metadata_results)

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

            # Create preview results for tree widget
            preview_results = {
                'status': 'PREVIEW',
                'timestamp': datetime.datetime.now().isoformat(),
                'message': summary_text,
                'summary': {
                    'total_rules': 0,
                    'compliance_counts': {}
                },
                'data_metrics': {
                    'row_count': rows,
                    'column_count': cols,
                    'columns': list(preview_df.columns)
                }
            }
            self.results_view.load_results(preview_results)
            
            # Update responsible party dropdown with column names
            self.responsible_party_combo.clear()
            self.responsible_party_combo.addItem("None")
            self.responsible_party_combo.addItems(list(preview_df.columns))
            self.responsible_party_combo.setEnabled(True)
            self.responsible_party_combo.setCurrentIndex(0)  # Default to "None"
            
        else:
            self.log_message("Data preview cleared", "INFO")

            # Disable save action when no valid preview
            self.save_source_action.setEnabled(False)
            
            # Clear and disable responsible party dropdown
            self.responsible_party_combo.clear()
            self.responsible_party_combo.addItem("None")
            self.responsible_party_combo.setEnabled(False)

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

    def browse_output_directory(self):
        """Browse for output directory."""
        current_dir = self.output_dir_edit.text()
        if not os.path.exists(current_dir):
            current_dir = os.getcwd()
            
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            current_dir,
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.output_dir_edit.setText(directory)
            self.log_message(f"Output directory set to: {directory}")
            
    def _on_report_option_changed(self):
        """Handle report option checkbox changes."""
        # Enable/disable output directory selection based on report options
        reports_enabled = (self.excel_report_checkbox.isChecked() or 
                          self.html_report_checkbox.isChecked())
        
        self.output_dir_edit.setEnabled(reports_enabled)
        self.output_dir_button.setEnabled(reports_enabled)
        
        if not reports_enabled:
            self.log_message("Report generation disabled - only JSON results will be saved", "INFO")
    
    def _on_leader_packs_changed(self, checked: bool):
        """Handle leader packs checkbox changes."""
        if checked and self.responsible_party_combo.currentIndex() == 0:  # "None" selected
            self.leader_packs_warning.setVisible(True)
            self.log_message("Leader packs require a responsible party column to be selected", "WARNING")
        else:
            self.leader_packs_warning.setVisible(False)
            if checked:
                self.log_message("Audit Leader-Specific Workbooks will be generated", "INFO")
    
    def _on_responsible_party_changed(self, index: int):
        """Handle responsible party column selection changes."""
        # Update leader packs warning visibility
        if self.leader_packs_checkbox.isChecked() and index == 0:  # "None" selected
            self.leader_packs_warning.setVisible(True)
        else:
            self.leader_packs_warning.setVisible(False)

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

        # Update UI state for execution
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.execution_status_label.setText("Status: Active")
        self.execution_status_label.setStyleSheet(f"""
            color: white; 
            background-color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR};
            font-weight: bold;
            padding: 4px 8px;
            border: none;
            border-radius: 4px;
        """)
        self.start_validation_action.setEnabled(False)
        self.stop_validation_action.setEnabled(True)
        self.show_progress(True)
        self.update_progress(0, "Initializing validation...")

        # Get new execution parameters
        analytic_id = self.analytic_id_input.text().strip()
        if not analytic_id:
            # Use default timestamp format if empty
            analytic_id = f"Analytics_Validation_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        else:
            # Validate analytic ID (no special characters that could cause issues)
            if not all(c.isalnum() or c in ['_', '-', ' '] for c in analytic_id):
                QMessageBox.warning(
                    self, 
                    "Invalid Analytic ID", 
                    "Analytic ID can only contain letters, numbers, spaces, hyphens, and underscores."
                )
                self.start_button.setEnabled(True)
                self.cancel_button.setEnabled(False)
                self.execution_status_label.setText("Status: Ready")
                self.execution_status_label.setStyleSheet(f"""
                    color: {AnalyticsRunnerStylesheet.DARK_TEXT}; 
                    background-color: transparent;
                    font-weight: bold;
                    padding: 4px 8px;
                    border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                    border-radius: 4px;
                """)
                return
        
        execution_mode = self.execution_mode_combo.currentText()
        use_parallel = (execution_mode == "Parallel")
        
        responsible_party_column = None
        if self.responsible_party_combo.currentIndex() > 0:  # Not "None"
            responsible_party_column = self.responsible_party_combo.currentText()
        
        # Log execution parameters
        self.log_message(f"Analytic ID: {analytic_id}")
        self.log_message(f"Execution Mode: {execution_mode}")
        if responsible_party_column:
            self.log_message(f"Responsible Party Column: {responsible_party_column}")
        
        # Check leader packs settings
        generate_leader_packs = self.leader_packs_checkbox.isChecked() and responsible_party_column is not None
        if self.leader_packs_checkbox.isChecked() and not responsible_party_column:
            self.log_message("Leader packs requested but no responsible party column selected - will be skipped", "WARNING")
        
        # Collect report generation options
        generate_reports = self.excel_report_checkbox.isChecked() or self.html_report_checkbox.isChecked()
        report_formats = []
        if self.excel_report_checkbox.isChecked():
            report_formats.append('excel')
        if self.html_report_checkbox.isChecked():
            report_formats.append('html')
        
        # Always include JSON for results
        report_formats.append('json')
        
        output_dir = self.output_dir_edit.text()
        
        # Debug logging
        self.log_message(f"Report generation enabled: {generate_reports}")
        self.log_message(f"Report formats requested: {report_formats}")
        self.log_message(f"Output directory: {output_dir}")
        if generate_leader_packs:
            self.log_message("Audit Leader-Specific Workbooks will be generated", "INFO")

        # Create and start cancellable validation worker
        self.validation_worker = CancellableValidationWorker(
            pipeline=None,  # Will be created in worker
            data_source=data_source_file,
            sheet_name=sheet_name,
            analytic_id=analytic_id,  # Use the validated analytic ID
            rule_ids=selected_rules,  # Pass selected rules
            generate_reports=generate_reports,
            report_formats=report_formats,
            output_dir=output_dir,
            use_parallel=use_parallel,
            responsible_party_column=responsible_party_column,
            generate_leader_packs=generate_leader_packs
        )

        # Connect worker signals
        self.validation_worker.signals.started.connect(self._on_validation_started)
        self.validation_worker.signals.progress.connect(self.update_progress)
        self.validation_worker.signals.result.connect(self._on_validation_complete)
        self.validation_worker.signals.error.connect(self._on_validation_error)
        self.validation_worker.signals.finished.connect(self._on_validation_finished)
        
        # Connect real-time progress tracking signals
        self.validation_worker.signals.progressUpdated.connect(self._on_progress_updated)
        self.validation_worker.signals.statusUpdated.connect(self._on_status_updated)
        self.validation_worker.signals.ruleStarted.connect(self._on_rule_started)
        
        # Connect report generation signals
        self.validation_worker.signals.reportStarted.connect(self._on_report_started)
        self.validation_worker.signals.reportProgress.connect(self.update_progress)
        self.validation_worker.signals.reportCompleted.connect(self._on_report_completed)
        self.validation_worker.signals.reportError.connect(self._on_report_error)
        
        # Connect execution management signals
        self.validation_worker.signals.sessionStarted.connect(self._on_session_started)
        self.validation_worker.signals.statusChanged.connect(self._on_execution_status_changed)
        self.validation_worker.signals.cancelled.connect(self._on_validation_cancelled)

        # Start worker
        self.threadpool.start(self.validation_worker)

    # ADD these new methods to the AnalyticsRunnerApp class:
    def _on_validation_started(self):
        """Handle validation start."""
        self.log_message("Validation started")
        # Show progress section
        self.progress_section.setVisible(True)
        self.validation_progress_bar.setVisible(True)
        self.validation_status_label.setVisible(True)
        self.rule_summary_label.setVisible(True)
        self.validation_progress_bar.setValue(0)

    def _on_validation_complete(self, results: dict):
        """Handle validation completion with results."""
        self.log_message("Validation completed successfully")

        # Update status in Results & Reports tab
        self.results_status_label.setText("Results loaded")
        self.results_status_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR};
                padding: 4px 8px;
                border: 1px solid {AnalyticsRunnerStylesheet.SUCCESS_COLOR};
                border-radius: 4px;
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
            }}
        """)
        self.clear_results_button.setEnabled(True)
        
        # Update Summary tab
        self._update_summary_tab(results)
        
        # Update Rule Details tab
        self._update_rule_details_tab(results)
        
        # Update Failed Items tab
        self._update_failed_items_tab(results)
        
        # Update Reports tab
        self._update_reports_tab(results)
        
        # Load results into interactive tree widget (in side panel for now)
        self.results_view.load_results(results)

        # Switch to Results & Reports tab and Summary sub-tab
        for i in range(self.mode_tabs.count()):
            if self.mode_tabs.tabText(i) == "Results & Reports":
                self.mode_tabs.setCurrentIndex(i)
                self.results_reports_tabs.setCurrentIndex(0)  # Summary tab
                break

    def _on_validation_error(self, error_message: str):
        """Handle validation error."""
        self.log_message(f"Validation failed: {error_message}", "ERROR")
        QMessageBox.critical(self, "Validation Error", f"Validation failed:\n\n{error_message}")
        
        # Update status in Results & Reports tab
        self.results_status_label.setText("Validation failed")
        self.results_status_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.ERROR_COLOR};
                padding: 4px 8px;
                border: 1px solid {AnalyticsRunnerStylesheet.ERROR_COLOR};
                border-radius: 4px;
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
            }}
        """)
        
        # Create error results for display
        error_results = {
            'status': 'ERROR',
            'timestamp': datetime.datetime.now().isoformat(),
            'error': error_message,
            'summary': {'total_rules': 0, 'compliance_counts': {'GC': 0, 'PC': 0, 'DNC': 0}, 'compliance_rate': 0},
            'rules_applied': [],
            'execution_time': 0,
            'data_source': 'N/A',
            'output_files': []
        }
        
        # Update tabs with error state
        self._update_summary_tab(error_results)
        self._update_rule_details_tab(error_results)
        self._update_failed_items_tab(error_results)
        self._update_reports_tab(error_results)
        
        # Still update the side panel
        self.results_view.load_results(error_results)
        
        # Switch to Results & Reports tab
        for i in range(self.mode_tabs.count()):
            if self.mode_tabs.tabText(i) == "Results & Reports":
                self.mode_tabs.setCurrentIndex(i)
                self.results_reports_tabs.setCurrentIndex(0)  # Summary tab
                break

    def _on_validation_finished(self):
        """Handle validation worker finished (cleanup)."""
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancel")
        self.start_validation_action.setEnabled(True)
        self.stop_validation_action.setEnabled(False)
        self.show_progress(False)
        self.status_label.setText("Validation completed")
        
        # Reset execution status if not already set
        if hasattr(self, 'execution_status_label'):
            current_status = self.execution_status_label.text()
            if "Active" in current_status:
                self.execution_status_label.setText("Status: Ready")
                self.execution_status_label.setStyleSheet(f"""
                    color: {AnalyticsRunnerStylesheet.DARK_TEXT}; 
                    background-color: transparent;
                    font-weight: bold;
                    padding: 4px 8px;
                    border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                    border-radius: 4px;
                """)
        
        # Hide progress after a delay
        QTimer.singleShot(3000, self._hide_progress_section)
    
    def _on_progress_updated(self, progress: int):
        """Handle real-time progress updates."""
        if progress == -1:
            # Error state
            self.validation_progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                    border: 1px solid {AnalyticsRunnerStylesheet.ERROR_COLOR};
                    border-radius: 4px;
                    text-align: center;
                    min-height: 20px;
                }}
                QProgressBar::chunk {{
                    background-color: {AnalyticsRunnerStylesheet.ERROR_COLOR};
                    border-radius: 3px;
                }}
            """)
        else:
            self.validation_progress_bar.setValue(progress)
    
    def _on_status_updated(self, status: str):
        """Handle status message updates."""
        self.validation_status_label.setText(status)
        
        # Extract ETA if present
        if "ETA:" in status:
            eta_match = status.find("ETA:")
            if eta_match != -1:
                eta_text = status[eta_match:]
                self.validation_status_label.setToolTip(eta_text)
    
    def _on_rule_started(self, rule_name: str, current: int, total: int):
        """Handle individual rule start notification."""
        self.rule_summary_label.setText(f"Rule {current} of {total}: {rule_name}")
        
        # Also update in log for detailed tracking
        self.log_message(f"Evaluating rule {current}/{total}: {rule_name}")
    
    def _hide_progress_section(self):
        """Hide the progress section with animation."""
        self.progress_section.setVisible(False)
    
    def cancel_validation(self):
        """Cancel the running validation."""
        if hasattr(self, 'validation_worker') and self.validation_worker:
            self.log_message("Cancellation requested by user")
            self.validation_worker.cancel("User requested cancellation")
            self.cancel_button.setEnabled(False)
            self.cancel_button.setText("Cancelling...")
    
    def _on_session_started(self, session_id: str, timestamp: str):
        """Handle session start notification."""
        self.session_info_label.setText(f"Session: {session_id} | Started: {timestamp}")
        self.session_info_label.setVisible(True)
        self.log_message(f"Validation session started: {session_id}")
    
    def _on_execution_status_changed(self, status: str):
        """Handle execution status changes."""
        self.execution_status_label.setText(f"Status: {status}")
        
        # Update status styling based on state
        if status == ExecutionStatus.ACTIVE:
            bg_color = AnalyticsRunnerStylesheet.SUCCESS_COLOR
            text_color = "white"
        elif status == ExecutionStatus.CANCELLED:
            bg_color = AnalyticsRunnerStylesheet.WARNING_COLOR
            text_color = "black"
        elif status == ExecutionStatus.ERROR:
            bg_color = AnalyticsRunnerStylesheet.ERROR_COLOR
            text_color = "white"
        elif status == ExecutionStatus.COMPLETED:
            bg_color = AnalyticsRunnerStylesheet.INFO_COLOR
            text_color = "white"
        else:
            bg_color = AnalyticsRunnerStylesheet.SURFACE_COLOR
            text_color = AnalyticsRunnerStylesheet.DARK_TEXT
            
        self.execution_status_label.setStyleSheet(f"""
            color: {text_color}; 
            background-color: {bg_color};
            font-weight: bold;
            padding: 4px 8px;
            border: none;
            border-radius: 4px;
        """)
    
    def _on_validation_cancelled(self, reason: str):
        """Handle validation cancellation."""
        self.log_message(f"Validation cancelled: {reason}")
        self.cancel_button.setText("Cancel")
        self.cancel_button.setEnabled(False)
        
        # Update progress to show cancellation
        self.validation_progress_bar.setValue(100)
        self.validation_status_label.setText("Validation cancelled")
        
        # Create cancelled results for display
        cancelled_results = {
            'status': 'CANCELLED',
            'timestamp': datetime.datetime.now().isoformat(),
            'message': reason,
            'summary': {'total_rules': 0, 'compliance_counts': {}}
        }
        if hasattr(self, 'results_view'):
            self.results_view.load_results(cancelled_results)
            
        QMessageBox.information(self, "Validation Cancelled", f"The validation was cancelled:\n{reason}")

    def _format_validation_results(self, results: dict) -> str:
        """Format validation results for text display with detailed item counts per rule."""
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

        # Add detailed rule results with item counts
        rule_results = results.get('rule_results', {})
        if rule_results:
            lines.append("=== RULE RESULTS (WITH ITEM COUNTS) ===")
            lines.append("")
            
            # Sort rules by name for consistent display
            sorted_rules = sorted(rule_results.items(), key=lambda x: x[1].rule.name if hasattr(x[1], 'rule') else x[0])
            
            for rule_id, result in sorted_rules:
                try:
                    # Extract rule information
                    if hasattr(result, 'rule'):
                        rule_name = result.rule.name
                        rule_status = result.compliance_status
                    else:
                        # Fallback if structure is different
                        rule_name = rule_id
                        rule_status = "UNKNOWN"
                    
                    # Get summary data with safe defaults
                    if hasattr(result, 'summary'):
                        result_summary = result.summary
                    else:
                        result_summary = {}
                    
                    # Extract counts with safe defaults
                    total_items = result_summary.get('total_items', 0)
                    gc_count = result_summary.get('gc_count', 0)
                    pc_count = result_summary.get('pc_count', 0)
                    dnc_count = result_summary.get('dnc_count', 0)
                    
                    # Calculate passed and failed
                    passed = gc_count
                    failed = dnc_count + pc_count  # PC treated as failed per requirements
                    
                    # Format the rule result line
                    if total_items > 0:
                        lines.append(f"{rule_name}: {rule_status} ({passed} passed, {failed} failed out of {total_items} total)")
                    else:
                        lines.append(f"{rule_name}: {rule_status} (No data processed)")
                        
                except Exception as e:
                    # Handle any unexpected structure
                    logger.warning(f"Error formatting rule result {rule_id}: {str(e)}")
                    lines.append(f"{rule_id}: Error displaying results")
                    
            lines.append("")

        exec_time = results.get('execution_time', 0)
        lines.append(f"Execution Time: {exec_time:.2f} seconds")

        # Add generated files if any
        output_files = results.get('output_files', [])
        if output_files:
            lines.append("")
            lines.append("=== GENERATED REPORTS ===")
            for file_path in output_files:
                file_name = os.path.basename(file_path)
                lines.append(f"• {file_name}")

        return "\n".join(lines)
    
    def _on_report_started(self):
        """Handle report generation start."""
        self.log_message("Report generation started")
        
    def _on_report_completed(self, report_info: dict):
        """Handle report generation completion."""
        # Check if this is a leader pack report
        if report_info.get('type') == 'leader_packs':
            self._handle_leader_pack_results(report_info.get('results', {}))
            return
            
        self.log_message("Reports generated successfully")
        
        # Display report files in results view
        output_files = report_info.get('output_files', [])
        if output_files:
            # Append to existing results
            current_text = self.results_view.toPlainText()
            
            report_text = [
                "",
                "=== GENERATED REPORTS ===",
                f"Output Directory: {report_info.get('output_dir', 'unknown')}",
                ""
            ]
            
            for file_path in output_files:
                file_name = os.path.basename(file_path)
                file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
                size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / (1024 * 1024):.1f} MB"
                
                # Format based on file type
                if file_path.endswith('.xlsx'):
                    icon = "📊"
                    desc = "Excel Report"
                elif file_path.endswith('.html'):
                    icon = "🌐"
                    desc = "HTML Report"
                elif file_path.endswith('.json'):
                    icon = "📄"
                    desc = "JSON Results"
                else:
                    icon = "📁"
                    desc = "Report File"
                    
                report_text.append(f"{icon} {file_name} ({size_str}) - {desc}")
                report_text.append(f"   Path: {file_path}")
                
            # For ResultsTreeWidget, we need to refresh with updated data
            # This is handled by the tree widget's report display
            
    def _on_report_error(self, error_msg: str):
        """Handle report generation error."""
        self.log_message(f"Report generation error: {error_msg}", "ERROR")
        QMessageBox.warning(
            self,
            "Report Generation Error",
            f"Failed to generate some reports:\n\n{error_msg}\n\nValidation results have still been saved."
        )
        
    def _handle_leader_pack_results(self, leader_pack_results: dict):
        """Handle leader pack generation results."""
        if leader_pack_results.get('success'):
            # Count the number of leader packs generated
            leader_reports = leader_pack_results.get('leader_reports', {})
            num_packs = len(leader_reports)
            
            self.log_message(f"Successfully generated {num_packs} Audit Leader-Specific Workbooks")
            
            # Show success message with details
            zip_path = leader_pack_results.get('zip_path', '')
            if zip_path and os.path.exists(zip_path):
                file_size = os.path.getsize(zip_path)
                size_str = f"{file_size / (1024 * 1024):.1f} MB" if file_size > 1024 * 1024 else f"{file_size / 1024:.1f} KB"
                
                message = f"Successfully generated {num_packs} Audit Leader-Specific Workbooks\n\n"
                message += f"ZIP file created: {os.path.basename(zip_path)} ({size_str})\n"
                message += f"Location: {zip_path}"
                
                QMessageBox.information(self, "Leader Packs Generated", message)
            else:
                # Just show count if no ZIP
                QMessageBox.information(
                    self, 
                    "Leader Packs Generated", 
                    f"Successfully generated {num_packs} Audit Leader-Specific Workbooks"
                )
        else:
            # Handle failure
            error_msg = leader_pack_results.get('error', 'Unknown error')
            self.log_message(f"Failed to generate leader packs: {error_msg}", "WARNING")
            
            # Don't show a warning dialog - just log it
            # This is as requested: "failures shouldn't block the validation from completing"

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

        # Show mock results in tree widget
        mock_results = {
            'status': 'MOCK',
            'timestamp': datetime.datetime.now().isoformat(),
            'message': "Validation Results:\n\nMock results - functionality will be implemented in later phases.",
            'summary': {
                'total_rules': 0,
                'compliance_counts': {}
            }
        }
        self.results_view.load_results(mock_results)

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
    
    def _on_result_rule_selected(self, rule_id: str):
        """Handle rule selection in results tree"""
        self.log_message(f"Rule selected for details: {rule_id}")
        
    def _on_result_export_requested(self, rule_id: str, df: pd.DataFrame):
        """Handle export request from results tree"""
        self.log_message(f"Exported {len(df)} failing items for rule: {rule_id}")


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
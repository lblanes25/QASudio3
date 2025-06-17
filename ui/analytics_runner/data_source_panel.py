"""
Simplified DataSourcePanel - Clean, Minimal Data Source Selection
Addresses UI clutter and redundancy issues with streamlined design
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import pandas as pd

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QFrame, QMessageBox, QFileDialog, QHeaderView,
)
from PySide6.QtCore import Signal, QThread, Qt

from ui.common.stylesheet import AnalyticsRunnerStylesheet
from ui.common.widgets.pre_validation_widget import PreValidationWidget
from ui.common.widgets.clickable_label import ClickableLabel
from ui.analytics_runner.dialogs.save_data_source_dialog import SaveDataSourceDialog
from ui.analytics_runner.data_source_registry import DataSourceRegistry
from core.lookup.smart_lookup_manager import SmartLookupManager

logger = logging.getLogger(__name__)


class FilePreviewWorker(QThread):
    """Worker thread for loading file previews without blocking UI."""

    # Signals
    previewLoaded = Signal(object, dict)  # DataFrame, metadata
    error = Signal(str)  # Error message

    def __init__(self, file_path: str, sheet_name: str = None, max_rows: int = 100):
        super().__init__()
        self.file_path = file_path
        self.sheet_name = sheet_name
        self.max_rows = max_rows
        self._should_stop = False

    def stop(self):
        """Request the worker to stop."""
        self._should_stop = True

    def run(self):
        """Load file preview in background thread."""
        try:
            if self._should_stop:
                return

            # Import here to avoid issues with thread imports
            from data_integration.io.importer import DataImporter

            data_importer = DataImporter()

            # Load preview with parameters
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

            # Emit results
            self.previewLoaded.emit(preview_df, metadata)

        except Exception as e:
            error_msg = f"Error loading file preview: {str(e)}"
            logger.error(error_msg)
            self.error.emit(error_msg)


class SheetSelectionWorker(QThread):
    """Worker thread for getting Excel sheet names."""

    # Signals
    sheetsLoaded = Signal(list)  # List of sheet names
    error = Signal(str)  # Error message

    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path

    def run(self):
        """Get sheet names in background thread."""
        try:
            # Import here to avoid issues with thread imports
            from data_integration.connectors.excel_connector import ExcelConnector

            connector = ExcelConnector({'file_path': self.file_path})
            if connector.connect():
                sheet_names = connector.get_sheet_names()
                connector.disconnect()
                self.sheetsLoaded.emit(sheet_names)
            else:
                self.error.emit("Could not connect to Excel file")

        except Exception as e:
            error_msg = f"Error getting sheet names: {str(e)}"
            logger.error(error_msg)
            self.error.emit(error_msg)


class DataSourcePanel(QWidget):

    # Signals
    dataSourceChanged = Signal(str)  # File path
    dataSourceValidated = Signal(bool, str)  # Is valid, message
    sheetChanged = Signal(str)  # Sheet name for Excel files
    previewUpdated = Signal(object)  # Preview DataFrame
    columnsDetected = Signal(list)  # List of column names when data is loaded
    lookupFileLoaded = Signal(str)  # Message when file is loaded for LOOKUP

    def __init__(self, session_manager=None, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.session_manager = session_manager
        self._current_file = ""
        self._current_sheet = None
        self._preview_df = None
        self._file_metadata = {}
        self._is_excel_file = False

        # Initialize data source registry
        self.data_source_registry = DataSourceRegistry(session_manager=session_manager)

        # Initialize SmartLookupManager
        self.lookup_manager = SmartLookupManager()

        # Worker threads
        self._preview_worker = None
        self._sheet_worker = None

        # Setup UI
        self._setup_ui()
        self._setup_connections()

        # Load recent files if session manager available
        if self.session_manager:
            self._load_recent_files()

        logger.debug("SimplifiedDataSourcePanel initialized")

    def _setup_ui(self):
        """Setup the simplified user interface."""
        # Main layout with reduced spacing
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(16)  # Reduced from 24
        self.main_layout.setContentsMargins(12, 12, 12, 12)  # Reduced padding

        # File selection section - single clean row
        self._create_file_selection_section()

        # Excel sheet selection (initially hidden)
        self._create_sheet_selection_section()

        # Data preview section - expanded and cleaner
        self._create_preview_section()

        # Pre-validation widget
        self.pre_validation_widget = PreValidationWidget()
        self.main_layout.addWidget(self.pre_validation_widget)

    def _save_data_source(self):
        """Open the save data source dialog."""
        if not self._current_file or self._preview_df is None or self._preview_df.empty:
            QMessageBox.warning(
                self,
                "No Data to Save",
                "Please load a valid data source before saving."
            )
            return

        try:
            # Create and show the save dialog
            dialog = SaveDataSourceDialog(
                file_path=self._current_file,
                sheet_name=self._current_sheet,
                preview_df=self._preview_df,
                registry=self.data_source_registry,
                parent=self
            )

            # Connect to success signal
            dialog.dataSourceSaved.connect(self._on_data_source_saved)

            # Show dialog
            dialog.exec()

        except Exception as e:
            error_msg = f"Error opening save dialog: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Save Error", error_msg)

    def _on_data_source_saved(self, source_id: str):
        """Handle successful data source save."""
        logger.info(f"Data source saved with ID: {source_id}")

        # Update recent files or other UI elements as needed
        # Could emit a signal here for other components to refresh their data source lists

        # Show brief success message in status or log
        if hasattr(self.parent(), 'log_message'):
            self.parent().log_message(f"Data source saved successfully: {source_id}")

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

    def _apply_connection_parameters(self, connection_params):
        """Apply saved connection parameters to the current data source."""
        # Handle Excel sheet selection
        sheet_name = connection_params.get('sheet_name')
        if sheet_name and self._is_excel_file:
            # Store the target sheet name for when sheets are loaded
            self._target_sheet_name = sheet_name
            logger.debug(f"Will set Excel sheet to: {sheet_name}")

        # Handle other connection parameters (cell range, etc.)
        cell_range = connection_params.get('range')
        if cell_range:
            # Store for later use in data loading
            self._target_cell_range = cell_range
            logger.debug(f"Will use cell range: {cell_range}")

    def _create_file_selection_section(self):
        """Create simplified file selection section."""
        # Container frame
        file_frame = QFrame()
        file_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 6px;
                padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
            }}
        """)

        file_layout = QVBoxLayout(file_frame)
        file_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)

        # Title
        title_label = QLabel("Data Source")
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
        selection_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)

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

        # Recent files button (collapsed)
        self.recent_button = QPushButton("Recent ▼")
        self.recent_button.setProperty("buttonStyle", "secondary")
        self.recent_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.recent_button.clicked.connect(self._show_recent_files)
        selection_layout.addWidget(self.recent_button)
        
        # Add lookup files button
        self.lookup_files_button = QPushButton("Add Lookup Files")
        self.lookup_files_button.setProperty("buttonStyle", "secondary")
        self.lookup_files_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.lookup_files_button.setToolTip("Load multiple files for LOOKUP operations")
        self.lookup_files_button.clicked.connect(self._browse_lookup_files)
        selection_layout.addWidget(self.lookup_files_button)

        # Clear button (only shown when file selected)
        self.clear_button = QPushButton("Clear")
        self.clear_button.setProperty("buttonStyle", "secondary")
        self.clear_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.clear_button.clicked.connect(self.clear_selection)
        self.clear_button.setVisible(False)
        selection_layout.addWidget(self.clear_button)

        file_layout.addLayout(selection_layout)

        # Save source button row (NEW)
        save_layout = QHBoxLayout()
        save_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)

        save_layout.addStretch()  # Push button to the right

        # Save source button
        self.save_source_button = QPushButton("Save Source")
        self.save_source_button.setProperty("buttonStyle", "secondary")
        self.save_source_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.save_source_button.setToolTip("Save this data source configuration for future use")
        self.save_source_button.clicked.connect(self._save_data_source)
        self.save_source_button.setEnabled(False)  # Disabled until valid data is loaded
        save_layout.addWidget(self.save_source_button)

        file_layout.addLayout(save_layout)

        # Drag and drop support
        self._setup_drag_drop(file_frame)

        self.main_layout.addWidget(file_frame)
        
        # Lookup status section
        self._create_lookup_status_section()

    def _create_lookup_status_section(self):
        """Create the lookup status section with clickable label."""
        # Create a frame for the lookup status
        lookup_frame = QFrame()
        lookup_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 8px;
                padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
                margin-top: 8px;
            }}
        """)
        
        lookup_layout = QHBoxLayout(lookup_frame)
        lookup_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        
        # Create the clickable lookup status label
        self.lookup_status = ClickableLabel("📁 No lookup files loaded")
        self.lookup_status.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
                padding: 4px;
                background-color: transparent;
            }}
            QLabel:hover {{
                color: {AnalyticsRunnerStylesheet.HOVER_COLOR};
            }}
        """)
        self.lookup_status.clicked.connect(self._show_lookup_details)
        
        lookup_layout.addWidget(self.lookup_status)
        lookup_layout.addStretch()
        
        self.main_layout.addWidget(lookup_frame)
        
        # Initialize the status
        self.update_lookup_status()
    
    def _create_sheet_selection_section(self):
        """Create Excel sheet selection section."""
        self.sheet_frame = QFrame()
        self.sheet_frame.setVisible(False)
        self.sheet_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR}40;
                border-radius: 6px;
                padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
            }}
        """)

        sheet_layout = QHBoxLayout(self.sheet_frame)
        sheet_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)

        # Sheet label
        sheet_label = QLabel("Excel Sheet:")
        sheet_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        sheet_layout.addWidget(sheet_label)

        # Sheet dropdown
        self.sheet_combo = QComboBox()
        self.sheet_combo.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.sheet_combo.setMinimumWidth(150)
        sheet_layout.addWidget(self.sheet_combo)

        sheet_layout.addStretch()
        self.main_layout.addWidget(self.sheet_frame)

    def _create_preview_section(self):
        """Create expanded data preview section - Updated to use centralized stylesheet."""
        # Preview container
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

        # Header row
        header_layout = QHBoxLayout()
        header_layout.setSpacing(12)

        # Title
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

        # Single refresh button
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setProperty("buttonStyle", "secondary")
        self.refresh_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.refresh_button.setEnabled(False)
        self.refresh_button.clicked.connect(self._refresh_preview)
        header_layout.addWidget(self.refresh_button)

        preview_layout.addLayout(header_layout)

        # Preview table - Using centralized stylesheet
        self.preview_table = QTableWidget()

        # Basic table configuration
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.preview_table.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        self.preview_table.setMinimumHeight(200)
        self.preview_table.setShowGrid(True)

        # Configure headers with better defaults
        horizontal_header = self.preview_table.horizontalHeader()
        horizontal_header.setVisible(True)
        horizontal_header.setMinimumHeight(45)  # Increased for better visibility
        horizontal_header.setDefaultSectionSize(150)
        horizontal_header.setSectionResizeMode(QHeaderView.Interactive)
        horizontal_header.setMinimumSectionSize(120)  # Prevent too-narrow columns
        horizontal_header.setStretchLastSection(False)

        # Hide vertical header (row numbers)
        self.preview_table.verticalHeader().setVisible(False)

        # CRITICAL: Apply centralized stylesheet instead of inline styles
        self.preview_table.setStyleSheet(AnalyticsRunnerStylesheet.get_table_stylesheet())

        preview_layout.addWidget(self.preview_table)
        self.main_layout.addWidget(preview_frame)

    def _setup_drag_drop(self, target_widget):
        """Setup drag and drop on the target widget."""
        target_widget.setAcceptDrops(True)
        target_widget.dragEnterEvent = self._drag_enter_event
        target_widget.dragLeaveEvent = self._drag_leave_event
        target_widget.dropEvent = self._drop_event

    def _setup_connections(self):
        """Setup signal connections."""
        # Sheet selection
        self.sheet_combo.currentTextChanged.connect(self._on_sheet_changed)

        # Pre-validation connections (FIXED - removed proceedRequested connection)
        self.pre_validation_widget.validationStatusChanged.connect(self._on_prevalidation_status_changed)

    def _load_recent_files(self):
        """Load recent files from session manager."""
        if self.session_manager:
            self.recent_files = self.session_manager.get('recent_files', [])[:5]
        else:
            self.recent_files = []

    def _detect_data_type(self, df) -> str:
        """
        Detect the likely data type based on column names.

        Args:
            df: DataFrame to analyze

        Returns:
            Detected data type string
        """
        if df is None or df.empty:
            return "generic"

        columns = [col.lower().strip() for col in df.columns]

        # Financial data indicators
        financial_indicators = ['amount', 'value', 'price', 'cost', 'revenue', 'expense', 'balance', 'transaction']
        if any(indicator in ' '.join(columns) for indicator in financial_indicators):
            return "financial"

        # Employee data indicators
        employee_indicators = ['employee', 'staff', 'worker', 'hire', 'department', 'salary', 'position']
        if any(indicator in ' '.join(columns) for indicator in employee_indicators):
            return "employee"

        # Sales data indicators
        sales_indicators = ['sales', 'product', 'customer', 'order', 'purchase', 'quantity', 'item']
        if any(indicator in ' '.join(columns) for indicator in sales_indicators):
            return "sales"

        return "generic"

    def _validate_data_file(self, file_path: str) -> tuple[bool, str]:
        """Validate a data file for basic compatibility."""
        try:
            if not os.path.exists(file_path):
                return False, "File does not exist"

            if not os.access(file_path, os.R_OK):
                return False, "File is not readable"

            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > 100 * 1024 * 1024:  # 100MB
                return True, f"Large file ({file_size // (1024*1024)}MB)"

            return True, "File appears valid"

        except Exception as e:
            return False, f"Validation error: {str(e)}"

    # Event handlers
    def _browse_file(self):
        """Open file browser dialog with multi-file selection support."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Data Source Files (Multi-select enabled)",
            "",
            "Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if file_paths:
            if len(file_paths) == 1:
                # Single file selected - use existing flow
                self._set_file(file_paths[0])
            else:
                # Multiple files selected - process as lookup files
                self._load_multiple_files(file_paths)
    
    def _browse_lookup_files(self):
        """Open file browser specifically for loading lookup files."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Files for LOOKUP Operations",
            "",
            "Data Files (*.csv *.xlsx *.xls);;CSV Files (*.csv);;Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if file_paths:
            self._load_multiple_files(file_paths)

    def _show_recent_files(self):
        """Show recent files menu."""
        if not hasattr(self, 'recent_files') or not self.recent_files:
            QMessageBox.information(self, "Recent Files", "No recent files available.")
            return

        # Create simple selection dialog
        from PySide6.QtWidgets import QInputDialog
        items = [os.path.basename(f) for f in self.recent_files if os.path.exists(f)]

        if not items:
            QMessageBox.information(self, "Recent Files", "No recent files are currently available.")
            return

        item, ok = QInputDialog.getItem(
            self, "Recent Files", "Select a recent file:", items, 0, False
        )

        if ok and item:
            # Find the full path
            for file_path in self.recent_files:
                if os.path.basename(file_path) == item:
                    self._set_file(file_path)
                    break

    def _set_file(self, file_path: str):
        """Set the current file and update UI."""
        self._current_file = file_path
        self._current_sheet = None

        # Update file display
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
        self.file_display.setToolTip(file_path)

        # Show clear button
        self.clear_button.setVisible(True)

        # Add to recent files
        if self.session_manager:
            self.session_manager.add_recent_file(file_path)
            self._load_recent_files()

        # Check if Excel file
        file_ext = Path(file_path).suffix.lower()
        self._is_excel_file = file_ext in ['.xlsx', '.xls']

        # Show/hide sheet selection
        self.sheet_frame.setVisible(self._is_excel_file)

        # Load sheet names for Excel files
        if self._is_excel_file:
            self._load_sheet_names()
        else:
            # For non-Excel files, load preview directly
            self._load_file_preview()

        # Enable refresh button
        self.refresh_button.setEnabled(True)

        # Emit signals
        self.dataSourceChanged.emit(file_path)

        # Validate file
        is_valid, message = self._validate_data_file(file_path)
        self.dataSourceValidated.emit(is_valid, message)

    def _on_sheet_changed(self, sheet_name: str):
        """Handle Excel sheet selection change."""
        if sheet_name and sheet_name != self._current_sheet and sheet_name != "Loading...":
            self._current_sheet = sheet_name
            self._load_file_preview()
            self.sheetChanged.emit(sheet_name)

    def _refresh_preview(self):
        """Refresh the data preview."""
        if self._current_file:
            self._load_file_preview()

    def _load_sheet_names(self):
        """Load Excel sheet names."""
        if self._sheet_worker and self._sheet_worker.isRunning():
            self._sheet_worker.quit()
            self._sheet_worker.wait()

        self.sheet_combo.clear()
        self.sheet_combo.addItem("Loading...")
        self.sheet_combo.setEnabled(False)

        self._sheet_worker = SheetSelectionWorker(self._current_file)
        self._sheet_worker.sheetsLoaded.connect(self._on_sheets_loaded)
        self._sheet_worker.error.connect(self._on_sheet_error)
        self._sheet_worker.start()

    def _on_sheets_loaded(self, sheet_names: List[str]):
        """Handle successful sheet names loading - Enhanced for saved sources."""
        self.sheet_combo.clear()

        if sheet_names:
            self.sheet_combo.addItems(sheet_names)

            # Check if we have a target sheet from saved source
            if hasattr(self, '_target_sheet_name') and self._target_sheet_name:
                target_sheet = self._target_sheet_name

                if target_sheet in sheet_names:
                    # Set to the saved sheet
                    sheet_index = sheet_names.index(target_sheet)
                    self.sheet_combo.setCurrentIndex(sheet_index)
                    self._current_sheet = target_sheet
                    logger.info(f"Set Excel sheet to saved preference: {target_sheet}")
                else:
                    # Saved sheet not found, use first sheet but warn
                    self.sheet_combo.setCurrentIndex(0)
                    self._current_sheet = sheet_names[0]
                    logger.warning(f"Saved sheet '{target_sheet}' not found, using '{sheet_names[0]}'")

                # Clear the target sheet name
                delattr(self, '_target_sheet_name')
            else:
                # No saved preference, use first sheet
                self.sheet_combo.setCurrentIndex(0)
                self._current_sheet = sheet_names[0]

        self.sheet_combo.setEnabled(len(sheet_names) > 0)

        # Auto-load preview for the selected sheet
        if sheet_names:
            self._load_file_preview()

    def _on_sheet_error(self, error_msg: str):
        """Handle sheet loading error."""
        self.sheet_combo.clear()
        self.sheet_combo.addItem("Error loading sheets")
        self.sheet_combo.setEnabled(False)
        logger.error(f"Sheet loading error: {error_msg}")

    def get_current_source_metadata(self):
        """Get the metadata for the currently loaded saved source, if any."""
        return getattr(self, '_current_source_metadata', None)

    def _load_file_preview(self):
        """Load file preview."""
        if not self._current_file:
            return
            
        # Don't try to load if sheet name is the placeholder
        if self._is_excel_file and self._current_sheet == "Loading...":
            return

        # Stop any existing preview worker
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.stop()
            self._preview_worker.quit()
            self._preview_worker.wait()

        # Disable refresh button during loading
        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("Loading...")

        # Start preview worker - load more rows for better preview
        self._preview_worker = FilePreviewWorker(
            self._current_file,
            self._current_sheet,
            max_rows=50  # Show more rows in preview
        )
        self._preview_worker.previewLoaded.connect(self._on_preview_loaded)
        self._preview_worker.error.connect(self._on_preview_error)
        self._preview_worker.start()

    def _on_preview_loaded(self, preview_df, metadata: Dict[str, Any]):
        """Handle successful preview loading."""
        self._preview_df = preview_df
        self._file_metadata = metadata

        # Update preview table
        self._update_preview_table()

        # Re-enable refresh button
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("Refresh")

        # Enable save source button when valid data is loaded
        if preview_df is not None and not preview_df.empty and self._current_file:
            self.save_source_button.setEnabled(True)
            logger.debug("Save Source button enabled - valid data loaded")
        else:
            self.save_source_button.setEnabled(False)
            logger.debug("Save Source button disabled - no valid data")

        # Auto-run pre-validation when preview loads
        if preview_df is not None and not preview_df.empty:
            # Always use generic validation for fast structural checks
            self.pre_validation_widget.validate_data(preview_df, "generic")

        # Emit signals
        self.previewUpdated.emit(preview_df)
        
        # Emit columns detected signal
        if preview_df is not None and not preview_df.empty:
            self.columnsDetected.emit(list(preview_df.columns))
            
        # Note: Full file registration with lookup manager will happen when the file is actually loaded
        # This is just a preview, so we don't register it yet

        logger.info(f"Preview loaded: {len(preview_df)} rows, {len(preview_df.columns)} columns")

    def _on_preview_error(self, error_msg: str):
        """Handle preview loading error."""
        self.refresh_button.setEnabled(True)
        self.refresh_button.setText("Refresh")

        # Clear preview table
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)

        # Disable save source button on error
        self.save_source_button.setEnabled(False)

        logger.error(f"Preview error: {error_msg}")
    def _on_prevalidation_status_changed(self, is_valid: bool, message: str):
        """Handle pre-validation status change."""
        logger.info(f"Pre-validation status: {'Valid' if is_valid else 'Invalid'} - {message}")

        # Update the main data source validation status
        # This combines file validation with pre-validation results
        file_valid, _ = self._validate_data_file(self._current_file) if self._current_file else (False, "No file")
        overall_valid = file_valid and is_valid

        self.dataSourceValidated.emit(overall_valid, f"Pre-validation: {message}")

    def _update_preview_table(self):
        """Update the preview table with data - Using centralized stylesheet."""
        if self._preview_df is None or self._preview_df.empty:
            self.preview_table.clear()
            self.preview_table.setRowCount(0)
            self.preview_table.setColumnCount(0)
            return

        # Set table dimensions
        rows, cols = self._preview_df.shape
        self.preview_table.setRowCount(rows)
        self.preview_table.setColumnCount(cols)

        # Prepare column names
        column_names = [str(col) for col in self._preview_df.columns]

        # Set horizontal header labels
        self.preview_table.setHorizontalHeaderLabels(column_names)

        # Configure header sizing (but NOT styling - that's handled by stylesheet)
        horizontal_header = self.preview_table.horizontalHeader()
        horizontal_header.setVisible(True)
        horizontal_header.setSectionResizeMode(QHeaderView.Interactive)

        # Populate table data
        for row in range(rows):
            for col in range(cols):
                try:
                    value = self._preview_df.iloc[row, col]
                    if value is None or (hasattr(value, 'isna') and value.isna()):
                        display_value = ""
                    else:
                        display_value = str(value)

                    item = QTableWidgetItem(display_value)
                    item.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
                    self.preview_table.setItem(row, col, item)

                except Exception as e:
                    item = QTableWidgetItem(f"Error: {str(e)}")
                    self.preview_table.setItem(row, col, item)

        # Intelligent column sizing based on content
        self._resize_columns_to_content(column_names, rows, cols)

        # Force table refresh
        self.preview_table.viewport().update()

        logger.debug(f"Headers configured with stylesheet: {column_names}")

    def _resize_columns_to_content(self, column_names: List[str], rows: int, cols: int):
        """Resize columns intelligently based on header text and content."""
        font_metrics = self.preview_table.fontMetrics()

        for col in range(cols):
            header_text = column_names[col]

            # Calculate minimum width for header text with padding
            # Use a more generous multiplier since stylesheet has padding: 8px 12px
            header_width = font_metrics.horizontalAdvance(header_text) + 50  # Extra padding for stylesheet

            # Calculate width needed for data (sample first few rows)
            max_data_width = 0
            sample_rows = min(10, rows)

            for row in range(sample_rows):
                item = self.preview_table.item(row, col)
                if item:
                    text_width = font_metrics.horizontalAdvance(item.text()) + 30
                    max_data_width = max(max_data_width, text_width)

            # Set column width to accommodate both header and data
            optimal_width = max(header_width, max_data_width, 130)  # Increased minimum
            optimal_width = min(optimal_width, 350)  # Cap maximum width

            self.preview_table.setColumnWidth(col, optimal_width)

    # Drag and drop events
    def _drag_enter_event(self, event):
        """Handle drag enter event - supports multiple files."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            # Check if all URLs are valid data files
            valid_files = []
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    file_ext = Path(file_path).suffix.lower()
                    if file_ext in ['.csv', '.xlsx', '.xls']:
                        valid_files.append(file_path)
            
            if valid_files:
                event.acceptProposedAction()
                return

        event.ignore()

    def _drag_leave_event(self, event):
        """Handle drag leave event."""
        pass

    def _drop_event(self, event):
        """Handle drop event - supports multiple files."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            valid_files = []
            
            for url in urls:
                if url.isLocalFile():
                    file_path = url.toLocalFile()
                    file_ext = Path(file_path).suffix.lower()
                    if file_ext in ['.csv', '.xlsx', '.xls']:
                        valid_files.append(file_path)
            
            if valid_files:
                if len(valid_files) == 1:
                    # Single file - use existing flow
                    self._set_file(valid_files[0])
                else:
                    # Multiple files - load for lookup
                    self._load_multiple_files(valid_files)
                event.acceptProposedAction()
                return

        event.ignore()

    # Public interface
    def get_current_file(self) -> str:
        """Get the currently selected file path."""
        return self._current_file

    def get_current_sheet(self) -> Optional[str]:
        """Get the currently selected Excel sheet name."""
        return self._current_sheet

    def get_preview_data(self):
        """Get the current preview DataFrame."""
        return self._preview_df

    def is_valid(self) -> bool:
        """Check if current data source is valid."""
        if not self._current_file:
            return False

        is_valid, _ = self._validate_data_file(self._current_file)
        return is_valid

    def clear_selection(self):
        """Clear the current data source selection - Enhanced to clear saved source metadata."""
        # Unload from lookup manager if loaded
        if self._current_file:
            self.lookup_manager.unload_file(self._current_file)
            logger.info(f"Unloaded {Path(self._current_file).name} from lookup manager")
            self.update_lookup_status()
        
        self._current_file = ""
        self._current_sheet = None
        self._preview_df = None
        self._file_metadata = {}

        # Clear saved source metadata
        if hasattr(self, '_current_source_metadata'):
            delattr(self, '_current_source_metadata')

        # Clear any pending connection parameters
        if hasattr(self, '_target_sheet_name'):
            delattr(self, '_target_sheet_name')
        if hasattr(self, '_target_cell_range'):
            delattr(self, '_target_cell_range')

        # Reset UI
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
        self.file_display.setToolTip("")

        # Hide controls
        self.clear_button.setVisible(False)
        self.sheet_frame.setVisible(False)
        self.refresh_button.setEnabled(False)

        # Disable save source button
        self.save_source_button.setEnabled(False)

        # Clear preview
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)

        # Clear pre-validation
        self.pre_validation_widget.clear_results()

        # Emit signals
        self.dataSourceChanged.emit("")

    def load_full_file(self, auto_register: bool = True) -> Optional[pd.DataFrame]:
        """
        Load the full file (not just preview) and optionally register with lookup manager.
        
        Args:
            auto_register: Whether to automatically register with lookup manager
            
        Returns:
            The loaded DataFrame or None if loading fails
        """
        if not self._current_file:
            return None
            
        try:
            from data_integration.io.importer import DataImporter
            importer = DataImporter()
            
            # Load full file
            kwargs = {}
            if self._current_sheet and self._is_excel_file:
                kwargs['sheet_name'] = self._current_sheet
                
            df = importer.load_file(self._current_file, **kwargs)
            
            if df is not None and not df.empty and auto_register:
                # Register with lookup manager
                self._on_file_loaded(self._current_file, df, self._current_sheet)
                
            return df
            
        except Exception as e:
            logger.error(f"Error loading full file: {e}")
            return None
    
    def _on_file_loaded(self, filepath: str, df: pd.DataFrame, sheet_name: str = None):
        """
        Called when a full file is loaded (not just preview).
        Registers the file with the lookup manager and shows informative message.
        
        Args:
            filepath: Path to the loaded file
            df: The loaded DataFrame
            sheet_name: Optional sheet name for Excel files
        """
        if df is None or df.empty:
            return
            
        # Register with lookup manager
        alias = None
        if sheet_name:
            # For Excel files with sheets, create alias like "filename_sheetname"
            base_name = Path(filepath).stem
            alias = f"{base_name}_{sheet_name}"
        
        self.lookup_manager.add_file(filepath, df, alias=alias)
        
        # Log informative message
        columns = len(df.columns)
        rows = len(df)
        file_name = Path(filepath).name
        
        message = (f"File loaded: {file_name} "
                  f"({rows:,} rows, {columns} columns) - "
                  f"available for LOOKUP operations")
        
        if sheet_name:
            message = (f"File loaded: {file_name} [{sheet_name}] "
                      f"({rows:,} rows, {columns} columns) - "
                      f"available for LOOKUP operations")
        
        logger.info(message)
        
        # Emit signal to notify UI
        self.lookupFileLoaded.emit(message)
        
        # Update the lookup status display
        self.update_lookup_status()
        
    def update_lookup_status(self):
        """Update the lookup status label with current file information."""
        manager = self.lookup_manager
        file_count = len(manager.file_metadata)
        total_columns = len(manager.column_index)
        
        if file_count == 0:
            self.lookup_status.setText("📁 No lookup files loaded")
            self.lookup_status.setToolTip("No files available for LOOKUP operations")
        else:
            # Make it informative and actionable
            status_text = f"📁 {file_count} files available | {total_columns} columns searchable | Click to see"
            self.lookup_status.setText(status_text)
            
            # Build detailed tooltip
            tooltip_lines = ["Files loaded for LOOKUP:"]
            for filepath, metadata in manager.file_metadata.items():
                alias = manager.file_aliases.get(filepath, Path(filepath).stem)
                row_count = metadata.get('row_count', 0)
                col_count = len(metadata.get('columns', []))
                size_mb = metadata.get('size_mb', 0)
                lazy_status = " (lazy)" if metadata.get('lazy', False) else ""
                
                tooltip_lines.append(
                    f"• {alias}: {row_count:,} rows, {col_count} cols, {size_mb:.1f}MB{lazy_status}"
                )
            
            self.lookup_status.setToolTip("\n".join(tooltip_lines))
    
    def _show_lookup_details(self):
        """Show detailed lookup information when clicked."""
        from ui.analytics_runner.dialogs.lookup_details_dialog import LookupDetailsDialog
        dialog = LookupDetailsDialog(self.lookup_manager, self)
        dialog.exec()
    
    def _load_multiple_files(self, file_paths: List[str]):
        """
        Load multiple files for lookup operations.
        Shows progress and handles partial failures.
        
        Args:
            file_paths: List of file paths to load
        """
        from PySide6.QtWidgets import QProgressDialog
        
        # Create progress dialog
        progress = QProgressDialog(
            "Loading files for LOOKUP operations...", 
            "Cancel", 
            0, 
            len(file_paths), 
            self
        )
        progress.setWindowTitle("Loading Multiple Files")
        progress.setWindowModality(Qt.WindowModal)
        progress.setMinimumDuration(0)
        
        loaded_count = 0
        failed_files = []
        
        for i, file_path in enumerate(file_paths):
            if progress.wasCanceled():
                break
                
            file_name = Path(file_path).name
            progress.setLabelText(f"Loading {file_name}...")
            progress.setValue(i)
            
            try:
                # Load the full file
                df = self.load_full_file_for_lookup(file_path)
                if df is not None and not df.empty:
                    loaded_count += 1
                    logger.info(f"Successfully loaded {file_name} for lookup")
                else:
                    failed_files.append((file_name, "Empty or invalid file"))
            except Exception as e:
                failed_files.append((file_name, str(e)))
                logger.error(f"Failed to load {file_name}: {e}")
        
        progress.setValue(len(file_paths))
        
        # Show summary
        if loaded_count > 0:
            message = f"Successfully loaded {loaded_count} file(s) for LOOKUP operations."
            if failed_files:
                message += f"\n\nFailed to load {len(failed_files)} file(s):"
                for fname, error in failed_files[:3]:  # Show first 3 errors
                    message += f"\n• {fname}: {error}"
                if len(failed_files) > 3:
                    message += f"\n• ... and {len(failed_files) - 3} more"
            
            QMessageBox.information(self, "Files Loaded", message)
        elif failed_files:
            QMessageBox.warning(
                self, 
                "Loading Failed", 
                f"Failed to load all {len(failed_files)} file(s).\n\n" +
                "\n".join([f"• {fname}: {error}" for fname, error in failed_files[:5]])
            )
    
    def load_full_file_for_lookup(self, file_path: str) -> Optional[pd.DataFrame]:
        """
        Load a file specifically for lookup operations (not as primary data source).
        
        Args:
            file_path: Path to the file to load
            
        Returns:
            The loaded DataFrame or None if loading fails
        """
        try:
            from data_integration.io.importer import DataImporter
            importer = DataImporter()
            
            # For Excel files, we might need to handle sheets
            if Path(file_path).suffix.lower() in ['.xlsx', '.xls']:
                # For lookup files, just load the first sheet by default
                df = importer.load_file(file_path, sheet_name=0)
            else:
                df = importer.load_file(file_path)
            
            if df is not None and not df.empty:
                # Register with lookup manager
                self._on_file_loaded(file_path, df)
                
            return df
            
        except Exception as e:
            logger.error(f"Error loading file for lookup: {e}")
            return None
    
    def get_lookup_manager(self) -> SmartLookupManager:
        """Get the SmartLookupManager instance."""
        return self.lookup_manager

    def cleanup(self):
        """Clean up resources."""
        if self._preview_worker and self._preview_worker.isRunning():
            self._preview_worker.stop()
            self._preview_worker.quit()
            self._preview_worker.wait()

        if self._sheet_worker and self._sheet_worker.isRunning():
            self._sheet_worker.quit()
            self._sheet_worker.wait()

        # Cleanup pre-validation widget
        self.pre_validation_widget.cleanup()
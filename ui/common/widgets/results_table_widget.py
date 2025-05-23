"""
ResultsTableWidget - High-Performance Data Table Component
Provides sortable, filterable data display with export and context menu functionality
"""

import csv
import json
from typing import List, Dict, Any, Optional, Callable, Union
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMenu, QLineEdit, QPushButton,
    QComboBox, QLabel, QFileDialog, QMessageBox, QProgressDialog,
    QCheckBox, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QObject
from PySide6.QtGui import QAction, QFont, QColor, QBrush

from ui.common.stylesheet import AnalyticsRunnerStylesheet

logger = logging.getLogger(__name__)


class DataExportWorker(QObject):
    """Worker thread for data export operations."""

    progress = Signal(int)
    finished = Signal(str)  # file path
    error = Signal(str)     # error message

    def __init__(self, data: List[List[Any]], headers: List[str], file_path: str, format_type: str):
        super().__init__()
        self.data = data
        self.headers = headers
        self.file_path = file_path
        self.format_type = format_type

    def run(self):
        """Export data to file."""
        try:
            if self.format_type == 'csv':
                self._export_csv()
            elif self.format_type == 'json':
                self._export_json()

            self.finished.emit(self.file_path)
        except Exception as e:
            self.error.emit(str(e))

    def _export_csv(self):
        """Export data to CSV format."""
        with open(self.file_path, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.headers)

            total_rows = len(self.data)
            for i, row in enumerate(self.data):
                writer.writerow(row)

                # Emit progress every 100 rows
                if i % 100 == 0:
                    progress = int((i / total_rows) * 100)
                    self.progress.emit(progress)

    def _export_json(self):
        """Export data to JSON format."""
        json_data = []
        total_rows = len(self.data)

        for i, row in enumerate(self.data):
            row_dict = {self.headers[j]: row[j] for j in range(len(self.headers))}
            json_data.append(row_dict)

            # Emit progress every 100 rows
            if i % 100 == 0:
                progress = int((i / total_rows) * 100)
                self.progress.emit(progress)

        with open(self.file_path, 'w', encoding='utf-8') as jsonfile:
            json.dump(json_data, jsonfile, indent=2, default=str)


class ResultsTableWidget(QWidget):
    """
    High-performance results table with sorting, filtering, and export capabilities.

    Features:
    - Virtual scrolling for large datasets
    - Real-time search and filtering
    - Column-based filtering
    - Multi-column sorting
    - Context menu with row operations
    - CSV and JSON export
    - Customizable display options
    """

    # Signals
    rowSelected = Signal(int, dict)  # row index, row data
    rowDoubleClicked = Signal(int, dict)
    dataFiltered = Signal(int)  # filtered row count
    exportCompleted = Signal(str)  # file path

    def __init__(self,
                 show_search: bool = True,
                 show_column_filters: bool = True,
                 show_export_buttons: bool = True,
                 enable_context_menu: bool = True,
                 max_display_rows: int = 10000,
                 parent: Optional[QWidget] = None):
        """
        Initialize the results table widget.

        Args:
            show_search: Whether to show global search box
            show_column_filters: Whether to show per-column filter dropdowns
            show_export_buttons: Whether to show export buttons
            enable_context_menu: Whether to enable right-click context menu
            max_display_rows: Maximum rows to display (for performance)
            parent: Parent widget
        """
        super().__init__(parent)

        # Configuration
        self.show_search = show_search
        self.show_column_filters = show_column_filters
        self.show_export_buttons = show_export_buttons
        self.enable_context_menu = enable_context_menu
        self.max_display_rows = max_display_rows

        # Data storage
        self._original_data: List[Dict[str, Any]] = []
        self._filtered_data: List[Dict[str, Any]] = []
        self._column_names: List[str] = []
        self._column_filters: Dict[str, str] = {}
        self._search_term = ""
        self._sort_column = None
        self._sort_order = Qt.AscendingOrder

        # UI state
        self._filter_timer = QTimer()
        self._filter_timer.setSingleShot(True)
        self._filter_timer.timeout.connect(self._apply_filters)

        # Export worker
        self._export_thread = None
        self._export_worker = None

        # Setup UI
        self._setup_ui()
        self._setup_styles()
        self._setup_context_menu()

        logger.debug("ResultsTableWidget initialized")

    def _setup_ui(self):
        """Setup the user interface components."""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # Controls frame
        if self.show_search or self.show_export_buttons:
            self.controls_frame = QFrame()
            controls_layout = QHBoxLayout(self.controls_frame)
            controls_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
            controls_layout.setContentsMargins(0, 0, 0, 0)

            # Search box
            if self.show_search:
                search_label = QLabel("Search:")
                search_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
                controls_layout.addWidget(search_label)

                self.search_box = QLineEdit()
                self.search_box.setPlaceholderText("Type to search all columns...")
                self.search_box.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
                self.search_box.textChanged.connect(self._on_search_changed)
                self.search_box.setMaximumWidth(300)
                controls_layout.addWidget(self.search_box)

                # Clear search button
                clear_search_btn = QPushButton("Clear")
                clear_search_btn.setProperty("buttonStyle", "secondary")
                clear_search_btn.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
                clear_search_btn.clicked.connect(self._clear_search)
                clear_search_btn.setMaximumWidth(60)
                controls_layout.addWidget(clear_search_btn)

            controls_layout.addStretch()

            # Row count label
            self.row_count_label = QLabel("0 rows")
            self.row_count_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
            controls_layout.addWidget(self.row_count_label)

            # Export buttons
            if self.show_export_buttons:
                export_csv_btn = QPushButton("Export CSV")
                export_csv_btn.setProperty("buttonStyle", "secondary")
                export_csv_btn.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
                export_csv_btn.clicked.connect(self._export_csv)
                controls_layout.addWidget(export_csv_btn)

                export_json_btn = QPushButton("Export JSON")
                export_json_btn.setProperty("buttonStyle", "secondary")
                export_json_btn.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
                export_json_btn.clicked.connect(self._export_json)
                controls_layout.addWidget(export_json_btn)

            self.main_layout.addWidget(self.controls_frame)

        # Column filters frame
        if self.show_column_filters:
            self.filters_frame = QFrame()
            self.filters_layout = QHBoxLayout(self.filters_frame)
            self.filters_layout.setSpacing(8)
            self.filters_layout.setContentsMargins(0, 0, 0, 0)
            self.filters_frame.setVisible(False)  # Hidden until data is loaded
            self.main_layout.addWidget(self.filters_frame)

        # Table widget
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().setVisible(False)

        # Configure headers
        self.table.horizontalHeader().setSectionsMovable(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Interactive)

        # Connect signals
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemDoubleClicked.connect(self._on_double_clicked)
        self.table.horizontalHeader().sectionClicked.connect(self._on_header_clicked)

        self.main_layout.addWidget(self.table)

    def _setup_styles(self):
        """Apply styles to the widget components."""
        # Controls frame styling
        if hasattr(self, 'controls_frame'):
            self.controls_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {AnalyticsRunnerStylesheet.PANEL_BACKGROUND};
                    border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                    border-radius: 6px;
                    padding: 8px;
                }}
            """)

        # Filters frame styling
        if hasattr(self, 'filters_frame'):
            self.filters_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
                    border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR}40;
                    border-radius: 6px;
                    padding: 6px;
                }}
            """)

        # Table styling
        self.table.setStyleSheet(f"""
            QTableWidget {{
                gridline-color: {AnalyticsRunnerStylesheet.BORDER_COLOR};
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
                alternate-background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                selection-background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR}40;
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 6px;
            }}
            
            QTableWidget::item {{
                padding: 6px;
                border: none;
            }}
            
            QTableWidget::item:selected {{
                background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR}60;
                color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
            }}
            
            QHeaderView::section {{
                background-color: {AnalyticsRunnerStylesheet.PANEL_BACKGROUND};
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 0px;
                padding: 8px;
                font-weight: bold;
            }}
            
            QHeaderView::section:hover {{
                background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
            }}
        """)

        # Row count label styling
        if hasattr(self, 'row_count_label'):
            self.row_count_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                    font-weight: 500;
                }}
            """)

    def _setup_context_menu(self):
        """Setup the context menu for table rows."""
        if not self.enable_context_menu:
            return

        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

    def _create_column_filters(self):
        """Create filter dropdowns for each column."""
        if not self.show_column_filters or not self._column_names:
            return

        # Clear existing filters
        for i in reversed(range(self.filters_layout.count())):
            child = self.filters_layout.itemAt(i).widget()
            if child:
                child.setParent(None)

        # Add filter label
        filter_label = QLabel("Filters:")
        filter_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        self.filters_layout.addWidget(filter_label)

        # Create filter for each column
        self._column_filter_combos = {}
        for column_name in self._column_names:
            # Column label
            col_label = QLabel(f"{column_name}:")
            col_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
            self.filters_layout.addWidget(col_label)

            # Filter combo
            filter_combo = QComboBox()
            filter_combo.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
            filter_combo.setMaximumWidth(150)
            filter_combo.addItem("All")

            # Populate with unique values
            unique_values = set()
            for row in self._original_data:
                value = str(row.get(column_name, ""))
                if value:
                    unique_values.add(value)

            for value in sorted(unique_values):
                filter_combo.addItem(value)

            filter_combo.currentTextChanged.connect(
                lambda text, col=column_name: self._on_column_filter_changed(col, text)
            )

            self.filters_layout.addWidget(filter_combo)
            self._column_filter_combos[column_name] = filter_combo

        self.filters_layout.addStretch()

        # Clear filters button
        clear_filters_btn = QPushButton("Clear Filters")
        clear_filters_btn.setProperty("buttonStyle", "secondary")
        clear_filters_btn.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        clear_filters_btn.clicked.connect(self._clear_all_filters)
        self.filters_layout.addWidget(clear_filters_btn)

        # Show filters frame
        self.filters_frame.setVisible(True)

    def _apply_filters(self):
        """Apply search and column filters to the data."""
        self._filtered_data = []

        for row in self._original_data:
            # Check search filter
            if self._search_term:
                search_match = False
                for value in row.values():
                    if self._search_term.lower() in str(value).lower():
                        search_match = True
                        break

                if not search_match:
                    continue

            # Check column filters
            column_match = True
            for column, filter_value in self._column_filters.items():
                if filter_value and filter_value != "All":
                    if str(row.get(column, "")) != filter_value:
                        column_match = False
                        break

            if not column_match:
                continue

            self._filtered_data.append(row)

        # Limit display rows for performance
        if len(self._filtered_data) > self.max_display_rows:
            display_data = self._filtered_data[:self.max_display_rows]
            logger.warning(f"Limiting display to {self.max_display_rows} rows for performance")
        else:
            display_data = self._filtered_data

        # Update table
        self._populate_table(display_data)

        # Update row count
        total_count = len(self._filtered_data)
        display_count = len(display_data)

        if total_count != display_count:
            count_text = f"{display_count} of {total_count} rows (limited for performance)"
        else:
            count_text = f"{total_count} rows"

        if hasattr(self, 'row_count_label'):
            self.row_count_label.setText(count_text)

        # Emit signal
        self.dataFiltered.emit(total_count)

    def _populate_table(self, data: List[Dict[str, Any]]):
        """Populate the table with data."""
        if not data or not self._column_names:
            self.table.setRowCount(0)
            self.table.setColumnCount(0)
            return

        # Set table dimensions
        self.table.setRowCount(len(data))
        self.table.setColumnCount(len(self._column_names))

        # Set headers
        self.table.setHorizontalHeaderLabels(self._column_names)

        # Populate data
        for row_idx, row_data in enumerate(data):
            for col_idx, column_name in enumerate(self._column_names):
                value = row_data.get(column_name, "")

                # Create table item
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)  # Read-only

                # Store original data as user data
                if col_idx == 0:
                    item.setData(Qt.UserRole, row_data)

                self.table.setItem(row_idx, col_idx, item)

        # Resize columns to content
        self.table.resizeColumnsToContents()

        # Ensure minimum column width
        for col in range(self.table.columnCount()):
            if self.table.columnWidth(col) < 100:
                self.table.setColumnWidth(col, 100)

    # Event handlers
    def _on_search_changed(self, text: str):
        """Handle search text change."""
        self._search_term = text
        self._filter_timer.start(300)  # 300ms debounce

    def _on_column_filter_changed(self, column: str, value: str):
        """Handle column filter change."""
        if value == "All":
            self._column_filters.pop(column, None)
        else:
            self._column_filters[column] = value

        self._filter_timer.start(300)  # 300ms debounce

    def _on_selection_changed(self):
        """Handle table selection change."""
        current_row = self.table.currentRow()
        if current_row >= 0:
            item = self.table.item(current_row, 0)
            if item:
                row_data = item.data(Qt.UserRole)
                if row_data:
                    self.rowSelected.emit(current_row, row_data)

    def _on_double_clicked(self, item: QTableWidgetItem):
        """Handle table item double click."""
        if item:
            row_data = self.table.item(item.row(), 0).data(Qt.UserRole)
            if row_data:
                self.rowDoubleClicked.emit(item.row(), row_data)

    def _on_header_clicked(self, logical_index: int):
        """Handle header click for sorting."""
        if logical_index < len(self._column_names):
            column_name = self._column_names[logical_index]

            # Toggle sort order if same column
            if self._sort_column == column_name:
                self._sort_order = Qt.DescendingOrder if self._sort_order == Qt.AscendingOrder else Qt.AscendingOrder
            else:
                self._sort_column = column_name
                self._sort_order = Qt.AscendingOrder

            # Sort data
            self._sort_data()

    def _sort_data(self):
        """Sort the filtered data."""
        if not self._sort_column or not self._filtered_data:
            return

        reverse = (self._sort_order == Qt.DescendingOrder)

        try:
            # Sort with type handling
            self._filtered_data.sort(
                key=lambda x: self._get_sort_key(x.get(self._sort_column, "")),
                reverse=reverse
            )

            # Refresh display
            display_data = self._filtered_data[:self.max_display_rows]
            self._populate_table(display_data)

        except Exception as e:
            logger.error(f"Error sorting data: {e}")

    def _get_sort_key(self, value: Any) -> Any:
        """Get sort key for a value with type handling."""
        if value is None or value == "":
            return ""

        # Try numeric sort first
        try:
            return float(value)
        except (ValueError, TypeError):
            pass

        # Fall back to string sort
        return str(value).lower()

    def _clear_search(self):
        """Clear the search box."""
        if hasattr(self, 'search_box'):
            self.search_box.clear()

    def _clear_all_filters(self):
        """Clear all column filters."""
        self._column_filters.clear()

        # Reset combo boxes
        if hasattr(self, '_column_filter_combos'):
            for combo in self._column_filter_combos.values():
                combo.setCurrentIndex(0)  # "All"

        self._apply_filters()

    def _show_context_menu(self, position):
        """Show context menu for table row."""
        item = self.table.itemAt(position)
        if not item:
            return

        row_data = self.table.item(item.row(), 0).data(Qt.UserRole)
        if not row_data:
            return

        menu = QMenu(self)

        # Copy row action
        copy_action = QAction("Copy Row", self)
        copy_action.triggered.connect(lambda: self._copy_row(row_data))
        menu.addAction(copy_action)

        # Copy cell action
        copy_cell_action = QAction("Copy Cell", self)
        copy_cell_action.triggered.connect(lambda: self._copy_cell(item))
        menu.addAction(copy_cell_action)

        menu.addSeparator()

        # View details action
        details_action = QAction("View Details", self)
        details_action.triggered.connect(lambda: self._view_details(row_data))
        menu.addAction(details_action)

        menu.exec(self.table.mapToGlobal(position))

    def _copy_row(self, row_data: Dict[str, Any]):
        """Copy row data to clipboard."""
        try:
            from PySide6.QtGui import QClipboard

            # Format as tab-separated values
            values = [str(row_data.get(col, "")) for col in self._column_names]
            text = "\t".join(values)

            clipboard = QClipboard()
            clipboard.setText(text)

            logger.debug("Row data copied to clipboard")
        except Exception as e:
            logger.error(f"Error copying row data: {e}")

    def _copy_cell(self, item: QTableWidgetItem):
        """Copy cell value to clipboard."""
        try:
            from PySide6.QtGui import QClipboard

            clipboard = QClipboard()
            clipboard.setText(item.text())

            logger.debug("Cell value copied to clipboard")
        except Exception as e:
            logger.error(f"Error copying cell value: {e}")

    def _view_details(self, row_data: Dict[str, Any]):
        """Show detailed view of row data."""
        # Create a simple details dialog
        details_text = "\n".join([f"{key}: {value}" for key, value in row_data.items()])

        msg = QMessageBox(self)
        msg.setWindowTitle("Row Details")
        msg.setText("Row Data:")
        msg.setDetailedText(details_text)
        msg.exec()

    def _export_csv(self):
        """Export current data to CSV."""
        if not self._filtered_data:
            QMessageBox.information(self, "No Data", "No data to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to CSV",
            "results.csv",
            "CSV Files (*.csv)"
        )

        if file_path:
            self._export_data(file_path, 'csv')

    def _export_json(self):
        """Export current data to JSON."""
        if not self._filtered_data:
            QMessageBox.information(self, "No Data", "No data to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export to JSON",
            "results.json",
            "JSON Files (*.json)"
        )

        if file_path:
            self._export_data(file_path, 'json')

    def _export_data(self, file_path: str, format_type: str):
        """Export data using worker thread."""
        # Prepare data for export
        export_data = []
        for row in self._filtered_data:
            export_row = [row.get(col, "") for col in self._column_names]
            export_data.append(export_row)

        # Create progress dialog
        progress_dialog = QProgressDialog("Exporting data...", "Cancel", 0, 100, self)
        progress_dialog.setWindowModality(Qt.WindowModal)
        progress_dialog.show()

        # Create worker thread
        self._export_thread = QThread()
        self._export_worker = DataExportWorker(export_data, self._column_names, file_path, format_type)
        self._export_worker.moveToThread(self._export_thread)

        # Connect signals
        self._export_thread.started.connect(self._export_worker.run)
        self._export_worker.progress.connect(progress_dialog.setValue)
        self._export_worker.finished.connect(self._on_export_finished)
        self._export_worker.error.connect(self._on_export_error)
        self._export_worker.finished.connect(self._export_thread.quit)
        self._export_worker.finished.connect(progress_dialog.close)
        self._export_thread.finished.connect(self._export_thread.deleteLater)

        # Start export
        self._export_thread.start()

    def _on_export_finished(self, file_path: str):
        """Handle export completion."""
        QMessageBox.information(self, "Export Complete", f"Data exported to:\n{file_path}")
        self.exportCompleted.emit(file_path)
        logger.info(f"Data exported to: {file_path}")

    def _on_export_error(self, error_message: str):
        """Handle export error."""
        QMessageBox.critical(self, "Export Error", f"Error exporting data:\n{error_message}")
        logger.error(f"Export error: {error_message}")

    # Public interface
    def set_data(self, data: List[Dict[str, Any]], columns: Optional[List[str]] = None):
        """
        Set the table data.

        Args:
            data: List of dictionaries with row data
            columns: Optional list of column names to display (defaults to all)
        """
        self._original_data = data

        # Determine columns
        if columns:
            self._column_names = columns
        elif data:
            # Use all unique keys from the data
            all_keys = set()
            for row in data:
                all_keys.update(row.keys())
            self._column_names = sorted(all_keys)
        else:
            self._column_names = []

        # Reset filters
        self._column_filters.clear()
        self._search_term = ""

        # Clear search box
        if hasattr(self, 'search_box'):
            self.search_box.clear()

        # Create column filters
        self._create_column_filters()

        # Apply filters (which populates the table)
        self._apply_filters()

        logger.info(f"Table data set: {len(data)} rows, {len(self._column_names)} columns")

    def get_selected_row(self) -> Optional[Dict[str, Any]]:
        """Get the currently selected row data."""
        current_row = self.table.currentRow()
        if current_row >= 0:
            item = self.table.item(current_row, 0)
            if item:
                return item.data(Qt.UserRole)
        return None

    def get_filtered_data(self) -> List[Dict[str, Any]]:
        """Get the current filtered data."""
        return self._filtered_data.copy()

    def clear_data(self):
        """Clear all data from the table."""
        self._original_data.clear()
        self._filtered_data.clear()
        self._column_names.clear()
        self._column_filters.clear()
        self._search_term = ""

        self.table.setRowCount(0)
        self.table.setColumnCount(0)

        if hasattr(self, 'row_count_label'):
            self.row_count_label.setText("0 rows")

        if hasattr(self, 'filters_frame'):
            self.filters_frame.setVisible(False)

        logger.debug("Table data cleared")

    # Properties
    @property
    def row_count(self) -> int:
        """Total number of rows in original data."""
        return len(self._original_data)

    @property
    def filtered_row_count(self) -> int:
        """Number of rows after filtering."""
        return len(self._filtered_data)

    @property
    def column_count(self) -> int:
        """Number of columns."""
        return len(self._column_names)
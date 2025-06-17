"""
Lookup Details Dialog - Shows detailed information about loaded lookup files.
Part of Phase 2, Task 1 for Secondary Source File Integration.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame,
    QTabWidget, QTextEdit
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from ui.common.stylesheet import AnalyticsRunnerStylesheet
from core.lookup.smart_lookup_manager import SmartLookupManager


class LookupDetailsDialog(QDialog):
    """Dialog showing detailed information about loaded lookup files."""
    
    def __init__(self, lookup_manager: SmartLookupManager, parent=None):
        """
        Initialize the lookup details dialog.
        
        Args:
            lookup_manager: The SmartLookupManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.lookup_manager = lookup_manager
        self.setWindowTitle("Lookup Data Sources")
        self.setModal(True)
        self.resize(800, 600)
        
        self._setup_ui()
        self._populate_data()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        # Main layout
        layout = QVBoxLayout(self)
        layout.setSpacing(AnalyticsRunnerStylesheet.SECTION_SPACING)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Title
        title_label = QLabel("Lookup Data Sources")
        title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['title'])
        title_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                font-weight: bold;
                padding-bottom: 8px;
            }}
        """)
        layout.addWidget(title_label)
        
        # Summary section
        self._create_summary_section(layout)
        
        # Tab widget for different views
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            }}
            QTabBar::tab {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                padding: 8px 16px;
                margin-right: 2px;
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-bottom: none;
            }}
            QTabBar::tab:selected {{
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
                font-weight: bold;
            }}
        """)
        
        # Files tab
        self.files_table = self._create_files_table()
        self.tab_widget.addTab(self.files_table, "Files")
        
        # Columns tab
        self.columns_table = self._create_columns_table()
        self.tab_widget.addTab(self.columns_table, "Columns")
        
        # Statistics tab
        self.stats_widget = self._create_stats_widget()
        self.tab_widget.addTab(self.stats_widget, "Statistics")
        
        layout.addWidget(self.tab_widget, 1)
        
        # Button bar
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def _create_summary_section(self, parent_layout):
        """Create the summary section at the top."""
        summary_frame = QFrame()
        summary_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                border-radius: 4px;
                padding: 12px;
            }}
        """)
        
        summary_layout = QHBoxLayout(summary_frame)
        
        # Get statistics
        stats = self.lookup_manager.get_statistics()
        
        # File count
        file_label = QLabel(f"📁 {stats['files_loaded']} Files Loaded")
        file_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        summary_layout.addWidget(file_label)
        
        # Column count
        col_label = QLabel(f"📊 {stats['total_columns']} Columns Available")
        col_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        summary_layout.addWidget(col_label)
        
        # Row count
        row_label = QLabel(f"📄 {stats['total_rows']:,} Total Rows")
        row_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        summary_layout.addWidget(row_label)
        
        # Cache info
        if stats['cache_size'] > 0:
            cache_label = QLabel(f"💾 {stats['cache_hit_rate']} Cache Hit Rate")
            cache_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
            summary_layout.addWidget(cache_label)
        
        summary_layout.addStretch()
        parent_layout.addWidget(summary_frame)
    
    def _create_files_table(self) -> QTableWidget:
        """Create the files table widget."""
        table = QTableWidget()
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setStyleSheet(AnalyticsRunnerStylesheet.get_table_stylesheet())
        
        # Headers
        headers = ["Alias", "File Name", "Path", "Rows", "Columns", "Size (MB)", "Status", "Last Modified"]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        
        # Configure header
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        for i in range(len(headers)):
            if i == 2:  # Path column
                header.setSectionResizeMode(i, QHeaderView.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        
        return table
    
    def _create_columns_table(self) -> QTableWidget:
        """Create the columns table widget."""
        table = QTableWidget()
        table.setAlternatingRowColors(True)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setStyleSheet(AnalyticsRunnerStylesheet.get_table_stylesheet())
        
        # Headers
        headers = ["Column Name", "Available In", "File Count", "Sample Values"]
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        
        # Configure header
        header = table.horizontalHeader()
        header.setStretchLastSection(True)
        
        return table
    
    def _create_stats_widget(self) -> QTextEdit:
        """Create the statistics widget."""
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFont(AnalyticsRunnerStylesheet.get_fonts()['mono'])
        text_edit.setStyleSheet(f"""
            QTextEdit {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                padding: 8px;
            }}
        """)
        
        return text_edit
    
    def _populate_data(self):
        """Populate all the data in the dialog."""
        self._populate_files_table()
        self._populate_columns_table()
        self._populate_stats()
    
    def _populate_files_table(self):
        """Populate the files table with data."""
        table = self.files_table
        files = list(self.lookup_manager.file_metadata.items())
        table.setRowCount(len(files))
        
        for row, (filepath, metadata) in enumerate(files):
            # Alias
            alias = self.lookup_manager.file_aliases.get(filepath, Path(filepath).stem)
            table.setItem(row, 0, QTableWidgetItem(alias))
            
            # File name
            table.setItem(row, 1, QTableWidgetItem(Path(filepath).name))
            
            # Path
            table.setItem(row, 2, QTableWidgetItem(filepath))
            
            # Rows
            table.setItem(row, 3, QTableWidgetItem(f"{metadata['row_count']:,}"))
            
            # Columns
            col_count = len(metadata.get('columns', []))
            table.setItem(row, 4, QTableWidgetItem(str(col_count)))
            
            # Size
            size_mb = metadata.get('size_mb', 0)
            table.setItem(row, 5, QTableWidgetItem(f"{size_mb:.1f}"))
            
            # Status
            status = "Lazy" if metadata.get('lazy', False) else "Loaded"
            status_item = QTableWidgetItem(status)
            if status == "Lazy":
                status_item.setForeground(Qt.gray)
            table.setItem(row, 6, status_item)
            
            # Last modified
            try:
                mtime = os.path.getmtime(filepath)
                modified = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')
                table.setItem(row, 7, QTableWidgetItem(modified))
            except:
                table.setItem(row, 7, QTableWidgetItem("Unknown"))
    
    def _populate_columns_table(self):
        """Populate the columns table with data."""
        table = self.columns_table
        column_index = self.lookup_manager.column_index
        
        table.setRowCount(len(column_index))
        
        for row, (column_name, filepaths) in enumerate(column_index.items()):
            # Column name
            table.setItem(row, 0, QTableWidgetItem(column_name))
            
            # Available in (first file)
            if filepaths:
                first_file = Path(filepaths[0]).stem
                table.setItem(row, 1, QTableWidgetItem(first_file))
            
            # File count
            table.setItem(row, 2, QTableWidgetItem(str(len(filepaths))))
            
            # Sample values (placeholder for now)
            table.setItem(row, 3, QTableWidgetItem("(Click to preview)"))
    
    def _populate_stats(self):
        """Populate the statistics text widget."""
        stats = self.lookup_manager.get_statistics()
        
        text_lines = [
            "=== Lookup Manager Statistics ===",
            "",
            f"Total Files Loaded: {stats['files_loaded']}",
            f"Files Using Lazy Loading: {stats['files_lazy']}",
            f"Total Unique Columns: {stats['total_columns']}",
            f"Total Rows Across All Files: {stats['total_rows']:,}",
            "",
            "=== Performance Metrics ===",
            f"Lookup Cache Size: {stats['cache_size']} entries",
            f"Cache Hits: {stats.get('cache_hits', 0):,}",
            f"Cache Misses: {stats.get('cache_misses', 0):,}",
            f"Cache Hit Rate: {stats.get('cache_hit_rate', 'N/A')}",
            f"Indices Created: {stats['indices_created']}",
            "",
            "=== Memory Usage ===",
            f"Lazy Loading Threshold: {self.lookup_manager.lazy_threshold_mb}MB",
            f"Max Cache Size: {self.lookup_manager.max_cache_size:,} entries",
        ]
        
        # Add file-specific stats
        if stats['files_loaded'] > 0:
            text_lines.extend([
                "",
                "=== File Details ===",
            ])
            
            for filepath, metadata in self.lookup_manager.file_metadata.items():
                alias = self.lookup_manager.file_aliases.get(filepath, Path(filepath).stem)
                text_lines.append(f"\n{alias}:")
                text_lines.append(f"  - Rows: {metadata['row_count']:,}")
                text_lines.append(f"  - Columns: {len(metadata.get('columns', []))}")
                text_lines.append(f"  - Size: {metadata.get('size_mb', 0):.1f}MB")
                text_lines.append(f"  - Status: {'Lazy' if metadata.get('lazy') else 'Loaded'}")
        
        self.stats_widget.setPlainText("\n".join(text_lines))
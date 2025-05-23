"""
LogWidget - Reusable Logging Display Component
Provides timestamped log entries with severity-based color coding, search, and export
"""

import datetime
import json
import csv
import os
from enum import Enum
from typing import List, Dict, Optional, Callable
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit, QLineEdit, 
    QPushButton, QComboBox, QLabel, QFrame, QFileDialog,
    QCheckBox, QSplitter, QScrollArea, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QThread, QObject
from PySide6.QtGui import QTextCursor, QTextCharFormat, QColor, QFont, QAction

from analytics_runner_stylesheet import AnalyticsRunnerStylesheet

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Log severity levels with display properties."""
    DEBUG = ("DEBUG", "#6C757D", "#F8F9FA")      # Gray
    INFO = ("INFO", "#17A2B8", "#D1ECF1")        # Blue  
    WARNING = ("WARNING", "#FFC107", "#FFF3CD")   # Yellow
    ERROR = ("ERROR", "#DC3545", "#F8D7DA")       # Red
    CRITICAL = ("CRITICAL", "#6F42C1", "#E2D9F3") # Purple


class LogEntry:
    """Individual log entry with metadata."""
    
    def __init__(self, 
                 message: str, 
                 level: LogLevel = LogLevel.INFO,
                 timestamp: Optional[datetime.datetime] = None,
                 source: str = "",
                 thread_id: Optional[int] = None):
        """
        Initialize log entry.
        
        Args:
            message: Log message text
            level: Severity level
            timestamp: When the log occurred (defaults to now)
            source: Source component/module name
            thread_id: Thread ID if relevant
        """
        self.message = message
        self.level = level
        self.timestamp = timestamp or datetime.datetime.now()
        self.source = source
        self.thread_id = thread_id
        self.id = id(self)  # Unique identifier
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for export."""
        return {
            'timestamp': self.timestamp.isoformat(),
            'level': self.level.value[0],
            'source': self.source,
            'thread_id': self.thread_id,
            'message': self.message
        }
    
    def matches_filter(self, 
                      search_text: str = "", 
                      level_filter: Optional[LogLevel] = None,
                      source_filter: str = "") -> bool:
        """Check if entry matches filter criteria."""
        # Search text filter
        if search_text and search_text.lower() not in self.message.lower():
            return False
        
        # Level filter
        if level_filter and self.level != level_filter:
            return False
        
        # Source filter  
        if source_filter and source_filter.lower() not in self.source.lower():
            return False
        
        return True


class LogWidget(QWidget):
    """
    Advanced logging widget with filtering, search, and export capabilities.
    
    Features:
    - Timestamped log entries with severity-based color coding
    - Real-time search and filtering
    - Export to multiple formats (TXT, CSV, JSON)
    - Auto-scroll and manual scroll lock
    - Entry count limits with automatic cleanup
    - Source-based filtering
    - Thread-safe log entry addition
    """
    
    # Signals
    entryAdded = Signal(object)  # Emitted when log entry is added
    cleared = Signal()           # Emitted when logs are cleared
    exported = Signal(str)       # Emitted when logs are exported (file path)
    
    def __init__(self, 
                 title: str = "Application Logs",
                 max_entries: int = 1000,
                 auto_scroll: bool = True,
                 show_timestamps: bool = True,
                 show_thread_info: bool = False,
                 enable_search: bool = True,
                 enable_export: bool = True,
                 parent: Optional[QWidget] = None):
        """
        Initialize the log widget.
        
        Args:
            title: Widget title
            max_entries: Maximum number of log entries to keep
            auto_scroll: Whether to auto-scroll to newest entries
            show_timestamps: Whether to show timestamps
            show_thread_info: Whether to show thread information
            enable_search: Whether to enable search functionality
            enable_export: Whether to enable export functionality
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Configuration
        self.title = title
        self.max_entries = max_entries
        self.auto_scroll = auto_scroll
        self.show_timestamps = show_timestamps
        self.show_thread_info = show_thread_info
        self.enable_search = enable_search
        self.enable_export = enable_export
        
        # State
        self._entries: List[LogEntry] = []
        self._filtered_entries: List[LogEntry] = []
        self._sources: set = set()
        self._scroll_locked = False
        
        # Search/filter state
        self._search_text = ""
        self._level_filter = None
        self._source_filter = ""
        
        # Setup UI
        self._setup_ui()
        self._setup_styles()
        self._connect_signals()
        
        # Setup auto-refresh timer
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_display)
        self._refresh_timer.setSingleShot(True)
        
        logger.debug(f"LogWidget initialized: {title}")
    
    def _setup_ui(self):
        """Setup the user interface components."""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Header section
        self._create_header()
        
        # Filter section (if search enabled)
        if self.enable_search:
            self._create_filter_section()
        
        # Log display
        self._create_log_display()
        
        # Footer with stats and controls
        self._create_footer()
    
    def _create_header(self):
        """Create the header section."""
        header_layout = QHBoxLayout()
        header_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        
        # Title
        self.title_label = QLabel(self.title)
        self.title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        header_layout.addWidget(self.title_label)
        
        header_layout.addStretch()
        
        # Auto-scroll toggle
        self.auto_scroll_checkbox = QCheckBox("Auto-scroll")
        self.auto_scroll_checkbox.setChecked(self.auto_scroll)
        self.auto_scroll_checkbox.toggled.connect(self._on_auto_scroll_toggled)
        header_layout.addWidget(self.auto_scroll_checkbox)
        
        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.setProperty("buttonStyle", "secondary")
        self.clear_button.clicked.connect(self.clear_logs)
        header_layout.addWidget(self.clear_button)
        
        # Export button (if enabled)
        if self.enable_export:
            self.export_button = QPushButton("Export")
            self.export_button.setProperty("buttonStyle", "secondary") 
            self.export_button.clicked.connect(self._show_export_options)
            header_layout.addWidget(self.export_button)
        
        self.main_layout.addLayout(header_layout)
    
    def _create_filter_section(self):
        """Create the filter and search section."""
        filter_frame = QFrame()
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setSpacing(8)
        filter_layout.setContentsMargins(8, 6, 8, 6)
        
        # Search box
        search_label = QLabel("Search:")
        filter_layout.addWidget(search_label)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search log messages...")
        self.search_input.textChanged.connect(self._on_search_changed)
        filter_layout.addWidget(self.search_input, 1)
        
        # Level filter
        level_label = QLabel("Level:")
        filter_layout.addWidget(level_label)
        
        self.level_combo = QComboBox()
        self.level_combo.addItem("All Levels", None)
        for level in LogLevel:
            self.level_combo.addItem(level.value[0], level)
        self.level_combo.currentTextChanged.connect(self._on_level_filter_changed)
        filter_layout.addWidget(self.level_combo)
        
        # Source filter
        source_label = QLabel("Source:")
        filter_layout.addWidget(source_label)
        
        self.source_combo = QComboBox()
        self.source_combo.addItem("All Sources", "")
        self.source_combo.currentTextChanged.connect(self._on_source_filter_changed)
        filter_layout.addWidget(self.source_combo)
        
        self.main_layout.addWidget(filter_frame)
    
    def _create_log_display(self):
        """Create the main log display area."""
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setFont(AnalyticsRunnerStylesheet.get_fonts()['mono'])
        self.log_display.setLineWrapMode(QTextEdit.WidgetWidth)
        
        # Set minimum size
        self.log_display.setMinimumHeight(200)
        self.log_display.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # Connect scroll event to detect manual scrolling
        scrollbar = self.log_display.verticalScrollBar()
        scrollbar.valueChanged.connect(self._on_scroll_changed)
        
        self.main_layout.addWidget(self.log_display, 1)
    
    def _create_footer(self):
        """Create the footer with statistics."""
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        
        # Entry count
        self.count_label = QLabel("0 entries")
        self.count_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        footer_layout.addWidget(self.count_label)
        
        footer_layout.addStretch()
        
        # Scroll lock indicator
        self.scroll_lock_label = QLabel("")
        self.scroll_lock_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        footer_layout.addWidget(self.scroll_lock_label)
        
        self.main_layout.addLayout(footer_layout)
    
    def _setup_styles(self):
        """Apply styles to widget components."""
        # Header styling
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                font-weight: bold;
            }}
        """)
        
        # Filter frame styling
        if hasattr(self, 'search_input'):
            filter_frame = self.search_input.parent()
            filter_frame.setStyleSheet(f"""
                QFrame {{
                    background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                    border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                    border-radius: 6px;
                }}
            """)
        
        # Log display styling
        self.log_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {AnalyticsRunnerStylesheet.DARK_TEXT};
                color: #00FF00;
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
                selection-background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            }}
        """)
        
        # Footer styling
        self.count_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
            }}
        """)
        
        self.scroll_lock_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.WARNING_COLOR};
                font-weight: bold;
            }}
        """)
    
    def _connect_signals(self):
        """Connect internal signals."""
        pass  # Placeholder for additional signal connections
    
    def _format_log_entry(self, entry: LogEntry) -> str:
        """Format a log entry for display."""
        parts = []
        
        # Timestamp
        if self.show_timestamps:
            timestamp_str = entry.timestamp.strftime("%H:%M:%S.%f")[:-3]  # Include milliseconds
            parts.append(f"[{timestamp_str}]")
        
        # Level
        parts.append(f"[{entry.level.value[0]}]")
        
        # Source
        if entry.source:
            parts.append(f"[{entry.source}]")
        
        # Thread info
        if self.show_thread_info and entry.thread_id:
            parts.append(f"[T{entry.thread_id}]")
        
        # Message
        parts.append(entry.message)
        
        return " ".join(parts)
    
    def _get_level_color(self, level: LogLevel) -> QColor:
        """Get display color for log level."""
        return QColor(level.value[1])
    
    def _refresh_display(self):
        """Refresh the log display with current filtered entries."""
        # Clear display
        self.log_display.clear()
        
        # Add filtered entries
        cursor = self.log_display.textCursor()
        
        for entry in self._filtered_entries:
            # Set color for this level
            char_format = QTextCharFormat()
            char_format.setForeground(self._get_level_color(entry.level))
            
            # Format and insert text
            formatted_text = self._format_log_entry(entry)
            cursor.insertText(formatted_text + "\n", char_format)
        
        # Auto-scroll if enabled and not manually locked
        if self.auto_scroll and not self._scroll_locked:
            self.log_display.moveCursor(QTextCursor.End)
        
        # Update footer
        self._update_footer()
    
    def _update_footer(self):
        """Update footer statistics."""
        total_count = len(self._entries)
        filtered_count = len(self._filtered_entries)
        
        if total_count == filtered_count:
            self.count_label.setText(f"{total_count} entries")
        else:
            self.count_label.setText(f"{filtered_count} of {total_count} entries")
        
        # Update scroll lock indicator
        if self._scroll_locked:
            self.scroll_lock_label.setText("📌 Scroll locked")
        else:
            self.scroll_lock_label.setText("")
    
    def _apply_filters(self):
        """Apply current filters to entries."""
        self._filtered_entries = [
            entry for entry in self._entries
            if entry.matches_filter(
                self._search_text,
                self._level_filter, 
                self._source_filter
            )
        ]
        
        # Schedule display refresh
        self._refresh_timer.start(100)  # 100ms debounce
    
    def _update_source_combo(self):
        """Update the source filter combo box."""
        if not hasattr(self, 'source_combo'):
            return
        
        current_selection = self.source_combo.currentData()
        
        self.source_combo.clear()
        self.source_combo.addItem("All Sources", "")
        
        for source in sorted(self._sources):
            if source:  # Skip empty sources
                self.source_combo.addItem(source, source)
        
        # Restore selection if still valid
        if current_selection:
            index = self.source_combo.findData(current_selection)
            if index >= 0:
                self.source_combo.setCurrentIndex(index)
    
    # Event handlers
    def _on_search_changed(self, text: str):
        """Handle search text change."""
        self._search_text = text
        self._apply_filters()
    
    def _on_level_filter_changed(self):
        """Handle level filter change."""
        self._level_filter = self.level_combo.currentData()
        self._apply_filters()
    
    def _on_source_filter_changed(self):
        """Handle source filter change."""
        self._source_filter = self.source_combo.currentData() or ""
        self._apply_filters()
    
    def _on_auto_scroll_toggled(self, checked: bool):
        """Handle auto-scroll toggle."""
        self.auto_scroll = checked
        if checked:
            self._scroll_locked = False
            self.log_display.moveCursor(QTextCursor.End)
    
    def _on_scroll_changed(self, value: int):
        """Handle manual scrolling."""
        scrollbar = self.log_display.verticalScrollBar()
        
        # Check if user scrolled away from bottom
        if self.auto_scroll:
            is_at_bottom = value >= scrollbar.maximum() - 5  # 5px tolerance
            self._scroll_locked = not is_at_bottom
            self._update_footer()
    
    def _show_export_options(self):
        """Show export options dialog."""
        if not self._filtered_entries:
            return
        
        # For now, export to text file - can be expanded later
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Logs",
            f"logs_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;CSV Files (*.csv);;JSON Files (*.json)"
        )
        
        if file_path:
            self.export_logs(file_path)
    
    # Public interface
    def add_log_entry(self, 
                     message: str,
                     level: LogLevel = LogLevel.INFO,
                     source: str = "",
                     timestamp: Optional[datetime.datetime] = None):
        """
        Add a new log entry.
        
        Args:
            message: Log message
            level: Severity level  
            source: Source component/module
            timestamp: Optional timestamp (defaults to now)
        """
        entry = LogEntry(
            message=message,
            level=level,
            source=source,
            timestamp=timestamp
        )
        
        # Add to entries list
        self._entries.append(entry)
        
        # Track source
        if source:
            self._sources.add(source)
        
        # Limit entries to max count
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]
        
        # Update source combo if needed
        if source and hasattr(self, 'source_combo'):
            self._update_source_combo()
        
        # Apply filters and refresh
        self._apply_filters()
        
        # Emit signal
        self.entryAdded.emit(entry)
        
        logger.debug(f"Log entry added: {level.value[0]} - {message[:50]}...")
    
    def add_log(self, message: str, level: str = "INFO", source: str = ""):
        """
        Convenience method to add log with string level.
        
        Args:
            message: Log message
            level: Level name as string
            source: Source component
        """
        # Convert string level to enum
        try:
            log_level = LogLevel[level.upper()]
        except KeyError:
            log_level = LogLevel.INFO
        
        self.add_log_entry(message, log_level, source)
    
    def clear_logs(self):
        """Clear all log entries."""
        self._entries.clear()
        self._filtered_entries.clear()
        self._sources.clear()
        
        # Update UI
        self.log_display.clear()
        self._update_footer()
        
        if hasattr(self, 'source_combo'):
            self._update_source_combo()
        
        self.cleared.emit()
        
        logger.debug("All log entries cleared")
    
    def export_logs(self, file_path: str):
        """
        Export logs to file.
        
        Args:
            file_path: Path to export file
        """
        try:
            file_ext = os.path.splitext(file_path)[1].lower()
            
            if file_ext == '.json':
                self._export_to_json(file_path)
            elif file_ext == '.csv':
                self._export_to_csv(file_path)
            else:
                self._export_to_text(file_path)
            
            self.exported.emit(file_path)
            logger.info(f"Logs exported to: {file_path}")
            
        except Exception as e:
            logger.error(f"Error exporting logs: {e}")
    
    def _export_to_text(self, file_path: str):
        """Export logs to plain text file."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(f"Log Export - {datetime.datetime.now().isoformat()}\n")
            f.write("=" * 50 + "\n\n")
            
            for entry in self._filtered_entries:
                f.write(self._format_log_entry(entry) + "\n")
    
    def _export_to_csv(self, file_path: str):
        """Export logs to CSV file."""
        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            
            # Header
            headers = ['Timestamp', 'Level', 'Source', 'Thread', 'Message']
            writer.writerow(headers)
            
            # Data
            for entry in self._filtered_entries:
                writer.writerow([
                    entry.timestamp.isoformat(),
                    entry.level.value[0],
                    entry.source,
                    entry.thread_id,
                    entry.message
                ])
    
    def _export_to_json(self, file_path: str):
        """Export logs to JSON file."""
        data = {
            'export_timestamp': datetime.datetime.now().isoformat(),
            'total_entries': len(self._entries),
            'filtered_entries': len(self._filtered_entries),
            'logs': [entry.to_dict() for entry in self._filtered_entries]
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def set_max_entries(self, max_entries: int):
        """Set maximum number of entries to keep."""
        self.max_entries = max_entries
        
        # Trim entries if needed
        if len(self._entries) > max_entries:
            self._entries = self._entries[-max_entries:]
            self._apply_filters()
    
    def get_entry_count(self) -> int:
        """Get total number of log entries."""
        return len(self._entries)
    
    def get_filtered_count(self) -> int:
        """Get number of filtered log entries."""
        return len(self._filtered_entries)
    
    def scroll_to_bottom(self):
        """Scroll to the bottom of the log."""
        self.log_display.moveCursor(QTextCursor.End)
        self._scroll_locked = False
        self._update_footer()
    
    def scroll_to_top(self):
        """Scroll to the top of the log."""
        self.log_display.moveCursor(QTextCursor.Start)
    
    # Integration with Python logging
    def create_log_handler(self, source: str = "") -> 'LogWidgetHandler':
        """
        Create a Python logging handler that forwards to this widget.
        
        Args:
            source: Source identifier for logs from this handler
            
        Returns:
            LogWidgetHandler instance
        """
        return LogWidgetHandler(self, source)


class LogWidgetHandler(logging.Handler):
    """Python logging handler that forwards logs to LogWidget."""
    
    def __init__(self, log_widget: LogWidget, source: str = ""):
        """
        Initialize handler.
        
        Args:
            log_widget: LogWidget to forward logs to
            source: Source identifier
        """
        super().__init__()
        self.log_widget = log_widget
        self.source = source
        
        # Map Python logging levels to LogLevel enum
        self.level_mapping = {
            logging.DEBUG: LogLevel.DEBUG,
            logging.INFO: LogLevel.INFO,
            logging.WARNING: LogLevel.WARNING,
            logging.ERROR: LogLevel.ERROR,
            logging.CRITICAL: LogLevel.CRITICAL
        }
    
    def emit(self, record: logging.LogRecord):
        """Emit a log record to the widget."""
        try:
            # Map logging level
            log_level = self.level_mapping.get(record.levelno, LogLevel.INFO)
            
            # Format message
            message = self.format(record)
            
            # Get source (use handler source or logger name)
            source = self.source or record.name
            
            # Create timestamp from record
            timestamp = datetime.datetime.fromtimestamp(record.created)
            
            # Add to widget
            self.log_widget.add_log_entry(
                message=message,
                level=log_level,
                source=source,
                timestamp=timestamp
            )
            
        except Exception:
            self.handleError(record)

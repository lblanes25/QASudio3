"""
Debug Panel for Analytics Runner
Provides runtime debugging controls and system information
"""

import sys
import os
import logging
import platform
import gc
from typing import Dict, Any
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox,
    QPushButton, QTextEdit, QTabWidget, QTableWidget,
    QTableWidgetItem, QHeaderView, QSplitter, QFrame
)
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont

from analytics_runner_stylesheet import AnalyticsRunnerStylesheet
from error_handler import get_error_handler


class SystemInfoWidget(QWidget):
    """Widget displaying system information"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.update_info()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # System info table
        self.info_table = QTableWidget()
        self.info_table.setColumnCount(2)
        self.info_table.setHorizontalHeaderLabels(["Property", "Value"])
        self.info_table.horizontalHeader().setStretchLastSection(True)
        self.info_table.setAlternatingRowColors(True)
        layout.addWidget(self.info_table)

        # Refresh button
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.update_info)
        layout.addWidget(refresh_btn)

    def update_info(self):
        """Update system information display"""
        info = {
            "Python Version": platform.python_version(),
            "Platform": platform.platform(),
            "Architecture": platform.machine(),
            "Processor": platform.processor(),
            "Python Executable": sys.executable,
            "Current Working Directory": os.getcwd(),
            "PySide6 Version": self._get_pyside_version(),
            "Memory Objects": str(len(gc.get_objects())),
            "Memory Stats": self._get_memory_stats(),
        }

        self.info_table.setRowCount(len(info))

        for row, (key, value) in enumerate(info.items()):
            self.info_table.setItem(row, 0, QTableWidgetItem(key))
            self.info_table.setItem(row, 1, QTableWidgetItem(str(value)))

    def _get_pyside_version(self) -> str:
        try:
            import PySide6
            return PySide6.__version__
        except:
            return "Unknown"

    def _get_memory_stats(self) -> str:
        try:
            import psutil
            process = psutil.Process()
            memory_info = process.memory_info()
            return f"RSS: {memory_info.rss // 1024 // 1024}MB, VMS: {memory_info.vms // 1024 // 1024}MB"
        except ImportError:
            return "psutil not available"
        except:
            return "Unable to get memory info"


class LogViewerWidget(QWidget):
    """Widget for viewing application logs"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_log_monitoring()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Controls
        controls_layout = QHBoxLayout()

        self.auto_refresh_cb = QCheckBox("Auto Refresh")
        self.auto_refresh_cb.setChecked(True)
        self.auto_refresh_cb.toggled.connect(self.toggle_auto_refresh)
        controls_layout.addWidget(self.auto_refresh_cb)

        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_logs)
        controls_layout.addWidget(clear_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_logs)
        controls_layout.addWidget(refresh_btn)

        controls_layout.addStretch()
        layout.addLayout(controls_layout)

        # Log display
        self.log_display = QTextEdit()
        self.log_display.setFont(AnalyticsRunnerStylesheet.get_fonts()['mono'])
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)

    def setup_log_monitoring(self):
        """Setup automatic log refresh"""
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.refresh_logs)
        self.refresh_timer.start(2000)  # Refresh every 2 seconds

    def toggle_auto_refresh(self, enabled: bool):
        """Toggle automatic log refresh"""
        if enabled:
            self.refresh_timer.start(2000)
        else:
            self.refresh_timer.stop()

    def refresh_logs(self):
        """Refresh log display"""
        try:
            log_file = Path("logs") / "analytics_runner.log"
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    # Read last 1000 lines
                    lines = f.readlines()
                    recent_lines = lines[-1000:] if len(lines) > 1000 else lines
                    self.log_display.setPlainText(''.join(recent_lines))

                    # Scroll to bottom
                    scrollbar = self.log_display.verticalScrollBar()
                    scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            self.log_display.setPlainText(f"Error reading log file: {e}")

    def clear_logs(self):
        """Clear log display"""
        self.log_display.clear()


class DebugPanel(QWidget):
    """
    Debug panel providing runtime debugging controls and system information.

    Features:
    - Debug mode toggle
    - Log level controls
    - System information display
    - Live log viewer
    - Memory and performance monitoring
    """

    # Signals
    debugModeChanged = Signal(bool)
    logLevelChanged = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.error_handler = get_error_handler()
        self.setup_ui()
        self.setup_connections()

        # Update timer for performance metrics
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_performance_metrics)
        self.update_timer.start(5000)  # Update every 5 seconds

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Title
        title_label = QLabel("Debug Panel")
        title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['title'])
        title_label.setStyleSheet(AnalyticsRunnerStylesheet.get_header_stylesheet())
        layout.addWidget(title_label)

        # Controls section
        controls_frame = QFrame()
        controls_frame.setStyleSheet(AnalyticsRunnerStylesheet.get_panel_stylesheet())
        controls_layout = QVBoxLayout(controls_frame)

        # Debug mode toggle
        self.debug_mode_cb = QCheckBox("Enable Debug Mode")
        self.debug_mode_cb.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        if self.error_handler:
            self.debug_mode_cb.setChecked(self.error_handler.debug_mode)
        controls_layout.addWidget(self.debug_mode_cb)

        # Log level controls
        log_level_layout = QHBoxLayout()
        log_level_layout.addWidget(QLabel("Log Level:"))

        self.log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        for level in self.log_levels:
            cb = QCheckBox(level)
            cb.setObjectName(f"log_level_{level}")
            if level == "INFO":
                cb.setChecked(True)
            log_level_layout.addWidget(cb)

        controls_layout.addLayout(log_level_layout)

        # Action buttons
        button_layout = QHBoxLayout()

        force_gc_btn = QPushButton("Force Garbage Collection")
        force_gc_btn.clicked.connect(self.force_garbage_collection)
        button_layout.addWidget(force_gc_btn)

        test_error_btn = QPushButton("Test Error Handling")
        test_error_btn.clicked.connect(self.test_error_handling)
        button_layout.addWidget(test_error_btn)

        controls_layout.addLayout(button_layout)
        layout.addWidget(controls_frame)

        # Tab widget for detailed views
        self.tab_widget = QTabWidget()

        # System info tab
        self.system_info_widget = SystemInfoWidget()
        self.tab_widget.addTab(self.system_info_widget, "System Info")

        # Log viewer tab
        self.log_viewer_widget = LogViewerWidget()
        self.tab_widget.addTab(self.log_viewer_widget, "Log Viewer")

        # Performance tab
        self.performance_widget = self.create_performance_widget()
        self.tab_widget.addTab(self.performance_widget, "Performance")

        layout.addWidget(self.tab_widget)

    def create_performance_widget(self) -> QWidget:
        """Create performance monitoring widget"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Performance metrics display
        self.perf_display = QTextEdit()
        self.perf_display.setFont(AnalyticsRunnerStylesheet.get_fonts()['mono'])
        self.perf_display.setReadOnly(True)
        layout.addWidget(self.perf_display)

        return widget

    def setup_connections(self):
        """Setup signal connections"""
        self.debug_mode_cb.toggled.connect(self.on_debug_mode_changed)

        # Connect log level checkboxes
        for level in self.log_levels:
            cb = self.findChild(QCheckBox, f"log_level_{level}")
            if cb:
                cb.toggled.connect(lambda checked, l=level: self.on_log_level_changed(l, checked))

        # Connect to error handler if available
        if self.error_handler:
            self.error_handler.debugModeChanged.connect(self.debug_mode_cb.setChecked)

    def on_debug_mode_changed(self, enabled: bool):
        """Handle debug mode change"""
        if self.error_handler:
            self.error_handler.set_debug_mode(enabled)

        self.debugModeChanged.emit(enabled)

    def on_log_level_changed(self, level: str, enabled: bool):
        """Handle log level change"""
        if enabled:
            # Set logging level
            numeric_level = getattr(logging, level, logging.INFO)
            logging.getLogger().setLevel(numeric_level)
            self.logLevelChanged.emit(level)

    def force_garbage_collection(self):
        """Force garbage collection"""
        collected = gc.collect()
        if self.error_handler:
            self.error_handler.report_info(
                f"Garbage collection completed. Collected {collected} objects."
            )

    def test_error_handling(self):
        """Test error handling system"""
        try:
            # Intentionally raise an error
            raise ValueError("This is a test error for debugging purposes")
        except Exception as e:
            if self.error_handler:
                self.error_handler.report_error(e, "Debug panel test error")

    def update_performance_metrics(self):
        """Update performance metrics display"""
        try:
            metrics = []

            # Memory information
            try:
                import psutil
                process = psutil.Process()
                memory_info = process.memory_info()
                cpu_percent = process.cpu_percent()

                metrics.extend([
                    f"Memory Usage: {memory_info.rss // 1024 // 1024} MB",
                    f"Virtual Memory: {memory_info.vms // 1024 // 1024} MB",
                    f"CPU Usage: {cpu_percent}%",
                ])
            except ImportError:
                metrics.append("psutil not available for detailed metrics")

            # Python objects
            object_count = len(gc.get_objects())
            metrics.append(f"Python Objects: {object_count}")

            # Threading information
            import threading
            thread_count = threading.active_count()
            metrics.append(f"Active Threads: {thread_count}")

            # Logging handlers
            root_logger = logging.getLogger()
            handler_count = len(root_logger.handlers)
            metrics.append(f"Log Handlers: {handler_count}")

            # Update display
            timestamp = f"Updated: {logging.Formatter().formatTime(logging.LogRecord('', 0, '', 0, '', (), None))}"
            content = f"{timestamp}\n\n" + "\n".join(metrics)
            self.perf_display.setPlainText(content)

        except Exception as e:
            self.perf_display.setPlainText(f"Error updating metrics: {e}")
"""
Test suite for LogWidget
Following TEST_GUIDELINES.md - unit tests with minimal dependencies
"""

import unittest
import sys
import tempfile
import os
import json
import csv
import datetime
import logging
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

# Skip PySide6 imports if not available
try:
    from PySide6.QtWidgets import QApplication
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    PYSIDE6_AVAILABLE = True
except ImportError:
    PYSIDE6_AVAILABLE = False

# Mock PySide6 if not available
if not PYSIDE6_AVAILABLE:
    # Create mock classes for testing logic without GUI
    class MockQWidget:
        def __init__(self, *args, **kwargs):
            pass
    
    class MockSignal:
        def emit(self, *args):
            pass
    
    # Mock the imports
    import sys
    from unittest.mock import MagicMock
    
    mock_module = MagicMock()
    mock_module.QWidget = MockQWidget
    mock_module.Signal = MockSignal
    mock_module.QVBoxLayout = MagicMock
    mock_module.QHBoxLayout = MagicMock
    mock_module.QTextEdit = MagicMock
    mock_module.QLineEdit = MagicMock
    mock_module.QPushButton = MagicMock
    mock_module.QComboBox = MagicMock
    mock_module.QLabel = MagicMock
    mock_module.QFrame = MagicMock
    mock_module.QFileDialog = MagicMock
    mock_module.QCheckBox = MagicMock
    mock_module.QSplitter = MagicMock
    mock_module.QScrollArea = MagicMock
    mock_module.QSizePolicy = MagicMock
    mock_module.Qt = MagicMock()
    mock_module.QTimer = MagicMock
    mock_module.QThread = MagicMock
    mock_module.QObject = MagicMock
    mock_module.QTextCursor = MagicMock
    mock_module.QTextCharFormat = MagicMock
    mock_module.QColor = MagicMock
    mock_module.QFont = MagicMock
    mock_module.QAction = MagicMock
    
    sys.modules['PySide6.QtWidgets'] = mock_module
    sys.modules['PySide6.QtCore'] = mock_module
    sys.modules['PySide6.QtGui'] = mock_module

# Mock the stylesheet module
sys.modules['analytics_runner_stylesheet'] = MagicMock()

# Now import our module
from ui.common.widgets.log_widget import LogEntry, LogLevel, LogWidget, LogWidgetHandler


class TestLogLevel(unittest.TestCase):
    """Test LogLevel enum functionality."""
    
    def test_log_level_values(self):
        """Test that all log levels have correct values."""
        self.assertEqual(LogLevel.DEBUG.value[0], "DEBUG")
        self.assertEqual(LogLevel.INFO.value[0], "INFO")
        self.assertEqual(LogLevel.WARNING.value[0], "WARNING")
        self.assertEqual(LogLevel.ERROR.value[0], "ERROR")
        self.assertEqual(LogLevel.CRITICAL.value[0], "CRITICAL")
    
    def test_log_level_colors(self):
        """Test that all log levels have color information."""
        for level in LogLevel:
            self.assertEqual(len(level.value), 3)  # name, foreground, background
            self.assertTrue(level.value[1].startswith('#'))  # foreground color
            self.assertTrue(level.value[2].startswith('#'))  # background color


class TestLogEntry(unittest.TestCase):
    """Test LogEntry functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.test_timestamp = datetime.datetime(2023, 1, 1, 12, 0, 0)
    
    def test_log_entry_creation(self):
        """Test basic log entry creation."""
        entry = LogEntry(
            message="Test message",
            level=LogLevel.INFO,
            timestamp=self.test_timestamp,
            source="TestSource",
            thread_id=123
        )
        
        self.assertEqual(entry.message, "Test message")
        self.assertEqual(entry.level, LogLevel.INFO)
        self.assertEqual(entry.timestamp, self.test_timestamp)
        self.assertEqual(entry.source, "TestSource")
        self.assertEqual(entry.thread_id, 123)
        self.assertIsNotNone(entry.id)
    
    def test_log_entry_defaults(self):
        """Test log entry with default values."""
        entry = LogEntry("Test message")
        
        self.assertEqual(entry.message, "Test message")
        self.assertEqual(entry.level, LogLevel.INFO)
        self.assertIsInstance(entry.timestamp, datetime.datetime)
        self.assertEqual(entry.source, "")
        self.assertIsNone(entry.thread_id)
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        entry = LogEntry(
            message="Test message",
            level=LogLevel.ERROR,
            timestamp=self.test_timestamp,
            source="TestSource",
            thread_id=456
        )
        
        result = entry.to_dict()
        
        self.assertEqual(result['message'], "Test message")
        self.assertEqual(result['level'], "ERROR")
        self.assertEqual(result['timestamp'], self.test_timestamp.isoformat())
        self.assertEqual(result['source'], "TestSource")
        self.assertEqual(result['thread_id'], 456)
    
    def test_matches_filter_text(self):
        """Test text-based filtering."""
        entry = LogEntry("This is a test message", LogLevel.INFO, source="TestSource")
        
        # Should match
        self.assertTrue(entry.matches_filter(search_text="test"))
        self.assertTrue(entry.matches_filter(search_text="TEST"))  # Case insensitive
        self.assertTrue(entry.matches_filter(search_text="message"))
        
        # Should not match
        self.assertFalse(entry.matches_filter(search_text="missing"))
        self.assertFalse(entry.matches_filter(search_text="xyz"))
    
    def test_matches_filter_level(self):
        """Test level-based filtering."""
        entry = LogEntry("Test message", LogLevel.ERROR)
        
        # Should match
        self.assertTrue(entry.matches_filter(level_filter=LogLevel.ERROR))
        
        # Should not match
        self.assertFalse(entry.matches_filter(level_filter=LogLevel.INFO))
        self.assertFalse(entry.matches_filter(level_filter=LogLevel.DEBUG))
    
    def test_matches_filter_source(self):
        """Test source-based filtering."""
        entry = LogEntry("Test message", source="TestModule")
        
        # Should match
        self.assertTrue(entry.matches_filter(source_filter="Test"))
        self.assertTrue(entry.matches_filter(source_filter="test"))  # Case insensitive
        self.assertTrue(entry.matches_filter(source_filter="Module"))
        
        # Should not match
        self.assertFalse(entry.matches_filter(source_filter="Other"))
        self.assertFalse(entry.matches_filter(source_filter="xyz"))
    
    def test_matches_filter_combined(self):
        """Test combined filtering criteria."""
        entry = LogEntry(
            "Test error message", 
            LogLevel.ERROR, 
            source="TestModule"
        )
        
        # All criteria match
        self.assertTrue(entry.matches_filter(
            search_text="error",
            level_filter=LogLevel.ERROR,
            source_filter="Test"
        ))
        
        # One criterion doesn't match
        self.assertFalse(entry.matches_filter(
            search_text="error",
            level_filter=LogLevel.INFO,  # Wrong level
            source_filter="Test"
        ))


class TestLogWidget(unittest.TestCase):
    """Test LogWidget functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock QApplication if needed
        if PYSIDE6_AVAILABLE:
            self.app = QApplication.instance()
            if self.app is None:
                self.app = QApplication([])
        
        # Create widget with mocked UI setup
        with patch.object(LogWidget, '_setup_ui'), \
             patch.object(LogWidget, '_setup_styles'), \
             patch.object(LogWidget, '_connect_signals'):
            self.widget = LogWidget(title="Test Log")
        
        # Mock the UI components that tests depend on
        self.widget.log_display = Mock()
        self.widget.count_label = Mock()
        self.widget.scroll_lock_label = Mock()
        self.widget._refresh_timer = Mock()
    
    def test_widget_initialization(self):
        """Test widget initialization with default parameters."""
        self.assertEqual(self.widget.title, "Test Log")
        self.assertEqual(self.widget.max_entries, 1000)
        self.assertTrue(self.widget.auto_scroll)
        self.assertTrue(self.widget.show_timestamps)
        self.assertFalse(self.widget.show_thread_info)
        self.assertTrue(self.widget.enable_search)
        self.assertTrue(self.widget.enable_export)
    
    def test_widget_initialization_custom(self):
        """Test widget initialization with custom parameters."""
        with patch.object(LogWidget, '_setup_ui'), \
             patch.object(LogWidget, '_setup_styles'), \
             patch.object(LogWidget, '_connect_signals'):
            widget = LogWidget(
                title="Custom Log",
                max_entries=500,
                auto_scroll=False,
                show_timestamps=False,
                show_thread_info=True,
                enable_search=False,
                enable_export=False
            )
        
        self.assertEqual(widget.title, "Custom Log")
        self.assertEqual(widget.max_entries, 500)
        self.assertFalse(widget.auto_scroll)
        self.assertFalse(widget.show_timestamps)
        self.assertTrue(widget.show_thread_info)
        self.assertFalse(widget.enable_search)
        self.assertFalse(widget.enable_export)
    
    def test_add_log_entry(self):
        """Test adding log entries."""
        # Add a log entry
        self.widget.add_log_entry("Test message", LogLevel.INFO, "TestSource")
        
        # Check that entry was added
        self.assertEqual(len(self.widget._entries), 1)
        entry = self.widget._entries[0]
        self.assertEqual(entry.message, "Test message")
        self.assertEqual(entry.level, LogLevel.INFO)
        self.assertEqual(entry.source, "TestSource")
        
        # Check that source was tracked
        self.assertIn("TestSource", self.widget._sources)
    
    def test_add_log_string_level(self):
        """Test adding log with string level."""
        self.widget.add_log("Test message", "ERROR", "TestSource")
        
        self.assertEqual(len(self.widget._entries), 1)
        entry = self.widget._entries[0]
        self.assertEqual(entry.level, LogLevel.ERROR)
    
    def test_add_log_invalid_level(self):
        """Test adding log with invalid string level."""
        self.widget.add_log("Test message", "INVALID", "TestSource")
        
        self.assertEqual(len(self.widget._entries), 1)
        entry = self.widget._entries[0]
        self.assertEqual(entry.level, LogLevel.INFO)  # Should default to INFO
    
    def test_max_entries_limit(self):
        """Test that entries are limited to max_entries."""
        self.widget.max_entries = 3
        
        # Add 5 entries
        for i in range(5):
            self.widget.add_log_entry(f"Message {i}", LogLevel.INFO)
        
        # Should only have 3 entries (the last 3)
        self.assertEqual(len(self.widget._entries), 3)
        self.assertEqual(self.widget._entries[0].message, "Message 2")
        self.assertEqual(self.widget._entries[2].message, "Message 4")
    
    def test_clear_logs(self):
        """Test clearing all logs."""
        # Add some entries
        self.widget.add_log_entry("Message 1", LogLevel.INFO)
        self.widget.add_log_entry("Message 2", LogLevel.ERROR, "Source1")
        
        # Clear logs
        self.widget.clear_logs()
        
        # Check that everything is cleared
        self.assertEqual(len(self.widget._entries), 0)
        self.assertEqual(len(self.widget._filtered_entries), 0)
        self.assertEqual(len(self.widget._sources), 0)
    
    def test_filtering_by_search_text(self):
        """Test filtering by search text."""
        # Add test entries
        self.widget.add_log_entry("Error occurred", LogLevel.ERROR)
        self.widget.add_log_entry("Info message", LogLevel.INFO)
        self.widget.add_log_entry("Another error", LogLevel.ERROR)
        
        # Apply search filter
        self.widget._search_text = "error"
        self.widget._apply_filters()
        
        # Should have 2 filtered entries
        self.assertEqual(len(self.widget._filtered_entries), 2)
        self.assertIn("Error occurred", [e.message for e in self.widget._filtered_entries])
        self.assertIn("Another error", [e.message for e in self.widget._filtered_entries])
    
    def test_filtering_by_level(self):
        """Test filtering by log level."""
        # Add test entries
        self.widget.add_log_entry("Debug message", LogLevel.DEBUG)
        self.widget.add_log_entry("Info message", LogLevel.INFO)
        self.widget.add_log_entry("Error message", LogLevel.ERROR)
        
        # Apply level filter
        self.widget._level_filter = LogLevel.ERROR
        self.widget._apply_filters()
        
        # Should have 1 filtered entry
        self.assertEqual(len(self.widget._filtered_entries), 1)
        self.assertEqual(self.widget._filtered_entries[0].level, LogLevel.ERROR)
    
    def test_filtering_by_source(self):
        """Test filtering by source."""
        # Add test entries
        self.widget.add_log_entry("Message 1", source="Module1")
        self.widget.add_log_entry("Message 2", source="Module2")
        self.widget.add_log_entry("Message 3", source="Module1")
        
        # Apply source filter
        self.widget._source_filter = "Module1"
        self.widget._apply_filters()
        
        # Should have 2 filtered entries
        self.assertEqual(len(self.widget._filtered_entries), 2)
        for entry in self.widget._filtered_entries:
            self.assertEqual(entry.source, "Module1")
    
    def test_format_log_entry_with_timestamps(self):
        """Test log entry formatting with timestamps."""
        self.widget.show_timestamps = True
        self.widget.show_thread_info = False
        
        timestamp = datetime.datetime(2023, 1, 1, 12, 30, 45, 123000)
        entry = LogEntry("Test message", LogLevel.INFO, timestamp, "TestSource")
        
        formatted = self.widget._format_log_entry(entry)
        
        self.assertIn("[12:30:45.123]", formatted)
        self.assertIn("[INFO]", formatted)
        self.assertIn("[TestSource]", formatted)
        self.assertIn("Test message", formatted)
    
    def test_format_log_entry_without_timestamps(self):
        """Test log entry formatting without timestamps."""
        self.widget.show_timestamps = False
        self.widget.show_thread_info = False
        
        entry = LogEntry("Test message", LogLevel.ERROR, source="TestSource")
        
        formatted = self.widget._format_log_entry(entry)
        
        self.assertNotIn(":", formatted)  # No timestamp
        self.assertIn("[ERROR]", formatted)
        self.assertIn("[TestSource]", formatted)
        self.assertIn("Test message", formatted)
    
    def test_format_log_entry_with_thread_info(self):
        """Test log entry formatting with thread info."""
        self.widget.show_timestamps = False
        self.widget.show_thread_info = True
        
        entry = LogEntry("Test message", LogLevel.INFO, thread_id=123)
        
        formatted = self.widget._format_log_entry(entry)
        
        self.assertIn("[T123]", formatted)
    
    def test_get_entry_count(self):
        """Test getting entry counts."""
        self.assertEqual(self.widget.get_entry_count(), 0)
        self.assertEqual(self.widget.get_filtered_count(), 0)
        
        # Add entries
        self.widget.add_log_entry("Message 1", LogLevel.INFO)
        self.widget.add_log_entry("Error message", LogLevel.ERROR)
        
        self.assertEqual(self.widget.get_entry_count(), 2)
        self.assertEqual(self.widget.get_filtered_count(), 2)
        
        # Apply filter
        self.widget._search_text = "error"
        self.widget._apply_filters()
        
        self.assertEqual(self.widget.get_entry_count(), 2)
        self.assertEqual(self.widget.get_filtered_count(), 1)
    
    def test_set_max_entries(self):
        """Test changing max entries limit."""
        # Add entries
        for i in range(5):
            self.widget.add_log_entry(f"Message {i}")
        
        self.assertEqual(len(self.widget._entries), 5)
        
        # Reduce max entries
        self.widget.set_max_entries(3)
        
        self.assertEqual(self.widget.max_entries, 3)
        self.assertEqual(len(self.widget._entries), 3)


class TestLogWidgetExport(unittest.TestCase):
    """Test LogWidget export functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch.object(LogWidget, '_setup_ui'), \
             patch.object(LogWidget, '_setup_styles'), \
             patch.object(LogWidget, '_connect_signals'):
            self.widget = LogWidget()
        
        # Mock UI components
        self.widget._refresh_timer = Mock()
        
        # Add test data
        self.widget.add_log_entry("Info message", LogLevel.INFO, "Module1")
        self.widget.add_log_entry("Error occurred", LogLevel.ERROR, "Module2")
        self.widget.add_log_entry("Debug info", LogLevel.DEBUG, "Module1")
        
        # Create temporary directory for test files
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)
    
    def test_export_to_text(self):
        """Test export to text file."""
        file_path = os.path.join(self.temp_dir, "test.txt")
        
        self.widget._export_to_text(file_path)
        
        # Check file exists and has content
        self.assertTrue(os.path.exists(file_path))
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        self.assertIn("Info message", content)
        self.assertIn("Error occurred", content)
        self.assertIn("Debug info", content)
        self.assertIn("Log Export", content)
    
    def test_export_to_csv(self):
        """Test export to CSV file."""
        file_path = os.path.join(self.temp_dir, "test.csv")
        
        self.widget._export_to_csv(file_path)
        
        # Check file exists
        self.assertTrue(os.path.exists(file_path))
        
        # Read and verify CSV content
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        # Should have header + 3 data rows
        self.assertEqual(len(rows), 4)
        
        # Check header
        self.assertEqual(rows[0], ['Timestamp', 'Level', 'Source', 'Thread', 'Message'])
        
        # Check data
        messages = [row[4] for row in rows[1:]]
        self.assertIn("Info message", messages)
        self.assertIn("Error occurred", messages)
        self.assertIn("Debug info", messages)
    
    def test_export_to_json(self):
        """Test export to JSON file."""
        file_path = os.path.join(self.temp_dir, "test.json")
        
        self.widget._export_to_json(file_path)
        
        # Check file exists
        self.assertTrue(os.path.exists(file_path))
        
        # Read and verify JSON content
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.assertIn('export_timestamp', data)
        self.assertEqual(data['total_entries'], 3)
        self.assertEqual(data['filtered_entries'], 3)
        self.assertIn('logs', data)
        
        logs = data['logs']
        self.assertEqual(len(logs), 3)
        
        messages = [log['message'] for log in logs]
        self.assertIn("Info message", messages)
        self.assertIn("Error occurred", messages)
        self.assertIn("Debug info", messages)
    
    def test_export_logs_by_extension(self):
        """Test export_logs method with different file extensions."""
        # Test text export
        txt_path = os.path.join(self.temp_dir, "test.txt")
        self.widget.export_logs(txt_path)
        self.assertTrue(os.path.exists(txt_path))
        
        # Test CSV export
        csv_path = os.path.join(self.temp_dir, "test.csv")
        self.widget.export_logs(csv_path)
        self.assertTrue(os.path.exists(csv_path))
        
        # Test JSON export
        json_path = os.path.join(self.temp_dir, "test.json")
        self.widget.export_logs(json_path)
        self.assertTrue(os.path.exists(json_path))
        
        # Test unknown extension (should default to text)
        unknown_path = os.path.join(self.temp_dir, "test.unknown")
        self.widget.export_logs(unknown_path)
        self.assertTrue(os.path.exists(unknown_path))


class TestLogWidgetHandler(unittest.TestCase):
    """Test LogWidgetHandler for Python logging integration."""
    
    def setUp(self):
        """Set up test fixtures."""
        with patch.object(LogWidget, '_setup_ui'), \
             patch.object(LogWidget, '_setup_styles'), \
             patch.object(LogWidget, '_connect_signals'):
            self.widget = LogWidget()
        
        self.widget._refresh_timer = Mock()
        self.handler = LogWidgetHandler(self.widget, "TestLogger")
    
    def test_handler_initialization(self):
        """Test handler initialization."""
        self.assertEqual(self.handler.log_widget, self.widget)
        self.assertEqual(self.handler.source, "TestLogger")
        self.assertIn(logging.INFO, self.handler.level_mapping)
    
    def test_emit_log_record(self):
        """Test emitting a log record."""
        # Create a log record
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/test/path.py",
            lineno=123,
            msg="Test error message",
            args=(),
            exc_info=None
        )
        
        # Emit the record
        self.handler.emit(record)
        
        # Check that entry was added to widget
        self.assertEqual(len(self.widget._entries), 1)
        entry = self.widget._entries[0]
        self.assertEqual(entry.message, "Test error message")
        self.assertEqual(entry.level, LogLevel.ERROR)
        self.assertEqual(entry.source, "TestLogger")
    
    def test_emit_with_formatter(self):
        """Test emitting with custom formatter."""
        formatter = logging.Formatter('%(levelname)s: %(message)s')
        self.handler.setFormatter(formatter)
        
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="/test/path.py",
            lineno=123,
            msg="Test warning",
            args=(),
            exc_info=None
        )
        
        self.handler.emit(record)
        
        # Check formatted message
        entry = self.widget._entries[0]
        self.assertEqual(entry.message, "WARNING: Test warning")
    
    def test_level_mapping(self):
        """Test that all Python logging levels are mapped correctly."""
        test_cases = [
            (logging.DEBUG, LogLevel.DEBUG),
            (logging.INFO, LogLevel.INFO),
            (logging.WARNING, LogLevel.WARNING),
            (logging.ERROR, LogLevel.ERROR),
            (logging.CRITICAL, LogLevel.CRITICAL),
        ]
        
        for py_level, expected_level in test_cases:
            record = logging.LogRecord(
                name="test",
                level=py_level,
                pathname="/test.py",
                lineno=1,
                msg=f"Test {py_level}",
                args=(),
                exc_info=None
            )
            
            self.handler.emit(record)
            
            entry = self.widget._entries[-1]  # Get last entry
            self.assertEqual(entry.level, expected_level)
    
    def test_create_log_handler(self):
        """Test creating a handler from widget."""
        handler = self.widget.create_log_handler("TestSource")
        
        self.assertIsInstance(handler, LogWidgetHandler)
        self.assertEqual(handler.log_widget, self.widget)
        self.assertEqual(handler.source, "TestSource")


class TestLogWidgetIntegration(unittest.TestCase):
    """Integration tests for LogWidget with Python logging."""
    
    @unittest.skipUnless(PYSIDE6_AVAILABLE, "PySide6 not available")
    def test_full_logging_integration(self):
        """Test full integration with Python logging system."""
        # This test requires PySide6 to actually work
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        
        # Create widget
        widget = LogWidget(title="Integration Test")
        
        # Create logger and handler
        logger = logging.getLogger("test.integration")
        handler = widget.create_log_handler("IntegrationTest")
        handler.setLevel(logging.DEBUG)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        
        # Log some messages
        logger.debug("Debug message")
        logger.info("Info message")
        logger.warning("Warning message")
        logger.error("Error message")
        logger.critical("Critical message")
        
        # Check that all messages were added
        self.assertEqual(len(widget._entries), 5)
        
        # Check message levels
        levels = [entry.level for entry in widget._entries]
        expected_levels = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, 
                          LogLevel.ERROR, LogLevel.CRITICAL]
        self.assertEqual(levels, expected_levels)
        
        # Clean up
        logger.removeHandler(handler)


def run_tests():
    """Run all tests with appropriate skipping for missing dependencies."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestLogLevel))
    suite.addTests(loader.loadTestsFromTestCase(TestLogEntry))
    suite.addTests(loader.loadTestsFromTestCase(TestLogWidget))
    suite.addTests(loader.loadTestsFromTestCase(TestLogWidgetExport))
    suite.addTests(loader.loadTestsFromTestCase(TestLogWidgetHandler))
    suite.addTests(loader.loadTestsFromTestCase(TestLogWidgetIntegration))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)

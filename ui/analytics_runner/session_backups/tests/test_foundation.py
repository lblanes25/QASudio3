#!/usr/bin/env python3
"""
Test script for Analytics Runner foundation components.
Run this to verify Phase 1.1 implementation is working correctly.
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path


def test_session_manager():
    """Test SessionManager functionality."""
    print("Testing SessionManager...")

    # Create temporary config file
    temp_dir = tempfile.mkdtemp()
    config_file = os.path.join(temp_dir, "test_session.json")

    try:
        # Add current directory to path for imports
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from session_manager import SessionManager

        # Test initialization
        session = SessionManager(config_file)
        print("✓ SessionManager initialization successful")

        # Test basic get/set operations
        session.set('test_key', 'test_value')
        assert session.get('test_key') == 'test_value'
        print("✓ Basic get/set operations working")

        # Test recent files
        test_file = __file__  # Use this script as test file
        session.add_recent_file(test_file)
        recent_files = session.get('recent_files', [])
        assert test_file in recent_files
        print("✓ Recent files functionality working")

        # Test configuration persistence
        session.save_config()
        assert os.path.exists(config_file)
        print("✓ Configuration persistence working")

        # Test reload
        new_session = SessionManager(config_file)
        assert new_session.get('test_key') == 'test_value'
        assert test_file in new_session.get('recent_files', [])
        print("✓ Configuration reload working")

        print("SessionManager tests PASSED ✓")
        return True

    except Exception as e:
        print(f"SessionManager test FAILED: {e}")
        return False

    finally:
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_main_application():
    """Test main application can be imported and initialized."""
    print("\nTesting main application...")

    try:
        # Add current directory to path for imports
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        # Test imports
        from PySide6.QtWidgets import QApplication
        from main_application import AnalyticsRunnerApp
        print("✓ Import successful")

        # Test application creation (without showing)
        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        # Create main window (but don't show it)
        window = AnalyticsRunnerApp()
        print("✓ Main window creation successful")

        # Test basic functionality
        assert window.session is not None
        assert window.threadpool is not None
        assert window.main_splitter is not None
        print("✓ Core components initialized")

        # Test session integration
        window.session.set('test_app_key', 'test_value')
        assert window.session.get('test_app_key') == 'test_value'
        print("✓ Session integration working")

        # Test UI state
        assert window.mode_tabs.count() == 2  # Simple and Advanced modes
        assert window.results_tabs.count() == 2  # Results and Logs
        print("✓ UI structure correct")

        # Test menu bar
        menubar = window.menuBar()
        assert menubar is not None
        actions = menubar.actions()
        assert len(actions) >= 3  # File, View, Help menus
        print("✓ Menu bar structure correct")

        # Test toolbar
        from PySide6.QtWidgets import QToolBar
        toolbars = window.findChildren(QToolBar)
        assert len(toolbars) > 0
        print("✓ Toolbar structure correct")

        # Test status bar
        status_bar = window.statusBar()
        assert status_bar is not None
        assert window.status_label is not None
        assert window.progress_bar is not None
        print("✓ Status bar structure correct")

        print("Main application tests PASSED ✓")
        return True

    except Exception as e:
        print(f"Main application test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_ui_functionality():
    """Test basic UI functionality."""
    print("\nTesting UI functionality...")

    try:
        # Add current directory to path for imports
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        from PySide6.QtWidgets import QApplication
        from main_application import AnalyticsRunnerApp

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        window = AnalyticsRunnerApp()

        # Test logging functionality
        window.log_message("Test log message")
        log_content = window.log_view.toPlainText()
        assert "Test log message" in log_content
        print("✓ Logging functionality working")

        # Test progress functionality
        window.show_progress(True)
        app.processEvents()  # Allow UI updates
        assert window.progress_bar.isVisible()

        window.update_progress(50, "Test progress")
        assert window.progress_bar.value() == 50
        assert "Test progress" in window.status_label.text()

        window.show_progress(False)
        app.processEvents()  # Allow UI updates
        assert not window.progress_bar.isVisible()
        print("✓ Progress functionality working")

        # Test mode switching
        window.mode_tabs.setCurrentIndex(1)  # Switch to Advanced mode
        assert window.mode_tabs.currentIndex() == 1
        print("✓ Mode switching working")

        # Test results panel toggle
        initial_visibility = window.results_widget.isVisible()
        window.toggle_results_panel()
        assert window.results_widget.isVisible() != initial_visibility
        print("✓ Results panel toggle working")

        # Test state saving/restoring
        window.save_state()
        session_info = window.session.get_session_info()
        assert session_info['config_exists']
        print("✓ State persistence working")

        print("UI functionality tests PASSED ✓")
        return True

    except Exception as e:
        print(f"UI functionality test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_thread_integration():
    """Test thread pool integration."""
    print("\nTesting thread integration...")

    try:
        # Add current directory to path for imports
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        from PySide6.QtWidgets import QApplication
        from PySide6.QtCore import QRunnable, QTimer
        from main_application import AnalyticsRunnerApp

        app = QApplication.instance()
        if app is None:
            app = QApplication([])

        window = AnalyticsRunnerApp()

        # Test thread pool availability
        assert window.threadpool is not None
        initial_max_threads = window.threadpool.maxThreadCount()
        assert initial_max_threads == 4  # As set in main application
        print("✓ Thread pool configured correctly")

        # Test thread count display
        window.update_thread_count()
        thread_text = window.thread_label.text()
        assert "Threads:" in thread_text
        assert f"/{initial_max_threads}" in thread_text
        print("✓ Thread count display working")

        # Create a simple test runnable
        class TestRunnable(QRunnable):
            def __init__(self):
                super().__init__()
                self.executed = False

            def run(self):
                self.executed = True

        test_runnable = TestRunnable()
        window.threadpool.start(test_runnable)

        # Wait briefly for execution
        QTimer.singleShot(100, app.quit)
        app.processEvents()

        # Note: Can't easily test execution without complex async setup
        print("✓ Thread pool can accept runnables")

        print("Thread integration tests PASSED ✓")
        return True

    except Exception as e:
        print(f"Thread integration test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_all_tests():
    """Run all foundation tests."""
    print("=" * 60)
    print("ANALYTICS RUNNER - PHASE 1.1 FOUNDATION TESTS")
    print("=" * 60)

    tests = [
        test_session_manager,
        test_main_application,
        test_ui_functionality,
        test_thread_integration
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"Test {test.__name__} crashed: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"TEST RESULTS: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 ALL TESTS PASSED! Phase 1.1 foundation is ready.")
        print("\nNext steps:")
        print("1. Run the main application: python main_application.py")
        print("2. Test basic UI functionality")
        print("3. Move to Phase 1.2 (Reusable Widget Library)")
    else:
        print("❌ Some tests failed. Please review the errors above.")

    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
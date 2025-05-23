#!/usr/bin/env python3
"""
Simple test script to verify the Analytics Runner foundation.
Run this directly with: python simple_test.py
"""

import sys
import os

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

def test_imports():
    """Test that all components can be imported."""
    print("Testing imports...")
    
    try:
        # Test PySide6
        from PySide6.QtWidgets import QApplication
        print("✓ PySide6 import successful")
        
        # Test SessionManager
        from session_manager import SessionManager
        print("✓ SessionManager import successful")
        
        # Test main application
        from main_application import AnalyticsRunnerApp
        print("✓ AnalyticsRunnerApp import successful")
        
        return True
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        return False

def test_session_basic():
    """Test basic SessionManager functionality."""
    print("\nTesting SessionManager...")
    
    try:
        from session_manager import SessionManager
        
        # Create session manager with test config
        session = SessionManager("test_session.json")
        
        # Test basic operations
        session.set('test_key', 'test_value', auto_save=False)
        value = session.get('test_key')
        
        if value == 'test_value':
            print("✓ SessionManager basic operations working")
            return True
        else:
            print(f"❌ SessionManager failed: expected 'test_value', got '{value}'")
            return False
            
    except Exception as e:
        print(f"❌ SessionManager test failed: {e}")
        return False

def test_app_creation():
    """Test that the main application can be created."""
    print("\nTesting application creation...")
    
    try:
        from PySide6.QtWidgets import QApplication
        from main_application import AnalyticsRunnerApp
        
        # Create QApplication if needed
        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)
        
        # Create main window (don't show it)
        window = AnalyticsRunnerApp()
        
        # Basic checks
        if window.windowTitle():
            print("✓ Main application window created successfully")
            return True
        else:
            print("❌ Main application window creation failed")
            return False
            
    except Exception as e:
        print(f"❌ Application creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("=" * 50)
    print("ANALYTICS RUNNER FOUNDATION TEST")
    print("=" * 50)
    
    tests = [
        ("Import Test", test_imports),
        ("SessionManager Test", test_session_basic),
        ("Application Creation Test", test_app_creation)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n[{test_name}]")
        if test_func():
            passed += 1
        else:
            print(f"❌ {test_name} FAILED")
    
    print("\n" + "=" * 50)
    print(f"RESULTS: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED!")
        print("\nFoundation is ready. You can now:")
        print("1. Run: python main_application.py")
        print("2. Test the UI manually")
        print("3. Proceed to Phase 1.2")
    else:
        print("❌ Some tests failed. Check the errors above.")
    
    print("=" * 50)
    
    # Clean up test files
    try:
        if os.path.exists("test_session.json"):
            os.remove("test_session.json")
    except:
        pass
    
    return passed == total

if __name__ == "__main__":
    success = main()
    input("\nPress Enter to continue...")  # Keep window open in PyCharm
    sys.exit(0 if success else 1)

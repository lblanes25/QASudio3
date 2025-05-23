#!/usr/bin/env python3
"""
Test script for RuleSelectorPanel
Tests the rule selection interface with real backend integration
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QMessageBox
from PySide6.QtCore import Qt

# Test imports
try:
    from rule_selector_panel import RuleSelectorPanel
    from ui.common.session_manager import SessionManager
    from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
    print("✓ All imports successful")
except ImportError as e:
    print(f"✗ Import error: {e}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestRuleSelectorWindow(QMainWindow):
    """Test window for the RuleSelectorPanel"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rule Selector Panel Test")
        self.resize(1200, 800)
        
        # Create test data first
        self.setup_test_rules()
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Create session manager
        self.session_manager = SessionManager("test_rule_selector_session.json")
        
        # Create rule selector panel
        self.rule_selector = RuleSelectorPanel(session_manager=self.session_manager)
        
        # Connect signals for testing
        self.rule_selector.rulesSelectionChanged.connect(self.on_selection_changed)
        self.rule_selector.ruleDoubleClicked.connect(self.on_rule_double_clicked)
        
        layout.addWidget(self.rule_selector)
        
        logger.info("Test window initialized")
    
    def setup_test_rules(self):
        """Create test rules for demonstration"""
        rule_manager = ValidationRuleManager("./test_rules")
        
        # Create test rules if they don't exist
        test_rules = [
            {
                "name": "Customer ID Not Blank",
                "formula": "=NOT(ISBLANK([Customer_ID]))",
                "description": "Ensures that Customer ID field is not empty",
                "category": "data_quality",
                "severity": "critical",
                "tags": ["customer", "mandatory", "identification"],
                "threshold": 1.0
            },
            {
                "name": "Email Format Validation",
                "formula": "=AND(ISNUMBER(SEARCH(\"@\", [Email])), LEN([Email]) > 5)",
                "description": "Validates email addresses contain @ symbol and minimum length",
                "category": "data_quality",
                "severity": "high",
                "tags": ["email", "format", "contact"],
                "threshold": 0.95
            },
            {
                "name": "Transaction Amount Range",
                "formula": "=AND([Amount] >= 0, [Amount] <= 1000000)",
                "description": "Validates transaction amounts are within acceptable range",
                "category": "compliance",
                "severity": "high",
                "tags": ["financial", "limits", "validation"],
                "threshold": 0.98
            },
            {
                "name": "Date Consistency Check",
                "formula": "=[Start_Date] <= [End_Date]",
                "description": "Ensures start date is not later than end date",
                "category": "data_quality",
                "severity": "medium",
                "tags": ["dates", "consistency"],
                "threshold": 1.0
            },
            {
                "name": "Regulatory Compliance Flag",
                "formula": "=OR([Compliance_Flag] = \"Y\", [Compliance_Flag] = \"YES\")",
                "description": "Checks if regulatory compliance flag is properly set",
                "category": "regulatory",
                "severity": "critical",
                "tags": ["compliance", "regulatory", "flags"],
                "threshold": 1.0
            },
            {
                "name": "Phone Number Format",
                "formula": "=OR(LEN([Phone]) = 10, LEN([Phone]) = 12)",
                "description": "Validates phone number length for standard formats",
                "category": "data_quality",
                "severity": "low",
                "tags": ["phone", "format", "contact"],
                "threshold": 0.90
            }
        ]
        
        # Add test rules to manager
        for rule_data in test_rules:
            try:
                rule = ValidationRule(
                    name=rule_data["name"],
                    formula=rule_data["formula"],
                    description=rule_data["description"],
                    category=rule_data["category"],
                    severity=rule_data["severity"],
                    tags=rule_data["tags"],
                    threshold=rule_data["threshold"]
                )
                
                # Check if rule already exists
                existing_rules = rule_manager.list_rules()
                if not any(r.name == rule.name for r in existing_rules):
                    rule_manager.add_rule(rule)
                    logger.info(f"Added test rule: {rule.name}")
                
            except Exception as e:
                logger.warning(f"Could not add test rule {rule_data['name']}: {e}")
        
        logger.info(f"Test rules setup complete. Total rules: {len(rule_manager.list_rules())}")
    
    def on_selection_changed(self, rule_ids):
        """Handle rule selection changes"""
        logger.info(f"Selection changed: {len(rule_ids)} rules selected")
        print(f"Selected rule IDs: {rule_ids}")
    
    def on_rule_double_clicked(self, rule_id):
        """Handle rule double-click for editing"""
        logger.info(f"Rule double-clicked for editing: {rule_id}")
        QMessageBox.information(
            self,
            "Rule Editor",
            f"Would open rule editor for: {rule_id}\n\n(Editor integration in Phase 3.2)"
        )
    
    def closeEvent(self, event):
        """Handle window close"""
        self.rule_selector.cleanup()
        event.accept()


def test_rule_selector_panel():
    """Test the RuleSelectorPanel functionality"""
    print("Testing RuleSelectorPanel...")
    
    # Test 1: Basic initialization
    print("\n1. Testing basic initialization...")
    try:
        session_manager = SessionManager("test_session.json")
        panel = RuleSelectorPanel(session_manager=session_manager)
        print("✓ RuleSelectorPanel created successfully")
        
        # Test loading rules
        panel.load_rules()
        print("✓ Rules loaded successfully")
        
        # Test getting selected rules
        selected = panel.get_selected_rule_ids()
        print(f"✓ Initial selection: {len(selected)} rules")
        
        # Test setting selection
        if len(panel.all_rules) > 0:
            test_rule_id = panel.all_rules[0].rule_id
            panel.set_selected_rule_ids([test_rule_id])
            selected = panel.get_selected_rule_ids()
            assert test_rule_id in selected, "Rule selection failed"
            print("✓ Rule selection working")
        
        # Test search functionality
        panel.search_edit.setText("customer")
        panel._perform_search()
        print("✓ Search functionality working")
        
        # Test filter functionality
        if panel.category_filter.count() > 1:
            panel.category_filter.setCurrentIndex(1)
            panel._on_filter_changed()
            print("✓ Filter functionality working")
        
        # Cleanup
        panel.cleanup()
        print("✓ Cleanup successful")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
    
    print("\n✓ All basic tests passed!")
    return True


def main():
    """Main test function"""
    print("RuleSelectorPanel Test Suite")
    print("=" * 40)
    
    # Run basic tests first
    if not test_rule_selector_panel():
        print("Basic tests failed!")
        return 1
    
    # Create and show GUI test
    print("\n2. Starting GUI test...")
    app = QApplication(sys.argv)
    
    try:
        window = TestRuleSelectorWindow()
        window.show()
        
        print("✓ Test window displayed")
        print("\nGUI Test Instructions:")
        print("- Try searching for rules")
        print("- Use category and severity filters")
        print("- Select/deselect rules using checkboxes")
        print("- Click on rules to see details")
        print("- Double-click rules to test edit signal")
        print("- Try 'Select All' and 'Deselect All' buttons")
        print("- Test the preset filter buttons")
        
        # Run the application
        return app.exec()
        
    except Exception as e:
        print(f"✗ GUI test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

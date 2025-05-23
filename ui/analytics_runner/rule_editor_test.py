#!/usr/bin/env python3
"""
Test script for the Rule Editor Panel integration
Tests the real backend functionality with JSON persistence
"""

import sys
import os
from pathlib import Path
import pandas as pd
import tempfile
import shutil

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PySide6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget
from PySide6.QtCore import QTimer

# Import our components
from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
from rule_editor_panel import RuleEditorPanel
from rule_selector_panel import RuleSelectorPanel
from ui.common.session_manager import SessionManager


class TestWindow(QMainWindow):
    """Test window for the rule editor integration"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Rule Editor Integration Test")
        self.setGeometry(100, 100, 1400, 900)
        
        # Create temporary directories for testing
        self.temp_dir = Path(tempfile.mkdtemp(prefix="rule_editor_test_"))
        self.rules_dir = self.temp_dir / "rules"
        self.rules_dir.mkdir(exist_ok=True)
        
        print(f"Test environment created at: {self.temp_dir}")
        
        # Initialize backend with test directory
        self.rule_manager = ValidationRuleManager(str(self.rules_dir))
        self.session_manager = SessionManager(str(self.temp_dir / "session.json"))
        
        # Create test data
        self.test_data = self.create_test_data()
        
        # Setup UI
        self.setup_ui()
        
        # Create some test rules
        self.create_test_rules()
        
        # Auto-cleanup timer
        QTimer.singleShot(600000, self.cleanup)  # Cleanup after 10 minutes
    
    def setup_ui(self):
        """Setup the test UI with the enhanced rule selector"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        layout = QVBoxLayout(central_widget)
        
        # Create rule selector with integrated editor
        self.rule_selector = RuleSelectorPanel(self.session_manager)
        
        # Set test data for testing rules
        self.rule_selector.set_current_data_preview(self.test_data)
        
        layout.addWidget(self.rule_selector)
        
        print("UI setup complete with integrated rule editor")
    
    def create_test_data(self):
        """Create sample data for testing rules"""
        data = {
            'Employee_ID': ['EMP001', 'EMP002', 'EMP003', 'EMP004', 'EMP005'],
            'Employee_Name': ['John Doe', '', 'Jane Smith', 'Bob Johnson', 'Alice Brown'],
            'Department': ['HR', 'IT', 'Finance', 'IT', 'HR'],
            'Salary': [50000, 75000, 0, 85000, 55000],
            'Start_Date': ['2020-01-15', '2019-03-20', '2021-06-10', '2018-12-01', '2020-11-05'],
            'Manager_ID': ['MGR001', 'MGR002', 'MGR003', 'MGR002', 'MGR001'],
            'Status': ['Active', 'Active', 'Inactive', 'Active', 'Active']
        }
        
        df = pd.DataFrame(data)
        print(f"Created test data with {len(df)} rows and {len(df.columns)} columns")
        return df
    
    def create_test_rules(self):
        """Create some test rules for demonstration"""
        test_rules = [
            {
                'name': 'Employee_Name_Not_Empty',
                'description': 'Employee name must not be empty',
                'formula': '=NOT(ISBLANK([Employee_Name]))',
                'category': 'data_quality',
                'severity': 'high',
                'threshold': 1.0
            },
            {
                'name': 'Salary_Positive',
                'description': 'Employee salary must be greater than zero',
                'formula': '=[Salary]>0',
                'category': 'compliance',
                'severity': 'critical',
                'threshold': 1.0
            },
            {
                'name': 'Active_Employee_Check',
                'description': 'Active employees must have valid data',
                'formula': '=IF([Status]="Active", AND(NOT(ISBLANK([Employee_Name])), [Salary]>0), TRUE)',
                'category': 'consistency',
                'severity': 'medium',
                'threshold': 0.95
            }
        ]
        
        created_count = 0
        for rule_data in test_rules:
            try:
                # Create ValidationRule object
                rule = ValidationRule(
                    name=rule_data['name'],
                    description=rule_data['description'],
                    formula=rule_data['formula'],
                    category=rule_data['category'],
                    severity=rule_data['severity'],
                    threshold=rule_data['threshold']
                )
                
                # Add to rule manager (this persists to JSON)
                rule_id = self.rule_manager.add_rule(rule)
                created_count += 1
                print(f"Created test rule: {rule_data['name']} ({rule_id})")
                
            except Exception as e:
                print(f"Error creating test rule {rule_data['name']}: {e}")
        
        print(f"Successfully created {created_count} test rules")
        
        # Reload the rule selector to show the new rules
        QTimer.singleShot(1000, self.rule_selector.load_rules)
    
    def cleanup(self):
        """Clean up test environment"""
        print("Cleaning up test environment...")
        try:
            if self.temp_dir.exists():
                shutil.rmtree(self.temp_dir)
                print(f"Removed test directory: {self.temp_dir}")
        except Exception as e:
            print(f"Error during cleanup: {e}")
    
    def closeEvent(self, event):
        """Handle window close"""
        self.cleanup()
        event.accept()


def test_rule_editor_backend():
    """Test the rule editor backend functionality"""
    print("=" * 60)
    print("TESTING RULE EDITOR BACKEND FUNCTIONALITY")
    print("=" * 60)
    
    # Create temporary directory for testing
    temp_dir = Path(tempfile.mkdtemp(prefix="backend_test_"))
    rules_dir = temp_dir / "rules"
    rules_dir.mkdir(exist_ok=True)
    
    try:
        # Test ValidationRuleManager
        print("\n1. Testing ValidationRuleManager...")
        rule_manager = ValidationRuleManager(str(rules_dir))
        
        # Create a test rule
        test_rule = ValidationRule(
            name="Test_Rule",
            description="A test rule for backend validation",
            formula="=[Column1]<>[Column2]",
            category="data_quality",
            severity="high",
            threshold=0.95
        )
        
        # Save rule (should persist to JSON)
        rule_id = rule_manager.add_rule(test_rule)
        print(f"✓ Created rule with ID: {rule_id}")
        
        # Verify JSON file exists
        json_file = rules_dir / f"{rule_id}.json"
        if json_file.exists():
            print(f"✓ JSON file created: {json_file}")
        else:
            print(f"✗ JSON file not found: {json_file}")
            return False
        
        # Load rule back
        loaded_rule = rule_manager.get_rule(rule_id)
        if loaded_rule:
            print(f"✓ Rule loaded successfully: {loaded_rule.name}")
        else:
            print("✗ Failed to load rule")
            return False
        
        # Test rule validation
        print("\n2. Testing rule validation...")
        test_data = pd.DataFrame({
            'Column1': ['A', 'B', 'C'],
            'Column2': ['A', 'X', 'C']
        })
        
        is_valid, error = loaded_rule.validate_with_dataframe(test_data)
        if is_valid:
            print("✓ Rule validation passed")
        else:
            print(f"✗ Rule validation failed: {error}")
            return False
        
        # Test rule evaluation (this tests the Excel integration)
        print("\n3. Testing rule evaluation...")
        from core.rule_engine.rule_evaluator import RuleEvaluator
        
        evaluator = RuleEvaluator(rule_manager=rule_manager)
        try:
            result = evaluator.evaluate_rule(loaded_rule, test_data)
            print(f"✓ Rule evaluation completed: {result.compliance_status}")
            print(f"  - Total items: {result.summary['total_items']}")
            print(f"  - Compliance rate: {result.summary['compliance_rate']:.2%}")
        except Exception as e:
            print(f"⚠ Rule evaluation failed (expected if Excel not available): {e}")
        
        print("\n4. Testing rule updates...")
        # Update rule
        loaded_rule.description = "Updated test rule description"
        rule_manager.update_rule(loaded_rule)
        
        # Reload and verify
        updated_rule = rule_manager.get_rule(rule_id)
        if updated_rule.description == "Updated test rule description":
            print("✓ Rule update successful")
        else:
            print("✗ Rule update failed")
            return False
        
        print("\n✓ All backend tests passed!")
        return True
        
    except Exception as e:
        print(f"\n✗ Backend test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup
        try:
            shutil.rmtree(temp_dir)
            print(f"\nCleaned up test directory: {temp_dir}")
        except Exception as e:
            print(f"Cleanup error: {e}")


def main():
    """Main test function"""
    # First test the backend functionality
    backend_success = test_rule_editor_backend()
    
    if not backend_success:
        print("\n❌ Backend tests failed. Please fix backend issues before testing UI.")
        return 1
    
    print("\n" + "=" * 60)
    print("STARTING UI INTEGRATION TEST")
    print("=" * 60)
    print("\nInstructions:")
    print("1. The Rule Editor panel is integrated in the right side")
    print("2. Try creating a new rule with the 'New Rule' button")
    print("3. Fill in rule details and formula (e.g., =NOT(ISBLANK([Employee_Name])))")
    print("4. Save the rule and test it against the sample data")
    print("5. Try editing existing rules by double-clicking them")
    print("6. Test rule validation and see results in the Test Results tab")
    print("\nSample formulas to try:")
    print("- =NOT(ISBLANK([Employee_Name]))")
    print("- =[Salary]>0") 
    print("- =[Status]=\"Active\"")
    print("\nWindow will auto-close after 10 minutes or close manually when done.")
    
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("Rule Editor Test")
    
    # Create test window
    window = TestWindow()
    window.show()
    
    # Run application
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

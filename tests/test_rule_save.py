"""
Test Script to Verify Rule Save Functionality
Run this to check if the ValidationRuleManager is working correctly
"""

import sys
import os
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_rule_save():
    """Test the rule saving functionality"""
    try:
        # Import the ValidationRule and ValidationRuleManager
        from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
        
        # Create a rule manager
        rule_manager = ValidationRuleManager()
        
        # Test 1: Create a simple rule
        print("=" * 50)
        print("TEST 1: Creating a new rule")
        print("=" * 50)
        
        test_rule = ValidationRule(
            name="Test Save Rule",
            formula="=[Column1]<>''",
            description="Test rule to verify save functionality",
            threshold=1.0,
            severity="medium",
            category="data_quality",
            tags=["test", "save_test"]
        )
        
        # Validate the rule
        is_valid, error = test_rule.validate()
        print(f"Rule validation: {'PASSED' if is_valid else 'FAILED'}")
        if not is_valid:
            print(f"Validation error: {error}")
            return False
            
        # Test 2: Save the rule
        print("\nTEST 2: Saving the rule")
        print("=" * 30)
        
        try:
            rule_id = rule_manager.add_rule(test_rule)
            print(f"Rule saved successfully with ID: {rule_id}")
        except Exception as e:
            print(f"SAVE FAILED: {e}")
            return False
            
        # Test 3: Verify the rule was saved
        print("\nTEST 3: Verifying rule was saved")
        print("=" * 35)
        
        # List all rules
        all_rules = rule_manager.list_rules()
        print(f"Total rules in manager: {len(all_rules)}")
        
        # Find our test rule
        saved_rule = rule_manager.get_rule(rule_id)
        if saved_rule:
            print(f"✓ Rule found: {saved_rule.name}")
            print(f"  Formula: {saved_rule.formula}")
            print(f"  ID: {saved_rule.rule_id}")
        else:
            print("✗ Rule NOT found after save")
            return False
            
        # Test 4: Check if rule file exists
        print("\nTEST 4: Checking rule file on disk")
        print("=" * 35)
        
        rule_file = rule_manager.rules_directory / f"{rule_id}.json"
        if rule_file.exists():
            print(f"✓ Rule file exists: {rule_file}")
            
            # Read and display the file content
            import json
            with open(rule_file, 'r') as f:
                rule_data = json.load(f)
            print(f"✓ Rule data: {rule_data['name']}")
        else:
            print(f"✗ Rule file NOT found: {rule_file}")
            return False
            
        print("\n" + "=" * 50)
        print("ALL TESTS PASSED - Rule save functionality is working!")
        print("=" * 50)
        return True
        
    except ImportError as e:
        print(f"Import error: {e}")
        print("Make sure you're running this from the project root directory")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_rule_save()
    sys.exit(0 if success else 1)

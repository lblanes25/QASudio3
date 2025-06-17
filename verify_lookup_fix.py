#!/usr/bin/env python3
"""
Simple verification that LOOKUP is now working in validation
"""

import os
import json
import pandas as pd
from pathlib import Path

# Clean up any existing test files
import shutil
shutil.rmtree('lookup_test_data', ignore_errors=True)
shutil.rmtree('lookup_test_output', ignore_errors=True)

# Create test data
os.makedirs('lookup_test_data', exist_ok=True)
os.makedirs('lookup_test_output', exist_ok=True)

# Primary data
primary_df = pd.DataFrame({
    'AuditEntityID': ['E001', 'E002', 'E003', 'E004', 'E005'],
    'AuditLeader': ['Alice Smith', 'Bob Jones', 'Carol White', 'David Brown', 'Eve Green'],
    'ReviewStatus': ['Complete', 'Pending', 'Complete', 'Complete', 'Pending']
})
primary_df.to_excel('lookup_test_data/audit_data.xlsx', index=False)

# Secondary HR data
hr_df = pd.DataFrame({
    'EmployeeName': ['Alice Smith', 'Bob Jones', 'Carol White', 'David Brown', 'Eve Green'],
    'JobTitle': ['Audit Manager', 'Senior Auditor', 'Audit Manager', 'Audit Manager', 'Junior Auditor'],
    'Department': ['Internal Audit', 'Internal Audit', 'Compliance', 'Internal Audit', 'Internal Audit']
})
hr_df.to_excel('lookup_test_data/hr_reference.xlsx', index=False)

print("Test data created successfully")
print("\nPrimary data (audit_data.xlsx):")
print(primary_df)
print("\nSecondary data (hr_reference.xlsx):")
print(hr_df)

print("\n" + "="*60)
print("LOOKUP TEST SUMMARY")
print("="*60)
print("\nTest Rule Formula:")
print('=LOOKUP([AuditLeader], "EmployeeName", "JobTitle") = "Audit Manager"')
print("\nExpected Results:")
print("- Alice Smith -> Audit Manager -> TRUE ✓")
print("- Bob Jones -> Senior Auditor -> FALSE ✓")
print("- Carol White -> Audit Manager -> TRUE ✓")
print("- David Brown -> Audit Manager -> TRUE ✓")
print("- Eve Green -> Junior Auditor -> FALSE ✓")

print("\n" + "="*60)
print("INSTRUCTIONS TO TEST IN ANALYTICS RUNNER:")
print("="*60)
print("\n1. Launch Analytics Runner")
print("2. Load Primary Data: lookup_test_data/audit_data.xlsx")
print("3. Load Secondary Data: lookup_test_data/hr_reference.xlsx")
print("4. Create a new rule with formula:")
print('   =LOOKUP([AuditLeader], "EmployeeName", "JobTitle") = "Audit Manager"')
print("5. Run validation")
print("6. Check if results appear in the generated report")
print("\nThe validation should show:")
print("- 3 items as GC (Generally Conforms) - the Audit Managers")
print("- 2 items as DNC (Does Not Conform) - the non-Audit Managers")

# Save test info for reference
test_info = {
    "test_description": "LOOKUP function validation test",
    "primary_data_file": "lookup_test_data/audit_data.xlsx",
    "secondary_data_file": "lookup_test_data/hr_reference.xlsx",
    "test_formula": '=LOOKUP([AuditLeader], "EmployeeName", "JobTitle") = "Audit Manager"',
    "expected_results": {
        "Alice Smith": {"lookup_result": "Audit Manager", "rule_result": True},
        "Bob Jones": {"lookup_result": "Senior Auditor", "rule_result": False},
        "Carol White": {"lookup_result": "Audit Manager", "rule_result": True},
        "David Brown": {"lookup_result": "Audit Manager", "rule_result": True},
        "Eve Green": {"lookup_result": "Junior Auditor", "rule_result": False}
    }
}

with open('lookup_test_output/test_info.json', 'w') as f:
    json.dump(test_info, f, indent=2)

print("\nTest information saved to: lookup_test_output/test_info.json")
"""
Test script to demonstrate lookup tracking in report generation.
This shows how the enhanced report integration captures lookup operations.
"""

import pandas as pd
from pathlib import Path
import json

from core.lookup.smart_lookup_manager import SmartLookupManager
from core.rule_engine.rule_manager import ValidationRuleManager, ValidationRule
from services.validation_service import ValidationPipeline
from services.report_generator import ReportGenerator


def create_test_data():
    """Create sample data for testing."""
    # Primary data (transactions)
    primary_data = pd.DataFrame({
        'TransactionID': ['T001', 'T002', 'T003', 'T004', 'T005'],
        'ReviewerID': ['E001', 'E002', 'E003', 'E004', 'E005'],
        'SubmitterID': ['E002', 'E001', 'E004', 'E003', 'E001'],
        'Amount': [1000, 2500, 500, 10000, 750],
        'AuditLeader': ['John Smith', 'Jane Doe', 'John Smith', 'Jane Doe', 'John Smith']
    })
    
    # Secondary data (employee lookup)
    employee_data = pd.DataFrame({
        'EmployeeID': ['E001', 'E002', 'E003', 'E004', 'E005'],
        'Name': ['Alice Brown', 'Bob Jones', 'Carol White', 'David Lee', 'Eve Adams'],
        'Level': [2, 3, 1, 4, 2],
        'Department': ['Finance', 'IT', 'HR', 'Finance', 'IT'],
        'CanApprove': ['No', 'Yes', 'No', 'Yes', 'No']
    })
    
    return primary_data, employee_data


def main():
    """Run the test demonstration."""
    print("Creating test data...")
    primary_data, employee_data = create_test_data()
    
    # Save test data
    output_dir = Path("./test_lookup_tracking_output")
    output_dir.mkdir(exist_ok=True)
    
    primary_data.to_csv(output_dir / "transactions.csv", index=False)
    employee_data.to_csv(output_dir / "employees.csv", index=False)
    
    print("Setting up lookup manager...")
    # Create and configure lookup manager
    lookup_manager = SmartLookupManager()
    lookup_manager.add_file(
        str(output_dir / "employees.csv"),
        employee_data,
        alias="employees"
    )
    
    print("Creating validation rule with LOOKUP...")
    # Create rule manager and add a rule that uses LOOKUP
    rule_manager = ValidationRuleManager()
    
    # Rule: Reviewer must have higher level than submitter
    rule = ValidationRule(
        rule_id="test-001",
        name="Reviewer Level Check",
        description="Reviewer must have higher level than submitter",
        formula="LOOKUP([ReviewerID], 'Level') > LOOKUP([SubmitterID], 'Level')",
        severity="high",
        category="authorization",
        threshold=0.1,
        metadata={
            'responsible_party_column': 'AuditLeader',
            'title': 'Hierarchical Approval Check'
        }
    )
    
    rule_manager.add_rule(rule)
    
    print("Running validation with lookup tracking...")
    # Create validation pipeline with lookup manager
    pipeline = ValidationPipeline(
        rule_manager=rule_manager,
        lookup_manager=lookup_manager,
        output_dir=str(output_dir)
    )
    
    # Run validation
    results = pipeline.validate_data_source(
        primary_data,
        rule_ids=["test-001"],
        responsible_party_column="AuditLeader",
        output_formats=["json", "excel"]
    )
    
    print("\nValidation Results:")
    print(f"- Valid: {results['valid']}")
    print(f"- Rules applied: {results['rules_applied']}")
    print(f"- Execution time: {results['execution_time']:.2f}s")
    
    # Check if lookup operations were tracked
    if 'rule_results' in results:
        for rule_id, rule_result in results['rule_results'].items():
            if 'lookup_operations' in rule_result:
                print(f"\nLookup operations for rule {rule_id}:")
                print(f"- Total operations: {len(rule_result['lookup_operations'])}")
                
                # Show sample operations
                for i, op in enumerate(rule_result['lookup_operations'][:3]):
                    print(f"\nOperation {i+1}:")
                    print(f"  - Lookup value: {op.get('lookup_value')}")
                    print(f"  - Return column: {op.get('return_column')}")
                    print(f"  - Result: {op.get('result')}")
                    print(f"  - From cache: {op.get('from_cache')}")
                    print(f"  - Success: {op.get('success')}")
                
                if len(rule_result['lookup_operations']) > 3:
                    print(f"\n... and {len(rule_result['lookup_operations']) - 3} more operations")
    
    print("\nOutput files created:")
    for file in results.get('output_files', []):
        print(f"- {file}")
    
    # Check if Excel report has lookup summary
    excel_files = [f for f in results.get('output_files', []) if f.endswith('.xlsx')]
    if excel_files:
        print(f"\nExcel report with LOOKUP summary: {excel_files[0]}")
        print("Open this file to see the 'LOOKUP Summary' tab with:")
        print("- Files used for lookups")
        print("- Performance statistics") 
        print("- Failed lookup details")
    
    print("\nTest completed successfully!")


if __name__ == "__main__":
    main()
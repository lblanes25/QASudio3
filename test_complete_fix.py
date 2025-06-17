#!/usr/bin/env python3
"""
Test the complete LOOKUP and report generation fix
"""

import os
import sys
import json
import pandas as pd
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
from core.lookup.smart_lookup_manager import SmartLookupManager
from services.validation_service import ValidationPipeline
from services.progress_tracking_pipeline import ProgressTrackingPipeline
from services.report_generator import ReportGenerator

# Create test data
print("Creating test data...")
primary_data = pd.DataFrame({
    'AuditEntityID': ['A001', 'A002', 'A003'],
    'AuditLeader': ['John Smith', 'Jane Doe', 'Bob Johnson'],
    'Status': ['Complete', 'In Progress', 'Complete']
})

hr_data = pd.DataFrame({
    'Employee_Name': ['John Smith', 'Jane Doe', 'Bob Johnson'],
    'Title': ['Audit Manager', 'Senior Auditor', 'Audit Manager']
})

# Save files
os.makedirs('test_data', exist_ok=True)
primary_data.to_excel('test_data/primary_data.xlsx', index=False)
hr_data.to_excel('test_data/hr_data.xlsx', index=False)

# Create lookup manager
lookup_manager = SmartLookupManager()
lookup_manager.add_file('test_data/hr_data.xlsx', alias='hr_data')

# Create test rule
rule_manager = ValidationRuleManager()
test_rule = ValidationRule(
    rule_id="test_lookup_rule",
    name="Audit Manager Check",
    formula="=LOOKUP([AuditLeader], 'Employee_Name', 'Title') = 'Audit Manager'",
    description="Check if AuditLeader is an Audit Manager",
    threshold=0.8,
    severity="High"
)
rule_manager.add_rule(test_rule)

# Create pipeline
pipeline = ValidationPipeline(
    rule_manager=rule_manager,
    lookup_manager=lookup_manager,
    output_dir='test_output'
)

# Test with progress tracking
print("\nRunning validation with progress tracking...")
progress_pipeline = ProgressTrackingPipeline(pipeline)

def progress_callback(progress, status):
    print(f"  {progress}% - {status}")

results = progress_pipeline.validate_data_source_with_progress(
    data_source_path='test_data/primary_data.xlsx',
    source_type='excel',
    rule_ids=[test_rule.rule_id],
    progress_callback=progress_callback,
    responsible_party_column='AuditLeader',
    output_formats=['json'],
    analytic_id='test_lookup'
)

# Check results
print(f"\nValidation status: {results.get('status')}")
print(f"Rules applied: {len(results.get('rules_applied', []))}")

# Check rule_results
rule_results = results.get('rule_results', {})
print(f"\nrule_results entries: {len(rule_results)}")

if rule_results:
    for rule_id, rule_result in rule_results.items():
        print(f"\nRule: {rule_id}")
        print(f"  Compliance status: {rule_result.get('compliance_status')}")
        print(f"  Total items: {rule_result.get('total_items')}")
        print(f"  GC count: {rule_result.get('gc_count')}")
        print(f"  DNC count: {rule_result.get('dnc_count')}")
        
        # Check if details are included
        if '_result_details' in rule_result:
            details = rule_result['_result_details']
            print(f"  Result details: {len(details)} items")
            for i, item in enumerate(details[:3]):  # Show first 3
                print(f"    Item {i}: {item.get('AuditLeader')} -> {item.get(rule_result.get('_result_column'))}")

# Generate Excel report
print("\nGenerating Excel report...")
json_path = 'test_output/test_results.json'
with open(json_path, 'w') as f:
    json.dump(results, f, indent=2, default=str)

excel_path = 'test_output/test_report.xlsx'
report_gen = ReportGenerator(rule_manager)
report_gen.generate_excel_report(json_path, excel_path)

print(f"\nReport generated: {excel_path}")

# Cleanup
import shutil
shutil.rmtree('test_data', ignore_errors=True)
shutil.rmtree('test_output', ignore_errors=True)
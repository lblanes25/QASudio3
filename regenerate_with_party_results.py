#!/usr/bin/env python3
"""
Regenerate validation results with party_results included
"""

from services.validation_service import ValidationPipeline
import json
import glob

# Find the most recent data file
data_files = glob.glob("*.xlsx")
if not data_files:
    print("No Excel files found!")
    exit(1)

# Use the business monitoring data
data_file = "business_monitoring_dummy_data.xlsx"
if data_file not in data_files:
    print(f"Could not find {data_file}")
    data_file = data_files[0]
    print(f"Using {data_file} instead")

print(f"Using data file: {data_file}")

# Create validation pipeline
pipeline = ValidationPipeline()

# Get all available rules
all_rules = pipeline.rule_manager.list_rules()
rule_ids = [rule.rule_id for rule in all_rules]
print(f"Found {len(rule_ids)} rules: {rule_ids}")

# Run validation with responsible_party_column specified
print("\nRunning validation with responsible_party_column='AuditLeader'...")
results = pipeline.validate_data_source(
    data_source=data_file,
    rule_ids=rule_ids,
    responsible_party_column='AuditLeader',  # This ensures party_results are generated
    output_formats=['json']
)

print(f"\nValidation complete!")
print(f"Status: {results.get('status')}")
print(f"Output files: {results.get('output_files')}")

# Check if party_results were generated
if 'rule_results' in results:
    has_party_results = False
    for rule_id, rule_result in results['rule_results'].items():
        if 'party_results' in rule_result:
            has_party_results = True
            print(f"\n✓ Rule {rule_id} has party_results with {len(rule_result['party_results'])} parties")
            break
    
    if not has_party_results:
        print("\n❌ No party_results found in any rules!")
else:
    print("\n❌ No rule_results found!")

# Save the updated results
output_file = "output/test_with_party_results.json"
with open(output_file, 'w') as f:
    json.dump(results, f, indent=2, default=str)
print(f"\nResults saved to: {output_file}")
print("\nNow you can use this file with test_iag_report.py to test severity weighting!")
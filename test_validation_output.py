#!/usr/bin/env python3
"""
Test script to check validation output format
"""

import json
import sys
from pathlib import Path
from glob import glob

# Find the most recent validation results
output_files = glob("output/*_results.json")
if not output_files:
    print("No validation results files found in output/")
    sys.exit(1)

# Get the most recent file
latest_file = max(output_files, key=lambda x: Path(x).stat().st_mtime)
print(f"Checking validation results file: {latest_file}")

# Load and inspect the results
with open(latest_file, 'r') as f:
    results = json.load(f)

print(f"\nTop-level keys in results:")
for key in sorted(results.keys()):
    if key.startswith('_'):
        continue
    print(f"  - {key}")

# Check rule_results structure
if 'rule_results' in results:
    rule_results = results['rule_results']
    print(f"\nNumber of rules in rule_results: {len(rule_results)}")
    
    # Check first rule result
    if rule_results:
        first_rule_id = list(rule_results.keys())[0]
        first_rule = rule_results[first_rule_id]
        
        print(f"\nFirst rule ID: {first_rule_id}")
        print(f"Keys in first rule result:")
        for key in sorted(first_rule.keys()):
            print(f"  - {key}")
        
        # Check if _result_details exists
        if '_result_details' in first_rule:
            details = first_rule['_result_details']
            print(f"\n_result_details contains {len(details)} items")
            if details:
                print(f"First item keys: {list(details[0].keys())}")
        else:
            print("\nNo _result_details found in rule result")
            
        # Check if items exists (old format)
        if 'items' in first_rule:
            items = first_rule['items']
            print(f"\nitems contains {len(items)} entries")
            if items:
                print(f"First item: {items[0]}")
else:
    print("\nNo 'rule_results' key found in validation results!")
    
# Check for _rule_evaluation_results
if '_rule_evaluation_results' in results:
    print("\n_rule_evaluation_results exists (raw RuleEvaluationResult objects)")
else:
    print("\nNo _rule_evaluation_results found")
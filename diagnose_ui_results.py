#!/usr/bin/env python3
"""
Diagnose why UI tabs aren't showing results
"""

import json
import os
from glob import glob
from pathlib import Path

# Find the most recent results file
results_files = glob("output/*_results.json")
if not results_files:
    print("No results files found!")
    exit(1)

latest_file = max(results_files, key=lambda x: Path(x).stat().st_mtime)
print(f"Checking latest results: {latest_file}\n")

with open(latest_file, 'r') as f:
    results = json.load(f)

# Check the structure
print("=== RESULTS STRUCTURE ===")
print(f"Top-level keys: {list(results.keys())}\n")

# Check rule_results
rule_results = results.get('rule_results', {})
print(f"=== RULE RESULTS ===")
print(f"Number of rules: {len(rule_results)}")

if rule_results:
    # Show first rule structure
    first_rule_id = list(rule_results.keys())[0]
    first_rule = rule_results[first_rule_id]
    print(f"\nFirst rule ID: {first_rule_id}")
    print(f"Rule result keys: {list(first_rule.keys())}")
    
    # Check if it has the expected fields for UI
    expected_fields = ['rule_name', 'compliance_status', 'total_items', 'gc_count', 'pc_count', 'dnc_count']
    missing_fields = [f for f in expected_fields if f not in first_rule]
    if missing_fields:
        print(f"Missing expected fields: {missing_fields}")
    
    # Check for result details
    if '_result_details' in first_rule:
        print(f"Has _result_details: {len(first_rule['_result_details'])} items")
    else:
        print("No _result_details found")
        
    # Check for items (old format)
    if 'items' in first_rule:
        print(f"Has items: {len(first_rule['items'])} items")
    else:
        print("No items found")

# Check summary
summary = results.get('summary', {})
print(f"\n=== SUMMARY ===")
print(f"Summary keys: {list(summary.keys())}")
print(f"Total rules: {summary.get('total_rules', 0)}")
print(f"Compliance counts: {summary.get('compliance_counts', {})}")

# Check for _rule_evaluation_results
if '_rule_evaluation_results' in results:
    print("\n=== RAW EVALUATION RESULTS ===")
    print("_rule_evaluation_results exists (these are the raw RuleEvaluationResult objects)")
    print("This suggests the results weren't properly serialized for the UI")

# Check validation status
print(f"\n=== VALIDATION STATUS ===")
print(f"Status: {results.get('status', 'Unknown')}")
print(f"Valid: {results.get('valid', False)}")

# Look for any errors
if 'error' in results:
    print(f"\n=== ERROR ===")
    print(f"Error: {results['error']}")

# Check if this might be a format issue
print("\n=== DIAGNOSIS ===")
if len(rule_results) == 0 and '_rule_evaluation_results' in results:
    print("❌ PROBLEM: rule_results is empty but _rule_evaluation_results exists")
    print("   This means the evaluation results weren't properly processed")
    print("   The UI can't display results because rule_results is empty")
elif len(rule_results) > 0:
    print("✓ rule_results is populated")
    if any('_result_details' not in r for r in rule_results.values()):
        print("⚠️  Some rules missing _result_details (needed for detailed view)")
    if any('items' not in r for r in rule_results.values()):
        print("⚠️  Some rules missing 'items' field (old format)")
else:
    print("❌ No rule results found at all")

# Save a summary for debugging
debug_summary = {
    "file_analyzed": latest_file,
    "has_rule_results": len(rule_results) > 0,
    "rule_count": len(rule_results),
    "has_raw_results": '_rule_evaluation_results' in results,
    "status": results.get('status', 'Unknown'),
    "summary": summary
}

with open("ui_debug_summary.json", 'w') as f:
    json.dump(debug_summary, f, indent=2)
    
print(f"\nDebug summary saved to: ui_debug_summary.json")
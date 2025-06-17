#!/usr/bin/env python3
"""
Debug script to trace validation flow
"""

import json
import os
from glob import glob
from pathlib import Path

# Find the most recent validation results
output_files = glob("output/*_results.json")
if not output_files:
    print("No validation results files found in output/")
    exit(1)

# Get the most recent file
latest_file = max(output_files, key=lambda x: Path(x).stat().st_mtime)
print(f"Checking: {latest_file}")

# Load results
with open(latest_file, 'r') as f:
    results = json.load(f)

# Check what happened during validation
print(f"\nValidation Status: {results.get('status', 'Unknown')}")
print(f"Valid: {results.get('valid', False)}")

# Check rules
print(f"\nRules Applied: {results.get('rules_applied', [])}")
print(f"Number of rules applied: {len(results.get('rules_applied', []))}")

# Check rule_results
rule_results = results.get('rule_results', {})
print(f"\nrule_results entries: {len(rule_results)}")

# Check for _rule_evaluation_results
if '_rule_evaluation_results' in results:
    print("\n_rule_evaluation_results exists but wasn't processed into rule_results")
    # This is a non-serializable object so we can't inspect it from JSON
    
# Check summary
summary = results.get('summary', {})
print(f"\nSummary:")
print(f"  Total rules: {summary.get('total_rules', 0)}")
print(f"  Compliance counts: {summary.get('compliance_counts', {})}")

# Check for errors
if 'error' in results:
    print(f"\nError found: {results['error']}")
    
# Look for log files
log_files = glob("logs/*.log")
if log_files:
    print(f"\nLog files found: {len(log_files)}")
    # Check the most recent log
    latest_log = max(log_files, key=lambda x: Path(x).stat().st_mtime)
    print(f"Most recent log: {latest_log}")
    
    # Read last few lines
    with open(latest_log, 'r') as f:
        lines = f.readlines()
        print(f"\nLast 10 lines of {latest_log}:")
        for line in lines[-10:]:
            print(f"  {line.rstrip()}")
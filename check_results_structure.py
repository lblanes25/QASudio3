#!/usr/bin/env python3
"""Check the structure of validation results to see what data is available"""

import json
import sys

# Load the results file
with open('output/test2_20250530_100015_results.json', 'r') as f:
    results = json.load(f)

print("=== Results Structure Analysis ===")
print(f"Top-level keys: {list(results.keys())}")
print()

# Check if grouped_summary exists
if 'grouped_summary' in results:
    print(f"grouped_summary has {len(results['grouped_summary'])} leaders:")
    for leader in list(results['grouped_summary'].keys())[:3]:
        print(f"  - {leader}")
    print()

# Check rule_results structure
if 'rule_results' in results:
    print(f"rule_results has {len(results['rule_results'])} rules")
    
    # Check first rule for party_results
    first_rule_id = list(results['rule_results'].keys())[0]
    first_rule = results['rule_results'][first_rule_id]
    print(f"\nFirst rule ({first_rule_id}) structure:")
    print(f"  Keys: {list(first_rule.keys())}")
    
    if 'party_results' in first_rule:
        print(f"  party_results has {len(first_rule['party_results'])} parties")
        first_party = list(first_rule['party_results'].keys())[0]
        print(f"  First party ({first_party}) data: {first_rule['party_results'][first_party]}")
    else:
        print("  No party_results found!")
else:
    print("No rule_results found!")

# Check data metrics
if 'data_metrics' in results:
    print(f"\ndata_metrics: {results['data_metrics']}")
    
if 'population_summary' in results:
    print(f"\npopulation_summary: {results['population_summary']}")
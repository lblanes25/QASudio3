#!/usr/bin/env python3
"""Test script to verify rule loading fix"""

import logging
from core.rule_engine.rule_manager import ValidationRuleManager

# Configure logging to see debug messages
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s - %(name)s - %(message)s')

# Create rule manager
rule_manager = ValidationRuleManager(rules_directory="./data/rules")

# Test loading specific rules by ID
test_rule_ids = ["QA-ID-1", "QA-ID-2", "QA-ID-3", "QA-ID-4", "QA-ID-5"]

print("Testing rule loading by ID:")
print("-" * 50)

for rule_id in test_rule_ids:
    rule = rule_manager.get_rule(rule_id)
    if rule:
        print(f"✓ {rule_id}: Found - {rule.name} (threshold: {rule.threshold})")
    else:
        print(f"✗ {rule_id}: NOT FOUND")

# List all loaded rules
print("\nAll loaded rules:")
print("-" * 50)
all_rules = rule_manager.list_rules()
for rule in all_rules:
    print(f"  {rule.rule_id}: {rule.name} (file: {rule.metadata.get('source_file', 'unknown')})")

print(f"\nTotal rules loaded: {len(all_rules)}")
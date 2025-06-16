#!/usr/bin/env python3
"""
Script to update rule JSON files with additional metadata for IAG reporting.

Adds:
- risk_level: Numeric risk level (1-3) based on severity
- error_threshold: Copy of threshold value to metadata
- out_of_scope: Boolean flag (default False)
- out_of_scope_rationale: Text field (default empty)
- applicability_formula: Optional formula to determine if rule applies
"""

import json
import os
from pathlib import Path
from typing import Dict, Any

# Severity to risk level mapping
SEVERITY_TO_RISK_LEVEL = {
    "critical": 1,
    "high": 2,
    "medium": 3,
    "low": 3
}

def update_rule_metadata(rule_path: Path) -> bool:
    """
    Update a single rule JSON file with new metadata fields.
    
    Args:
        rule_path: Path to the rule JSON file
        
    Returns:
        True if file was updated, False otherwise
    """
    try:
        # Read existing rule
        with open(rule_path, 'r') as f:
            rule_data = json.load(f)
        
        # Check if metadata exists
        if 'metadata' not in rule_data:
            print(f"WARNING: No metadata in {rule_path}")
            return False
        
        metadata = rule_data['metadata']
        updated = False
        
        # Add risk_level based on severity
        if 'risk_level' not in metadata and 'severity' in metadata:
            severity = metadata['severity'].lower()
            metadata['risk_level'] = SEVERITY_TO_RISK_LEVEL.get(severity, 3)
            updated = True
            print(f"  Added risk_level: {metadata['risk_level']} (from severity: {severity})")
        
        # Add error_threshold (copy from root threshold)
        if 'error_threshold' not in metadata and 'threshold' in rule_data:
            metadata['error_threshold'] = rule_data['threshold']
            updated = True
            print(f"  Added error_threshold: {metadata['error_threshold']}")
        
        # Add out_of_scope fields if not present
        if 'out_of_scope' not in metadata:
            metadata['out_of_scope'] = False
            updated = True
            print(f"  Added out_of_scope: False")
        
        if 'out_of_scope_rationale' not in metadata:
            metadata['out_of_scope_rationale'] = ""
            updated = True
            print(f"  Added out_of_scope_rationale: (empty)")
        
        # Add applicability_formula if not present
        if 'applicability_formula' not in metadata:
            metadata['applicability_formula'] = ""
            updated = True
            print(f"  Added applicability_formula: (empty)")
        
        # Write back if updated
        if updated:
            with open(rule_path, 'w') as f:
                json.dump(rule_data, f, indent=2)
            print(f"Updated: {rule_path.name}")
            return True
        else:
            print(f"No updates needed: {rule_path.name}")
            return False
            
    except Exception as e:
        print(f"ERROR processing {rule_path}: {e}")
        return False

def main():
    """Update all rule JSON files in the data/rules directory."""
    # Find rules directory
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    rules_dir = project_root / "data" / "rules"
    
    if not rules_dir.exists():
        print(f"ERROR: Rules directory not found: {rules_dir}")
        return
    
    print(f"Updating rule files in: {rules_dir}")
    print("-" * 50)
    
    # Process all JSON files
    json_files = list(rules_dir.glob("*.json"))
    if not json_files:
        print("No JSON files found!")
        return
    
    updated_count = 0
    for rule_file in json_files:
        if update_rule_metadata(rule_file):
            updated_count += 1
        print()  # Blank line between files
    
    print("-" * 50)
    print(f"Summary: Updated {updated_count} of {len(json_files)} rule files")

if __name__ == "__main__":
    main()
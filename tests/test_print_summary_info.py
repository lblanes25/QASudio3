#!/usr/bin/env python3
"""
Test script to demonstrate printing summary information without templates.
This shows how to integrate with the existing validation pipeline.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from reporting.generation.print_summary_info import print_summary_report_info, print_raw_data_structure
from reporting.generation.report_generator import ReportGenerator
from services.validation_service import ValidationService
from data_integration.connectors.excel_connector import ExcelConnector
from core.rule_engine.rule_manager import RuleManager
import json


def test_with_sample_data():
    """Test with sample validation results."""
    print("Testing Summary Information Extraction")
    print("=" * 80)
    
    try:
        # Load a sample results file if it exists
        results_file = "output/Analytics_Validation_20250611_204241_20250611_204246_results.json"
        
        if os.path.exists(results_file):
            print(f"Loading results from: {results_file}")
            with open(results_file, 'r') as f:
                results_data = json.load(f)
            
            # The results file contains serialized data, we need to reconstruct it
            # For demonstration, we'll show what information is available
            print("\nAvailable sections in results file:")
            for key in results_data.keys():
                print(f"  - {key}")
            
            if 'validation_results' in results_data:
                print("\nValidation Results Summary:")
                val_results = results_data['validation_results']
                for rule_id, rule_data in val_results.items():
                    print(f"\n  Rule: {rule_data.get('rule_name', rule_id)}")
                    print(f"    Status: {rule_data.get('compliance_status', 'Unknown')}")
                    if 'compliance_metrics' in rule_data:
                        metrics = rule_data['compliance_metrics']
                        print(f"    GC: {metrics.get('gc_count', 0)}")
                        print(f"    PC: {metrics.get('pc_count', 0)}")
                        print(f"    DNC: {metrics.get('dnc_count', 0)}")
        
        else:
            print(f"Results file not found: {results_file}")
            print("\nTo generate real data, run a validation using the Analytics Runner UI")
            print("or use the validation service directly.")
            
    except Exception as e:
        print(f"Error loading sample data: {e}")
        import traceback
        traceback.print_exc()


def demonstrate_integration():
    """Show how to integrate with the validation pipeline."""
    print("\n\nIntegration Example")
    print("=" * 80)
    print("""
To integrate with your validation pipeline, modify your report generation code:

1. In your validation workflow, after getting rule_results:

    from reporting.generation.print_summary_info import print_summary_report_info
    
    # After validation completes and you have rule_results
    print_summary_report_info(rule_results)

2. In template_integration.py, add an option to print instead of generate:

    def generate_reports(rule_results, output_dir, print_only=False):
        if print_only:
            print_summary_report_info(rule_results)
            return None
        # ... existing template generation code ...

3. In your UI or command line tool, add a flag:

    # Add a checkbox or command line flag
    if print_summary_only:
        generate_reports(rule_results, output_dir, print_only=True)
    """)


if __name__ == "__main__":
    test_with_sample_data()
    demonstrate_integration()
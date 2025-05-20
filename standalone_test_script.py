#!/usr/bin/env python
# standalone_test_report_generator.py
"""
Simple standalone test script for ReportGenerator.
This can be run directly without pytest to quickly test functionality.
"""

import os
import sys
import pandas as pd
import numpy as np
import datetime
import json
from pathlib import Path

# Add parent directory to path to import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Try importing modules (with some error handling)
try:
    from reporting.generation.report_generator_original import ReportGenerator
    from core.rule_engine.rule_manager import ValidationRule
    from core.rule_engine.rule_evaluator import RuleEvaluationResult
    from core.rule_engine.compliance_determiner import ComplianceStatus
except ImportError as e:
    print(f"Error importing required modules: {str(e)}")
    print("Make sure the module paths are correct and the required modules are available.")
    sys.exit(1)


def create_mock_data():
    """Create mock validation data for testing the report generator."""
    
    print("Creating mock validation data...")
    
    # Create test rules
    rules = [
        ValidationRule(
            rule_id="rule1", 
            name="Expense Validation", 
            formula="=AND([Amount] > 0, [ApproverName] <> \"\")", 
            description="Validates that expense records have an amount and approver",
            category="financial",
            severity="high"
        ),
        ValidationRule(
            rule_id="rule2", 
            name="Timeliness Check", 
            formula="=DATEDIF([SubmissionDate], [ReviewDate], \"D\") <= 5", 
            description="Checks that reviews were completed within 5 days",
            category="compliance",
            severity="medium"
        ),
        ValidationRule(
            rule_id="rule3", 
            name="Documentation Quality", 
            formula="=AND(NOT(ISBLANK([Notes])), LEN([Notes]) >= 25)", 
            description="Validates that notes are substantive (at least 25 chars)",
            category="quality",
            severity="low"
        )
    ]
    
    # Add metadata to rules
    for rule in rules:
        rule.metadata['responsible_party_column'] = 'AuditLeader'
    
    # Create test datasets
    expense_data = pd.DataFrame({
        'RecordID': range(1, 11),
        'AuditLeader': ['Alice', 'Bob', 'Charlie', 'Alice', 'Bob', 'Charlie', 'Alice', 'Bob', 'Charlie', 'Alice'],
        'Amount': [100, 250, 0, 500, 150, 200, 350, 0, 425, 175],
        'ApproverName': ['Smith', 'Jones', '', 'Wilson', 'Garcia', 'Miller', 'Davis', '', 'Brown', 'Wilson'],
        'Result_Expense Validation': [True, True, False, True, True, True, True, False, True, True],
        'Region': ['North', 'South', 'East', 'West', 'North', 'South', 'East', 'West', 'North', 'South']
    })
    
    # Create date fields for timeliness check
    today = datetime.datetime.now().date()
    submission_dates = [today - datetime.timedelta(days=d) for d in [10, 12, 7, 15, 8, 9, 5, 20, 11, 6]]
    review_dates = [today - datetime.timedelta(days=d) for d in [5, 5, 5, 7, 4, 2, 1, 10, 2, 1]]
    
    timeliness_data = pd.DataFrame({
        'RecordID': range(1, 11),
        'AuditLeader': ['Alice', 'Bob', 'Charlie', 'Alice', 'Bob', 'Charlie', 'Alice', 'Bob', 'Charlie', 'Alice'],
        'SubmissionDate': submission_dates,
        'ReviewDate': review_dates,
        'Result_Timeliness Check': [True, False, True, False, True, True, True, False, True, True],
        'Region': ['North', 'South', 'East', 'West', 'North', 'South', 'East', 'West', 'North', 'South']
    })
    
    # Create notes data for documentation quality check
    notes = [
        "This is a detailed note explaining the expense in full detail.",
        "Short note",
        "Comprehensive explanation of purpose and business justification for this expense.",
        "Missing documentation",
        "Detailed breakdown of all attendees and business purpose.",
        "Very thorough and detailed explanation of the expense with all required information.",
        "Detailed note",
        "Brief only",
        "Complete documentation with all supporting evidence properly attached.",
        "This expense is fully documented and approved."
    ]
    
    doc_quality_data = pd.DataFrame({
        'RecordID': range(1, 11),
        'AuditLeader': ['Alice', 'Bob', 'Charlie', 'Alice', 'Bob', 'Charlie', 'Alice', 'Bob', 'Charlie', 'Alice'],
        'Notes': notes,
        'Result_Documentation Quality': [True, False, True, False, True, True, True, False, True, True],
        'Region': ['North', 'South', 'East', 'West', 'North', 'South', 'East', 'West', 'North', 'South']
    })
    
    # Create rule results
    rule_results = {}

    # Helper function to create party results
    def create_party_results(df, result_column):
        party_results = {}
        for leader, group_df in df.groupby('AuditLeader'):
            # Calculate metrics
            dnc_rate = (group_df[result_column] == False).mean()
            gc_count = (group_df[result_column] == True).sum()
            pc_count = 0  # Simplified for testing
            dnc_count = (group_df[result_column] == False).sum()
            error_count = 0  # Simplified for testing
            total_count = len(group_df)
            
            # Determine status
            if dnc_rate <= 0.1:
                leader_status = "GC"
            elif dnc_rate <= 0.3:
                leader_status = "PC"
            else:
                leader_status = "DNC"
                
            party_results[leader] = {
                'status': leader_status,
                'metrics': {
                    'gc_rate': 1.0 - dnc_rate,
                    'pc_rate': 0.0,  # Simplified for testing
                    'dnc_rate': dnc_rate,
                    'gc_count': gc_count,
                    'pc_count': pc_count,
                    'dnc_count': dnc_count,
                    'error_count': error_count,
                    'total_count': total_count
                }
            }
        return party_results
    
    # Create RuleEvaluationResult instances
    rule_results['rule1'] = RuleEvaluationResult(
        rule=rules[0],
        result_df=expense_data,
        result_column="Result_Expense Validation",
        compliance_status="GC",  # Overall status
        compliance_metrics={  # Metrics
            'gc_rate': 0.8,
            'pc_rate': 0.0,
            'dnc_rate': 0.2,
            'gc_count': 8,
            'pc_count': 0,
            'dnc_count': 2,
            'error_count': 0,
            'total_count': 10
        },
        party_results=create_party_results(expense_data, "Result_Expense Validation")
    )
    
    rule_results['rule2'] = RuleEvaluationResult(
        rule=rules[1],
        result_df=timeliness_data,
        result_column="Result_Timeliness Check",
        compliance_status="PC",  # Overall status
        compliance_metrics={  # Metrics
            'gc_rate': 0.7,
            'pc_rate': 0.0,
            'dnc_rate': 0.3,
            'gc_count': 7,
            'pc_count': 0,
            'dnc_count': 3,
            'error_count': 0,
            'total_count': 10
        },
        party_results=create_party_results(timeliness_data, "Result_Timeliness Check")
    )
    
    rule_results['rule3'] = RuleEvaluationResult(
        rule=rules[2],
        result_df=doc_quality_data,
        result_column="Result_Documentation Quality",
        compliance_status="GC",  # Overall status
        compliance_metrics={  # Metrics
            'gc_rate': 0.8,
            'pc_rate': 0.0,
            'dnc_rate': 0.2,
            'gc_count': 8,
            'pc_count': 0,
            'dnc_count': 2,
            'error_count': 0,
            'total_count': 10
        },
        party_results=create_party_results(doc_quality_data, "Result_Documentation Quality")
    )
    
    # Create overall validation results
    results = {
        'valid': False,
        'analytic_id': 'test_audit_validation',
        'timestamp': datetime.datetime.now().isoformat(),
        'data_source': "Mock data for testing",
        'rule_results': {
            'rule1': rule_results['rule1'].summary,
            'rule2': rule_results['rule2'].summary,
            'rule3': rule_results['rule3'].summary
        },
        'summary': {
            'total_rules': 3,
            'compliance_counts': {
                'GC': 2,
                'PC': 1,
                'DNC': 0
            },
            'compliance_rate': 0.7667,  # (0.8 + 0.7 + 0.8) / 3
            'rule_stats': {
                'by_category': {
                    'financial': {'count': 1, 'GC': 1, 'PC': 0, 'DNC': 0},
                    'compliance': {'count': 1, 'GC': 0, 'PC': 1, 'DNC': 0},
                    'quality': {'count': 1, 'GC': 1, 'PC': 0, 'DNC': 0}
                },
                'by_severity': {
                    'high': {'count': 1, 'GC': 1, 'PC': 0, 'DNC': 0},
                    'medium': {'count': 1, 'GC': 0, 'PC': 1, 'DNC': 0},
                    'low': {'count': 1, 'GC': 1, 'PC': 0, 'DNC': 0}
                }
            }
        },
        'execution_time': 2.345,
        'status': 'PARTIALLY_COMPLIANT'
    }
    
    # Add grouped summary by AuditLeader
    grouped_summary = {}
    
    for leader in ['Alice', 'Bob', 'Charlie']:
        leader_results = {}
        gc_count = 0
        pc_count = 0
        dnc_count = 0
        total_count = 0
        
        for rule_id, result in rule_results.items():
            if leader in result.party_results:
                party_result = result.party_results[leader]
                
                # Update counts
                gc_count += party_result['metrics']['gc_count']
                pc_count += party_result['metrics']['pc_count']
                dnc_count += party_result['metrics']['dnc_count']
                total_count += party_result['metrics']['total_count']
        
        # Calculate compliance rate for this leader
        compliance_rate = (gc_count + (pc_count * 0.5)) / total_count if total_count > 0 else 0
        
        # Store in grouped summary
        grouped_summary[leader] = {
            'total_rules': 3,
            'GC': gc_count,
            'PC': pc_count,
            'DNC': dnc_count,
            'compliance_rate': compliance_rate
        }
    
    results['grouped_summary'] = grouped_summary
    
    return results, rule_results


def generate_sample_config():
    """Generate a sample configuration file for the report generator."""
    config = {
        'report_config': {
            'test_weights': {
                'rule1': 0.25,
                'rule2': 0.20,
                'rule3': 0.15
            },
            'score_mapping': {
                "0.95-1.00": 5,
                "0.85-0.94": 4,
                "0.70-0.84": 3,
                "0.50-0.69": 2,
                "0.00-0.49": 1
            },
            'rating_labels': {
                5: "✅ Satisfactory",
                4: "✓ Meets Expectations",
                3: "⚠ Requires Attention",
                2: "⚠ Needs Improvement",
                1: "❌ Unsatisfactory"
            },
            'rule_explanations': {
                'rule1': "This rule validates that expense records have a positive amount and an approver name.",
                'rule2': "This rule checks that reviews were completed within 5 days of submission.",
                'rule3': "This rule ensures that documentation notes are substantive (at least 25 characters long)."
            }
        }
    }
    
    # Create the output directory if it doesn't exist
    os.makedirs('test_output', exist_ok=True)
    
    # Write the config to a file
    config_path = os.path.join('test_output', 'report_config.yaml')
    try:
        import yaml
        with open(config_path, 'w') as f:
            yaml.dump(config, f, sort_keys=False)
        print(f"Generated sample configuration file: {config_path}")
        return config_path
    except ImportError:
        print("PyYAML not installed. Using default configuration.")
        return None
    except Exception as e:
        print(f"Error generating configuration file: {str(e)}")
        return None


def main():
    """Test the ReportGenerator with mock data."""
    print("=== ReportGenerator Standalone Test ===")
    
    # Generate sample configuration
    config_path = generate_sample_config()
    
    # Create mock data
    results, rule_results = create_mock_data()
    
    print("\nInitializing ReportGenerator...")
    # Initialize ReportGenerator with the config if available
    if config_path and os.path.exists(config_path):
        report_generator = ReportGenerator(config_path)
        print(f"Using configuration from: {config_path}")
    else:
        report_generator = ReportGenerator()
        print("Using default configuration")
    
    # Create output directory if it doesn't exist
    output_dir = "test_output"
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate Excel report
    try:
        excel_path = os.path.join(output_dir, "test_report.xlsx")
        print(f"\nGenerating Excel report: {excel_path}")
        report_generator.generate_excel(results, rule_results, excel_path, group_by="AuditLeader")
        print(f"Excel report generated successfully!")
        
        # Check file size
        excel_size = os.path.getsize(excel_path) / 1024  # Size in KB
        print(f"Report size: {excel_size:.1f} KB")
    except Exception as e:
        print(f"Error generating Excel report: {str(e)}")
    
    # Generate HTML report
    try:
        html_path = os.path.join(output_dir, "test_report.html")
        print(f"\nGenerating HTML report: {html_path}")
        report_generator.generate_html(results, rule_results, html_path)
        print(f"HTML report generated successfully!")
        
        # Check file size
        html_size = os.path.getsize(html_path) / 1024  # Size in KB
        print(f"Report size: {html_size:.1f} KB")
    except Exception as e:
        print(f"Error generating HTML report: {str(e)}")
    
    print(f"\nReports generated in {output_dir}/ directory")
    
    # Test score calculation
    print("\nTesting score calculation...")
    
    # Calculate scores for each audit leader
    for leader in ['Alice', 'Bob', 'Charlie']:
        score = report_generator.calculate_weighted_score(results, rule_results, leader)
        print(f"Calculated score for {leader}: {score}")
        
        # Get the rating label
        rating = report_generator.config['rating_labels'].get(round(score), f"Score {score}")
        print(f"Rating: {rating}")
    
    print("\nTest completed!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Print Summary Report Information Without Templates

This script extracts and displays all the information that would normally
go into a summary report, but outputs it as plain text instead of using
Excel templates.
"""

import json
from typing import Dict, List, Tuple, Any
from collections import defaultdict
# import pandas as pd  # Commented out - not currently used


def extract_dynamic_structure(rule_results: Dict, responsible_party_column: str = "Responsible Party") -> Tuple[List[str], List[str], Dict]:
    """Extract rules, audit leaders, and create performance matrix."""
    rule_names = []
    audit_leaders = set()
    leader_rule_matrix = defaultdict(lambda: defaultdict(dict))
    
    for rule_id, eval_result in rule_results.items():
        rule_name = eval_result.rule.name
        rule_names.append(rule_name)
        
        if hasattr(eval_result, 'party_results') and eval_result.party_results:
            for leader, party_data in eval_result.party_results.items():
                audit_leaders.add(leader)
                metrics = party_data.get('metrics', {})
                
                leader_rule_matrix[leader][rule_name] = {
                    'gc_count': metrics.get('gc_count', 0),
                    'pc_count': metrics.get('pc_count', 0),
                    'dnc_count': metrics.get('dnc_count', 0),
                    'na_count': metrics.get('na_count', 0),
                    'total_count': metrics.get('total_count', 0),
                    'status': party_data.get('status', 'N/A'),
                    'error_rate': metrics.get('dnc_rate', 0),
                    'threshold': eval_result.rule.risk_level.threshold
                }
    
    return sorted(rule_names), sorted(list(audit_leaders)), dict(leader_rule_matrix)


def calculate_weighted_scores(leader_rule_matrix: Dict) -> Dict[str, Dict]:
    """Calculate weighted scores and ratings for each leader."""
    leader_scores = {}
    
    for leader, rules in leader_rule_matrix.items():
        total_score = 0
        rule_count = 0
        
        for rule_name, metrics in rules.items():
            # Weighted scoring: GC=5, PC=3, DNC=1
            gc_count = metrics.get('gc_count', 0)
            pc_count = metrics.get('pc_count', 0)
            dnc_count = metrics.get('dnc_count', 0)
            total_count = metrics.get('total_count', 0)
            
            if total_count > 0:
                rule_score = (gc_count * 5 + pc_count * 3 + dnc_count * 1) / total_count
                total_score += rule_score
                rule_count += 1
        
        avg_score = total_score / rule_count if rule_count > 0 else 0
        
        # Determine rating based on average score
        if avg_score >= 4:
            rating = "GC"
        elif avg_score >= 2.5:
            rating = "PC"
        else:
            rating = "DNC"
        
        leader_scores[leader] = {
            'average_score': avg_score,
            'rating': rating,
            'rule_count': rule_count
        }
    
    return leader_scores


def print_summary_report_info(rule_results: Dict, responsible_party_column: str = "Responsible Party"):
    """Print all summary report information in a readable format."""
    
    print("=" * 80)
    print("SUMMARY REPORT INFORMATION (Without Template)")
    print("=" * 80)
    print()
    
    # Extract dynamic structure
    rule_names, audit_leaders, leader_rule_matrix = extract_dynamic_structure(
        rule_results, responsible_party_column
    )
    
    # Section 1: IAG Overall Results
    print("SECTION 1: IAG OVERALL RESULTS")
    print("-" * 40)
    
    # Calculate overall IAG metrics
    total_gc = total_pc = total_dnc = total_na = total_count = 0
    
    for rule_id, eval_result in rule_results.items():
        metrics = eval_result.compliance_metrics
        total_gc += metrics.get('gc_count', 0)
        total_pc += metrics.get('pc_count', 0)
        total_dnc += metrics.get('dnc_count', 0)
        total_na += metrics.get('na_count', 0)
        total_count += metrics.get('total_count', 0)
    
    print(f"Total Records Evaluated: {total_count}")
    print(f"Generally Compliant (GC): {total_gc} ({total_gc/total_count*100:.1f}%)" if total_count > 0 else "GC: 0")
    print(f"Partially Compliant (PC): {total_pc} ({total_pc/total_count*100:.1f}%)" if total_count > 0 else "PC: 0")
    print(f"Does Not Comply (DNC): {total_dnc} ({total_dnc/total_count*100:.1f}%)" if total_count > 0 else "DNC: 0")
    print(f"Not Applicable (N/A): {total_na} ({total_na/total_count*100:.1f}%)" if total_count > 0 else "N/A: 0")
    print()
    
    # Section 2: Audit Leader Overall Results
    print("SECTION 2: AUDIT LEADER OVERALL RESULTS")
    print("-" * 40)
    
    leader_scores = calculate_weighted_scores(leader_rule_matrix)
    
    for leader in sorted(audit_leaders):
        scores = leader_scores.get(leader, {})
        print(f"\n{leader}:")
        print(f"  Average Score: {scores.get('average_score', 0):.2f}")
        print(f"  Overall Rating: {scores.get('rating', 'N/A')}")
        print(f"  Rules Evaluated: {scores.get('rule_count', 0)}")
    
    print()
    
    # Section 3: Detailed Test Results
    print("SECTION 3: DETAILED TEST RESULTS BY RULE")
    print("-" * 40)
    
    for rule_name in rule_names:
        print(f"\nRule: {rule_name}")
        
        # Find the rule details
        rule_details = None
        for rule_id, eval_result in rule_results.items():
            if eval_result.rule.name == rule_name:
                rule_details = eval_result
                break
        
        if rule_details:
            print(f"  Description: {rule_details.rule.description}")
            print(f"  Risk Level: {rule_details.rule.risk_level.level}")
            print(f"  Threshold: {rule_details.rule.risk_level.threshold}")
            print(f"  Overall Status: {rule_details.compliance_status}")
            
            # Print results by audit leader
            print("\n  Results by Audit Leader:")
            for leader in sorted(audit_leaders):
                if leader in leader_rule_matrix and rule_name in leader_rule_matrix[leader]:
                    metrics = leader_rule_matrix[leader][rule_name]
                    total = metrics.get('total_count', 0)
                    if total > 0:
                        print(f"    {leader}:")
                        print(f"      Status: {metrics.get('status', 'N/A')}")
                        print(f"      GC: {metrics.get('gc_count', 0)} ({metrics.get('gc_count', 0)/total*100:.1f}%)")
                        print(f"      PC: {metrics.get('pc_count', 0)} ({metrics.get('pc_count', 0)/total*100:.1f}%)")
                        print(f"      DNC: {metrics.get('dnc_count', 0)} ({metrics.get('dnc_count', 0)/total*100:.1f}%)")
                        print(f"      Error Rate: {metrics.get('error_rate', 0)*100:.1f}%")
    
    print("\n" + "=" * 80)
    print("END OF SUMMARY REPORT INFORMATION")
    print("=" * 80)


def print_raw_data_structure(rule_results: Dict):
    """Print the raw data structure for debugging purposes."""
    print("\n" + "=" * 80)
    print("RAW DATA STRUCTURE")
    print("=" * 80)
    
    for rule_id, eval_result in rule_results.items():
        print(f"\nRule ID: {rule_id}")
        print(f"Rule Name: {eval_result.rule.name}")
        print(f"Compliance Status: {eval_result.compliance_status}")
        print(f"Compliance Metrics: {json.dumps(eval_result.compliance_metrics, indent=2)}")
        
        if hasattr(eval_result, 'party_results') and eval_result.party_results:
            print("Party Results:")
            for party, data in eval_result.party_results.items():
                print(f"  {party}: {json.dumps(data, indent=4)}")


if __name__ == "__main__":
    # Example usage - this would normally come from your validation pipeline
    print("This script extracts and prints summary report information.")
    print("To use it, import the print_summary_report_info function and pass your rule_results dict.")
    print("\nExample:")
    print("  from reporting.generation.print_summary_info import print_summary_report_info")
    print("  print_summary_report_info(rule_results)")
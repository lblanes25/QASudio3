import os
import pytest
import pandas as pd
import numpy as np
import datetime
from pathlib import Path
import tempfile

# Import modules to test
from reporting.generation.report_generator import ReportGenerator
from core.rule_engine.rule_manager import ValidationRule
from core.rule_engine.rule_evaluator import RuleEvaluationResult


# Fixture for mock rules
@pytest.fixture
def mock_rules():
    """Create test validation rules"""
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

    # Add metadata
    for rule in rules:
        rule.metadata['responsible_party_column'] = 'AuditLeader'

    return rules


# Fixture for mock result data
@pytest.fixture
def mock_result_data(mock_rules):
    """Create mock test data and evaluation results"""
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
        rule=mock_rules[0],
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
        rule=mock_rules[1],
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
        rule=mock_rules[2],
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


# Fixture for ReportGenerator instance
@pytest.fixture
def report_generator():
    """Create a ReportGenerator instance"""
    return ReportGenerator()


# Test ReportGenerator initialization
def test_report_generator_init():
    """Test ReportGenerator initialization with default and custom config"""
    # Test with default config
    generator = ReportGenerator()
    assert generator.config is not None
    assert 'score_mapping' in generator.config
    assert 'rating_labels' in generator.config

    # Test with custom config
    config_data = {
        'report_config': {
            'test_weights': {'rule1': 0.5, 'rule2': 0.3, 'rule3': 0.2},
            'score_mapping': {'0.9-1.0': 5, '0.7-0.89': 4, '0.0-0.69': 3}
        }
    }

    # Create a temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as temp:
        import yaml
        yaml.dump(config_data, temp)
        temp_path = temp.name

    try:
        # Initialize with temp config
        generator_with_config = ReportGenerator(temp_path)
        assert generator_with_config.config['test_weights']['rule1'] == 0.5
        assert '0.9-1.0' in generator_with_config.config['score_mapping']
    finally:
        # Clean up
        if os.path.exists(temp_path):
            os.unlink(temp_path)


# Test formula analysis functions
def test_analyze_formula_components(report_generator):
    """Test the formula analysis functionality"""
    # Test simple formula
    formula1 = "=[Amount] > 0"
    analysis1 = report_generator._analyze_formula_components(formula1)
    assert analysis1['referenced_columns'] == ['Amount']
    assert '>' in analysis1['comparisons']
    assert analysis1['complexity'] == 'simple'

    # Test complex formula
    formula2 = "=AND(NOT(ISBLANK([Field1])), [Field2] > 100, DATEDIF([StartDate], [EndDate], \"D\") <= 5)"
    analysis2 = report_generator._analyze_formula_components(formula2)
    assert set(analysis2['referenced_columns']) == set(['Field1', 'Field2', 'StartDate', 'EndDate'])
    assert 'AND' in analysis2['logical_operators']
    assert 'NOT' in analysis2['logical_operators']
    assert 'ISBLANK' in analysis2['functions']
    assert 'DATEDIF' in analysis2['functions']
    assert analysis2['complexity'] == 'complex'


# Test score calculation
def test_calculate_score(report_generator, mock_result_data):
    """Test the score calculation functionality"""
    results, rule_results = mock_result_data

    # Test basic score calculation
    score1 = report_generator._calculate_score(0.95)
    assert score1 == 5

    score2 = report_generator._calculate_score(0.75)
    assert score2 == 4

    score3 = report_generator._calculate_score(0.5)
    assert score3 == 2

    # Test weighted score calculation
    weighted_score = report_generator.calculate_weighted_score(results, rule_results)
    assert 1 <= weighted_score <= 5

    # Test leader-specific score
    alice_score = report_generator.calculate_weighted_score(results, rule_results, 'Alice')
    assert 1 <= alice_score <= 5


# Test Excel report generation
def test_generate_excel(report_generator, mock_result_data, tmp_path):
    """Test Excel report generation"""
    results, rule_results = mock_result_data

    # Create output file in temp directory
    output_path = tmp_path / "test_report.xlsx"

    # Generate the report
    try:
        report_path = report_generator.generate_excel(
            results, rule_results, str(output_path), group_by="AuditLeader"
        )

        # Verify the file was created
        assert os.path.exists(report_path)
        assert os.path.getsize(report_path) > 0

    except ImportError:
        # Skip test if xlsxwriter is not available
        pytest.skip("xlsxwriter not available")


# Test HTML report generation
def test_generate_html(report_generator, mock_result_data, tmp_path):
    """Test HTML report generation"""
    results, rule_results = mock_result_data

    # Create output file in temp directory
    output_path = tmp_path / "test_report.html"

    # Generate the report
    report_path = report_generator.generate_html(
        results, rule_results, str(output_path)
    )

    # Verify the file was created
    assert os.path.exists(report_path)
    assert os.path.getsize(report_path) > 0

    # Check content
    with open(report_path, 'r') as f:
        content = f.read()
        assert 'QA Analytics Framework' in content
        assert 'Summary' in content
        assert 'PARTIALLY_COMPLIANT' in content


# Test rule explanation methods
def test_rule_explanation(report_generator, mock_rules):
    """Test the rule explanation functionality"""
    rule = mock_rules[0]  # Expense Validation rule

    # Test formula explanation
    explanation = report_generator._generate_formula_explanation(rule)
    assert 'formula' in explanation.lower()
    assert 'amount' in explanation.lower()
    assert 'approvername' in explanation.lower()

    # Test with pre-configured explanation
    report_generator.config['rule_explanations'][rule.rule_id] = "Custom explanation"
    explanation2 = report_generator._generate_formula_explanation(rule)
    assert explanation2 == "Custom explanation"


# Test failure analysis and explanation
def test_failure_explanation(report_generator, mock_result_data):
    """Test the failure explanation functionality"""
    results, rule_results = mock_result_data

    # Get a rule result with failures
    result = rule_results['rule1']  # Expense Validation

    # Get failing items
    failing_df = result.get_failing_items()
    assert not failing_df.empty

    # Test failure formatting
    explanation = report_generator._format_rule_explanation(result.rule, failing_df)
    assert explanation is not None
    assert "Missing data" in explanation or "Failed validation" in explanation

    # Test calculation column adding
    enhanced_df = report_generator._add_calculation_columns(failing_df, result)
    assert any(col.startswith("Calc_") for col in enhanced_df.columns)
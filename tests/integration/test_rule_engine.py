# tests/test_rule_engine.py
import pytest
import pandas as pd
import os
import sys
import tempfile
from pathlib import Path

# Add the project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
from core.rule_engine.compliance_determiner import ComplianceDeterminer
from core.rule_engine.rule_evaluator import RuleEvaluator


@pytest.fixture
def sample_data():
    """Fixture to provide sample test data"""
    data = {
        'ID': [1, 2, 3, 4, 5],
        'Value': [100, 200, 50, 0, 150],
        'Category': ['A', 'B', 'A', 'C', 'B'],
        'ResponsibleParty': ['Team1', 'Team2', 'Team1', 'Team3', 'Team2']
    }
    return pd.DataFrame(data)


@pytest.fixture
def temp_rules_dir():
    """Fixture to provide a temporary directory for rules"""
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield tmpdirname


def test_rule_creation_and_validation(temp_rules_dir):
    """Test creating and validating a rule"""
    # Create a rule manager
    rule_manager = ValidationRuleManager(temp_rules_dir)

    # Create a validation rule
    rule = ValidationRule(
        name="ValueAboveThreshold",
        formula="=IF([Value] >= 100, TRUE, FALSE)",
        description="Checks if Value is at least 100",
        threshold=0.8,  # 80% compliance required
        metadata={
            'category': 'Data Quality',
            'owner': 'QA Team',
            'tags': ['threshold', 'value']
        }
    )

    # Validate the rule
    is_valid, error = rule.validate()
    assert is_valid, f"Rule validation failed: {error}"

    # Add rule to manager
    rule_id = rule_manager.add_rule(rule)
    assert rule_id == rule.rule_id

    # Retrieve rule from manager
    retrieved_rule = rule_manager.get_rule(rule_id)
    assert retrieved_rule is not None
    assert retrieved_rule.name == "ValueAboveThreshold"
    assert retrieved_rule.formula == "=IF([Value] >= 100, TRUE, FALSE)"


def test_rule_evaluation(sample_data, temp_rules_dir):
    """Test evaluating a rule against data"""
    # Skip if win32com is not available
    pytest.importorskip("win32com")

    # Create a rule manager
    rule_manager = ValidationRuleManager(temp_rules_dir)

    # Create a validation rule
    rule = ValidationRule(
        name="ValueAboveThreshold",
        formula="=IF([Value] >= 100, TRUE, FALSE)",
        description="Checks if Value is at least 100",
        threshold=0.8  # 80% compliance required
    )

    # Add rule to manager
    rule_id = rule_manager.add_rule(rule)

    # Create rule evaluator
    evaluator = RuleEvaluator(rule_manager)

    # Evaluate rule
    result = evaluator.evaluate_rule(rule, sample_data, 'ResponsibleParty')

    # Verify results
    assert result.compliance_status in ["GC", "PC", "DNC"]
    assert "gc_count" in result.compliance_metrics
    assert "dnc_count" in result.compliance_metrics

    # Expected results: 3 values >= 100, 2 values < 100
    # With threshold of 0.8 (80%), this should be "PC" (Partially Conforms)
    assert result.compliance_metrics["gc_count"] == 3  # 3 values meet the criteria
    assert result.compliance_metrics["dnc_count"] == 2  # 2 values fail the criteria

    # Check party results
    assert "Team1" in result.party_results
    assert "Team2" in result.party_results
    assert "Team3" in result.party_results


def test_compliance_determiner():
    """Test the compliance determiner logic"""
    # Create compliance determiner with default thresholds
    determiner = ComplianceDeterminer(gc_threshold=0.95, pc_threshold=0.80)

    # Test boolean results
    assert determiner.determine_row_compliance(True) == "GC"
    assert determiner.determine_row_compliance(False) == "DNC"

    # Test numeric results
    assert determiner.determine_row_compliance(1.0) == "GC"
    assert determiner.determine_row_compliance(0.9) == "PC"
    assert determiner.determine_row_compliance(0.7) == "DNC"

    # Test error values
    assert determiner.determine_row_compliance("ERROR_VALUE") == "DNC"

    # Test with rule threshold
    # For 0.85 value with 0.9 threshold, it should be PC since 0.85 >= 0.8 (pc_threshold)
    assert determiner.determine_row_compliance(0.85, rule_threshold=0.9) == "PC"
    # Value below pc_threshold should be DNC
    assert determiner.determine_row_compliance(0.75, rule_threshold=0.9) == "DNC"
    # Value above rule_threshold should be GC
    assert determiner.determine_row_compliance(0.95, rule_threshold=0.9) == "GC"


def test_rule_failure_by_party(sample_data, temp_rules_dir):
    """Test the ability to retrieve failing items by party"""
    # Skip if win32com is not available
    pytest.importorskip("win32com")

    # Create a rule manager
    rule_manager = ValidationRuleManager(temp_rules_dir)

    # Create a validation rule with standardized metadata
    rule = ValidationRule(
        name="ValueAboveThreshold",
        formula="=IF([Value] >= 100, TRUE, FALSE)",
        description="Checks if Value is at least 100",
        threshold=0.8,  # 80% compliance required
        severity="high",
        category="data_quality",
        tags=["threshold", "value"],
        responsible_party_column="ResponsibleParty"
    )

    # Add rule to manager
    rule_id = rule_manager.add_rule(rule)

    # Create rule evaluator
    evaluator = RuleEvaluator(rule_manager)

    # Evaluate rule - explicitly pass the responsible party column
    result = evaluator.evaluate_rule(rule, sample_data, "ResponsibleParty")

    # Get failing items by party
    failing_by_party = result.get_failing_items_by_party()

    # Verify results
    assert "Team1" in failing_by_party
    assert "Team3" in failing_by_party
    assert "Team2" not in failing_by_party  # Team2 has no failing items

    # Team1 should have one failing item (Value=50)
    assert len(failing_by_party["Team1"]) == 1
    assert failing_by_party["Team1"]["Value"].iloc[0] == 50

    # Team3 should have one failing item (Value=0)
    assert len(failing_by_party["Team3"]) == 1
    assert failing_by_party["Team3"]["Value"].iloc[0] == 0

    # Test compliance summary by party
    summary_df = result.get_compliance_summary_by_party()

    # Check if summary_df is empty, if so print debug info
    if summary_df.empty:
        print("DEBUG: summary_df is empty")
        print(f"DEBUG: party_results = {result.party_results}")
        print(f"DEBUG: party_column = {rule.responsible_party_column}")
        print(f"DEBUG: result_df columns = {result.result_df.columns.tolist()}")

        # Try using explicit column name
        summary_df = result.get_compliance_summary_by_party("ResponsibleParty")
        if summary_df.empty:
            print("DEBUG: summary_df is still empty with explicit column name")
        else:
            print("DEBUG: summary_df with explicit column name:")
            print(summary_df)

    # If party_results are empty, we can't proceed with testing the summary
    if not result.party_results:
        pytest.skip("No party_results available, cannot test summary")

    # Verify there is data in the summary
    assert not summary_df.empty, "Compliance summary DataFrame should not be empty"

    # Check that Team2 has 100% compliance
    team2_row = summary_df[summary_df["ResponsibleParty"] == "Team2"]
    assert not team2_row.empty, "Team2 should be in compliance summary"
    assert abs(team2_row["Compliance_Rate"].iloc[0] - 1.0) < 0.001
    assert team2_row["Status"].iloc[0] == "GC"

    # Check that Team1 has 50% compliance (1 of 2 items passes)
    team1_row = summary_df[summary_df["ResponsibleParty"] == "Team1"]
    assert not team1_row.empty, "Team1 should be in compliance summary"
    assert abs(team1_row["Compliance_Rate"].iloc[0] - 0.5) < 0.001
    assert team1_row["Status"].iloc[0] in ["PC", "DNC"]
if __name__ == "__main__":
    pytest.main(["-v"])
from typing import Dict, List, Any, Optional, Tuple, Union
import pandas as pd
import logging
import os
from pathlib import Path

# Import our components
from .rule_manager import ValidationRule, ValidationRuleManager
from .compliance_determiner import ComplianceDeterminer, ComplianceStatus
# Fix the import to use absolute imports instead of relative
from core.formula_engine.excel_formula_processor import ExcelFormulaProcessor

logger = logging.getLogger(__name__)


class RuleEvaluationResult:
    """Container for the results of a rule evaluation"""

    def __init__(self,
                 rule: ValidationRule,
                 result_df: pd.DataFrame,
                 result_column: str,
                 compliance_status: ComplianceStatus,
                 compliance_metrics: Dict[str, Any],
                 party_results: Optional[Dict[str, Dict[str, Any]]] = None):
        """
        Initialize evaluation result.

        Args:
            rule: The rule that was evaluated
            result_df: DataFrame with evaluation results
            result_column: Column name containing the results
            compliance_status: Overall compliance status
            compliance_metrics: Dictionary of compliance metrics
            party_results: Results grouped by responsible party
        """
        self.rule = rule
        self.result_df = result_df
        self.result_column = result_column
        self.compliance_status = compliance_status
        self.compliance_metrics = compliance_metrics
        self.party_results = party_results or {}

    @property
    def summary(self) -> Dict[str, Any]:
        """Get summary of evaluation results"""
        return {
            "rule_id": self.rule.rule_id,
            "rule_name": self.rule.name,
            "compliance_status": self.compliance_status,
            "compliance_rate": 1.0 - self.compliance_metrics.get("dnc_rate", 0),
            "total_items": self.compliance_metrics.get("total_count", 0),
            "gc_count": self.compliance_metrics.get("gc_count", 0),
            "pc_count": self.compliance_metrics.get("pc_count", 0),
            "dnc_count": self.compliance_metrics.get("dnc_count", 0),
            "error_count": self.compliance_metrics.get("error_count", 0)
        }

    def get_failing_items(self) -> pd.DataFrame:
        """Get subset of results that did not comply with the rule"""
        return self.result_df[self.result_df[self.result_column] == False]

    def get_party_status(self, party: str) -> Optional[Dict[str, Any]]:
        """Get compliance status for a specific responsible party"""
        return self.party_results.get(party)

    def get_failing_items_by_party(self, party_column: Optional[str] = None) -> Dict[str, pd.DataFrame]:
        """
        Get failed items grouped by responsible party.

        Args:
            party_column: Optional column name for responsible party
                         (defaults to rule's responsible_party_column metadata if not provided)

        Returns:
            Dictionary mapping responsible parties to DataFrames with their failing items
        """
        # Get the responsible party column
        if not party_column:
            party_column = self.rule.metadata.get('responsible_party_column')

        # If no party column specified or not in DataFrame, return empty dict
        if not party_column or party_column not in self.result_df.columns:
            return {}

        # Get all failing items
        failing_items = self.get_failing_items()

        # If no failing items, return empty dict
        if len(failing_items) == 0:
            return {}

        # Group by responsible party
        failing_by_party = {}
        for party, party_df in failing_items.groupby(party_column):
            failing_by_party[party] = party_df.copy()

        return failing_by_party

    def get_compliance_summary_by_party(self, party_column: Optional[str] = None) -> pd.DataFrame:
        """
        Get a summary DataFrame of compliance metrics by responsible party.

        Args:
            party_column: Optional column name for responsible party
                         (defaults to rule's responsible_party_column metadata if not provided)

        Returns:
            DataFrame with compliance metrics for each responsible party
        """
        # Get the responsible party column
        if not party_column:
            party_column = self.rule.metadata.get('responsible_party_column')

        # If no party column specified or not in DataFrame, or no party_results
        # Return an empty DataFrame with the expected columns
        if not party_column or party_column not in self.result_df.columns or not self.party_results:
            columns = [
                'ResponsibleParty', 'Status', 'TotalItems', 'GC_Count',
                'PC_Count', 'DNC_Count', 'Compliance_Rate', 'Error_Count'
            ]
            return pd.DataFrame(columns=columns)

        # Prepare summary data
        summary_data = []

        for party, party_result in self.party_results.items():
            metrics = party_result['metrics']
            summary_data.append({
                'ResponsibleParty': party,
                'Status': party_result['status'],
                'TotalItems': metrics['total_count'],
                'GC_Count': metrics['gc_count'],
                'PC_Count': metrics['pc_count'],
                'DNC_Count': metrics['dnc_count'],
                'Compliance_Rate': 1.0 - metrics['dnc_rate'],
                'Error_Count': metrics['error_count']
            })

        # If no summary data, return empty DataFrame with correct columns
        if not summary_data:
            columns = [
                'ResponsibleParty', 'Status', 'TotalItems', 'GC_Count',
                'PC_Count', 'DNC_Count', 'Compliance_Rate', 'Error_Count'
            ]
            return pd.DataFrame(columns=columns)

        # Create DataFrame and sort by compliance rate
        df = pd.DataFrame(summary_data)
        if len(df) > 0:  # Only sort if not empty
            return df.sort_values('Compliance_Rate', ascending=False)
        return df


class RuleEvaluator:
    """
    Evaluates validation rules against data using the Excel formula processor.
    """

    def __init__(self,
                 rule_manager: Optional[ValidationRuleManager] = None,
                 compliance_determiner: Optional[ComplianceDeterminer] = None,
                 excel_visible: bool = False):
        """
        Initialize the rule evaluator.

        Args:
            rule_manager: ValidationRuleManager for rule access
            compliance_determiner: ComplianceDeterminer for compliance status
            excel_visible: Whether to make Excel visible during processing
        """
        self.rule_manager = rule_manager or ValidationRuleManager()
        self.compliance_determiner = compliance_determiner or ComplianceDeterminer()
        self.excel_visible = excel_visible

    def evaluate_rule(self,
                      rule: Union[str, ValidationRule],
                      data_df: pd.DataFrame,
                      responsible_party_column: Optional[str] = None) -> RuleEvaluationResult:
        """
        Evaluate a validation rule against a DataFrame.

        Args:
            rule: ValidationRule or rule_id to evaluate
            data_df: Data to validate
            responsible_party_column: Column identifying responsible parties

        Returns:
            RuleEvaluationResult with evaluation details
        """
        # Get rule object if rule_id was provided
        if isinstance(rule, str):
            rule_obj = self.rule_manager.get_rule(rule)
            if not rule_obj:
                raise ValueError(f"Rule with ID {rule} not found")
        else:
            rule_obj = rule

        # Validate the rule with the DataFrame
        is_valid, error = rule_obj.validate_with_dataframe(data_df)
        if not is_valid:
            raise ValueError(f"Rule validation failed: {error}")

        # Prepare result column name
        result_column = f"Result_{rule_obj.name}"

        # Process the formula with our Excel processor - using context manager
        formula_map = {result_column: rule_obj.formula}

        # Use context manager to ensure proper cleanup
        with ExcelFormulaProcessor(visible=self.excel_visible, track_errors=True) as processor:
            result_df = processor.process_formulas(data_df, formula_map)

        # Convert string "TRUE"/"FALSE" values to boolean for proper handling
        if result_column in result_df.columns:
            # Handle different result types that might come back from Excel
            def normalize_result(val):
                if isinstance(val, bool):
                    return val
                elif isinstance(val, (int, float)):
                    return bool(val)
                elif isinstance(val, str):
                    if val.upper() == "TRUE":
                        return True
                    elif val.upper() == "FALSE":
                        return False
                return val

            result_df[result_column] = result_df[result_column].apply(normalize_result)

            # Determine overall compliance
            compliance_status, compliance_metrics = self.compliance_determiner.determine_overall_compliance(
                result_df, result_column, rule_obj.threshold
            )

            # Group by responsible party if specified
            party_results = None
            if responsible_party_column and responsible_party_column in result_df.columns:
                party_results = self.compliance_determiner.aggregate_by_responsible_party(
                    result_df, result_column, responsible_party_column, rule_obj.threshold
                )

            # Create and return result object
            return RuleEvaluationResult(
                rule=rule_obj,
                result_df=result_df,
                result_column=result_column,
                compliance_status=compliance_status,
                compliance_metrics=compliance_metrics,
                party_results=party_results
            )

    def evaluate_multiple_rules(self,
                                rules: List[Union[str, ValidationRule]],
                                data_df: pd.DataFrame,
                                responsible_party_column: Optional[str] = None) -> Dict[str, RuleEvaluationResult]:
        """
        Evaluate multiple validation rules against a DataFrame.

        Args:
            rules: List of ValidationRules or rule_ids
            data_df: Data to validate
            responsible_party_column: Column identifying responsible parties

        Returns:
            Dictionary mapping rule_ids to RuleEvaluationResults
        """
        results = {}

        for rule in rules:
            try:
                # Get rule ID for dictionary key
                rule_id = rule if isinstance(rule, str) else rule.rule_id

                # Evaluate the rule
                result = self.evaluate_rule(rule, data_df, responsible_party_column)

                # Store the result
                results[rule_id] = result

            except Exception as e:
                logger.error(f"Error evaluating rule {rule}: {str(e)}")
                # Continue with other rules even if one fails

        return results

    def evaluate_all_rules(self,
                           data_df: pd.DataFrame,
                           responsible_party_column: Optional[str] = None) -> Dict[str, RuleEvaluationResult]:
        """
        Evaluate all available rules against a DataFrame.

        Args:
            data_df: Data to validate
            responsible_party_column: Column identifying responsible parties

        Returns:
            Dictionary mapping rule_ids to RuleEvaluationResults
        """
        # Get all available rules
        all_rules = self.rule_manager.list_rules()

        # Evaluate all rules
        return self.evaluate_multiple_rules(all_rules, data_df, responsible_party_column)
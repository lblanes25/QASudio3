from typing import Dict, List, Any, Optional, Tuple, Union, Literal
import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Define compliance status types
ComplianceStatus = Literal["GC", "PC", "DNC"]  # Generally Conforms, Partially Conforms, Does Not Conform


class ComplianceDeterminer:
    """
    Determines compliance status (GC/PC/DNC) based on validation rule results.
    Applies thresholds and aggregates results by responsible parties.
    """

    def __init__(self,
                 gc_threshold: float = 0.95,
                 pc_threshold: float = 0.80):
        """
        Initialize with compliance thresholds.

        Args:
            gc_threshold: Minimum compliance rate for Generally Conforms (GC) status
            pc_threshold: Minimum compliance rate for Partially Conforms (PC) status
        """
        # Ensure thresholds are in valid range and properly ordered
        self.gc_threshold = min(1.0, max(0.0, gc_threshold))
        self.pc_threshold = min(self.gc_threshold, max(0.0, pc_threshold))

    def determine_row_compliance(self,
                                 result: Any,
                                 rule_threshold: float = 1.0) -> ComplianceStatus:
        """
        Determine compliance status for a single validation result.

        Args:
            result: Result of validation (usually True/False or numeric)
            rule_threshold: Rule-specific threshold (overrides global thresholds)

        Returns:
            Compliance status (GC, PC, DNC)
        """
        # Handle boolean results directly
        if isinstance(result, bool):
            return "GC" if result else "DNC"

        # Handle numeric results (0.0 to 1.0 scale)
        if isinstance(result, (int, float, np.number)):
            value = float(result)

            # Apply thresholds
            if value >= rule_threshold:
                return "GC"
            elif value >= self.pc_threshold:
                return "PC"
            else:
                return "DNC"

        # Handle Excel error values or other non-compliance indicators
        if isinstance(result, str):
            if result.startswith(("ERROR", "#")):
                return "DNC"
            # Handle string "TRUE"/"FALSE" values
            elif result.upper() == "TRUE":
                return "GC"
            elif result.upper() == "FALSE":
                return "DNC"

        # Default to DNC for unrecognized results
        logger.warning(f"Unrecognized validation result: {result}, defaulting to DNC")
        return "DNC"

    def determine_overall_compliance(self,
                                     result_df: pd.DataFrame,
                                     compliance_column: str,
                                     rule_threshold: float = 1.0) -> Tuple[ComplianceStatus, Dict[str, Any]]:
        """
        Determine overall compliance status for results from a single rule.

        Args:
            result_df: DataFrame with validation results
            compliance_column: Column name containing validation results
            rule_threshold: Rule-specific threshold

        Returns:
            Tuple of (compliance_status, compliance_metrics)
        """
        # Count items for each compliance status
        gc_count = 0
        pc_count = 0
        dnc_count = 0
        error_count = 0
        total_count = len(result_df)

        # Calculate compliance status for each row
        for _, row in result_df.iterrows():
            result = row[compliance_column]

            # Skip nulls/NaNs
            if pd.isna(result):
                total_count -= 1
                continue

            # Count by status
            if isinstance(result, str) and result.startswith("ERROR"):
                error_count += 1
                dnc_count += 1  # Errors count as DNC
            else:
                status = self.determine_row_compliance(result, rule_threshold)
                if status == "GC":
                    gc_count += 1
                elif status == "PC":
                    pc_count += 1
                else:  # DNC
                    dnc_count += 1

        # Prevent division by zero
        if total_count == 0:
            return "DNC", {
                "gc_rate": 0,
                "pc_rate": 0,
                "dnc_rate": 0,
                "gc_count": 0,
                "pc_count": 0,
                "dnc_count": 0,
                "error_count": 0,
                "total_count": 0
            }

        # Calculate compliance rates
        gc_rate = gc_count / total_count
        pc_rate = pc_count / total_count
        dnc_rate = dnc_count / total_count

        # Determine overall compliance
        if gc_rate >= self.gc_threshold:
            overall_status = "GC"
        elif gc_rate + pc_rate >= self.pc_threshold:
            overall_status = "PC"
        else:
            overall_status = "DNC"

        # Compile metrics
        metrics = {
            "gc_rate": gc_rate,
            "pc_rate": pc_rate,
            "dnc_rate": dnc_rate,
            "gc_count": gc_count,
            "pc_count": pc_count,
            "dnc_count": dnc_count,
            "error_count": error_count,
            "total_count": total_count
        }

        return overall_status, metrics

    def aggregate_by_responsible_party(self,
                                       result_df: pd.DataFrame,
                                       compliance_column: str,
                                       responsible_party_column: str,
                                       rule_threshold: float = 1.0) -> Dict[str, Dict[str, Any]]:
        """
        Aggregate compliance results by responsible party.

        Args:
            result_df: DataFrame with validation results
            compliance_column: Column with validation results
            responsible_party_column: Column with responsible party names
            rule_threshold: Rule-specific threshold

        Returns:
            Dictionary mapping responsible parties to their compliance metrics
        """
        # Group by responsible party
        grouped = result_df.groupby(responsible_party_column)
        results = {}

        # Calculate compliance for each group
        for party, group_df in grouped:
            status, metrics = self.determine_overall_compliance(
                group_df, compliance_column, rule_threshold
            )

            results[party] = {
                "status": status,
                "metrics": metrics
            }

        return results
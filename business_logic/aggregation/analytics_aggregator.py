# business_logic/aggregation/analytics_aggregator.py

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union, Set
import logging
import json
import os
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AnalyticsSummary:
    """
    Container for aggregated analytics results with analysis capabilities.
    Stores summary data and provides methods for analysis and reporting.

    Memory-optimized with __slots__ for reduced memory footprint.
    """

    # Define __slots__ to optimize memory usage
    __slots__ = ('leader_summary', 'department_summary', 'rule_details',
                 'config', 'timestamp', '_leader_ranking', 'rule_performance')

    def __init__(
            self,
            leader_summary: pd.DataFrame,
            department_summary: Dict[str, Any],
            rule_details: pd.DataFrame,
            config: Optional[Dict[str, Any]] = None,
            timestamp: Optional[str] = None
    ):
        """
        Initialize analytics summary with aggregated data.

        Args:
            leader_summary: DataFrame with per-leader statistics
            department_summary: Dictionary with overall department metrics
            rule_details: DataFrame with per-rule statistics
            config: Configuration used for aggregation
            timestamp: Timestamp of aggregation
        """
        self.leader_summary = leader_summary
        self.department_summary = department_summary
        self.rule_details = rule_details
        self.config = config or {}
        self.timestamp = timestamp or datetime.now().isoformat()

        # Computed metrics
        self._leader_ranking = None
        self.rule_performance = None

    def get_leader_ranking(self) -> pd.DataFrame:
        """Get leaders ranked by weighted score."""
        if self._leader_ranking is None:
            # Create ranking if not already computed
            if 'weighted_score' in self.leader_summary.columns:
                self._leader_ranking = self.leader_summary.sort_values(
                    by='weighted_score', ascending=False
                ).reset_index(drop=True)
                # Add rank column
                self._leader_ranking['rank'] = self._leader_ranking.index + 1
            else:
                # If no weighted score, sort by compliance rate
                self._leader_ranking = self.leader_summary.sort_values(
                    by='compliance_rate', ascending=False
                ).reset_index(drop=True)
                self._leader_ranking['rank'] = self._leader_ranking.index + 1

        return self._leader_ranking

    def get_rules_by_compliance(self) -> pd.DataFrame:
        """Get rules ranked by compliance rate."""
        return self.rule_details.sort_values(
            by='compliance_rate', ascending=False
        ).reset_index(drop=True)

    def get_leaders_by_rule(self, rule_id: str) -> pd.DataFrame:
        """
        Get leader performance for a specific rule.

        Args:
            rule_id: ID of the rule to analyze

        Returns:
            DataFrame with leader performance for the rule
        """
        # If we don't have rule_performance data, try to compute it from rule_details
        if not hasattr(self, 'rule_performance') or self.rule_performance is None:
            # Check if we have audit_leader in rule_details
            if 'audit_leader' in self.rule_details.columns and 'rule_id' in self.rule_details.columns:
                # Group rule details by rule_id
                self.rule_performance = {}
                for rid, group in self.rule_details.groupby('rule_id'):
                    self.rule_performance[rid] = group
            else:
                logger.warning("Rule performance data not available and cannot be computed")
                return pd.DataFrame()

        if rule_id not in self.rule_performance:
            logger.warning(f"Rule {rule_id} not found in performance data")
            return pd.DataFrame()

        return self.rule_performance[rule_id].sort_values(
            by='compliance_rate', ascending=False
        )

    def export_to_dict(self) -> Dict[str, Any]:
        """Export summary data to a dictionary."""
        return {
            'leader_summary': self.leader_summary.to_dict(orient='records'),
            'department_summary': self.department_summary,
            'rule_details': self.rule_details.to_dict(orient='records'),
            'config': self.config,
            'timestamp': self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalyticsSummary':
        """Create AnalyticsSummary from dictionary data."""
        return cls(
            leader_summary=pd.DataFrame(data['leader_summary']),
            department_summary=data['department_summary'],
            rule_details=pd.DataFrame(data['rule_details']),
            config=data.get('config', {}),
            timestamp=data.get('timestamp')
        )

    def export_to_file(self, file_path: str) -> str:
        """
        Export summary to a file (JSON format).

        Args:
            file_path: Path to save the file

        Returns:
            Path to the saved file
        """
        data = self.export_to_dict()

        # Ensure directory exists
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)

        # Save to file
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)

        return file_path

    @classmethod
    def from_file(cls, file_path: str) -> 'AnalyticsSummary':
        """Load AnalyticsSummary from a file."""
        with open(file_path, 'r') as f:
            data = json.load(f)

        return cls.from_dict(data)


def load_weights_configuration(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load weights configuration from file or use defaults.

    Args:
        config_path: Path to weights configuration file (JSON or YAML)

    Returns:
        Dictionary with weights configuration
    """
    default_weights = {
        # Default weights for rule categories
        'category_weights': {
            'data_quality': 1.0,
            'completeness': 1.0,
            'timeliness': 1.0,
            'accuracy': 1.0,
            'compliance': 1.0,
            'default': 1.0  # Default weight for uncategorized rules
        },
        # Default weights for rule severities
        'severity_weights': {
            'critical': 2.0,
            'high': 1.5,
            'medium': 1.0,
            'low': 0.5,
            'info': 0.1,
            'default': 1.0  # Default weight for unspecified severity
        },
        # Specific rule weights (overrides category and severity)
        'rule_weights': {}
    }

    if not config_path:
        return default_weights

    try:
        # Determine file type and load accordingly
        if config_path.lower().endswith(('.yaml', '.yml')):
            import yaml
            with open(config_path, 'r') as f:
                user_weights = yaml.safe_load(f)
        elif config_path.lower().endswith('.json'):
            with open(config_path, 'r') as f:
                user_weights = json.load(f)
        else:
            logger.warning(f"Unsupported config file format: {config_path}")
            return default_weights

        # Merge with defaults (keeping user values where specified)
        merged_weights = default_weights.copy()

        if 'category_weights' in user_weights:
            merged_weights['category_weights'].update(user_weights['category_weights'])

        if 'severity_weights' in user_weights:
            merged_weights['severity_weights'].update(user_weights['severity_weights'])

        if 'rule_weights' in user_weights:
            merged_weights['rule_weights'].update(user_weights['rule_weights'])

        return merged_weights

    except Exception as e:
        logger.error(f"Error loading weights configuration: {str(e)}")
        return default_weights


def standardize_result_format(result_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Standardize validation result dictionary format for consistent processing.

    Args:
        result_dict: Raw validation result dictionary

    Returns:
        Standardized result dictionary
    """
    standardized = {
        'analytic_id': None,
        'status': None,
        'timestamp': None,
        'rule_results': {},
        'summary': {},
        'grouped_summary': {}
    }

    # Copy original values that are present
    for key in standardized.keys():
        if key in result_dict:
            standardized[key] = result_dict[key]

    # Ensure timestamp is a string
    if standardized['timestamp'] is None:
        standardized['timestamp'] = datetime.now().isoformat()
    elif not isinstance(standardized['timestamp'], str):
        standardized['timestamp'] = str(standardized['timestamp'])

    # Ensure analytic_id is set
    if standardized['analytic_id'] is None and 'id' in result_dict:
        standardized['analytic_id'] = result_dict['id']

    # If there's no rule_results but there are results in a different format,
    # attempt to normalize them
    if not standardized['rule_results'] and 'results' in result_dict:
        results = result_dict['results']

        # Handle list of rule results
        if isinstance(results, list):
            for rule_result in results:
                if 'rule_id' in rule_result:
                    standardized['rule_results'][rule_result['rule_id']] = rule_result

        # Handle dictionary with rule_id as keys
        elif isinstance(results, dict):
            standardized['rule_results'] = results

    return standardized


def aggregate_by_audit_leader(result_dicts: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Aggregate validation results by audit leader (responsible party).

    Args:
        result_dicts: List of validation result dictionaries

    Returns:
        DataFrame with aggregated results by audit leader
    """
    # First standardize all result dictionaries
    std_results = [standardize_result_format(result) for result in result_dicts]

    # Extract leader-level statistics from all result dictionaries
    all_leader_stats = []

    for result in std_results:
        analytic_id = result.get('analytic_id', 'unknown')
        timestamp = result.get('timestamp', datetime.now().isoformat())

        # Process grouped summary if available
        if 'grouped_summary' in result and result['grouped_summary']:
            for leader, stats in result['grouped_summary'].items():
                # Create a record for this leader
                leader_record = {
                    'audit_leader': leader,
                    'analytic_id': analytic_id,
                    'timestamp': timestamp,
                    'total_rules': stats.get('total_rules', 0),
                    'gc_count': stats.get('GC', 0),
                    'pc_count': stats.get('PC', 0),
                    'dnc_count': stats.get('DNC', 0),
                    'compliance_rate': stats.get('compliance_rate', 0.0)
                }

                all_leader_stats.append(leader_record)

    # Create DataFrame from collected statistics
    if not all_leader_stats:
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=[
            'audit_leader', 'analytic_id', 'timestamp',
            'total_rules', 'gc_count', 'pc_count', 'dnc_count', 'compliance_rate'
        ])

    leader_df = pd.DataFrame(all_leader_stats)

    # Calculate aggregated statistics by leader across all analytics
    aggregated_df = leader_df.groupby('audit_leader').agg({
        'total_rules': 'sum',
        'gc_count': 'sum',
        'pc_count': 'sum',
        'dnc_count': 'sum',
        # We'll recalculate compliance rate based on total counts
    }).reset_index()

    # Calculate aggregated compliance rate
    aggregated_df['compliance_rate'] = (
            aggregated_df['gc_count'] /
            aggregated_df['total_rules'].clip(lower=1)  # Avoid division by zero
    )

    # Sort by compliance rate descending
    aggregated_df = aggregated_df.sort_values(
        by='compliance_rate', ascending=False
    ).reset_index(drop=True)

    return aggregated_df


def calculate_weighted_scores(
        summary_df: pd.DataFrame,
        weights_config: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """
    Calculate weighted scores for audit leaders based on rule importance.

    Args:
        summary_df: DataFrame with aggregated results by audit leader
        weights_config: Configuration for weighting rules

    Returns:
        DataFrame with added weighted scores
    """
    # If no weights provided, use defaults
    if weights_config is None:
        weights_config = load_weights_configuration()

    # Create a copy to avoid modifying the original
    result_df = summary_df.copy()

    # Simple weighting model based on 5-point scale
    # Map compliance rate ranges to scores
    def map_to_score(compliance_rate):
        if compliance_rate >= 0.95:
            return 5.0
        elif compliance_rate >= 0.90:
            return 4.5
        elif compliance_rate >= 0.85:
            return 4.0
        elif compliance_rate >= 0.80:
            return 3.5
        elif compliance_rate >= 0.75:
            return 3.0
        elif compliance_rate >= 0.70:
            return 2.5
        elif compliance_rate >= 0.60:
            return 2.0
        elif compliance_rate >= 0.50:
            return 1.5
        else:
            return 1.0

    # Apply scoring function
    result_df['weighted_score'] = result_df['compliance_rate'].apply(map_to_score)

    # Map scores to ratings
    rating_map = {
        5.0: "Exemplary",
        4.5: "Strong",
        4.0: "Satisfactory",
        3.5: "Adequate",
        3.0: "Fair",
        2.5: "Needs Improvement",
        2.0: "Unsatisfactory",
        1.5: "Deficient",
        1.0: "Critical Concerns"
    }

    # Add rating column
    result_df['rating'] = result_df['weighted_score'].map(rating_map)

    # Add columns for manual override
    result_df['override_score'] = np.nan
    result_df['override_rating'] = ""
    result_df['comments'] = ""

    return result_df


def generate_comparative_summary(summary_df: pd.DataFrame) -> pd.DataFrame:
    """
    Generate comparative summary with performance relative to department average.

    Args:
        summary_df: DataFrame with audit leader statistics

    Returns:
        DataFrame with added comparative metrics
    """
    # Create a copy to avoid modifying the original
    result_df = summary_df.copy()

    # Calculate department averages for key metrics
    dept_avg_compliance = result_df['compliance_rate'].mean()

    if 'weighted_score' in result_df.columns:
        dept_avg_score = result_df['weighted_score'].mean()
    else:
        dept_avg_score = None

    # Calculate deviation from average for each leader
    result_df['compliance_vs_avg'] = result_df['compliance_rate'] - dept_avg_compliance

    if dept_avg_score is not None:
        result_df['score_vs_avg'] = result_df['weighted_score'] - dept_avg_score

    # Calculate percentile ranking
    result_df['compliance_percentile'] = result_df['compliance_rate'].rank(pct=True) * 100

    if 'weighted_score' in result_df.columns:
        result_df['score_percentile'] = result_df['weighted_score'].rank(pct=True) * 100

    # Add department summary as metadata in dataframe attributes
    result_df.attrs['dept_avg_compliance'] = dept_avg_compliance

    if dept_avg_score is not None:
        result_df.attrs['dept_avg_score'] = dept_avg_score

    # Add column for year-over-year change (placeholder for now)
    result_df['yoy_change'] = np.nan

    # TODO: Implement time-based trend analysis when historical data is available
    # This would track performance over multiple reporting periods
    result_df['trend'] = 'stable'  # Default placeholder

    return result_df


def tag_outliers_and_exceptions(
        summary_df: pd.DataFrame,
        threshold_config: Optional[Dict[str, Any]] = None
) -> pd.DataFrame:
    """
    Identify and tag outliers and exceptions in the audit leader summary.

    Args:
        summary_df: DataFrame with audit leader statistics
        threshold_config: Configuration for outlier thresholds

    Returns:
        DataFrame with added outlier flags and tags
    """
    # Set default thresholds if not provided
    if threshold_config is None:
        threshold_config = {
            'high_performer_threshold': 0.95,  # 95% compliance
            'concern_threshold': 0.75,  # 75% compliance
            'critical_threshold': 0.60,  # 60% compliance
            'z_score_threshold': 1.5  # Z-score for statistical outliers
        }

    # Create a copy to avoid modifying the original
    result_df = summary_df.copy()

    # Add outlier flags based on absolute thresholds
    result_df['is_high_performer'] = result_df['compliance_rate'] >= threshold_config['high_performer_threshold']
    result_df['is_concern'] = result_df['compliance_rate'] <= threshold_config['concern_threshold']
    result_df['is_critical'] = result_df['compliance_rate'] <= threshold_config['critical_threshold']

    # Add statistical outlier detection using Z-scores
    if len(result_df) >= 4:  # Need enough data for meaningful z-scores
        # Calculate z-scores for compliance rate
        compliance_mean = result_df['compliance_rate'].mean()
        compliance_std = result_df['compliance_rate'].std()

        if compliance_std > 0:  # Avoid division by zero
            result_df['compliance_z_score'] = (result_df['compliance_rate'] - compliance_mean) / compliance_std

            # Flag statistical outliers
            z_threshold = threshold_config['z_score_threshold']
            result_df['is_statistical_outlier'] = abs(result_df['compliance_z_score']) > z_threshold

            # High statistical performers
            result_df['is_statistical_high'] = result_df['compliance_z_score'] > z_threshold

            # Low statistical performers
            result_df['is_statistical_low'] = result_df['compliance_z_score'] < -z_threshold

    # TODO: Add trend analysis for time-based comparisons
    # Would compare current performance to historical benchmarks

    # Create overall tag for each leader
    def determine_tag(row):
        if row.get('is_high_performer', False):
            return "High Performer"
        elif row.get('is_critical', False):
            return "Critical Concern"
        elif row.get('is_concern', False):
            return "Needs Attention"
        elif row.get('is_statistical_high', False):
            return "Above Average"
        elif row.get('is_statistical_low', False):
            return "Below Average"
        else:
            return "Average"

    result_df['performance_tag'] = result_df.apply(determine_tag, axis=1)

    return result_df


def extract_rule_details_summary(std_results: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Extract and aggregate rule-level details from standardized results.
    Includes audit_leader in output to support leader-level drilldowns per rule.

    Args:
        std_results: List of standardized result dictionaries

    Returns:
        DataFrame with rule-level details including audit_leader
    """
    rule_records = []

    # Optimize for memory by pre-defining the columns we'll use
    # This helps especially with large datasets
    rule_record_columns = [
        'rule_id', 'analytic_id', 'rule_name', 'compliance_status',
        'compliance_rate', 'total_items', 'gc_count', 'pc_count',
        'dnc_count', 'audit_leader', 'category', 'severity'
    ]

    for result in std_results:
        analytic_id = result.get('analytic_id', 'unknown')

        # Process rule_results if available
        if 'rule_results' in result and result['rule_results']:
            # Get all audit leaders from grouped_summary for cross-referencing
            audit_leaders = []
            if 'grouped_summary' in result and result['grouped_summary']:
                audit_leaders = list(result['grouped_summary'].keys())

            for rule_id, rule_result in result['rule_results'].items():
                # Extract base fields, filtering to only needed columns
                rule_record = {
                    'rule_id': rule_id,
                    'analytic_id': analytic_id,
                    'rule_name': rule_result.get('rule_name', rule_id),
                    'compliance_status': rule_result.get('compliance_status', 'Unknown'),
                    'compliance_rate': rule_result.get('compliance_rate', 0.0),
                    'total_items': rule_result.get('total_items', 0),
                    'gc_count': rule_result.get('gc_count', 0),
                    'pc_count': rule_result.get('pc_count', 0),
                    'dnc_count': rule_result.get('dnc_count', 0)
                }

                # Add category and severity if available
                if 'category' in rule_result:
                    rule_record['category'] = rule_result['category']

                if 'severity' in rule_result:
                    rule_record['severity'] = rule_result['severity']

                # If we have party results, add a record for each leader
                if 'party_results' in rule_result and rule_result['party_results']:
                    for leader, party_data in rule_result['party_results'].items():
                        leader_record = rule_record.copy()
                        leader_record['audit_leader'] = leader

                        # Add leader-specific metrics if available
                        if isinstance(party_data, dict):
                            if 'metrics' in party_data:
                                metrics = party_data['metrics']
                                leader_record['total_items'] = metrics.get('total_count', 0)
                                leader_record['gc_count'] = metrics.get('gc_count', 0)
                                leader_record['pc_count'] = metrics.get('pc_count', 0)
                                leader_record['dnc_count'] = metrics.get('dnc_count', 0)

                                # Recalculate compliance rate for this leader
                                if leader_record['total_items'] > 0:
                                    leader_record['compliance_rate'] = (
                                            leader_record['gc_count'] / leader_record['total_items']
                                    )

                            if 'status' in party_data:
                                leader_record['compliance_status'] = party_data['status']

                        rule_records.append(leader_record)
                else:
                    # No party-specific data, add overall rule record for each known leader
                    for leader in audit_leaders:
                        leader_record = rule_record.copy()
                        leader_record['audit_leader'] = leader
                        rule_records.append(leader_record)

                    # Also add a record without a specific leader for overall stats
                    rule_records.append(rule_record)

    # Create DataFrame from collected records
    if not rule_records:
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=rule_record_columns)

    # Convert to DataFrame, selecting only the columns we need
    rule_df = pd.DataFrame(rule_records)

    # For rules that appear in multiple analytics, aggregate their results
    # First handle rules with audit leaders
    leader_rule_df = rule_df[rule_df['audit_leader'].notna()]

    if not leader_rule_df.empty:
        aggregated_leader_rule_df = leader_rule_df.groupby(['rule_id', 'rule_name', 'audit_leader']).agg({
            'total_items': 'sum',
            'gc_count': 'sum',
            'pc_count': 'sum',
            'dnc_count': 'sum',
            'category': 'first',  # Take first non-null value
            'severity': 'first'  # Take first non-null value
        }).reset_index()

        # Recalculate compliance rate
        aggregated_leader_rule_df['compliance_rate'] = (
                aggregated_leader_rule_df['gc_count'] /
                aggregated_leader_rule_df['total_items'].clip(lower=1)  # Avoid division by zero
        )

        # Determine compliance status
        def determine_status(row):
            rate = row['compliance_rate']
            if rate >= 0.95:
                return "GC"
            elif rate >= 0.80:
                return "PC"
            else:
                return "DNC"

        aggregated_leader_rule_df['compliance_status'] = aggregated_leader_rule_df.apply(determine_status, axis=1)
    else:
        # Create empty DataFrame with right structure
        aggregated_leader_rule_df = pd.DataFrame(columns=rule_record_columns)

    # Also aggregate rules without audit leader for overall metrics
    overall_rule_df = rule_df[rule_df['audit_leader'].isna()]

    if not overall_rule_df.empty:
        aggregated_overall_rule_df = overall_rule_df.groupby(['rule_id', 'rule_name']).agg({
            'total_items': 'sum',
            'gc_count': 'sum',
            'pc_count': 'sum',
            'dnc_count': 'sum',
            'category': 'first',
            'severity': 'first'
        }).reset_index()

        # Recalculate compliance rate
        aggregated_overall_rule_df['compliance_rate'] = (
                aggregated_overall_rule_df['gc_count'] /
                aggregated_overall_rule_df['total_items'].clip(lower=1)
        )

        # Determine compliance status
        aggregated_overall_rule_df['compliance_status'] = aggregated_overall_rule_df.apply(determine_status, axis=1)

        # Set audit_leader to None for these records
        aggregated_overall_rule_df['audit_leader'] = None
    else:
        # Create empty DataFrame with right structure
        aggregated_overall_rule_df = pd.DataFrame(columns=rule_record_columns)

    # Combine leader-specific and overall metrics
    if not aggregated_leader_rule_df.empty and not aggregated_overall_rule_df.empty:
        aggregated_rule_df = pd.concat([aggregated_leader_rule_df, aggregated_overall_rule_df])
    elif not aggregated_leader_rule_df.empty:
        aggregated_rule_df = aggregated_leader_rule_df
    elif not aggregated_overall_rule_df.empty:
        aggregated_rule_df = aggregated_overall_rule_df
    else:
        # No data to aggregate
        return pd.DataFrame(columns=rule_record_columns)

    # Sort by compliance rate descending
    aggregated_rule_df = aggregated_rule_df.sort_values(
        by=['rule_id', 'compliance_rate'], ascending=[True, False]
    ).reset_index(drop=True)

    return aggregated_rule_df


def create_summary_report(summary: AnalyticsSummary) -> Dict[str, Any]:
    """
    Create a structured report from an analytics summary.

    Args:
        summary: AnalyticsSummary object with aggregated data

    Returns:
        Dictionary with report structure
    """
    # Get leader ranking
    leader_ranking = summary.get_leader_ranking()

    # Create department overview
    department_overview = {
        'timestamp': summary.timestamp,
        'total_leaders': len(leader_ranking),
        'total_rules': summary.department_summary.get('total_rules', 0),
        'overall_compliance_rate': summary.department_summary.get('overall_compliance_rate', 0),
        'high_performers': sum(leader_ranking.get('is_high_performer', [False])),
        'concerns': sum(leader_ranking.get('is_concern', [False])),
        'critical_concerns': sum(leader_ranking.get('is_critical', [False]))
    }

    # Create top/bottom performers lists
    top_performers = leader_ranking.head(3).to_dict(orient='records') if len(leader_ranking) > 0 else []
    bottom_performers = leader_ranking.tail(3).to_dict(orient='records') if len(leader_ranking) > 0 else []

    # Combine into report structure
    report = {
        'department_overview': department_overview,
        'top_performers': top_performers,
        'bottom_performers': bottom_performers,
        'all_leaders': leader_ranking.to_dict(orient='records'),
        'rule_details': summary.rule_details.to_dict(orient='records')
    }

    return report


def aggregate_analytics_results(
        result_dicts: List[Dict[str, Any]],
        weights_config: Optional[Dict[str, Any]] = None,
        threshold_config: Optional[Dict[str, Any]] = None
) -> AnalyticsSummary:
    """
    Main function to aggregate analytics results into a comprehensive summary.

    Args:
        result_dicts: List of validation result dictionaries
        weights_config: Configuration for rule weights
        threshold_config: Configuration for outlier thresholds

    Returns:
        AnalyticsSummary object with aggregated data
    """
    # Standardize all result dictionaries
    std_results = [standardize_result_format(result) for result in result_dicts]

    # Aggregate results by audit leader
    leader_summary = aggregate_by_audit_leader(std_results)

    # Calculate weighted scores
    leader_summary = calculate_weighted_scores(leader_summary, weights_config)

    # Generate comparative summary
    leader_summary = generate_comparative_summary(leader_summary)

    # Tag outliers and exceptions
    leader_summary = tag_outliers_and_exceptions(leader_summary, threshold_config)

    # Extract rule-level details with audit leader information
    rule_details = extract_rule_details_summary(std_results)

    # Extract department-level summary
    department_summary = {
        'total_rules': leader_summary['total_rules'].sum(),
        'gc_count': leader_summary['gc_count'].sum(),
        'pc_count': leader_summary['pc_count'].sum(),
        'dnc_count': leader_summary['dnc_count'].sum(),
        'overall_compliance_rate':
            leader_summary['gc_count'].sum() / leader_summary['total_rules'].sum()
            if leader_summary['total_rules'].sum() > 0 else 0,
        'avg_compliance_rate': leader_summary['compliance_rate'].mean(),
        'avg_weighted_score': leader_summary['weighted_score'].mean()
        if 'weighted_score' in leader_summary.columns else None
    }

    # Create and return AnalyticsSummary object
    return AnalyticsSummary(
        leader_summary=leader_summary,
        department_summary=department_summary,
        rule_details=rule_details,
        config={
            'weights': weights_config,
            'thresholds': threshold_config
        },
        timestamp=datetime.now().isoformat()
    )


# Unit test harness function for validation
def test_analytics_aggregation():
    """
    Basic end-to-end test harness for analytics aggregation.
    Validates the flow from result dictionaries to AnalyticsSummary.

    Returns:
        True if tests pass, raises AssertionError otherwise
    """
    # Create test data - two sample result dictionaries
    result1 = {
        'analytic_id': 'test_analytic_1',
        'status': 'PARTIALLY_COMPLIANT',
        'timestamp': '2023-01-01T00:00:00',
        'grouped_summary': {
            'Leader1': {
                'total_rules': 3,
                'GC': 2,
                'PC': 1,
                'DNC': 0,
                'compliance_rate': 0.67
            },
            'Leader2': {
                'total_rules': 3,
                'GC': 1,
                'PC': 1,
                'DNC': 1,
                'compliance_rate': 0.33
            }
        },
        'rule_results': {
            'rule1': {
                'rule_id': 'rule1',
                'rule_name': 'Test Rule 1',
                'compliance_status': 'GC',
                'compliance_rate': 0.9,
                'total_items': 10,
                'gc_count': 9,
                'pc_count': 1,
                'dnc_count': 0,
                'party_results': {
                    'Leader1': {
                        'status': 'GC',
                        'metrics': {
                            'total_count': 5,
                            'gc_count': 5,
                            'pc_count': 0,
                            'dnc_count': 0
                        }
                    },
                    'Leader2': {
                        'status': 'GC',
                        'metrics': {
                            'total_count': 5,
                            'gc_count': 4,
                            'pc_count': 1,
                            'dnc_count': 0
                        }
                    }
                }
            }
        }
    }

    result2 = {
        'analytic_id': 'test_analytic_2',
        'status': 'FULLY_COMPLIANT',
        'timestamp': '2023-01-02T00:00:00',
        'grouped_summary': {
            'Leader1': {
                'total_rules': 2,
                'GC': 2,
                'PC': 0,
                'DNC': 0,
                'compliance_rate': 1.0
            },
            'Leader2': {
                'total_rules': 2,
                'GC': 1,
                'PC': 1,
                'DNC': 0,
                'compliance_rate': 0.5
            },
            'Leader3': {
                'total_rules': 2,
                'GC': 0,
                'PC': 1,
                'DNC': 1,
                'compliance_rate': 0.0
            }
        }
    }

    # Perform aggregation
    summary = aggregate_analytics_results([result1, result2])

    # Verify summary data structure
    assert isinstance(summary, AnalyticsSummary), "Result should be AnalyticsSummary instance"

    # Verify leader summary
    assert len(summary.leader_summary) == 3, "Should have 3 leaders"
    assert 'audit_leader' in summary.leader_summary.columns, "Should have audit_leader column"
    assert 'weighted_score' in summary.leader_summary.columns, "Should have weighted_score column"

    # Verify highest performer
    leader_ranking = summary.get_leader_ranking()
    assert leader_ranking.iloc[0]['audit_leader'] == 'Leader1', "Leader1 should be highest performer"

    # Verify rule details
    assert len(summary.rule_details) > 0, "Should have rule details"

    # Verify export functionality
    export_dict = summary.export_to_dict()
    assert 'leader_summary' in export_dict, "Export dict should contain leader_summary"

    # Test with a temp file
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tmp:
        try:
            # Export to file
            file_path = summary.export_to_file(tmp.name)

            # Reload from file
            reloaded = AnalyticsSummary.from_file(file_path)

            # Verify reloaded data
            assert len(reloaded.leader_summary) == len(summary.leader_summary), "Reloaded data should match original"
        finally:
            # Clean up temp file
            if os.path.exists(tmp.name):
                os.unlink(tmp.name)

    return True


# If this module is run directly, execute the test
if __name__ == "__main__":
    print("Running analytics aggregation test...")
    success = test_analytics_aggregation()
    print(f"Test {'passed' if success else 'failed'}")
# services/data_validator.py

"""Enhanced data validation functionality."""

import logging
from typing import Dict, List, Any, Optional, Tuple, Union
import pandas as pd
from collections import defaultdict

from data_integration.io.data_validator import DataValidator as BaseDataValidator
from services.validation_constants import (
    VALIDATION_MESSAGES, DEFAULT_ENTITY_ID_COLUMN,
    COMPLIANCE_STATUSES, IAG_SCORING_WEIGHTS
)

logger = logging.getLogger(__name__)


class EnhancedDataValidator(BaseDataValidator):
    """Enhanced data validator with additional validation and statistics calculation."""
    
    def __init__(self):
        """Initialize the enhanced validator."""
        super().__init__()
        
    def validate_schema(self, df: pd.DataFrame, expected_schema: Union[List[str], str],
                       strict: bool = False) -> Tuple[bool, List[str]]:
        """
        Validate DataFrame schema against expected columns.
        
        Args:
            df: DataFrame to validate
            expected_schema: List of expected columns or path to schema file
            strict: If True, DataFrame must have exactly the expected columns
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Load schema if it's a file path
        if isinstance(expected_schema, str):
            try:
                # Assume it's a simple text file with one column name per line
                with open(expected_schema, 'r') as f:
                    expected_columns = [line.strip() for line in f if line.strip()]
            except Exception as e:
                errors.append(f"Failed to load schema file: {str(e)}")
                return False, errors
        else:
            expected_columns = expected_schema
        
        # Get actual columns
        actual_columns = list(df.columns)
        
        # Check for missing columns
        missing_columns = set(expected_columns) - set(actual_columns)
        if missing_columns:
            errors.append(f"Missing required columns: {sorted(missing_columns)}")
        
        # Check for extra columns if strict mode
        if strict:
            extra_columns = set(actual_columns) - set(expected_columns)
            if extra_columns:
                errors.append(f"Unexpected columns found: {sorted(extra_columns)}")
        
        return len(errors) == 0, errors
    
    def calculate_compliance_statistics(self, evaluation_results: List[Dict[str, Any]],
                                      responsible_party_column: Optional[str] = None) -> Dict[str, Any]:
        """
        Calculate compliance statistics from evaluation results.
        
        Args:
            evaluation_results: List of evaluation results from rules
            responsible_party_column: Column name for responsible party grouping
            
        Returns:
            Dictionary with compliance statistics
        """
        # Initialize counters
        total_evaluations = 0
        compliance_counts = defaultdict(int)
        leader_stats = defaultdict(lambda: defaultdict(int))
        rule_stats = defaultdict(lambda: defaultdict(int))
        
        # Process each evaluation result
        for result in evaluation_results:
            rule_id = result.get('rule_id', 'Unknown')
            
            # Process items in the result
            for item in result.get('items', []):
                total_evaluations += 1
                status = item.get('compliance_status', 'NA')
                if status is None:
                    status = 'NA'
                compliance_counts[status] += 1
                
                # Track by leader if column specified
                if responsible_party_column and responsible_party_column in item:
                    leader = item[responsible_party_column]
                    if leader is not None:
                        leader_stats[leader][status] += 1
                
                # Track by rule
                rule_stats[rule_id][status] += 1
        
        # Calculate overall compliance rate
        compliant_count = compliance_counts.get('GC', 0)
        non_compliant_count = sum(compliance_counts.get(status, 0) 
                                 for status in ['PC', 'DNC'])
        total_applicable = compliant_count + non_compliant_count
        
        compliance_rate = 0.0
        if total_applicable > 0:
            compliance_rate = (compliant_count / total_applicable) * 100
        
        # Calculate IAG score
        iag_score = self._calculate_iag_score(compliance_counts)
        
        return {
            'total_evaluations': total_evaluations,
            'compliance_counts': dict(compliance_counts),
            'compliance_rate': compliance_rate,
            'iag_score': iag_score,
            'leader_statistics': dict(leader_stats),
            'rule_statistics': dict(rule_stats)
        }
    
    def process_grouped_results(self, grouped_results: Dict[str, List[Any]],
                              entity_id_column: str = DEFAULT_ENTITY_ID_COLUMN) -> Dict[str, Any]:
        """
        Process results grouped by entity.
        
        Args:
            grouped_results: Results grouped by entity ID
            entity_id_column: Name of the entity ID column
            
        Returns:
            Processed results with entity-level summaries
        """
        entity_summaries = {}
        
        for entity_id, entity_results in grouped_results.items():
            # Calculate entity-level statistics
            entity_compliance = defaultdict(int)
            total_rules = len(entity_results)
            
            for result in entity_results:
                status = result.get('compliance_status', 'NA')
                entity_compliance[status] += 1
            
            # Calculate entity compliance rate
            compliant = entity_compliance.get('GC', 0)
            total_applicable = sum(entity_compliance.get(s, 0) 
                                 for s in ['GC', 'PC', 'DNC'])
            
            compliance_rate = 0.0
            if total_applicable > 0:
                compliance_rate = (compliant / total_applicable) * 100
            
            entity_summaries[entity_id] = {
                'total_rules': total_rules,
                'compliance_counts': dict(entity_compliance),
                'compliance_rate': compliance_rate,
                'details': entity_results
            }
        
        return entity_summaries
    
    def validate_pre_conditions(self, df: pd.DataFrame, 
                              pre_validation_rules: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Validate pre-conditions before main validation.
        
        Args:
            df: DataFrame to validate
            pre_validation_rules: Dictionary of pre-validation rules
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        # Check required columns
        if 'required_columns' in pre_validation_rules:
            missing = set(pre_validation_rules['required_columns']) - set(df.columns)
            if missing:
                errors.append(f"Missing required columns: {sorted(missing)}")
        
        # Check minimum rows
        if 'min_rows' in pre_validation_rules:
            if len(df) < pre_validation_rules['min_rows']:
                errors.append(f"Insufficient data: {len(df)} rows, "
                            f"minimum {pre_validation_rules['min_rows']} required")
        
        # Check data types
        if 'column_types' in pre_validation_rules:
            for col, expected_type in pre_validation_rules['column_types'].items():
                if col in df.columns:
                    actual_type = str(df[col].dtype)
                    if not self._check_type_compatibility(actual_type, expected_type):
                        errors.append(f"Column '{col}' has type '{actual_type}', "
                                    f"expected '{expected_type}'")
        
        # Check value constraints
        if 'value_constraints' in pre_validation_rules:
            for col, constraints in pre_validation_rules['value_constraints'].items():
                if col in df.columns:
                    col_errors = self._check_value_constraints(df[col], constraints, col)
                    errors.extend(col_errors)
        
        return len(errors) == 0, errors
    
    def aggregate_validation_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Aggregate multiple validation results into summary.
        
        Args:
            results: List of validation results
            
        Returns:
            Aggregated summary
        """
        # Initialize aggregated data
        total_rules = len(results)
        total_items = 0
        compliance_counts = defaultdict(int)
        failed_rules = []
        errors = []
        
        # Aggregate from each result
        for result in results:
            # Count items
            items = result.get('items', [])
            total_items += len(items)
            
            # Aggregate compliance counts
            for item in items:
                status = item.get('compliance_status', 'NA')
                compliance_counts[status] += 1
            
            # Track failed rules
            if result.get('status') == 'FAILED':
                failed_rules.append({
                    'rule_id': result.get('rule_id'),
                    'error': result.get('error')
                })
            
            # Collect errors
            if 'error' in result:
                errors.append(result['error'])
        
        # Calculate summary statistics
        compliant = compliance_counts.get('GC', 0)
        total_applicable = sum(compliance_counts.get(s, 0) 
                             for s in ['GC', 'PC', 'DNC'])
        
        compliance_rate = 0.0
        if total_applicable > 0:
            compliance_rate = (compliant / total_applicable) * 100
        
        return {
            'total_rules': total_rules,
            'total_items': total_items,
            'compliance_counts': dict(compliance_counts),
            'compliance_rate': compliance_rate,
            'failed_rules': failed_rules,
            'errors': errors
        }
    
    # Private helper methods
    
    def _calculate_iag_score(self, compliance_counts: Dict[str, int]) -> float:
        """Calculate IAG score from compliance counts."""
        total_weighted = 0
        total_items = 0
        
        for status, count in compliance_counts.items():
            if status in IAG_SCORING_WEIGHTS and count is not None:
                total_weighted += count * IAG_SCORING_WEIGHTS[status]
                total_items += count
        
        if total_items == 0:
            return 0.0
        
        # Maximum possible score
        max_score = total_items * IAG_SCORING_WEIGHTS['GC']
        
        return (total_weighted / max_score) * 100
    
    def _check_type_compatibility(self, actual_type: str, expected_type: str) -> bool:
        """Check if actual type is compatible with expected type."""
        type_mappings = {
            'numeric': ['int64', 'float64', 'int32', 'float32'],
            'string': ['object', 'string'],
            'datetime': ['datetime64[ns]', 'datetime64'],
            'boolean': ['bool']
        }
        
        if expected_type in type_mappings:
            return actual_type in type_mappings[expected_type]
        
        return actual_type == expected_type
    
    def _check_value_constraints(self, series: pd.Series, constraints: Dict[str, Any],
                               column_name: str) -> List[str]:
        """Check value constraints on a series."""
        errors = []
        
        # Check for nulls
        if constraints.get('not_null', False):
            null_count = series.isna().sum()
            if null_count > 0:
                errors.append(f"Column '{column_name}' has {null_count} null values")
        
        # Check allowed values
        if 'allowed_values' in constraints:
            invalid = ~series.isin(constraints['allowed_values'])
            invalid_count = invalid.sum()
            if invalid_count > 0:
                errors.append(f"Column '{column_name}' has {invalid_count} invalid values")
        
        # Check numeric ranges
        if 'min_value' in constraints:
            below_min = series < constraints['min_value']
            count = below_min.sum()
            if count > 0:
                errors.append(f"Column '{column_name}' has {count} values below minimum")
        
        if 'max_value' in constraints:
            above_max = series > constraints['max_value']
            count = above_max.sum()
            if count > 0:
                errors.append(f"Column '{column_name}' has {count} values above maximum")
        
        return errors
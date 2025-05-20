# data_integration/io/data_validator.py

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple, Union, Callable
import logging
import re

logger = logging.getLogger(__name__)


class DataValidationError(Exception):
    """Custom exception for data validation errors"""

    def __init__(self, message: str, validation_results: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.validation_results = validation_results or {}


class DataValidator:
    """
    Validates DataFrame data based on configurable rules.
    Provides data quality checks and validation reporting.
    """

    def __init__(self):
        """Initialize the data validator"""
        # Define standard validation functions
        self.validation_functions = {
            'not_null': self._validate_not_null,
            'unique': self._validate_unique,
            'min_value': self._validate_min_value,
            'max_value': self._validate_max_value,
            'in_set': self._validate_in_set,
            'regex': self._validate_regex,
            'date_format': self._validate_date_format,
            'column_exists': self._validate_column_exists,
            'row_count': self._validate_row_count,
            'column_count': self._validate_column_count,
            'type': self._validate_type,
            'custom': self._validate_custom
        }

    def validate(self,
                 df: pd.DataFrame,
                 validation_rules: Dict[str, Any],
                 raise_exception: bool = False,
                 treat_warnings_as_errors: bool = False) -> Dict[str, Any]:
        """
        Validate a DataFrame against a set of rules.

        Args:
            df: DataFrame to validate
            validation_rules: Dictionary of validation rules
            raise_exception: Whether to raise an exception on validation failure
            treat_warnings_as_errors: Whether to consider warnings as failures for overall validity

        Returns:
            Dictionary with validation results
        """
        results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'details': {}
        }

        # Track the overall validation status
        is_valid = True

        # Process each validation rule
        for rule_name, rule_config in validation_rules.items():
            # Get rule parameters
            rule_type = rule_config.get('type')
            columns = rule_config.get('columns', [])
            severity = rule_config.get('severity', 'error')
            params = rule_config.get('params', {})
            message = rule_config.get('message', f"Validation rule '{rule_name}' failed")

            # Ensure columns is a list
            if isinstance(columns, str):
                columns = [columns]

            # Skip if rule type is not supported
            if rule_type not in self.validation_functions:
                results['warnings'].append(f"Unsupported validation rule type: {rule_type}")
                continue

            # Execute validation function
            try:
                rule_result = self.validation_functions[rule_type](df, columns, params)

                # Add detailed results
                results['details'][rule_name] = rule_result

                # If the rule failed and is an error, mark the overall validation as failed
                if not rule_result['valid'] and severity == 'error':
                    is_valid = False
                    results['errors'].append({
                        'rule': rule_name,
                        'message': message,
                        'details': rule_result
                    })
                # If the rule failed but is a warning, add to warnings list
                elif not rule_result['valid'] and severity == 'warning':
                    # If treating warnings as errors, mark the overall validation as failed
                    if treat_warnings_as_errors:
                        is_valid = False

                    results['warnings'].append({
                        'rule': rule_name,
                        'message': message,
                        'details': rule_result
                    })
            except Exception as e:
                logger.error(f"Error executing validation rule '{rule_name}': {str(e)}")
                is_valid = False
                results['errors'].append({
                    'rule': rule_name,
                    'message': f"Error executing validation rule: {str(e)}",
                    'exception': str(e)
                })

        # Set overall validation result
        results['valid'] = is_valid

        # Raise exception if requested and validation failed
        if raise_exception and not is_valid:
            error_messages = [e['message'] for e in results['errors']]
            raise DataValidationError(
                f"Data validation failed: {'; '.join(error_messages)}",
                results
            )

        return results

    def generate_report(self, validation_results: Dict[str, Any], format: str = 'text') -> str:
        """
        Generate a human-readable report from validation results.

        Args:
            validation_results: Results from validate() method
            format: Report format ('text', 'html', 'markdown')

        Returns:
            Formatted validation report
        """
        if format == 'text':
            return self._generate_text_report(validation_results)
        elif format == 'html':
            return self._generate_html_report(validation_results)
        elif format == 'markdown':
            return self._generate_markdown_report(validation_results)
        else:
            raise ValueError(f"Unsupported report format: {format}")

    def _generate_text_report(self, results: Dict[str, Any]) -> str:
        """Generate a plain text validation report"""
        lines = []
        lines.append("=== Data Validation Report ===")
        lines.append(f"Overall Status: {'PASSED' if results['valid'] else 'FAILED'}")
        lines.append(f"Errors: {len(results['errors'])}")
        lines.append(f"Warnings: {len(results['warnings'])}")
        lines.append("")

        if results['errors']:
            lines.append("=== Errors ===")
            for i, error in enumerate(results['errors'], 1):
                lines.append(f"{i}. {error['message']}")
                if 'details' in error and isinstance(error['details'], dict):
                    for k, v in error['details'].items():
                        if k != 'failures':  # Skip detailed failures list
                            lines.append(f"   - {k}: {v}")
            lines.append("")

        if results['warnings']:
            lines.append("=== Warnings ===")
            for i, warning in enumerate(results['warnings'], 1):
                lines.append(f"{i}. {warning['message']}")
            lines.append("")

        lines.append("=== Rule Details ===")
        for rule_name, rule_result in results['details'].items():
            status = "PASSED" if rule_result['valid'] else "FAILED"
            lines.append(f"{rule_name}: {status}")
            if not rule_result['valid'] and 'failures' in rule_result:
                if isinstance(rule_result['failures'], list):
                    if len(rule_result['failures']) > 10:
                        # Limit the number of failures shown
                        lines.append(f"   First 10 of {len(rule_result['failures'])} failures:")
                        for failure in rule_result['failures'][:10]:
                            lines.append(f"   - {failure}")
                        lines.append(f"   ... and {len(rule_result['failures']) - 10} more.")
                    else:
                        lines.append(f"   Failures ({len(rule_result['failures'])}):")
                        for failure in rule_result['failures']:
                            lines.append(f"   - {failure}")

        return "\n".join(lines)

    def _generate_html_report(self, results: Dict[str, Any]) -> str:
        """Generate an HTML validation report"""
        # This is a simple HTML report, you can make it more elaborate if needed
        html = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            ".passed { color: green; }",
            ".failed { color: red; }",
            ".warning { color: orange; }",
            "table { border-collapse: collapse; width: 100%; }",
            "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
            "th { background-color: #f2f2f2; }",
            "</style>",
            "<title>Data Validation Report</title>",
            "</head>",
            "<body>",
            "<h1>Data Validation Report</h1>"
        ]

        # Overall status
        status_class = "passed" if results['valid'] else "failed"
        html.append(f"<h2>Overall Status: <span class='{status_class}'>" +
                    f"{'PASSED' if results['valid'] else 'FAILED'}</span></h2>")

        html.append(f"<p>Errors: {len(results['errors'])}</p>")
        html.append(f"<p>Warnings: {len(results['warnings'])}</p>")

        # Errors section
        if results['errors']:
            html.append("<h2>Errors</h2>")
            html.append("<ul>")
            for error in results['errors']:
                html.append(f"<li>{error['message']}</li>")
            html.append("</ul>")

        # Warnings section
        if results['warnings']:
            html.append("<h2>Warnings</h2>")
            html.append("<ul>")
            for warning in results['warnings']:
                html.append(f"<li>{warning['message']}</li>")
            html.append("</ul>")

        # Rule details
        html.append("<h2>Rule Details</h2>")
        html.append("<table>")
        html.append("<tr><th>Rule</th><th>Status</th><th>Details</th></tr>")

        for rule_name, rule_result in results['details'].items():
            status = "PASSED" if rule_result['valid'] else "FAILED"
            status_class = "passed" if rule_result['valid'] else "failed"

            details = ""
            if not rule_result['valid'] and 'failures' in rule_result:
                if isinstance(rule_result['failures'], list):
                    if len(rule_result['failures']) > 5:
                        # Limit the number of failures shown
                        details = f"First 5 of {len(rule_result['failures'])} failures:<br>"
                        details += "<ul>"
                        for failure in rule_result['failures'][:5]:
                            details += f"<li>{failure}</li>"
                        details += "</ul>"
                        details += f"... and {len(rule_result['failures']) - 5} more."
                    else:
                        details = f"Failures ({len(rule_result['failures'])}):<br>"
                        details += "<ul>"
                        for failure in rule_result['failures']:
                            details += f"<li>{failure}</li>"
                        details += "</ul>"

            html.append(f"<tr><td>{rule_name}</td><td class='{status_class}'>{status}</td><td>{details}</td></tr>")

        html.append("</table>")
        html.append("</body></html>")

        return "\n".join(html)

    def _generate_markdown_report(self, results: Dict[str, Any]) -> str:
        """Generate a Markdown validation report"""
        lines = []
        lines.append("# Data Validation Report")
        lines.append(f"**Overall Status:** {'✅ PASSED' if results['valid'] else '❌ FAILED'}")
        lines.append(f"**Errors:** {len(results['errors'])}")
        lines.append(f"**Warnings:** {len(results['warnings'])}")
        lines.append("")

        if results['errors']:
            lines.append("## Errors")
            for i, error in enumerate(results['errors'], 1):
                lines.append(f"{i}. {error['message']}")
            lines.append("")

        if results['warnings']:
            lines.append("## Warnings")
            for i, warning in enumerate(results['warnings'], 1):
                lines.append(f"{i}. {warning['message']}")
            lines.append("")

        lines.append("## Rule Details")
        lines.append("| Rule | Status | Details |")
        lines.append("| ---- | ------ | ------- |")

        for rule_name, rule_result in results['details'].items():
            status = "✅ PASSED" if rule_result['valid'] else "❌ FAILED"

            details = ""
            if not rule_result['valid'] and 'failures' in rule_result:
                if isinstance(rule_result['failures'], list):
                    if len(rule_result['failures']) > 5:
                        # Limit the number of failures shown
                        details = f"First 5 of {len(rule_result['failures'])} failures:<br>"
                        for failure in rule_result['failures'][:5]:
                            details += f"- {failure}<br>"
                        details += f"... and {len(rule_result['failures']) - 5} more."
                    else:
                        details = f"Failures ({len(rule_result['failures'])}):<br>"
                        for failure in rule_result['failures']:
                            details += f"- {failure}<br>"

            lines.append(f"| {rule_name} | {status} | {details} |")

        return "\n".join(lines)

    # === Validation Functions ===

    def _validate_not_null(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that specified columns don't have null values"""
        result = {
            'valid': True,
            'rule_type': 'not_null',
            'columns_checked': columns,
            'failure_count': 0,
            'failures': []
        }

        # Check each column
        for col in columns:
            if col not in df.columns:
                result['failures'].append(f"Column '{col}' does not exist")
                result['valid'] = False
                result['failure_count'] += 1
                continue

            # Count null values
            null_count = df[col].isna().sum()
            if null_count > 0:
                result['valid'] = False
                result['failure_count'] += null_count

                # Get indices of null values (limit to first 100)
                null_indices = df[df[col].isna()].index.tolist()
                if len(null_indices) > 100:
                    result['failures'].append(
                        f"Column '{col}' has {null_count} null values. First 100 at rows: {null_indices[:100]}")
                else:
                    result['failures'].append(f"Column '{col}' has {null_count} null values at rows: {null_indices}")

        return result

    def _validate_unique(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that values in specified columns are unique"""
        result = {
            'valid': True,
            'rule_type': 'unique',
            'columns_checked': columns,
            'failure_count': 0,
            'failures': []
        }

        # Check each column
        for col in columns:
            if col not in df.columns:
                result['failures'].append(f"Column '{col}' does not exist")
                result['valid'] = False
                result['failure_count'] += 1
                continue

            # Check for duplicates
            duplicates = df[df.duplicated(col, keep='first')][col]
            duplicate_count = len(duplicates)

            if duplicate_count > 0:
                result['valid'] = False
                result['failure_count'] += duplicate_count

                # Get duplicate values (limit to first 20)
                duplicate_values = duplicates.tolist()
                if len(duplicate_values) > 20:
                    result['failures'].append(
                        f"Column '{col}' has {duplicate_count} duplicate values. First 20: {duplicate_values[:20]}")
                else:
                    result['failures'].append(
                        f"Column '{col}' has {duplicate_count} duplicate values: {duplicate_values}")

        return result

    def _validate_min_value(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that values in specified columns are >= min_value"""
        result = {
            'valid': True,
            'rule_type': 'min_value',
            'columns_checked': columns,
            'failure_count': 0,
            'failures': []
        }

        # Get min value from params
        min_value = params.get('min_value')
        if min_value is None:
            result['failures'].append("No min_value specified in params")
            result['valid'] = False
            return result

        # Check each column
        for col in columns:
            if col not in df.columns:
                result['failures'].append(f"Column '{col}' does not exist")
                result['valid'] = False
                result['failure_count'] += 1
                continue

            # Skip non-numeric columns
            if not pd.api.types.is_numeric_dtype(df[col]):
                result['failures'].append(f"Column '{col}' is not numeric")
                result['valid'] = False
                result['failure_count'] += 1
                continue

            # Check for values below min_value
            invalid_values = df[df[col] < min_value]
            invalid_count = len(invalid_values)

            if invalid_count > 0:
                result['valid'] = False
                result['failure_count'] += invalid_count

                # Add failure details
                result['failures'].append(f"Column '{col}' has {invalid_count} values below minimum {min_value}")

        return result

    def _validate_max_value(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that values in specified columns are <= max_value"""
        result = {
            'valid': True,
            'rule_type': 'max_value',
            'columns_checked': columns,
            'failure_count': 0,
            'failures': []
        }

        # Get max value from params
        max_value = params.get('max_value')
        if max_value is None:
            result['failures'].append("No max_value specified in params")
            result['valid'] = False
            return result

        # Check each column
        for col in columns:
            if col not in df.columns:
                result['failures'].append(f"Column '{col}' does not exist")
                result['valid'] = False
                result['failure_count'] += 1
                continue

            # Skip non-numeric columns
            if not pd.api.types.is_numeric_dtype(df[col]):
                result['failures'].append(f"Column '{col}' is not numeric")
                result['valid'] = False
                result['failure_count'] += 1
                continue

            # Check for values above max_value
            invalid_values = df[df[col] > max_value]
            invalid_count = len(invalid_values)

            if invalid_count > 0:
                result['valid'] = False
                result['failure_count'] += invalid_count

                # Add failure details
                result['failures'].append(f"Column '{col}' has {invalid_count} values above maximum {max_value}")

        return result

    def _validate_in_set(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that values in specified columns are in a defined set"""
        result = {
            'valid': True,
            'rule_type': 'in_set',
            'columns_checked': columns,
            'failure_count': 0,
            'failures': []
        }

        # Get allowed values from params
        allowed_values = params.get('values')
        if not allowed_values:
            result['failures'].append("No 'values' specified in params")
            result['valid'] = False
            return result

        # Ensure allowed_values is a set for faster lookups
        allowed_set = set(allowed_values)

        # Check each column
        for col in columns:
            if col not in df.columns:
                result['failures'].append(f"Column '{col}' does not exist")
                result['valid'] = False
                result['failure_count'] += 1
                continue

            # Find invalid values
            invalid_mask = ~df[col].isin(allowed_set)
            invalid_count = invalid_mask.sum()

            if invalid_count > 0:
                result['valid'] = False
                result['failure_count'] += invalid_count

                # Get distinct invalid values (limit to first 20)
                invalid_values = df.loc[invalid_mask, col].dropna().unique().tolist()
                if len(invalid_values) > 20:
                    result['failures'].append(
                        f"Column '{col}' has {invalid_count} values not in allowed set. Examples: {invalid_values[:20]}")
                else:
                    result['failures'].append(
                        f"Column '{col}' has {invalid_count} values not in allowed set: {invalid_values}")

        return result

    def _validate_regex(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that values in specified columns match a regex pattern"""
        result = {
            'valid': True,
            'rule_type': 'regex',
            'columns_checked': columns,
            'failure_count': 0,
            'failures': []
        }

        # Get pattern from params
        pattern = params.get('pattern')
        if not pattern:
            result['failures'].append("No regex pattern specified in params")
            result['valid'] = False
            return result

        # Compile the regex pattern
        try:
            regex = re.compile(pattern)
        except Exception as e:
            result['failures'].append(f"Invalid regex pattern: {str(e)}")
            result['valid'] = False
            return result

        # Check each column
        for col in columns:
            if col not in df.columns:
                result['failures'].append(f"Column '{col}' does not exist")
                result['valid'] = False
                result['failure_count'] += 1
                continue

            # Skip non-string columns
            if not pd.api.types.is_string_dtype(df[col]):
                try:
                    # Try to convert to string
                    df[col] = df[col].astype(str)
                except:
                    result['failures'].append(f"Column '{col}' cannot be converted to string")
                    result['valid'] = False
                    result['failure_count'] += 1
                    continue

            # Find invalid values
            invalid_mask = ~df[col].str.match(pattern).fillna(False)
            invalid_count = invalid_mask.sum()

            if invalid_count > 0:
                result['valid'] = False
                result['failure_count'] += invalid_count

                # Get examples of invalid values (limit to first 10)
                invalid_examples = df.loc[invalid_mask, col].head(10).tolist()
                result['failures'].append(
                    f"Column '{col}' has {invalid_count} values not matching pattern '{pattern}'. Examples: {invalid_examples}")

        return result

    def _validate_date_format(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that date values in specified columns match a format"""
        result = {
            'valid': True,
            'rule_type': 'date_format',
            'columns_checked': columns,
            'failure_count': 0,
            'failures': []
        }

        # Get format from params
        date_format = params.get('format', '%Y-%m-%d')

        # Check each column
        for col in columns:
            if col not in df.columns:
                result['failures'].append(f"Column '{col}' does not exist")
                result['valid'] = False
                result['failure_count'] += 1
                continue

            # Try to parse dates
            invalid_count = 0
            invalid_examples = []

            for idx, value in df[col].items():
                # Skip nulls
                if pd.isna(value):
                    continue

                # Try to parse as date
                try:
                    if isinstance(value, str):
                        pd.to_datetime(value, format=date_format)
                    # If already a datetime, it's valid
                    elif isinstance(value, (pd.Timestamp, np.datetime64)):
                        continue
                    else:
                        # Convert to string and try to parse
                        pd.to_datetime(str(value), format=date_format)
                except:
                    invalid_count += 1
                    if len(invalid_examples) < 10:
                        invalid_examples.append(str(value))

            if invalid_count > 0:
                result['valid'] = False
                result['failure_count'] += invalid_count

                result['failures'].append(
                    f"Column '{col}' has {invalid_count} values not matching date format '{date_format}'. Examples: {invalid_examples}")

        return result

    def _validate_column_exists(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that specified columns exist in the DataFrame"""
        result = {
            'valid': True,
            'rule_type': 'column_exists',
            'columns_checked': columns,
            'failure_count': 0,
            'failures': []
        }

        # Check if each column exists
        for col in columns:
            if col not in df.columns:
                result['failures'].append(f"Column '{col}' does not exist")
                result['valid'] = False
                result['failure_count'] += 1

        return result

    def _validate_row_count(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that DataFrame has a specific row count or range"""
        result = {
            'valid': True,
            'rule_type': 'row_count',
            'columns_checked': [],
            'failure_count': 0,
            'failures': []
        }

        # Get parameters
        min_rows = params.get('min_rows')
        max_rows = params.get('max_rows')
        exact_rows = params.get('exact_rows')

        actual_rows = len(df)
        result['actual_row_count'] = actual_rows

        if exact_rows is not None:
            if actual_rows != exact_rows:
                result['valid'] = False
                result['failure_count'] = 1
                result['failures'].append(f"Row count is {actual_rows}, expected exactly {exact_rows}")
            return result

        if min_rows is not None and actual_rows < min_rows:
            result['valid'] = False
            result['failure_count'] = 1
            result['failures'].append(f"Row count is {actual_rows}, expected at least {min_rows}")

        if max_rows is not None and actual_rows > max_rows:
            result['valid'] = False
            result['failure_count'] = 1
            result['failures'].append(f"Row count is {actual_rows}, expected at most {max_rows}")

        return result

    def _validate_column_count(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that DataFrame has a specific column count or range"""
        result = {
            'valid': True,
            'rule_type': 'column_count',
            'columns_checked': [],
            'failure_count': 0,
            'failures': []
        }

        # Get parameters
        min_cols = params.get('min_columns')
        max_cols = params.get('max_columns')
        exact_cols = params.get('exact_columns')

        actual_cols = len(df.columns)
        result['actual_column_count'] = actual_cols

        if exact_cols is not None:
            if actual_cols != exact_cols:
                result['valid'] = False
                result['failure_count'] = 1
                result['failures'].append(f"Column count is {actual_cols}, expected exactly {exact_cols}")
            return result

        if min_cols is not None and actual_cols < min_cols:
            result['valid'] = False
            result['failure_count'] = 1
            result['failures'].append(f"Column count is {actual_cols}, expected at least {min_cols}")

        if max_cols is not None and actual_cols > max_cols:
            result['valid'] = False
            result['failure_count'] = 1
            result['failures'].append(f"Column count is {actual_cols}, expected at most {max_cols}")

        return result

    def _validate_type(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that columns have the specified data type"""
        result = {
            'valid': True,
            'rule_type': 'type',
            'columns_checked': columns,
            'failure_count': 0,
            'failures': []
        }

        # Get expected type from params
        expected_type = params.get('type')
        if not expected_type:
            result['failures'].append("No type specified in params")
            result['valid'] = False
            return result

        # Map string types to numpy/pandas types
        type_mapping = {
            'int': ['int', 'int64', 'int32', 'int16', 'int8'],
            'float': ['float', 'float64', 'float32', 'float16'],
            'string': ['object', 'string'],
            'bool': ['bool', 'boolean'],
            'datetime': ['datetime64[ns]', 'datetime64'],
            'category': ['category']
        }

        # Get acceptable dtypes for the expected type
        acceptable_types = type_mapping.get(expected_type.lower(), [expected_type])

        # Check each column
        for col in columns:
            if col not in df.columns:
                result['failures'].append(f"Column '{col}' does not exist")
                result['valid'] = False
                result['failure_count'] += 1
                continue

            # Check if column type is acceptable
            col_type = str(df[col].dtype)
            if col_type not in acceptable_types:
                result['valid'] = False
                result['failure_count'] += 1
                result['failures'].append(f"Column '{col}' has type '{col_type}', expected one of: {acceptable_types}")

        return result

    def _validate_custom(self, df: pd.DataFrame, columns: List[str], params: Dict[str, Any]) -> Dict[str, Any]:
        """Apply a custom validation function"""
        result = {
            'valid': True,
            'rule_type': 'custom',
            'columns_checked': columns,
            'failure_count': 0,
            'failures': []
        }

        # Get custom function from params
        custom_func = params.get('function')
        if not custom_func or not callable(custom_func):
            result['failures'].append("No valid function provided in params")
            result['valid'] = False
            return result

        # Call the custom function
        try:
            custom_result = custom_func(df, columns)

            # Process function result
            if isinstance(custom_result, bool):
                # Simple pass/fail result
                if not custom_result:
                    result['valid'] = False
                    result['failure_count'] = 1
                    result['failures'].append("Custom validation failed")
            elif isinstance(custom_result, dict):
                # Detailed result dict
                result.update(custom_result)
            else:
                # Unknown result format
                result['valid'] = False
                result['failure_count'] = 1
                result['failures'].append(f"Custom function returned unexpected result type: {type(custom_result)}")

        except Exception as e:
            result['valid'] = False
            result['failure_count'] = 1
            result['failures'].append(f"Error in custom validation function: {str(e)}")

        return result
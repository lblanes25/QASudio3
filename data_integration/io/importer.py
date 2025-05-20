# data_integration/io/importer.py

import pandas as pd
import os
import logging
import datetime
from typing import Dict, List, Any, Optional, Tuple, Union
from pathlib import Path

# Import our connectors
from ..connectors import get_connector_for_file
from .data_validator import DataValidator, DataValidationError

logger = logging.getLogger(__name__)


class DataImporter:
    """
    High-level interface for importing data from various sources into DataFrames.
    Provides common utilities, preprocessing, and validation capabilities.
    """

    @staticmethod
    def load_file(file_path: str,
                  sheet_name: Optional[str] = None,
                  range: Optional[str] = None,
                  validate: Optional[Dict[str, Any]] = None,
                  raise_on_validation_error: bool = False,
                  **kwargs) -> Union[pd.DataFrame, Tuple[pd.DataFrame, Dict[str, Any]]]:
        """
        Load data from a file into a DataFrame using the appropriate connector.

        Args:
            file_path: Path to the data file
            sheet_name: Name of sheet to load (for Excel files)
            range: Cell range to load (for Excel files)
            validate: Optional validation rules to apply
            raise_on_validation_error: Whether to raise exception on validation failure
            **kwargs: Additional parameters specific to the file type

        Returns:
            DataFrame or tuple of (DataFrame, validation_results) if validate is provided
        """
        try:
            # Get appropriate connector for file type
            connector = get_connector_for_file(file_path, **kwargs)

            # Connect to the file
            if not connector.connect():
                raise ConnectionError(f"Failed to connect to file: {file_path}")

            # Prepare query and parameters for Excel files
            query = sheet_name
            params = {}
            if range:
                params['range'] = range

            # Load data
            df = connector.get_data(query, params)

            # Close connection
            connector.disconnect()

            # Apply validation if specified
            if validate:
                validator = DataValidator()
                validation_results = validator.validate(
                    df,
                    validate,
                    raise_exception=raise_on_validation_error
                )
                return df, validation_results

            return df

        except Exception as e:
            logger.error(f"Error loading file {file_path}: {str(e)}")
            raise

    # Other existing methods...

    # data_integration/io/importer.py - update the validate_dataframe method

    @staticmethod
    def validate_dataframe(df: pd.DataFrame,
                           validation_rules: Dict[str, Any],
                           raise_on_error: bool = False,
                           treat_warnings_as_errors: bool = False,
                           generate_report: bool = False,
                           report_format: str = 'text') -> Dict[str, Any]:
        """
        Validate a DataFrame against a set of validation rules.

        Args:
            df: DataFrame to validate
            validation_rules: Dictionary of validation rules
            raise_on_error: Whether to raise exception on validation failure
            treat_warnings_as_errors: Whether to consider warnings as failures for overall validity
            generate_report: Whether to generate a human-readable report
            report_format: Report format if generating a report ('text', 'html', 'markdown')

        Returns:
            Dictionary with validation results and optionally a report
        """
        validator = DataValidator()

        # Validate the DataFrame
        results = validator.validate(
            df,
            validation_rules,
            raise_exception=raise_on_error,
            treat_warnings_as_errors=treat_warnings_as_errors
        )

        # Generate report if requested
        if generate_report:
            report = validator.generate_report(results, format=report_format)
            results['report'] = report

        return results

    @staticmethod
    def preview_file(file_path: str,
                     max_rows: int = 5,
                     **kwargs) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Preview the contents of a data file.

        Args:
            file_path: Path to the data file
            max_rows: Maximum number of rows to preview
            **kwargs: Additional parameters for file loading

        Returns:
            Tuple of (preview DataFrame, file metadata)
        """
        try:
            # Get appropriate connector for file type
            connector = get_connector_for_file(file_path, **kwargs)

            # Connect to the file
            if not connector.connect():
                raise ConnectionError(f"Failed to connect to file: {file_path}")

            # Collect file metadata
            metadata = {
                'file_name': os.path.basename(file_path),
                'file_path': file_path,
                'file_size': os.path.getsize(file_path),
                'file_type': os.path.splitext(file_path)[1].lower(),
                'last_modified': datetime.datetime.fromtimestamp(os.path.getmtime(file_path))
            }

            # For Excel files, get sheet names
            if hasattr(connector, 'get_sheet_names'):
                try:
                    metadata['sheets'] = connector.get_sheet_names()
                except:
                    pass

            # Load preview data (limit rows)
            params = kwargs.copy()
            params['nrows'] = max_rows

            # Load data
            df = connector.get_data(params=params)

            # Close connection
            connector.disconnect()

            # Add DataFrame metadata
            metadata['columns'] = list(df.columns)
            metadata['row_count'] = len(df)
            metadata['column_count'] = len(df.columns)

            return df, metadata

        except Exception as e:
            logger.error(f"Error previewing file {file_path}: {str(e)}")
            raise

    @staticmethod
    def get_standard_validation_rules(data_type: str = 'generic') -> Dict[str, Any]:
        """
        Get a set of standard validation rules for common data types.

        Args:
            data_type: Type of data ('generic', 'sales', 'employee', 'financial')

        Returns:
            Dictionary of validation rules
        """
        # Generic rules applicable to most datasets
        generic_rules = {
            'no_empty_data': {
                'type': 'row_count',
                'severity': 'error',
                'params': {'min_rows': 1},
                'message': 'Dataset cannot be empty'
            },
            'reasonable_columns': {
                'type': 'column_count',
                'severity': 'warning',
                'params': {'min_columns': 2, 'max_columns': 100},
                'message': 'Dataset has an unusual number of columns'
            }
        }

        # Rules specific to data types
        if data_type == 'generic':
            return generic_rules

        elif data_type == 'employee':
            employee_rules = generic_rules.copy()
            employee_rules.update({
                'employee_id_present': {
                    'type': 'column_exists',
                    'columns': ['Employee ID', 'EmployeeID', 'ID'],
                    'severity': 'error',
                    'message': 'Employee ID column is required'
                },
                'employee_id_unique': {
                    'type': 'unique',
                    'columns': ['Employee ID', 'EmployeeID', 'ID'],
                    'severity': 'error',
                    'message': 'Employee IDs must be unique'
                }
            })
            return employee_rules

        elif data_type == 'financial':
            financial_rules = generic_rules.copy()
            financial_rules.update({
                'amount_column_present': {
                    'type': 'column_exists',
                    'columns': ['Amount', 'Value', 'Transaction Amount'],
                    'severity': 'error',
                    'message': 'Amount column is required'
                },
                'date_column_present': {
                    'type': 'column_exists',
                    'columns': ['Date', 'Transaction Date', 'Entry Date'],
                    'severity': 'error',
                    'message': 'Date column is required'
                }
            })
            return financial_rules

        elif data_type == 'sales':
            sales_rules = generic_rules.copy()
            sales_rules.update({
                'product_column_present': {
                    'type': 'column_exists',
                    'columns': ['Product', 'Product ID', 'Item', 'Item ID'],
                    'severity': 'error',
                    'message': 'Product column is required'
                },
                'sales_amount_present': {
                    'type': 'column_exists',
                    'columns': ['Amount', 'Sales Amount', 'Revenue', 'Price'],
                    'severity': 'error',
                    'message': 'Sales amount column is required'
                }
            })
            return sales_rules

        # Default to generic rules
        return generic_rules

    @staticmethod
    def load_directory(directory_path: str,
                       file_pattern: str = "*.*",
                       recursive: bool = False,
                       **kwargs) -> Dict[str, pd.DataFrame]:
        """
        Load multiple files from a directory into DataFrames.

        Args:
            directory_path: Path to directory containing data files
            file_pattern: Glob pattern for matching files
            recursive: Whether to search directories recursively
            **kwargs: Additional parameters for file loading

        Returns:
            Dictionary mapping file names to DataFrames
        """
        try:
            # Get directory path
            dir_path = Path(directory_path)

            # Find matching files
            if recursive:
                file_paths = list(dir_path.glob(f"**/{file_pattern}"))
            else:
                file_paths = list(dir_path.glob(file_pattern))

            # Load each file
            dataframes = {}
            for file_path in file_paths:
                try:
                    # Use the file name (without extension) as key
                    key = file_path.stem

                    # Load the file
                    df = DataImporter.load_file(str(file_path), **kwargs)

                    # Add to dictionary
                    dataframes[key] = df

                except Exception as e:
                    logger.warning(f"Error loading file {file_path}: {str(e)}")

            return dataframes

        except Exception as e:
            logger.error(f"Error loading files from directory {directory_path}: {str(e)}")
            raise
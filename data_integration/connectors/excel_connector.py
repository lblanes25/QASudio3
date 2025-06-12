# data_integration/connectors/excel_connector.py

import os
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Union
import logging
from pathlib import Path

from .base_connector import BaseConnector
from data_integration.errors.error_handler import retry_operation, safe_dataframe_operation

logger = logging.getLogger(__name__)


class ExcelConnector(BaseConnector):
    """
    Connector for loading data from Excel files into DataFrames.
    Supports multiple sheets, range selection, and handles Excel-specific data types.
    """

    def __init__(self,
                 connection_params: Optional[Dict[str, Any]] = None):
        """
        Initialize the Excel connector.

        Args:
            connection_params: Dictionary with connection parameters, may include:
                - file_path: Path to the Excel file
                - sheet_name: Name or index of sheet to load (optional)
                - range: Cell range to load (optional)
                - headers: Row number containing headers (optional)
                - password: Password for protected workbooks (optional)
        """
        super().__init__(connection_params)

        # Set file path if provided
        self.file_path = self.connection_params.get('file_path')

        # Excel-specific options
        self.sheet_name = self.connection_params.get('sheet_name')
        self.cell_range = self.connection_params.get('range')
        self.header_row = self.connection_params.get('headers', 0)  # Default to first row (0)
        self.password = self.connection_params.get('password')

        # Extra options for handling Excel specifics
        self.na_values = self.connection_params.get('na_values', ['#N/A', '#N/A N/A', '#NA', '-NA', '#NULL!',
                                                                  '#NUM!', '#DIV/0!', '#VALUE!', '#REF!', '#NAME?',
                                                                  '#DIV/0', '#NUM', '#REF', '#VALUE'])

        # Check if pandas supports the engine requested, default to openpyxl for .xlsx
        self.engine = self.connection_params.get('engine')
        if not self.engine:
            if self.file_path and str(self.file_path).lower().endswith('.xlsx'):
                self.engine = 'openpyxl'
            else:
                self.engine = None  # Let pandas choose

        # Configure retry settings
        self.max_retries = self.connection_params.get('max_retries', 3)
        self.retry_delay = self.connection_params.get('retry_delay', 1.0)

    def connect(self) -> bool:
        """
        Validate the Excel file is accessible.

        Returns:
            True if file exists and is readable, False otherwise
        """
        if not self.file_path:
            logger.error("No file path provided to Excel connector")
            return False

        try:
            # Check if file exists
            file_path = Path(self.file_path)
            if not file_path.exists():
                error_msg = f"Excel file not found: {self.file_path}"
                logger.error(error_msg)
                self.handle_connection_error(FileNotFoundError(error_msg))
                return False

            # Check if file is readable
            if not os.access(file_path, os.R_OK):
                error_msg = f"Excel file is not readable: {self.file_path}"
                logger.error(error_msg)
                self.handle_connection_error(PermissionError(error_msg))
                return False

            self._is_connected = True
            return True

        except Exception as e:
            logger.error(f"Error connecting to Excel file: {str(e)}")
            self.handle_connection_error(e)
            self._is_connected = False
            return False

    def disconnect(self) -> bool:
        """
        Close connection (no persistent connection for Excel files).

        Returns:
            Always returns True for Excel connector
        """
        # No persistent connection to close with Excel files
        self._is_connected = False
        return True

    def test_connection(self) -> bool:
        """
        Test if the Excel file is accessible.

        Returns:
            True if file exists and is readable, False otherwise
        """
        return self.connect()

    def get_data(self,
                 query: Optional[str] = None,
                 params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Load data from Excel file into a DataFrame.

        Args:
            query: Sheet name or index (overrides init parameter if provided)
            params: Additional parameters, can include:
                - range: Cell range to load
                - header: Row number for headers
                - skiprows: Number of rows to skip
                - usecols: Columns to include

        Returns:
            DataFrame containing the Excel data
        """
        if not self._is_connected and not self.connect():
            raise ConnectionError(f"Cannot connect to Excel file: {self.file_path}")

        # Merge parameters from initialization with those provided in the call
        all_params = {}

        # Start with the initialization parameters
        if self.sheet_name is not None:
            all_params['sheet_name'] = self.sheet_name
        if self.cell_range:
            # pandas doesn't directly support 'range', but we'll handle that
            all_params['skiprows'] = self._parse_range_skiprows(self.cell_range)
            all_params['usecols'] = self._parse_range_usecols(self.cell_range)
        if self.header_row is not None:
            all_params['header'] = self.header_row

        # Override with parameters from this call
        if params:
            # Handle 'range' parameter specially
            if 'range' in params:
                params['skiprows'] = self._parse_range_skiprows(params['range'])
                params['usecols'] = self._parse_range_usecols(params['range'])
                del params['range']

            # Update with remaining parameters
            all_params.update(params)

        # If query is provided, use it as sheet_name
        if query is not None:
            all_params['sheet_name'] = query

        # Add standard parameters for Excel loading
        all_params['na_values'] = self.na_values
        if self.engine:
            all_params['engine'] = self.engine
        if self.password:
            all_params['password'] = self.password

        # Enable date parsing by default
        if 'parse_dates' not in all_params:
            all_params['parse_dates'] = True

        try:
            # Use retry for robustness against transient errors
            def load_excel():
                try:
                    # Use safe_dataframe_operation to improve error reporting
                    return safe_dataframe_operation(
                        pd.read_excel,
                        self.file_path,
                        **all_params
                    )
                except Exception as e:
                    # Add additional context to the error
                    logger.debug(f"Excel load attempt failed: {str(e)}")
                    # Re-raise to let retry_operation handle it
                    raise

            # Execute with retry logic
            df = retry_operation(
                load_excel,
                max_attempts=self.max_retries,
                retry_delay=self.retry_delay,
                exception_types=(IOError, pd.errors.ParserError, ValueError)
            )

            # Post-process the DataFrame
            df = self._post_process_dataframe(df)

            return df

        except Exception as e:
            # Handle the error
            logger.error(f"Error loading Excel file {self.file_path}: {str(e)}")
            self.handle_data_load_error(e, query, all_params)
            raise

        def get_sheet_names(self) -> List[str]:
            """
            Get list of sheet names in the Excel file.

            Returns:
                List of sheet names
            """
            if not self._is_connected and not self.connect():
                raise ConnectionError(f"Cannot connect to Excel file: {self.file_path}")

            try:
                # Use retry for robustness against transient errors
                def get_excel_sheets():
                    try:
                        # Use ExcelFile for better performance when just getting metadata
                        excel_file = pd.ExcelFile(self.file_path, engine=self.engine)
                        return excel_file.sheet_names
                    except Exception as e:
                        # Log the error for debugging
                        logger.debug(f"Sheet names retrieval attempt failed: {str(e)}")
                        # Re-raise to let retry_operation handle it
                        raise

                # Execute with retry logic
                sheet_names = retry_operation(
                    get_excel_sheets,
                    max_attempts=self.max_retries,
                    retry_delay=self.retry_delay,
                    exception_types=(IOError, ValueError, Exception)
                )

                return sheet_names

            except Exception as e:
                # Handle the error
                logger.error(f"Error getting sheet names from {self.file_path}: {str(e)}")
                self.handle_data_load_error(e)
                raise

        def get_sheet_info(self) -> List[Dict[str, Any]]:
            """
            Get detailed information about all sheets in the Excel file.

            Returns:
                List of dictionaries with sheet information
            """
            if not self._is_connected and not self.connect():
                raise ConnectionError(f"Cannot connect to Excel file: {self.file_path}")

            try:
                # Get sheet names
                sheet_names = self.get_sheet_names()
                sheet_info = []

                # Use ExcelFile to avoid reopening the file for each sheet
                excel_file = pd.ExcelFile(self.file_path, engine=self.engine)

                # Process each sheet
                for sheet_name in sheet_names:
                    try:
                        # Get a small sample of data to determine column types
                        sample_df = excel_file.parse(
                            sheet_name=sheet_name,
                            nrows=5  # Just get first 5 rows for metadata
                        )

                        # Create sheet info dictionary
                        info = {
                            'name': sheet_name,
                            'row_count': self._get_sheet_row_count(excel_file, sheet_name),
                            'column_count': len(sample_df.columns),
                            'columns': sample_df.columns.tolist(),
                            'column_types': {col: str(sample_df[col].dtype) for col in sample_df.columns}
                        }

                        sheet_info.append(info)

                    except Exception as e:
                        logger.warning(f"Error getting info for sheet '{sheet_name}': {str(e)}")
                        # Add sheet with error information
                        sheet_info.append({
                            'name': sheet_name,
                            'error': str(e)
                        })

                return sheet_info

            except Exception as e:
                # Handle the error
                logger.error(f"Error getting sheet info from {self.file_path}: {str(e)}")
                self.handle_data_load_error(e)
                raise

        def _get_sheet_row_count(self, excel_file: pd.ExcelFile, sheet_name: str) -> int:
            """
            Get the row count for a sheet more efficiently than loading all data.

            Args:
                excel_file: Open pandas ExcelFile object
                sheet_name: Name of the sheet

            Returns:
                Number of rows in the sheet
            """
            try:
                # For some engines like openpyxl, we can get row count more efficiently
                if self.engine == 'openpyxl':
                    # Access the underlying openpyxl workbook
                    workbook = excel_file.book
                    worksheet = workbook[sheet_name]
                    return worksheet.max_row

                # For other engines, we need to count the rows by loading the data
                # Use a more efficient approach by reading just the index
                df = excel_file.parse(
                    sheet_name=sheet_name,
                    usecols=[0],  # Just first column
                    header=None  # Don't process headers
                )
                return len(df)

            except Exception as e:
                logger.warning(f"Error getting row count for sheet '{sheet_name}': {str(e)}")
                return -1  # Indicate error with negative row count

        def _parse_range_skiprows(self, cell_range: str) -> Union[int, None]:
            """
            Parse cell range to determine rows to skip.

            Args:
                cell_range: Cell range in Excel format (e.g., 'A1:D10')

            Returns:
                Number of rows to skip or None if not applicable
            """
            try:
                # Extract the row number from range start (e.g., 'A1' -> 1)
                if ':' in cell_range:
                    start_cell = cell_range.split(':')[0]
                    # Extract the row number using regex
                    import re
                    match = re.search(r'(\d+)', start_cell)
                    if match:
                        # Convert to 0-based index for pandas (Excel is 1-based)
                        return int(match.group(1)) - 1
            except Exception as e:
                logger.warning(f"Error parsing range for skiprows: {str(e)}")

            return None

        def _parse_range_usecols(self, cell_range: str) -> Union[List[int], None]:
            """
            Parse cell range to determine columns to include.

            Args:
                cell_range: Cell range in Excel format (e.g., 'A1:D10')

            Returns:
                List of column indices to include or None if not applicable
            """
            try:
                # This is a simplified implementation - a complete one would
                # need to handle column letters more robustly
                if ':' in cell_range:
                    start_cell, end_cell = cell_range.split(':')

                    # Extract column letters
                    start_col = ''.join(c for c in start_cell if c.isalpha())
                    end_col = ''.join(c for c in end_cell if c.isalpha())

                    # Convert to column indices
                    start_idx = self._excel_column_to_index(start_col)
                    end_idx = self._excel_column_to_index(end_col)

                    # Return range of columns
                    return list(range(start_idx, end_idx + 1))
            except Exception as e:
                logger.warning(f"Error parsing range for usecols: {str(e)}")

            return None

        def _excel_column_to_index(self, column: str) -> int:
            """
            Convert Excel column letter to 0-based index.

            Args:
                column: Column letter (e.g., 'A', 'AB')

            Returns:
                0-based column index
            """
            index = 0
            for char in column:
                index = index * 26 + (ord(char.upper()) - ord('A') + 1)
            # Convert to 0-based index
            return index - 1

        def _post_process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
            """
            Perform post-processing on the loaded DataFrame.
            - Clean column names
            - Handle Excel-specific data types
            - Apply any transformations

            Args:
                df: Raw DataFrame from Excel

            Returns:
                Processed DataFrame
            """
            if df.empty:
                return df

            try:
                # Clean column names - remove extra whitespace and handle duplicate columns
                df.columns = self._clean_column_names(df.columns)

                # Replace 'nan' strings with actual NaN
                for col in df.columns:
                    if df[col].dtype == 'object':
                        # Use safe conversion to avoid errors with mixed types
                        try:
                            df[col] = df[col].replace('nan', np.nan)
                            df[col] = df[col].replace('None', np.nan)
                            df[col] = df[col].replace('#N/A', np.nan)
                        except Exception as e:
                            logger.debug(f"Error cleaning column {col}: {str(e)}")

                # Detect and fix merged cells (may have missing values)
                df = self._fix_merged_cells(df)

                # Detect and convert date columns that pandas didn't recognize
                df = self._fix_date_columns(df)

                return df

            except Exception as e:
                logger.warning(f"Error in post-processing DataFrame: {str(e)}")
                return df

        def _clean_column_names(self, columns) -> List[str]:
            """
            Clean up column names from Excel.
            - Remove whitespace
            - Make column names unique

            Args:
                columns: Original column names

            Returns:
                Cleaned column names
            """
            # Remove whitespace and convert to strings
            cleaned = [str(col).strip() if col is not None else f"Unnamed_{i}" for i, col in enumerate(columns)]

            # Handle duplicate column names
            seen = {}
            for i, col in enumerate(cleaned):
                if col in seen:
                    seen[col] += 1
                    cleaned[i] = f"{col}_{seen[col]}"
                else:
                    seen[col] = 0

            return cleaned

        def _fix_merged_cells(self, df: pd.DataFrame) -> pd.DataFrame:
            """
            Fix issues with merged cells in Excel files.
            Excel often puts the value in the first cell of a merged range and leaves others blank.

            Args:
                df: DataFrame with potentially merged cells

            Returns:
                Fixed DataFrame
            """
            # Look for fill patterns - identify columns with significant repeating null patterns
            # which might indicate merged cells
            for col in df.columns:
                # Skip columns with few nulls
                null_count = df[col].isna().sum()
                if null_count < 5 or null_count / len(df) < 0.1:
                    continue

                # Fill NaN values with the last valid value (common pattern for merged cells)
                try:
                    # Check if there's a pattern of nulls after values
                    if self._check_merged_cell_pattern(df[col]):
                        df[col] = df[col].fillna(method='ffill')
                except Exception as e:
                    logger.debug(f"Error fixing merged cells in column {col}: {str(e)}")

            return df

        def _check_merged_cell_pattern(self, series: pd.Series) -> bool:
            """
            Check if a series has a pattern indicative of merged cells.

            Args:
                series: Series to check

            Returns:
                True if merged cell pattern detected, False otherwise
            """
            # Calculate run lengths of nulls and non-nulls
            is_null = series.isna()

            if is_null.sum() == 0:
                return False

            # Look for patterns where non-null values are followed by runs of nulls
            prev_null = False
            null_runs = 0
            null_after_value = 0

            for i, val in enumerate(is_null):
                if val:  # Current value is null
                    if not prev_null and i > 0:  # Start of a null run after a value
                        null_after_value += 1
                    prev_null = True
                else:  # Current value is not null
                    if prev_null:  # End of a null run
                        null_runs += 1
                    prev_null = False

            # If we have multiple instances of nulls following values, it might be merged cells
            return null_after_value >= 3 and null_runs >= 2

        def _fix_date_columns(self, df: pd.DataFrame) -> pd.DataFrame:
            """
            Detect and convert date columns that pandas didn't recognize.

            Args:
                df: DataFrame with potential date columns

            Returns:
                DataFrame with fixed date columns
            """
            for col in df.columns:
                # Skip columns that are already datetime
                if pd.api.types.is_datetime64_dtype(df[col]):
                    continue

                # Skip columns with few values
                if df[col].count() < 5:
                    continue

                # Check if column might contain dates
                try:
                    # Sample values for date detection
                    sample = df[col].dropna().head(10)

                    # Try different date formats based on common patterns
                    date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%d-%m-%Y', '%m-%d-%Y']

                    for date_format in date_formats:
                        success_count = 0
                        for val in sample:
                            try:
                                if isinstance(val, str):
                                    pd.to_datetime(val, format=date_format)
                                    success_count += 1
                            except:
                                pass

                        # If most values match this format, convert the column
                        if success_count >= 0.7 * len(sample):
                            try:
                                df[col] = pd.to_datetime(df[col], format=date_format, errors='coerce')
                                break
                            except Exception as e:
                                logger.debug(f"Error converting column {col} to datetime: {str(e)}")
                except Exception as e:
                    logger.debug(f"Error checking if column {col} contains dates: {str(e)}")

            return df

    def get_sheet_names(self) -> List[str]:
        """
        Get list of sheet names in the Excel file.

        Returns:
            List of sheet names
        """
        if not self._is_connected and not self.connect():
            raise ConnectionError(f"Cannot connect to Excel file: {self.file_path}")

        try:
            # Use ExcelFile to get sheet names
            excel_file = pd.ExcelFile(self.file_path, engine=self.engine)
            return excel_file.sheet_names

        except Exception as e:
            logger.error(f"Error getting sheet names from {self.file_path}: {str(e)}")
            self.handle_data_load_error(e)
            raise

    def _post_process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Perform post-processing on the loaded DataFrame.
        - Clean column names
        - Handle Excel-specific data types
        - Apply any transformations

        Args:
            df: Raw DataFrame from Excel

        Returns:
            Processed DataFrame
        """
        if df.empty:
            return df

        # Clean column names - remove extra whitespace
        df.columns = df.columns.str.strip()

        # Replace 'nan' strings with actual NaN
        for col in df.columns:
            if df[col].dtype == 'object':
                df[col] = df[col].replace('nan', np.nan)

        return df
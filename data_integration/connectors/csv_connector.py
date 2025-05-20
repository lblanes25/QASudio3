# data_integration/connectors/csv_connector.py

import os
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
import logging
from pathlib import Path

from .base_connector import BaseConnector
from data_integration.errors.error_handler import retry_operation, safe_dataframe_operation

logger = logging.getLogger(__name__)


class CSVConnector(BaseConnector):
    """
    Connector for loading data from CSV and other delimited text files into DataFrames.
    Supports automatic delimiter detection, encoding detection, and other CSV processing features.
    """

    def __init__(self,
                 connection_params: Optional[Dict[str, Any]] = None):
        """
        Initialize the CSV connector.

        Args:
            connection_params: Dictionary with connection parameters, may include:
                - file_path: Path to the CSV file
                - delimiter: Field delimiter (default: auto-detect)
                - encoding: File encoding (default: auto-detect)
                - header: Row number containing headers (default: 0)
                - skiprows: Number of rows to skip (default: 0)
                - na_values: Values to interpret as NaN
        """
        super().__init__(connection_params)

        # Set file path if provided
        self.file_path = self.connection_params.get('file_path')

        # CSV-specific options
        self.delimiter = self.connection_params.get('delimiter')
        self.encoding = self.connection_params.get('encoding')
        self.header_row = self.connection_params.get('header', 0)  # Default to first row (0)
        self.skiprows = self.connection_params.get('skiprows', 0)

        # Extra options for handling CSV specifics
        self.na_values = self.connection_params.get('na_values', ['NA', 'N/A', '', '#N/A', '#N/A N/A',
                                                                  '#NA', '-NA', '#NULL!', '#NUM!',
                                                                  '#DIV/0!', '#VALUE!', '#REF!', '#NAME?',
                                                                  'n/a', 'nan', '-', '#'])

        # Options for performance and flexibility
        self.low_memory = self.connection_params.get('low_memory', False)
        self.dtype = self.connection_params.get('dtype')  # Column dtypes

        # Configure retry settings
        self.max_retries = self.connection_params.get('max_retries', 3)
        self.retry_delay = self.connection_params.get('retry_delay', 1.0)

    def connect(self) -> bool:
        """
        Validate the CSV file is accessible.

        Returns:
            True if file exists and is readable, False otherwise
        """
        if not self.file_path:
            error_msg = "No file path provided to CSV connector"
            logger.error(error_msg)
            self.handle_connection_error(ValueError(error_msg))
            return False

        try:
            # Check if file exists
            file_path = Path(self.file_path)
            if not file_path.exists():
                error_msg = f"CSV file not found: {self.file_path}"
                logger.error(error_msg)
                self.handle_connection_error(FileNotFoundError(error_msg))
                return False

            # Check if file is readable
            if not os.access(file_path, os.R_OK):
                error_msg = f"CSV file is not readable: {self.file_path}"
                logger.error(error_msg)
                self.handle_connection_error(PermissionError(error_msg))
                return False

            self._is_connected = True
            return True

        except Exception as e:
            logger.error(f"Error connecting to CSV file: {str(e)}")
            self.handle_connection_error(e)
            self._is_connected = False
            return False

    def disconnect(self) -> bool:
        """
        Close connection (no persistent connection for CSV files).

        Returns:
            Always returns True for CSV connector
        """
        # No persistent connection to close with CSV files
        self._is_connected = False
        return True

    def test_connection(self) -> bool:
        """
        Test if the CSV file is accessible.

        Returns:
            True if file exists and is readable, False otherwise
        """
        return self.connect()

    def get_data(self,
                 query: Optional[str] = None,
                 params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Load data from CSV file into a DataFrame.

        Args:
            query: Not used for CSV connector but maintained for interface consistency
            params: Additional parameters, can include any parameter accepted by pd.read_csv()

        Returns:
            DataFrame containing the CSV data
        """
        if not self._is_connected and not self.connect():
            error_msg = f"Cannot connect to CSV file: {self.file_path}"
            logger.error(error_msg)
            self.handle_connection_error(ConnectionError(error_msg))
            return pd.DataFrame()  # Return empty DataFrame to maintain interface

        # Merge parameters from initialization with those provided in the call
        all_params = {}

        # Start with the initialization parameters
        if self.delimiter is not None:
            all_params['delimiter'] = self.delimiter
        if self.encoding is not None:
            all_params['encoding'] = self.encoding
        if self.header_row is not None:
            all_params['header'] = self.header_row
        if self.skiprows is not None:
            all_params['skiprows'] = self.skiprows
        if self.na_values is not None:
            all_params['na_values'] = self.na_values
        if self.low_memory is not None:
            all_params['low_memory'] = self.low_memory
        if self.dtype is not None:
            all_params['dtype'] = self.dtype

        # Override with parameters from this call
        if params:
            all_params.update(params)

        try:
            # Auto-detect delimiter if not specified
            if 'delimiter' not in all_params or not all_params['delimiter']:
                all_params['delimiter'] = self._detect_delimiter()

            # Auto-detect encoding if not specified
            if 'encoding' not in all_params or not all_params['encoding']:
                all_params['encoding'] = self._detect_encoding()

            # Use retry for robustness against transient errors
            def load_csv():
                try:
                    # Use safe_dataframe_operation to improve error reporting
                    return safe_dataframe_operation(
                        pd.read_csv,
                        self.file_path,
                        **all_params
                    )
                except Exception as e:
                    # Log the error
                    logger.debug(f"CSV load attempt failed: {str(e)}")
                    # Re-raise to let retry_operation handle it
                    raise

            # Execute with retry logic
            df = retry_operation(
                load_csv,
                max_attempts=self.max_retries,
                retry_delay=self.retry_delay,
                exception_types=(IOError, pd.errors.ParserError, UnicodeDecodeError)
            )

            # Post-process the DataFrame
            df = self._post_process_dataframe(df)

            return df

        except Exception as e:
            # Handle the error
            logger.error(f"Error loading CSV file {self.file_path}: {str(e)}")
            self.handle_data_load_error(e, None, all_params)
            raise

    def get_file_info(self) -> Dict[str, Any]:
        """
        Get information about the CSV file.

        Returns:
            Dictionary with file information
        """
        if not self._is_connected and not self.connect():
            error_msg = f"Cannot connect to CSV file: {self.file_path}"
            logger.error(error_msg)
            self.handle_connection_error(ConnectionError(error_msg))
            return {}

        try:
            info = {
                'file_path': self.file_path,
                'file_name': os.path.basename(self.file_path),
                'file_size': os.path.getsize(self.file_path),
                'last_modified': datetime.datetime.fromtimestamp(os.path.getmtime(self.file_path)).isoformat()
            }

            # Get delimiter and encoding
            info['delimiter'] = self._detect_delimiter()
            info['encoding'] = self._detect_encoding()

            # Count lines in the file
            info['line_count'] = self._count_lines()

            # Get sample of the data
            try:
                with open(self.file_path, 'r', encoding=info['encoding'], errors='replace') as f:
                    # Read first few lines for sample
                    sample_lines = []
                    for i, line in enumerate(f):
                        if i >= 5:  # Sample first 5 lines
                            break
                        sample_lines.append(line.strip())

                    info['sample'] = sample_lines
            except Exception as e:
                logger.warning(f"Error getting sample data: {str(e)}")
                info['sample_error'] = str(e)

            return info

        except Exception as e:
            # Handle the error
            logger.error(f"Error getting file info for {self.file_path}: {str(e)}")
            self.handle_data_load_error(e)
            return {'error': str(e)}

    def _count_lines(self) -> int:
        """
        Count the number of lines in the file efficiently.

        Returns:
            Number of lines in the file
        """
        try:
            # Use an efficient line counting method
            with open(self.file_path, 'rb') as f:
                # Count newline characters
                return sum(1 for _ in f)
        except Exception as e:
            logger.warning(f"Error counting lines in file: {str(e)}")
            return -1  # Indicate error with negative count

    def _detect_delimiter(self) -> str:
        """
        Auto-detect the delimiter used in the CSV file.

        Returns:
            Detected delimiter or comma as default
        """
        try:
            # Read a sample of the file
            with open(self.file_path, 'r', newline='', encoding='utf-8-sig', errors='replace') as csvfile:
                # Read a sample of the file
                sample = csvfile.read(4096)

                # Count potential delimiters
                delimiters = [',', '\t', ';', '|', ':']
                delimiter_counts = {d: sample.count(d) for d in delimiters}

                # Find the delimiter with the highest count
                max_count = 0
                detected_delimiter = ','  # Default

                for delim, count in delimiter_counts.items():
                    if count > max_count:
                        max_count = count
                        detected_delimiter = delim

                return detected_delimiter

        except Exception as e:
            logger.warning(f"Error detecting delimiter, defaulting to comma: {str(e)}")
            return ','

    def _detect_encoding(self) -> str:
        """
        Attempt to detect the file encoding.

        Returns:
            Detected encoding or utf-8 as default
        """
        try:
            import chardet

            # Read a sample of the file
            with open(self.file_path, 'rb') as file:
                sample = file.read(4096)

            # Detect encoding
            result = chardet.detect(sample)

            # Use detected encoding if confidence is high enough
            if result['confidence'] > 0.7:
                return result['encoding']

        except ImportError:
            logger.info("chardet library not installed, defaulting to utf-8")
        except Exception as e:
            logger.warning(f"Error detecting encoding, defaulting to utf-8: {str(e)}")

        return 'utf-8'

    def _post_process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Perform post-processing on the loaded DataFrame.
        - Clean column names
        - Handle data type conversions
        - Apply any transformations

        Args:
            df: Raw DataFrame from CSV

        Returns:
            Processed DataFrame
        """
        if df.empty:
            return df

        try:
            # Clean column names - remove extra whitespace and handle duplicates
            df.columns = self._clean_column_names(df.columns)

            # Convert 'NA', 'N/A', etc. strings to actual NaN (might be missed during loading)
            for col in df.columns:
                if df[col].dtype == 'object':
                    try:
                        df[col] = df[col].replace(['NA', 'N/A', '#N/A', 'n/a'], np.nan)
                    except Exception as e:
                        logger.debug(f"Error cleaning column {col}: {str(e)}")

            # Detect and convert date columns
            df = self._detect_and_convert_date_columns(df)

            # Detect and convert numeric columns that were read as strings
            df = self._detect_and_convert_numeric_columns(df)

            return df

        except Exception as e:
            logger.warning(f"Error in post-processing DataFrame: {str(e)}")
            return df

    def _clean_column_names(self, columns) -> List[str]:
        """
        Clean up column names from CSV.
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

    def _detect_and_convert_date_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect and convert columns that appear to contain dates.

        Args:
            df: DataFrame to process

        Returns:
            DataFrame with date columns converted
        """
        # Common date formats to check
        date_formats = ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%Y/%m/%d', '%d-%m-%Y', '%m-%d-%Y']

        for col in df.columns:
            # Skip columns that are already datetime
            if pd.api.types.is_datetime64_dtype(df[col]):
                continue

            # Only check string columns with at least 5 values
            if not pd.api.types.is_string_dtype(df[col]) or df[col].count() < 5:
                continue

            # Sample values for testing
            sample = df[col].dropna().head(10)

            # Try each date format
            for date_format in date_formats:
                try:
                    # Count how many values match this format
                    match_count = 0
                    for val in sample:
                        try:
                            pd.to_datetime(val, format=date_format)
                            match_count += 1
                        except:
                            pass

                    # If most values match, convert the column
                    if match_count >= len(sample) * 0.8:
                        df[col] = pd.to_datetime(df[col], format=date_format, errors='coerce')
                        break
                except Exception as e:
                    logger.debug(f"Error testing date format {date_format} for column {col}: {str(e)}")

        return df

    def _detect_and_convert_numeric_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Detect and convert columns that appear to contain numeric values.

        Args:
            df: DataFrame to process

        Returns:
            DataFrame with numeric columns converted
        """
        for col in df.columns:
            # Skip columns that are already numeric
            if pd.api.types.is_numeric_dtype(df[col]):
                continue

            # Only check object columns with at least 5 values
            if not pd.api.types.is_object_dtype(df[col]) or df[col].count() < 5:
                continue

            # Sample values for testing
            sample = df[col].dropna().head(20)

            # Count how many values can be converted to numeric
            match_count = 0
            for val in sample:
                try:
                    # Remove common currency symbols and thousands separators
                    cleaned = str(val).replace('$', '').replace('€', '').replace('£', '').replace(',', '')
                    float(cleaned)
                    match_count += 1
                except:
                    pass

            # If most values are numeric, convert the column
            if match_count >= len(sample) * 0.8:
                try:
                    # Convert with appropriate handling of currency symbols, etc.
                    df[col] = df[col].apply(lambda x: pd.to_numeric(
                        str(x).replace('$', '').replace('€', '').replace('£', '').replace(',', ''),
                        errors='coerce'
                    ))
                except Exception as e:
                    logger.debug(f"Error converting column {col} to numeric: {str(e)}")

        return df
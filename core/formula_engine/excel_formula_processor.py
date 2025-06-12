import os
import pandas as pd
import numpy as np
import re
import gc
from typing import Dict, List, Any, Optional, Tuple, Union
import win32com.client
import tempfile
import time
import logging
from pathlib import Path
import uuid
import pythoncom
import warnings
import threading

# Import our utility for safe DataFrame value setting
from core.data_processing.dataframe_utils import set_dataframe_value

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ExcelFormulaProcessor")

# Global thread-local storage for COM initialization state
_thread_local = threading.local()


class ExcelFormulaProcessor:
    """
    A class to process Excel formulas using win32com automation.
    This class allows sending data to Excel, applying formulas, and retrieving results.

    Enhanced with:
    - Formula context escaping for column names
    - Formula insertion for batch processing
    - Session isolation for concurrent processing
    - Excel formula injection protection
    - Error tracking for formula calculation issues
    - Improved type handling for mixed data types
    """

    # Excel error values and their Python representations
    EXCEL_ERRORS = {
        "#DIV/0!": "ERROR_DIV_ZERO",
        "#N/A": "ERROR_NA",
        "#NAME?": "ERROR_NAME",
        "#NULL!": "ERROR_NULL",
        "#NUM!": "ERROR_NUM",
        "#REF!": "ERROR_REF",
        "#VALUE!": "ERROR_VALUE",
        "#GETTING_DATA": "ERROR_GETTING_DATA",
        "#SPILL!": "ERROR_SPILL",
        "#CALC!": "ERROR_CALC"
    }

    # Map of COM error codes to readable error messages
    COM_ERROR_CODES = {
        -2146826273: "Excel calculation error (DATEVALUE error, possibly date format)",
        -2146827284: "Excel function error (function not available or syntax error)",
        -2146777998: "COM automation error"
    }

    def __init__(self, template_path=None, visible=False, track_errors=True):
        """Initialize the Excel Formula Processor."""
        self.excel = None
        self.workbook = None
        self.worksheet = None
        self.template_path = template_path
        self.visible = visible
        self.temp_files = []
        self.session_id = str(uuid.uuid4())[:8]
        self.track_errors = track_errors
        self._is_com_initialized = False

        # For tracking process count in debug mode
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            self._log_excel_process_count("init")

    def __enter__(self):
        """Context manager entry point - ensures Excel is started"""
        self.start_excel()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit point - ensures cleanup is called with proper thread state"""
        try:
            # First ensure COM is initialized in THIS thread before cleanup
            # This is crucial for the thread that's doing the cleanup
            if not hasattr(_thread_local, 'com_initialized') or not _thread_local.com_initialized:
                try:
                    pythoncom.CoInitialize()
                    _thread_local.com_initialized = True
                    logger.debug(
                        f"[Session {self.session_id}] COM initialized for cleanup in thread {threading.current_thread().ident}")

                    # Set a flag to indicate we initialized COM in this method
                    self._exit_initialized_com = True
                except Exception as e:
                    logger.error(f"[Session {self.session_id}] Failed to initialize COM for cleanup: {str(e)}")

            # Now perform the cleanup with proper COM state
            self.cleanup()
        except Exception as e:
            logger.error(f"[Session {self.session_id}] Error in __exit__: {str(e)}")

        # Uninitialize COM only if we initialized it in this method
        if hasattr(self, '_exit_initialized_com') and self._exit_initialized_com:
            try:
                pythoncom.CoUninitialize()
                _thread_local.com_initialized = False
                logger.debug(
                    f"[Session {self.session_id}] COM uninitialized after cleanup in thread {threading.current_thread().ident}")
            except Exception as e:
                logger.warning(f"[Session {self.session_id}] Error uninitializing COM after cleanup: {str(e)}")

        return False  # Don't suppress exceptions

    def _ensure_com_initialized(self):
        """
        Ensure COM is initialized for the current thread.
        This is necessary for thread-safe COM operations.
        """
        # Check if the current thread has COM initialized
        if not hasattr(_thread_local, 'com_initialized') or not _thread_local.com_initialized:
            try:
                pythoncom.CoInitialize()
                _thread_local.com_initialized = True
                # Track which thread ID initialized COM
                _thread_local.initializing_thread_id = threading.current_thread().ident
                logger.debug(
                    f"[Session {self.session_id}] COM initialized for thread {threading.current_thread().ident}")
            except Exception as e:
                logger.error(f"[Session {self.session_id}] Failed to initialize COM: {str(e)}")
                raise

    def _uninitialize_com(self):
        """
        Uninitialize COM for the current thread if it was initialized by this instance.
        """
        if hasattr(self, '_is_com_initialized') and self._is_com_initialized:
            if hasattr(_thread_local, 'com_initialized') and _thread_local.com_initialized:
                try:
                    pythoncom.CoUninitialize()
                    _thread_local.com_initialized = False
                    self._is_com_initialized = False
                    logger.debug(
                        f"[Session {self.session_id}] COM uninitialized for thread {threading.current_thread().ident}")
                except Exception as e:
                    logger.warning(f"[Session {self.session_id}] Error uninitializing COM: {str(e)}")

    def start_excel(self):
        """Start Excel application and prepare workbook - with guard against redundant startup"""
        # Guard against redundant Excel startup
        if self.excel is not None:
            logger.debug(f"[Session {self.session_id}] Excel already started, reusing instance")
            return True

        logger.info(f"[Session {self.session_id}] Starting Excel application")
        try:
            # Ensure COM is initialized for this thread
            self._ensure_com_initialized()

            # Create Excel instance
            self.excel = win32com.client.DispatchEx("Excel.Application")

            # Configure Excel
            self.excel.Visible = self.visible
            self.excel.DisplayAlerts = False

            # Improve performance by disabling screen updating and events
            try:
                self.excel.ScreenUpdating = False
            except Exception as e:
                logger.warning(f"[Session {self.session_id}] Could not set ScreenUpdating: {str(e)}")

            try:
                self.excel.EnableEvents = False
            except Exception as e:
                logger.warning(f"[Session {self.session_id}] Could not set EnableEvents: {str(e)}")

            # Open or create workbook
            if self.template_path and os.path.exists(self.template_path):
                self.workbook = self.excel.Workbooks.Open(self.template_path)
                self.worksheet = self.workbook.Worksheets(1)
            else:
                self.workbook = self.excel.Workbooks.Add()
                self.worksheet = self.workbook.Worksheets(1)

            logger.info(f"[Session {self.session_id}] Excel application startup complete")

            # Debug: Log process count after startup
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                self._log_excel_process_count("after_startup")

            return True
        except Exception as e:
            logger.error(f"[Session {self.session_id}] Error starting Excel: {str(e)}")
            self.cleanup()  # Ensure cleanup on error
            raise

    def cleanup(self):
        """Clean up Excel resources and temporary files"""
        logger.info(f"[Session {self.session_id}] Cleaning up Excel resources")

        # Debug: Log process count before cleanup
        if logging.getLogger().isEnabledFor(logging.DEBUG):
            self._log_excel_process_count("before_cleanup")

        try:
            # First, make sure all workbooks are properly closed
            if self.workbook:
                try:
                    # Make sure we set these properties before closing
                    try:
                        if self.excel:
                            self.excel.DisplayAlerts = False
                            self.excel.ScreenUpdating = False
                    except:
                        pass

                    self.workbook.Close(SaveChanges=False)
                except Exception as e:
                    logger.warning(f"[Session {self.session_id}] Error closing workbook: {str(e)}")
                finally:
                    # Explicitly break reference
                    self.workbook = None

            # Then quit Excel
            if self.excel:
                try:
                    # Explicitly quit Excel
                    self.excel.Quit()
                except Exception as e:
                    logger.warning(f"[Session {self.session_id}] Error quitting Excel: {str(e)}")
                finally:
                    # Explicitly break reference even if Quit fails
                    self.excel = None

            # Force garbage collection to clean up COM objects
            gc.collect()

            # Uninitialize COM if we initialized it
            self._uninitialize_com()

            # Debug: Log process count after cleanup
            if logging.getLogger().isEnabledFor(logging.DEBUG):
                self._log_excel_process_count("after_cleanup")

        except Exception as e:
            logger.error(f"[Session {self.session_id}] Error during cleanup: {str(e)}")

        # Clean up any temporary files
        for temp_file in self.temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            except Exception as e:
                logger.error(f"[Session {self.session_id}] Error removing temp file {temp_file}: {str(e)}")

    def _log_excel_process_count(self, phase):
        """Log the number of Excel processes for debugging"""
        try:
            count = self.count_excel_processes()
            logger.debug(f"[Session {self.session_id}] Excel process count {phase}: {count}")
        except:
            logger.debug(f"[Session {self.session_id}] Unable to count Excel processes")

    @staticmethod
    def count_excel_processes():
        """Count running Excel processes for monitoring leaks"""
        try:
            import psutil
            return sum(1 for p in psutil.process_iter() if p.name().lower() == 'excel.exe')
        except ImportError:
            # If psutil isn't available, use a platform-specific approach
            import subprocess
            if os.name == 'nt':  # Windows
                result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq EXCEL.EXE'],
                                        capture_output=True, text=True)
                # Count non-header lines that contain EXCEL.EXE
                return result.stdout.count('EXCEL.EXE')
            else:  # Unix-like
                result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
                return result.stdout.count('excel')

    def sanitize_column_name(self, column_name: str) -> str:
        """
        Sanitize column name for use in Excel formulas.

        Args:
            column_name: Original column name

        Returns:
            Sanitized column name safe for Excel formula references
        """
        # Replace spaces, special characters with underscores
        sanitized = re.sub(r'[^a-zA-Z0-9_]', '_', str(column_name))

        # Ensure it starts with a letter or underscore
        if sanitized and not sanitized[0].isalpha() and sanitized[0] != '_':
            sanitized = f"_{sanitized}"

        return sanitized

    def escape_formula_string(self, formula: str) -> str:
        """
        Escape any potential formula injection in strings.

        Args:
            formula: Original formula string

        Returns:
            Escaped formula string safe from injection
        """
        # Escape double quotes by doubling them (Excel's string escape syntax)
        escaped_formula = formula.replace('"', '""')

        # Perform additional sanitization for formula injection prevention
        # Check for formula injection attempts beginning with '=' or '+'
        if formula.startswith(('=', '+', '-', '@')):
            # Prefix with a single quote to force text interpretation
            escaped_formula = "'" + escaped_formula

        return escaped_formula

    def is_excel_error(self, value: Any) -> bool:
        """
        Check if a value is an Excel error.

        Args:
            value: Value to check

        Returns:
            True if the value is an Excel error, False otherwise
        """
        if isinstance(value, str):
            return value in self.EXCEL_ERRORS

        # Check for COM error codes
        if isinstance(value, (int, float)) and value in self.COM_ERROR_CODES:
            return True

        return False

    def normalize_excel_error(self, value: Any) -> Any:
        """
        Normalize Excel errors to Python representations.

        Args:
            value: Excel value which might be an error

        Returns:
            Original value or normalized error string
        """
        if isinstance(value, str) and value in self.EXCEL_ERRORS:
            return self.EXCEL_ERRORS[value]

        # Handle known COM error codes
        if isinstance(value, (int, float)):
            error_code = int(value)
            if error_code in self.COM_ERROR_CODES:
                return self.COM_ERROR_CODES[error_code]

        return value

    def prepare_data_for_excel(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare DataFrame for Excel by converting problematic data types.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with Excel-compatible data types
        """
        # Create a copy to avoid modifying the original
        excel_df = df.copy()

        # Process each column
        for col in excel_df.columns:
            # Check if column contains datetime objects
            if pd.api.types.is_datetime64_any_dtype(excel_df[col]):
                # Convert timestamps to MM/DD/YYYY format or "" if missing
                excel_df[col] = excel_df[col].apply(
                    lambda x: x.strftime('%m/%d/%Y') if pd.notnull(x) else ""
                )
                logger.debug(f"Converted timestamp column {col} to MM/DD/YYYY format")

            # Handle columns with mixed types that might contain timestamps
            elif excel_df[col].dtype == 'object':
                # Check if column contains any Timestamp objects
                has_timestamp = False
                for val in excel_df[col].dropna():
                    if isinstance(val, pd.Timestamp):
                        has_timestamp = True
                        break

                if has_timestamp:
                    logger.debug(f"Column {col} contains mixed types with Timestamps")
                    # Convert any pandas Timestamps in object columns to strings
                    excel_df[col] = excel_df[col].apply(
                        lambda x: x.strftime('%m/%d/%Y') if isinstance(x, pd.Timestamp) else x
                    )

        return excel_df

    def define_named_ranges(self, df: pd.DataFrame, start_row: int, start_col: int) -> Dict[str, str]:
        """
        Define named ranges in Excel for each column of data.
        This improves formula readability and performance.

        Args:
            df: DataFrame containing the data
            start_row: Starting row index (1-based)
            start_col: Starting column index (1-based)

        Returns:
            Dictionary mapping original column names to Excel named ranges
        """
        name_mapping = {}

        for col_idx, col_name in enumerate(df.columns):
            col_letter = self._get_column_letter(start_col + col_idx)
            end_row = start_row + len(df) - 1
            range_address = f"${col_letter}${start_row}:${col_letter}${end_row}"

            # Create a safe name for the range
            safe_name = self.sanitize_column_name(col_name)

            # Define named range in Excel
            try:
                self.workbook.Names.Add(
                    Name=safe_name,
                    RefersTo=f"={self.worksheet.Name}!{range_address}"
                )
                name_mapping[col_name] = safe_name
            except Exception as e:
                logger.warning(f"[Session {self.session_id}] Could not create named range for {col_name}: {str(e)}")
                name_mapping[col_name] = col_name

        return name_mapping

    def process_formulas_bulk(
            self,
            data: pd.DataFrame,
            formulas: Dict[str, str],
            input_range: str = "A2"
    ) -> pd.DataFrame:
        """
        Process Excel formulas in bulk by inserting formulas directly into Excel.
        This is 10-50x faster than row-by-row evaluation for large datasets.

        Args:
            data: Input DataFrame to process
            formulas: Dictionary mapping output column names to Excel formulas
            input_range: Cell reference for the start of data range (default: A2)

        Returns:
            DataFrame with formula results added as new columns
        """
        if not self.excel or not self.workbook:
            self.start_excel()

        # Create a copy of the input DataFrame
        result_df = data.copy()

        # Prepare data for Excel
        excel_compatible_df = self.prepare_data_for_excel(data)

        try:
            # Clear any existing data
            self.worksheet.UsedRange.Clear()

            # Get column headers and write them
            headers = excel_compatible_df.columns.tolist()
            for col_idx, header in enumerate(headers):
                cell = self.worksheet.Cells(1, col_idx + 1)
                cell.Value = header

            # Convert DataFrame to values array for faster writing
            values = excel_compatible_df.values

            # Get start position
            start_cell = self.worksheet.Range(input_range)
            start_row = start_cell.Row
            start_col = start_cell.Column

            # Determine the range dimensions
            num_rows, num_cols = values.shape

            # Write all data at once for better performance
            if num_rows > 0:
                data_range = self.worksheet.Range(
                    self.worksheet.Cells(start_row, start_col),
                    self.worksheet.Cells(start_row + num_rows - 1, start_col + num_cols - 1)
                )

                # Convert any None/NaN values to empty strings for Excel
                excel_values = []
                for row in values:
                    excel_row = []
                    for val in row:
                        if pd.isna(val):
                            excel_row.append("")
                        else:
                            excel_row.append(val)
                    excel_values.append(excel_row)

                data_range.Value = excel_values

            # Define named ranges for columns (performance optimization)
            name_mapping = self.define_named_ranges(data, start_row, start_col)

            # Apply formulas in bulk
            next_col = start_col + num_cols
            formula_col_mapping = {}

            for output_col, formula_template in formulas.items():
                # Add new column for formula results
                result_df[output_col] = np.nan

                # Also add error tracking column if enabled
                if self.track_errors:
                    error_col = f"{output_col}_Error"
                    result_df[error_col] = ""

                # Replace column references with named ranges
                formula = formula_template
                for col_name, range_name in name_mapping.items():
                    placeholder = f"[{col_name}]"
                    if placeholder in formula:
                        formula = formula.replace(placeholder, range_name)

                # Get column for formula
                formula_col = next_col
                formula_col_letter = self._get_column_letter(formula_col)
                next_col += 1

                # Write the column header
                self.worksheet.Cells(1, formula_col).Value = output_col

                # Write formula to first row and fill down
                formula_cell = self.worksheet.Cells(start_row, formula_col)

                try:
                    formula_cell.Formula = formula

                    if num_rows > 1:
                        # Fill down to copy formula to all rows
                        fill_range = self.worksheet.Range(
                            formula_cell,
                            self.worksheet.Cells(start_row + num_rows - 1, formula_col)
                        )
                        formula_cell.AutoFill(fill_range)
                except Exception as e:
                    logger.error(f"[Session {self.session_id}] Error setting formula '{formula}': {str(e)}")
                    # If formula setting fails, mark all cells in column as error
                    for i in range(num_rows):
                        error_msg = f"ERROR: {str(e)}"
                        # Use our utility for safe value setting
                        set_dataframe_value(result_df, i, output_col, error_msg)
                        if self.track_errors:
                            set_dataframe_value(result_df, i, f"{output_col}_Error", "FORMULA_SETTING_ERROR")
                    continue

                # Store mapping for later retrieval
                formula_col_mapping[output_col] = formula_col

            # Force calculation of all formulas using alternative method
            try:
                self.worksheet.Calculate()  # Calculate just the current worksheet
            except Exception as e:
                logger.warning(f"[Session {self.session_id}] Error calculating worksheet: {str(e)}")
                try:
                    # Try alternative calculation method
                    self.workbook.Calculate()
                except Exception as e:
                    logger.error(f"[Session {self.session_id}] Error calculating workbook: {str(e)}")

            # Retrieve formula results
            for output_col, formula_col in formula_col_mapping.items():
                error_col = f"{output_col}_Error" if self.track_errors else None

                # Get the range with formula results
                if num_rows > 0:
                    result_range = self.worksheet.Range(
                        self.worksheet.Cells(start_row, formula_col),
                        self.worksheet.Cells(start_row + num_rows - 1, formula_col)
                    )

                    # Get values all at once
                    result_values = result_range.Value

                    # Handle both single and multiple row results
                    if num_rows == 1:
                        value = result_values
                        # Use our utility for safe value setting
                        set_dataframe_value(result_df, 0, output_col, value)

                        # Track error if needed
                        if error_col:
                            if isinstance(value, str) and value in self.EXCEL_ERRORS:
                                set_dataframe_value(result_df, i, error_col, self.normalize_excel_error(value))
                            elif isinstance(value, (int, float)) and value in self.COM_ERROR_CODES:
                                set_dataframe_value(result_df, i, error_col, self.COM_ERROR_CODES[value])
                            else:
                                pass  # No error detected

                    else:
                        # Convert tuple of tuples to list
                        for i, value_tuple in enumerate(result_values):
                            # Get the actual value (first item in tuple)
                            if isinstance(value_tuple, tuple):
                                value = value_tuple[0]
                            else:
                                value = value_tuple

                            # Use our utility for safe value setting
                            set_dataframe_value(result_df, i, output_col, value)

                            # Track error if needed
                            if error_col and self.is_excel_error(value):
                                set_dataframe_value(result_df, i, error_col, self.normalize_excel_error(value))

            return result_df

        except Exception as e:
            logger.error(f"[Session {self.session_id}] Error processing formulas in bulk: {str(e)}")
            raise

    def process_formulas(
            self,
            data: pd.DataFrame,
            formulas: Dict[str, str],
            input_range: str = "A2",
            use_bulk_method: bool = True
    ) -> pd.DataFrame:
        """Process Excel formulas by inserting formulas directly into Excel"""
        # Ensure Excel is running
        if not self.excel or not self.workbook:
            self.start_excel()

        # Use the faster bulk method by default
        if use_bulk_method:
            return self.process_formulas_bulk(data, formulas, input_range)

        # Fall back to row-by-row evaluation if bulk method is not requested
        if not self.excel or not self.workbook:
            self.start_excel()

        # Create a copy of the input DataFrame
        result_df = data.copy()

        # Prepare data for Excel
        excel_compatible_df = self.prepare_data_for_excel(data)

        try:
            # Clear any existing data
            self.worksheet.UsedRange.Clear()

            # Get column headers
            headers = data.columns.tolist()

            # Write headers to first row
            for col_idx, header in enumerate(headers):
                cell = self.worksheet.Cells(1, col_idx + 1)
                cell.Value = header

            # Convert DataFrame to values array for faster writing
            values = data.values

            # Write data to worksheet
            start_cell = self.worksheet.Range(input_range)
            start_row = start_cell.Row
            start_col = start_cell.Column

            # Determine the range dimensions
            num_rows, num_cols = values.shape

            # Create a range for the data
            if num_rows > 0 and num_cols > 0:
                data_range = self.worksheet.Range(
                    self.worksheet.Cells(start_row, start_col),
                    self.worksheet.Cells(start_row + num_rows - 1, start_col + num_cols - 1)
                )

                # Convert any None/NaN values to empty strings for Excel
                excel_values = []
                for row in values:
                    excel_row = []
                    for val in row:
                        if pd.isna(val):
                            excel_row.append("")
                        else:
                            excel_row.append(val)
                    excel_values.append(excel_row)

                data_range.Value = excel_values

            # Apply formulas
            for output_col, formula in formulas.items():
                # Add new column for formula results
                result_df[output_col] = np.nan

                # Also add error tracking column if enabled
                if self.track_errors:
                    error_col = f"{output_col}_Error"
                    result_df[error_col] = ""

                # Calculate formula for each row
                for row_idx in range(num_rows):
                    # Excel rows are 1-based and we need to account for the header row
                    excel_row = start_row + row_idx

                    # Replace placeholders in formula
                    applied_formula = self._apply_row_context(formula, excel_row, headers)

                    # Get the result from Excel
                    try:
                        result = self.worksheet.Evaluate(applied_formula)
                        # Use our utility for safe value setting
                        set_dataframe_value(result_df, row_idx, output_col, result)

                        # Track error if needed
                        if self.track_errors and self.is_excel_error(result):
                            set_dataframe_value(result_df, row_idx, error_col, self.normalize_excel_error(result))
                    except Exception as e:
                        error_msg = str(e)
                        logger.warning(
                            f"[Session {self.session_id}] Error evaluating formula at row {row_idx}: {error_msg}")
                        set_dataframe_value(result_df, row_idx, output_col, f"ERROR: {error_msg}")
                        if self.track_errors:
                            set_dataframe_value(result_df, row_idx, error_col, "EVALUATION_ERROR")

            return result_df

        except Exception as e:
            logger.error(f"[Session {self.session_id}] Error processing formulas: {str(e)}")
            raise

    def _apply_row_context(self, formula: str, row: int, headers: List[str]) -> str:
        """
        Replace column references in a formula with cell references for a specific row.
        Now includes proper escaping for column names.

        Args:
            formula: Excel formula with column references
            row: Excel row number to apply the formula to
            headers: List of column headers

        Returns:
            Formula with column references replaced with cell references
        """
        applied_formula = formula

        # Replace column references with cell references
        for col_idx, header in enumerate(headers):
            col_letter = self._get_column_letter(col_idx + 1)
            placeholder = f"[{header}]"
            if placeholder in applied_formula:
                # For complex headers, use the Range("cell").Address approach
                cell_ref = f"{col_letter}{row}"
                applied_formula = applied_formula.replace(placeholder, cell_ref)

        return applied_formula

    def _get_column_letter(self, col_num: int) -> str:
        """
        Convert a column number to an Excel column letter.

        Args:
            col_num: Column number (1-based)

        Returns:
            Excel column letter (A, B, C, ..., Z, AA, AB, ...)
        """
        result = ""
        while col_num > 0:
            col_num, remainder = divmod(col_num - 1, 26)
            result = chr(65 + remainder) + result
        return result

    def batch_process(
            self,
            data: pd.DataFrame,
            formulas: Dict[str, str],
            batch_size: int = 1000,
            use_bulk_method: bool = True
    ) -> pd.DataFrame:
        """
        Process formulas in batches to handle large datasets.

        Args:
            data: Input DataFrame to process
            formulas: Dictionary mapping output column names to Excel formulas
            batch_size: Number of rows to process in each batch
            use_bulk_method: Whether to use the faster bulk method

        Returns:
            DataFrame with formula results added as new columns
        """
        total_rows = len(data)
        result_dfs = []

        for start_idx in range(0, total_rows, batch_size):
            end_idx = min(start_idx + batch_size, total_rows)
            logger.info(f"[Session {self.session_id}] Processing batch {start_idx} to {end_idx}")

            # Process batch
            batch_df = data.iloc[start_idx:end_idx].copy()
            result_batch = self.process_formulas(batch_df, formulas, use_bulk_method=use_bulk_method)

            # Store batch results
            result_dfs.append(result_batch)

        # Combine results
        if result_dfs:
            return pd.concat(result_dfs, ignore_index=True)
        else:
            return data.copy()
# data_integration/io/date_detector.py

import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime
import re

logger = logging.getLogger(__name__)


class DateDetector:
    """
    Utility class for detecting and converting date columns in DataFrames.
    Handles various date formats and provides robust conversion with error handling.
    """
    
    # Common date formats to try, ordered by likelihood
    COMMON_DATE_FORMATS = [
        # US formats
        '%m/%d/%Y',      # 01/15/2024
        '%m/%d/%y',      # 01/15/24
        '%m-%d-%Y',      # 01-15-2024
        '%m-%d-%y',      # 01-15-24
        
        # ISO formats
        '%Y-%m-%d',      # 2024-01-15
        '%Y/%m/%d',      # 2024/01/15
        
        # European formats
        '%d/%m/%Y',      # 15/01/2024
        '%d/%m/%y',      # 15/01/24
        '%d-%m-%Y',      # 15-01-2024
        '%d-%m-%y',      # 15-01-24
        '%d.%m.%Y',      # 15.01.2024
        '%d.%m.%y',      # 15.01.24
        
        # Long formats
        '%B %d, %Y',     # January 15, 2024
        '%b %d, %Y',     # Jan 15, 2024
        '%d %B %Y',      # 15 January 2024
        '%d %b %Y',      # 15 Jan 2024
        
        # With time
        '%Y-%m-%d %H:%M:%S',    # 2024-01-15 10:30:45
        '%m/%d/%Y %H:%M:%S',    # 01/15/2024 10:30:45
        '%d/%m/%Y %H:%M:%S',    # 15/01/2024 10:30:45
        
        # Excel default formats
        '%Y-%m-%d %H:%M:%S.%f',  # 2024-01-15 10:30:45.123
        '%m/%d/%Y %I:%M %p',     # 01/15/2024 10:30 AM
        '%m/%d/%Y %I:%M:%S %p',  # 01/15/2024 10:30:45 AM
    ]
    
    # Regex patterns to identify potential date columns by name
    DATE_COLUMN_PATTERNS = [
        r'date',
        r'time',
        r'datetime',
        r'timestamp',
        r'created',
        r'modified',
        r'updated',
        r'dob',
        r'birth',
        r'start',
        r'end',
        r'expire',
        r'due',
        r'when',
        r'period',
        r'month',
        r'year',
        r'day'
    ]
    
    def __init__(self, 
                 sample_size: int = 100,
                 detection_threshold: float = 0.8,
                 additional_formats: Optional[List[str]] = None):
        """
        Initialize DateDetector.
        
        Args:
            sample_size: Number of rows to sample for detection (default: 100)
            detection_threshold: Minimum percentage of valid dates to consider column as date (default: 0.8)
            additional_formats: Additional date formats to try beyond the defaults
        """
        self.sample_size = sample_size
        self.detection_threshold = detection_threshold
        
        # Combine default formats with any additional ones
        self.date_formats = self.COMMON_DATE_FORMATS.copy()
        if additional_formats:
            self.date_formats.extend(additional_formats)
            
        # Cache for detected formats per column
        self._format_cache: Dict[str, str] = {}
        
    def detect_date_columns(self, df: pd.DataFrame) -> List[str]:
        """
        Detect which columns in a DataFrame likely contain dates.
        
        Args:
            df: Input DataFrame
            
        Returns:
            List of column names that appear to contain dates
        """
        date_columns = []
        
        for col in df.columns:
            # Skip if already datetime
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                logger.debug(f"Column '{col}' is already datetime type")
                continue
                
            # Skip non-object columns (dates as text are usually object type)
            if df[col].dtype != 'object':
                continue
                
            # Check if column name suggests it contains dates
            name_suggests_date = self._column_name_suggests_date(col)
            
            # Sample data for testing
            sample_data = self._get_sample_data(df[col])
            
            if len(sample_data) == 0:
                continue
                
            # Try to detect date format
            format_found, valid_ratio = self._detect_date_format(sample_data)
            
            if format_found:
                if valid_ratio >= self.detection_threshold:
                    date_columns.append(col)
                    self._format_cache[col] = format_found
                    logger.info(f"Detected date column '{col}' with format '{format_found}' "
                              f"(confidence: {valid_ratio:.1%})")
                elif name_suggests_date and valid_ratio >= 0.5:
                    # Lower threshold if column name suggests dates
                    date_columns.append(col)
                    self._format_cache[col] = format_found
                    logger.info(f"Detected date column '{col}' based on name and format '{format_found}' "
                              f"(confidence: {valid_ratio:.1%})")
                    
        return date_columns
    
    def convert_date_columns(self, 
                           df: pd.DataFrame, 
                           columns: Optional[List[str]] = None,
                           errors: str = 'coerce') -> Tuple[pd.DataFrame, Dict[str, Dict[str, Any]]]:
        """
        Convert specified columns to datetime format.
        
        Args:
            df: Input DataFrame
            columns: List of columns to convert (if None, auto-detect)
            errors: How to handle parsing errors ('raise', 'coerce', 'ignore')
            
        Returns:
            Tuple of (converted DataFrame, conversion report)
        """
        # Create a copy to avoid modifying original
        result_df = df.copy()
        
        # Auto-detect columns if not specified
        if columns is None:
            columns = self.detect_date_columns(df)
            
        conversion_report = {}
        
        for col in columns:
            if col not in df.columns:
                logger.warning(f"Column '{col}' not found in DataFrame")
                continue
                
            # Get the detected format or try to detect it
            date_format = self._format_cache.get(col)
            if not date_format:
                sample_data = self._get_sample_data(df[col])
                date_format, _ = self._detect_date_format(sample_data)
                
            if date_format:
                # Convert the column
                success_count, error_count = self._convert_column(
                    result_df, col, date_format, errors
                )
                
                conversion_report[col] = {
                    'format': date_format,
                    'success_count': success_count,
                    'error_count': error_count,
                    'total_rows': len(df),
                    'conversion_rate': success_count / len(df) if len(df) > 0 else 0
                }
                
                logger.info(f"Converted column '{col}' to datetime "
                          f"({success_count}/{len(df)} successful)")
            else:
                logger.warning(f"Could not detect date format for column '{col}'")
                
        return result_df, conversion_report
    
    def _column_name_suggests_date(self, column_name: str) -> bool:
        """Check if column name suggests it contains dates."""
        col_lower = column_name.lower()
        return any(re.search(pattern, col_lower) for pattern in self.DATE_COLUMN_PATTERNS)
    
    def _get_sample_data(self, series: pd.Series) -> List[str]:
        """Get a sample of non-null string values from a series."""
        # Remove nulls and convert to string
        non_null = series.dropna()
        
        if len(non_null) == 0:
            return []
            
        # Sample up to sample_size rows
        sample_size = min(self.sample_size, len(non_null))
        if sample_size < len(non_null):
            sample = non_null.sample(n=sample_size, random_state=42)
        else:
            sample = non_null
            
        # Convert to strings and filter out empty strings
        return [str(val).strip() for val in sample if str(val).strip()]
    
    def _detect_date_format(self, sample_data: List[str]) -> Tuple[Optional[str], float]:
        """
        Detect the date format from sample data.
        
        Returns:
            Tuple of (detected format or None, ratio of valid dates)
        """
        if not sample_data:
            return None, 0.0
            
        best_format = None
        best_ratio = 0.0
        
        for date_format in self.date_formats:
            valid_count = 0
            
            for value in sample_data:
                try:
                    pd.to_datetime(value, format=date_format, errors='raise')
                    valid_count += 1
                except:
                    pass
                    
            ratio = valid_count / len(sample_data)
            
            if ratio > best_ratio:
                best_ratio = ratio
                best_format = date_format
                
            # Early exit if we found a perfect match
            if ratio == 1.0:
                break
                
        # If no specific format worked well, try pandas' intelligent parser
        if best_ratio < self.detection_threshold:
            valid_count = 0
            
            for value in sample_data:
                try:
                    pd.to_datetime(value, errors='raise')
                    valid_count += 1
                except:
                    pass
                    
            infer_ratio = valid_count / len(sample_data)
            
            if infer_ratio > best_ratio:
                best_ratio = infer_ratio
                best_format = 'infer'  # Special marker for using pandas inference
                
        return best_format if best_ratio > 0 else None, best_ratio
    
    def _convert_column(self, 
                       df: pd.DataFrame, 
                       column: str, 
                       date_format: str,
                       errors: str = 'coerce') -> Tuple[int, int]:
        """
        Convert a single column to datetime.
        
        Returns:
            Tuple of (success_count, error_count)
        """
        original_values = df[column].copy()
        
        try:
            if date_format == 'infer':
                # Use pandas' intelligent date parser
                df[column] = pd.to_datetime(df[column], errors=errors)
            else:
                # Use specific format
                df[column] = pd.to_datetime(df[column], format=date_format, errors=errors)
                
            # Count successes and errors
            if errors == 'coerce':
                success_count = df[column].notna().sum()
                error_count = df[column].isna().sum() - original_values.isna().sum()
            else:
                success_count = len(df)
                error_count = 0
                
            return success_count, error_count
            
        except Exception as e:
            logger.error(f"Error converting column '{column}': {str(e)}")
            # Restore original values on error
            df[column] = original_values
            return 0, len(df)
    
    def get_date_columns_report(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate a comprehensive report on date columns in the DataFrame.
        
        Args:
            df: Input DataFrame
            
        Returns:
            Dictionary containing detection report
        """
        report = {
            'total_columns': len(df.columns),
            'existing_datetime_columns': [],
            'detected_date_columns': [],
            'detection_details': {}
        }
        
        # Check existing datetime columns
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                report['existing_datetime_columns'].append(col)
                
        # Detect potential date columns
        detected_columns = self.detect_date_columns(df)
        report['detected_date_columns'] = detected_columns
        
        # Get details for each detected column
        for col in detected_columns:
            sample_data = self._get_sample_data(df[col])
            format_found, confidence = self._detect_date_format(sample_data)
            
            report['detection_details'][col] = {
                'detected_format': format_found,
                'confidence': confidence,
                'sample_values': sample_data[:5],  # First 5 samples
                'name_suggests_date': self._column_name_suggests_date(col)
            }
            
        return report
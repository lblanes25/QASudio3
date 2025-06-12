# tests/unit/data_integration/test_date_detector.py

import unittest
import pandas as pd
import numpy as np
from datetime import datetime, date
import tempfile
import os

from data_integration.io.date_detector import DateDetector


class TestDateDetector(unittest.TestCase):
    """Unit tests for DateDetector class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.detector = DateDetector()
        
    def test_detect_date_columns_basic(self):
        """Test basic date column detection."""
        # Create test DataFrame with various date formats
        df = pd.DataFrame({
            'id': [1, 2, 3],
            'start_date': ['01/15/2024', '02/20/2024', '03/25/2024'],
            'end_date': ['2024-01-20', '2024-02-25', '2024-03-30'],
            'created_at': ['Jan 15, 2024', 'Feb 20, 2024', 'Mar 25, 2024'],
            'not_a_date': ['ABC123', 'DEF456', 'GHI789'],
            'amount': [100.50, 200.75, 300.25]
        })
        
        detected = self.detector.detect_date_columns(df)
        
        # Should detect the date columns but not the others
        self.assertIn('start_date', detected)
        self.assertIn('end_date', detected)
        self.assertIn('created_at', detected)
        self.assertNotIn('not_a_date', detected)
        self.assertNotIn('amount', detected)
        self.assertNotIn('id', detected)
        
    def test_convert_date_columns(self):
        """Test date column conversion."""
        df = pd.DataFrame({
            'us_date': ['01/15/2024', '02/20/2024', '03/25/2024'],
            'iso_date': ['2024-01-20', '2024-02-25', '2024-03-30'],
            'text': ['apple', 'banana', 'cherry']
        })
        
        # Convert specific columns
        result_df, report = self.detector.convert_date_columns(
            df, 
            columns=['us_date', 'iso_date']
        )
        
        # Check conversions
        self.assertEqual(result_df['us_date'].dtype, 'datetime64[ns]')
        self.assertEqual(result_df['iso_date'].dtype, 'datetime64[ns]')
        self.assertEqual(result_df['text'].dtype, 'object')
        
        # Check report
        self.assertEqual(report['us_date']['success_count'], 3)
        self.assertEqual(report['us_date']['error_count'], 0)
        self.assertEqual(report['iso_date']['success_count'], 3)
        self.assertEqual(report['iso_date']['error_count'], 0)
        
    def test_mixed_valid_invalid_dates(self):
        """Test handling of mixed valid and invalid dates."""
        df = pd.DataFrame({
            'mixed_dates': ['01/15/2024', 'Not a date', '02/20/2024', None, '03/25/2024']
        })
        
        result_df, report = self.detector.convert_date_columns(
            df, 
            columns=['mixed_dates'],
            errors='coerce'
        )
        
        # Should convert valid dates and set invalid ones to NaT
        self.assertEqual(result_df['mixed_dates'].dtype, 'datetime64[ns]')
        self.assertFalse(pd.isna(result_df['mixed_dates'].iloc[0]))  # Valid date
        self.assertTrue(pd.isna(result_df['mixed_dates'].iloc[1]))   # Invalid date
        self.assertFalse(pd.isna(result_df['mixed_dates'].iloc[2]))  # Valid date
        self.assertTrue(pd.isna(result_df['mixed_dates'].iloc[3]))   # None
        self.assertFalse(pd.isna(result_df['mixed_dates'].iloc[4]))  # Valid date
        
        # Check report
        self.assertEqual(report['mixed_dates']['success_count'], 3)
        self.assertEqual(report['mixed_dates']['error_count'], 1)  # 'Not a date' is error
        
    def test_various_date_formats(self):
        """Test detection of various date formats."""
        df = pd.DataFrame({
            'us_slash': ['01/15/2024', '02/20/2024'],
            'us_dash': ['01-15-2024', '02-20-2024'],
            'iso': ['2024-01-15', '2024-02-20'],
            'euro_dot': ['15.01.2024', '20.02.2024'],
            'long_format': ['January 15, 2024', 'February 20, 2024'],
            'short_month': ['Jan 15, 2024', 'Feb 20, 2024'],
            'with_time': ['2024-01-15 10:30:45', '2024-02-20 14:15:00']
        })
        
        detected = self.detector.detect_date_columns(df)
        
        # All columns should be detected as dates
        self.assertEqual(len(detected), 7)
        for col in df.columns:
            self.assertIn(col, detected)
            
    def test_column_name_detection(self):
        """Test detection based on column names."""
        df = pd.DataFrame({
            'transaction_date': ['ABC', 'DEF'],  # Not valid dates but name suggests date
            'created_timestamp': ['XYZ', '123'],
            'modified_time': ['!!!', '@@@'],
            'regular_column': ['AAA', 'BBB']
        })
        
        # Create detector with lower threshold
        detector = DateDetector(detection_threshold=0.5)
        
        # Test column name suggestion
        self.assertTrue(detector._column_name_suggests_date('transaction_date'))
        self.assertTrue(detector._column_name_suggests_date('created_timestamp'))
        self.assertTrue(detector._column_name_suggests_date('modified_time'))
        self.assertFalse(detector._column_name_suggests_date('regular_column'))
        
    def test_custom_date_formats(self):
        """Test adding custom date formats."""
        df = pd.DataFrame({
            'custom_date': ['2024|01|15', '2024|02|20', '2024|03|25']
        })
        
        # Create detector with custom format
        detector = DateDetector(additional_formats=['%Y|%m|%d'])
        
        detected = detector.detect_date_columns(df)
        self.assertIn('custom_date', detected)
        
        # Convert and verify
        result_df, _ = detector.convert_date_columns(df)
        self.assertEqual(result_df['custom_date'].dtype, 'datetime64[ns]')
        
    def test_detection_report(self):
        """Test comprehensive detection report generation."""
        df = pd.DataFrame({
            'date1': pd.date_range('2024-01-01', periods=3),  # Already datetime
            'date2': ['01/15/2024', '02/20/2024', '03/25/2024'],  # Will be detected
            'text': ['apple', 'banana', 'cherry']  # Not a date
        })
        
        report = self.detector.get_date_columns_report(df)
        
        # Check report structure
        self.assertEqual(report['total_columns'], 3)
        self.assertIn('date1', report['existing_datetime_columns'])
        self.assertIn('date2', report['detected_date_columns'])
        self.assertNotIn('text', report['detected_date_columns'])
        
        # Check detection details
        self.assertIn('date2', report['detection_details'])
        details = report['detection_details']['date2']
        self.assertIsNotNone(details['detected_format'])
        self.assertGreater(details['confidence'], 0.8)
        
    def test_performance_sampling(self):
        """Test that sampling works correctly for large datasets."""
        # Create large DataFrame
        n_rows = 10000
        df = pd.DataFrame({
            'dates': ['01/15/2024'] * n_rows,
            'values': range(n_rows)
        })
        
        # Detector should only sample, not process all rows
        detector = DateDetector(sample_size=100)
        
        # This should be fast due to sampling
        detected = detector.detect_date_columns(df)
        self.assertIn('dates', detected)
        
    def test_empty_dataframe(self):
        """Test handling of empty DataFrame."""
        df = pd.DataFrame()
        
        detected = self.detector.detect_date_columns(df)
        self.assertEqual(len(detected), 0)
        
        result_df, report = self.detector.convert_date_columns(df)
        self.assertEqual(len(report), 0)
        
    def test_null_values(self):
        """Test handling of null values in date columns."""
        df = pd.DataFrame({
            'dates': ['01/15/2024', None, '02/20/2024', pd.NA, '03/25/2024']
        })
        
        result_df, report = self.detector.convert_date_columns(df, columns=['dates'])
        
        # Should handle nulls gracefully
        self.assertEqual(result_df['dates'].dtype, 'datetime64[ns]')
        self.assertTrue(pd.isna(result_df['dates'].iloc[1]))  # None
        self.assertTrue(pd.isna(result_df['dates'].iloc[3]))  # pd.NA
        
        # Success count should only include actual conversions
        self.assertEqual(report['dates']['success_count'], 3)


if __name__ == '__main__':
    unittest.main()
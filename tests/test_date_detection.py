# tests/test_date_detection.py

import pandas as pd
import numpy as np
from datetime import datetime
import tempfile
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_integration.io import DataImporter, DateDetector


def create_test_csv_with_dates():
    """Create a test CSV file with various date formats."""
    data = {
        'ID': [1, 2, 3, 4, 5],
        'Name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'Start_Date': ['01/15/2024', '02/20/2024', '03/25/2024', '04/30/2024', '05/05/2024'],
        'End_Date': ['2024-01-20', '2024-02-25', '2024-03-30', '2024-05-05', '2024-05-10'],
        'Birth_Date': ['Jan 15, 1990', 'Feb 20, 1985', 'Mar 25, 1992', 'Apr 30, 1988', 'May 5, 1995'],
        'Last_Modified': ['15.01.2024 10:30:45', '20.02.2024 14:15:00', '25.03.2024 09:45:30', 
                         '30.04.2024 16:20:15', '05.05.2024 11:00:00'],
        'Amount': [1000.50, 2000.75, 1500.25, 3000.00, 2500.50],
        'Status': ['Active', 'Inactive', 'Active', 'Pending', 'Active']
    }
    
    df = pd.DataFrame(data)
    
    # Create temporary CSV file
    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
    df.to_csv(temp_file.name, index=False)
    temp_file.close()
    
    return temp_file.name, df


def test_date_detection():
    """Test the date detection functionality."""
    print("Testing Date Detection and Conversion")
    print("=" * 50)
    
    # Create test data
    csv_file, original_df = create_test_csv_with_dates()
    print(f"Created test CSV file: {csv_file}")
    
    try:
        # Test 1: Load with automatic date detection
        print("\nTest 1: Loading with automatic date detection")
        df_auto = DataImporter.load_file(csv_file, detect_dates=True)
        
        print("\nColumn types after loading:")
        for col in df_auto.columns:
            print(f"  {col}: {df_auto[col].dtype}")
        
        # Test 2: Get date detection report
        print("\nTest 2: Date detection report")
        detector = DateDetector()
        report = detector.get_date_columns_report(original_df)
        
        print(f"\nDetection Report:")
        print(f"  Total columns: {report['total_columns']}")
        print(f"  Detected date columns: {report['detected_date_columns']}")
        
        for col, details in report['detection_details'].items():
            print(f"\n  Column '{col}':")
            print(f"    Format: {details['detected_format']}")
            print(f"    Confidence: {details['confidence']:.1%}")
            print(f"    Sample values: {details['sample_values'][:3]}")
        
        # Test 3: Load with specific date columns
        print("\nTest 3: Loading with specific date columns")
        df_specific = DataImporter.load_file(
            csv_file, 
            detect_dates=False,
            date_columns=['Start_Date', 'End_Date']
        )
        
        print("\nSpecified columns converted:")
        for col in ['Start_Date', 'End_Date']:
            print(f"  {col}: {df_specific[col].dtype}")
            if pd.api.types.is_datetime64_any_dtype(df_specific[col]):
                print(f"    Sample: {df_specific[col].iloc[0]}")
        
        # Test 4: Load with custom date formats
        print("\nTest 4: Loading with custom date formats")
        df_custom = DataImporter.load_file(
            csv_file,
            date_formats=['%d.%m.%Y %H:%M:%S']  # For Last_Modified column
        )
        
        if pd.api.types.is_datetime64_any_dtype(df_custom['Last_Modified']):
            print(f"  Last_Modified successfully converted!")
            print(f"    Sample: {df_custom['Last_Modified'].iloc[0]}")
        
        # Test 5: Verify Excel formula compatibility
        print("\nTest 5: Excel formula compatibility check")
        from core.formula_engine.excel_formula_processor import ExcelFormulaProcessor
        
        processor = ExcelFormulaProcessor()
        excel_ready_df = processor.prepare_data_for_excel(df_auto)
        
        print("\nColumns prepared for Excel:")
        date_cols = ['Start_Date', 'End_Date', 'Birth_Date', 'Last_Modified']
        for col in date_cols:
            if col in excel_ready_df.columns:
                print(f"  {col}: {excel_ready_df[col].iloc[0]} (type: {type(excel_ready_df[col].iloc[0])})")
        
        # Test 6: Test with mixed/invalid dates
        print("\nTest 6: Testing with mixed/invalid dates")
        mixed_data = {
            'Mixed_Dates': ['01/15/2024', 'Invalid Date', '2024-02-20', None, 'Not a date', '03/30/2024']
        }
        mixed_df = pd.DataFrame(mixed_data)
        
        converted_df, conversion_report = detector.convert_date_columns(mixed_df)
        
        print(f"\nMixed date conversion results:")
        for col, report in conversion_report.items():
            print(f"  Column '{col}':")
            print(f"    Success: {report['success_count']}")
            print(f"    Errors: {report['error_count']}")
            print(f"    Conversion rate: {report['conversion_rate']:.1%}")
        
        print("\nConverted values:")
        for i, (orig, conv) in enumerate(zip(mixed_df['Mixed_Dates'], converted_df['Mixed_Dates'])):
            print(f"  Row {i}: '{orig}' -> {conv}")
        
    finally:
        # Clean up
        os.unlink(csv_file)
        print(f"\nCleaned up test file: {csv_file}")


def test_performance():
    """Test performance with larger dataset."""
    print("\n\nPerformance Test")
    print("=" * 50)
    
    # Create larger dataset
    n_rows = 10000
    data = {
        'ID': range(n_rows),
        'Date1': ['01/15/2024'] * n_rows,
        'Date2': ['2024-01-15'] * n_rows,
        'Date3': ['Jan 15, 2024'] * n_rows,
        'NotDate': ['ABC123'] * n_rows,
        'Value': np.random.rand(n_rows) * 1000
    }
    
    df = pd.DataFrame(data)
    
    # Time the detection
    import time
    detector = DateDetector(sample_size=100)  # Only sample 100 rows for detection
    
    start_time = time.time()
    detected_columns = detector.detect_date_columns(df)
    detection_time = time.time() - start_time
    
    print(f"Detected {len(detected_columns)} date columns in {detection_time:.2f} seconds")
    print(f"Columns detected: {detected_columns}")
    
    # Time the conversion
    start_time = time.time()
    converted_df, _ = detector.convert_date_columns(df, columns=detected_columns)
    conversion_time = time.time() - start_time
    
    print(f"Converted {len(detected_columns)} columns ({n_rows} rows each) in {conversion_time:.2f} seconds")
    print(f"Average time per column: {conversion_time/len(detected_columns):.2f} seconds")


if __name__ == "__main__":
    test_date_detection()
    test_performance()
    print("\n\nAll tests completed!")
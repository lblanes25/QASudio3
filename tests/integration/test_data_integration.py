# tests/test_data_integration.py

import os
import pandas as pd
import numpy as np
import logging
import tempfile
from pathlib import Path
import pytest
import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DataIntegrationTest")

# Import our components - adjust the import path as needed
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from data_integration.connectors import ExcelConnector, CSVConnector, get_connector_for_file
from data_integration.io import DataImporter


@pytest.fixture(scope="module")
def test_files():
    """Create sample Excel and CSV files for testing"""

    # Create a temporary directory
    temp_dir = tempfile.mkdtemp()
    logger.info(f"Created temporary directory: {temp_dir}")

    # Create sample data
    data = {
        'ID': [1, 2, 3, 4, 5],
        'Name': ['Alice', 'Bob', 'Charlie', 'David', 'Eve'],
        'Department': ['HR', 'IT', 'Finance', 'Marketing', 'IT'],
        'Salary': [75000, 85000, 95000, 70000, 90000],
        'Start Date': pd.date_range(start='2020-01-01', periods=5, freq='M')
    }
    df = pd.DataFrame(data)

    # Create a more complex dataset for the second sheet
    data2 = {
        'Project ID': ['P001', 'P002', 'P003', 'P004', 'P005'],
        'Project Name': ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon'],
        'Status': ['Completed', 'In Progress', 'Planned', 'Cancelled', 'In Progress'],
        'Budget': [50000, 75000, 100000, 25000, 80000],
        'Start Date': pd.date_range(start='2021-01-01', periods=5, freq='3M'),
        'Owner ID': [2, 3, 1, 5, 2]  # References IDs from first dataset
    }
    df2 = pd.DataFrame(data2)

    # Create Excel file with multiple sheets
    excel_path = os.path.join(temp_dir, 'test_data.xlsx')
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Employees', index=False)
        df2.to_excel(writer, sheet_name='Projects', index=False)
    logger.info(f"Created Excel file: {excel_path}")

    # Create CSV file
    csv_path = os.path.join(temp_dir, 'employees.csv')
    df.to_csv(csv_path, index=False)
    logger.info(f"Created CSV file: {csv_path}")

    # Create tab-delimited file
    tsv_path = os.path.join(temp_dir, 'projects.tsv')
    df2.to_csv(tsv_path, sep='\t', index=False)
    logger.info(f"Created TSV file: {tsv_path}")

    # Yield the paths to the test files
    yield temp_dir, excel_path, csv_path, tsv_path

    # Clean up after tests
    try:
        import shutil
        shutil.rmtree(temp_dir)
        logger.info(f"Removed temporary directory: {temp_dir}")
    except Exception as e:
        logger.warning(f"Error cleaning up temporary directory: {str(e)}")


def test_excel_connector(test_files):
    """Test the ExcelConnector with various options"""
    _, excel_path, _, _ = test_files
    logger.info("\n=== Testing ExcelConnector ===")

    # Basic connection
    connector = ExcelConnector({'file_path': excel_path})
    assert connector.connect(), "Failed to connect to Excel file"
    logger.info("Successfully connected to Excel file")

    # List sheet names
    sheet_names = connector.get_sheet_names()
    logger.info(f"Found sheets: {sheet_names}")
    assert 'Employees' in sheet_names and 'Projects' in sheet_names, "Sheets not found"

    # Load first sheet with default options
    df1 = connector.get_data('Employees')
    logger.info(f"Loaded 'Employees' sheet: {len(df1)} rows, {len(df1.columns)} columns")
    logger.info(f"Columns: {df1.columns.tolist()}")
    logger.info(f"First few rows:\n{df1.head(2)}")

    # Load second sheet with parameters
    df2 = connector.get_data('Projects')
    logger.info(f"Loaded 'Projects' sheet: {len(df2)} rows, {len(df2.columns)} columns")
    logger.info(f"First few rows:\n{df2.head(2)}")

    # Test range selection (load subset of columns)
    params = {'usecols': 'A:C'}  # Load only first 3 columns
    df3 = connector.get_data('Employees', params)
    logger.info(f"Loaded partial 'Employees' sheet: {len(df3)} rows, {len(df3.columns)} columns")
    logger.info(f"Columns: {df3.columns.tolist()}")

    # Clean up
    connector.disconnect()
    logger.info("ExcelConnector tests completed successfully")


def test_csv_connector(test_files):
    """Test the CSVConnector with various options"""
    _, _, csv_path, tsv_path = test_files
    logger.info("\n=== Testing CSVConnector ===")

    # Test with CSV file
    logger.info("Testing with CSV file")
    connector = CSVConnector({'file_path': csv_path})
    assert connector.connect(), "Failed to connect to CSV file"

    # Load data
    df = connector.get_data()
    logger.info(f"Loaded CSV data: {len(df)} rows, {len(df.columns)} columns")
    logger.info(f"Columns: {df.columns.tolist()}")
    logger.info(f"First few rows:\n{df.head(2)}")
    connector.disconnect()

    # Test with TSV file and delimiter auto-detection
    logger.info("\nTesting with TSV file")
    connector = CSVConnector({'file_path': tsv_path})
    assert connector.connect(), "Failed to connect to TSV file"

    # Detect delimiter
    delimiter = connector._detect_delimiter()
    logger.info(f"Auto-detected delimiter: '{delimiter}'")

    # Load data
    df = connector.get_data()
    logger.info(f"Loaded TSV data: {len(df)} rows, {len(df.columns)} columns")
    logger.info(f"Columns: {df.columns.tolist()}")
    logger.info(f"First few rows:\n{df.head(2)}")
    connector.disconnect()

    logger.info("CSVConnector tests completed successfully")


def test_factory_method(test_files):
    """Test the connector factory method"""
    _, excel_path, csv_path, tsv_path = test_files
    logger.info("\n=== Testing Factory Method ===")

    # Test with Excel file
    connector = get_connector_for_file(excel_path)
    assert isinstance(connector, ExcelConnector), "Wrong connector type for Excel"
    logger.info(f"Factory correctly returned ExcelConnector for {os.path.basename(excel_path)}")

    # Test with CSV file
    connector = get_connector_for_file(csv_path)
    assert isinstance(connector, CSVConnector), "Wrong connector type for CSV"
    logger.info(f"Factory correctly returned CSVConnector for {os.path.basename(csv_path)}")

    # Test with TSV file
    connector = get_connector_for_file(tsv_path)
    assert isinstance(connector, CSVConnector), "Wrong connector type for TSV"
    logger.info(f"Factory correctly returned CSVConnector for {os.path.basename(tsv_path)}")

    logger.info("Factory method tests completed successfully")


def test_data_importer(test_files):
    """Test the DataImporter high-level interface"""
    temp_dir, excel_path, csv_path, _ = test_files
    logger.info("\n=== Testing DataImporter ===")

    # Test loading single file
    logger.info("Testing load_file method")
    df = DataImporter.load_file(excel_path, sheet_name='Employees')
    logger.info(f"Loaded Excel file: {len(df)} rows, {len(df.columns)} columns")
    logger.info(f"First few rows:\n{df.head(2)}")

    # Test previewing file
    logger.info("\nTesting preview_file method")
    # Fix: Add proper datetime import
    preview, metadata = DataImporter.preview_file(excel_path, max_rows=2)
    logger.info(f"File metadata: {metadata}")
    logger.info(f"Preview data:\n{preview}")

    # Test loading directory
    logger.info("\nTesting load_directory method")
    dataframes = DataImporter.load_directory(temp_dir, file_pattern="*.csv")
    logger.info(f"Loaded {len(dataframes)} files from directory")
    for name, df in dataframes.items():
        logger.info(f"File '{name}': {len(df)} rows, {len(df.columns)} columns")

    logger.info("DataImporter tests completed successfully")
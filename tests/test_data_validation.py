# tests/test_data_validation.py

import pytest
import pandas as pd
import os
import tempfile
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Fix import paths
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import our components
from data_integration.io.data_validator import DataValidator
from data_integration.io import DataImporter
from data_integration.errors.error_handler import ErrorHandler, DataIntegrationError, ValidationError


@pytest.fixture
def sample_dataframe():
    """Create a sample DataFrame for testing"""
    data = {
        'ID': [1, 2, 3, 4, 5],
        'Name': ['Alice', 'Bob', 'Charlie', 'David', None],
        'Age': [25, 30, None, 40, 35],
        'Salary': [50000, 60000, 70000, 80000, 90000],
        'Department': ['HR', 'IT', 'Finance', 'IT', 'HR'],
        'JoinDate': pd.to_datetime(['2020-01-01', '2019-05-15', '2021-03-10', '2018-11-20', '2022-02-28'])
    }
    return pd.DataFrame(data)


@pytest.fixture
def invalid_dataframe():
    """Create an invalid DataFrame for testing validation failures"""
    data = {
        'ID': [1, 2, 2, 4, 5],  # Duplicate ID
        'Name': [None, 'Bob', None, 'David', None],  # Multiple nulls
        'Age': [25, 300, 35, 40, 35],  # Age 300 is invalid
        'Salary': [-50000, 60000, 70000, 80000, 90000],  # Negative salary
        'Department': ['HR', 'IT', 'Finance', 'Unknown', 'HR'],  # Invalid department
        'JoinDate': ['2020-01-01', '2019-05-15', 'invalid-date', '2018-11-20', '2022-02-28']  # Invalid date
    }
    df = pd.DataFrame(data)
    # Convert JoinDate to datetime with errors='coerce' to include NaT values
    df['JoinDate'] = pd.to_datetime(df['JoinDate'], errors='coerce')
    return df


@pytest.fixture
def corrupted_excel_file():
    """Create a corrupted Excel file for testing error handling"""
    # Create a temporary file
    fd, path = tempfile.mkstemp(suffix='.xlsx')
    os.close(fd)

    # Write invalid content (not a valid Excel file)
    with open(path, 'w') as f:
        f.write('This is not a valid Excel file content.')

    yield path

    # Clean up
    os.unlink(path)


def test_data_validator_basic(sample_dataframe):
    """Test basic validation functionality"""
    validator = DataValidator()

    # Create validation rules
    validation_rules = {
        'no_nulls_in_id': {
            'type': 'not_null',
            'columns': ['ID'],
            'severity': 'error',
            'message': 'ID column cannot contain null values'
        },
        'name_not_null': {
            'type': 'not_null',
            'columns': ['Name'],
            'severity': 'warning',
            'message': 'Name column should not contain null values'
        }
    }

    # Validate the DataFrame with treat_warnings_as_errors=True
    results = validator.validate(sample_dataframe, validation_rules, treat_warnings_as_errors=True)

    # Check results
    assert results['valid'] is False, "Validation should fail due to null in Name column"
    assert len(results['warnings']) == 1, "Should have one warning"
    assert len(results['errors']) == 0, "Should have no errors"
    assert 'no_nulls_in_id' in results['details'], "Should have details for no_nulls_in_id rule"
    assert 'name_not_null' in results['details'], "Should have details for name_not_null rule"
    assert results['details']['no_nulls_in_id']['valid'] is True, "no_nulls_in_id should pass"
    assert results['details']['name_not_null']['valid'] is False, "name_not_null should fail"

    # Test report generation
    report = validator.generate_report(results)
    assert "=== Data Validation Report ===" in report, "Report should contain header"
    assert "Errors: 0" in report, "Report should show error count"
    assert "Warnings: 1" in report, "Report should show warning count"

def test_validation_complex_rules(invalid_dataframe):
    """Test validation with multiple complex rules"""
    validator = DataValidator()

    # Create validation rules
    validation_rules = {
        'unique_ids': {
            'type': 'unique',
            'columns': ['ID'],
            'severity': 'error',
            'message': 'ID values must be unique'
        },
        'valid_age': {
            'type': 'max_value',
            'columns': ['Age'],
            'params': {'max_value': 100},
            'severity': 'error',
            'message': 'Age must be <= 100'
        },
        'positive_salary': {
            'type': 'min_value',
            'columns': ['Salary'],
            'params': {'min_value': 0},
            'severity': 'error',
            'message': 'Salary must be >= 0'
        },
        'valid_department': {
            'type': 'in_set',
            'columns': ['Department'],
            'params': {'values': ['HR', 'IT', 'Finance', 'Marketing']},
            'severity': 'error',
            'message': 'Department must be one of the allowed values'
        },
        'valid_join_date': {
            'type': 'not_null',
            'columns': ['JoinDate'],
            'severity': 'warning',
            'message': 'JoinDate should not be null'
        }
    }

    # Validate the DataFrame
    results = validator.validate(invalid_dataframe, validation_rules)

    # Check results
    assert results['valid'] is False, "Validation should fail"
    assert len(results['errors']) >= 4, "Should have at least 4 errors"
    assert results['details']['unique_ids']['valid'] is False, "unique_ids should fail"
    assert results['details']['valid_age']['valid'] is False, "valid_age should fail"
    assert results['details']['positive_salary']['valid'] is False, "positive_salary should fail"
    assert results['details']['valid_department']['valid'] is False, "valid_department should fail"

    # Test HTML report
    html_report = validator.generate_report(results, format='html')
    assert "<!DOCTYPE html>" in html_report, "HTML report should contain DOCTYPE"
    assert "<title>Data Validation Report</title>" in html_report, "HTML report should have title"
    assert "<span class='failed'>FAILED</span>" in html_report, "HTML report should show failed status"

    # Test Markdown report
    md_report = validator.generate_report(results, format='markdown')
    assert "# Data Validation Report" in md_report, "Markdown report should have header"
    assert "**Overall Status:** ❌ FAILED" in md_report, "Markdown report should show failed status"


def test_data_importer_validation(sample_dataframe, tmp_path):
    """Test DataImporter with validation"""
    # Create a CSV file from the sample DataFrame
    csv_path = os.path.join(tmp_path, "test_data.csv")
    sample_dataframe.to_csv(csv_path, index=False)

    # Create validation rules
    validation_rules = {
        'no_nulls_in_id': {
            'type': 'not_null',
            'columns': ['ID'],
            'severity': 'error',
            'message': 'ID column cannot contain null values'
        },
        'age_range': {
            'type': 'min_value',
            'columns': ['Age'],
            'params': {'min_value': 18},
            'severity': 'error',
            'message': 'Age must be at least 18'
        }
    }

    # Load and validate in one step
    df, validation_results = DataImporter.load_file(
        csv_path,
        validate=validation_rules,
        raise_on_validation_error=False
    )

    # Check results
    assert df is not None, "DataFrame should be loaded"
    assert validation_results is not None, "Validation results should be returned"
    assert validation_results['valid'] is True, "Validation should pass for sample data"

    # Test with standalone validation
    results = DataImporter.validate_dataframe(
        sample_dataframe,
        validation_rules,
        generate_report=True
    )

    assert results['valid'] is True, "Validation should pass"
    assert 'report' in results, "Report should be generated"
    assert "=== Data Validation Report ===" in results['report'], "Report should have proper format"


def test_error_handler_basic():
    """Test basic error handling"""
    error_handler = ErrorHandler(raise_errors=False)

    # Test handling a string error
    error = error_handler.handle_error("Test error message")
    assert isinstance(error, DataIntegrationError), "Should return DataIntegrationError"
    assert str(error) == "Test error message", "Error message should match"

    # Test handling an exception
    error = error_handler.handle_error(ValueError("Invalid value"))
    assert isinstance(error, ValueError), "Should return original exception type"
    assert str(error) == "Invalid value", "Error message should match"

    # Test handling with context
    context = {'source': 'test', 'operation': 'validation'}
    error = error_handler.handle_error("Context error", context=context)
    assert error.details == context, "Error details should contain context"


def test_error_handler_specific_errors():
    """Test specific error handling methods"""
    error_handler = ErrorHandler(raise_errors=False)

    # Test connection error
    conn_error = error_handler.handle_connection_error(
        "Connection failed",
        source_name="TestDatabase",
        connection_params={'host': 'localhost', 'password': 'secret'}
    )
    assert isinstance(conn_error, DataIntegrationError), "Should return ConnectionError"
    assert "Connection failed" in str(conn_error), "Error message should contain original message"
    assert conn_error.details.get('source_name') == "TestDatabase", "Details should contain source name"
    assert conn_error.details.get('connection_params', {}).get('password') == '*****', "Password should be redacted"

    # Test validation error
    validation_results = {'valid': False, 'errors': ['Test error']}
    val_error = error_handler.handle_validation_error(
        "Validation failed",
        validation_results=validation_results,
        data_source="test_file.csv"
    )
    assert isinstance(val_error, ValidationError), "Should return ValidationError"
    assert val_error.validation_results == validation_results, "Should contain validation results"


def test_error_handler_with_data_importer(corrupted_excel_file):
    """Test error handling with DataImporter"""
    # Create DataImporter with non-raising error handler
    # This should return None instead of raising an exception
    try:
        # Try to load corrupted Excel file (should fail)
        df = DataImporter.load_file(corrupted_excel_file)
        assert False, "Should raise an exception for corrupted file"
    except Exception as e:
        # Should get a DataIntegrationError or a wrapped pandas error
        assert "Excel" in str(e) or "file format" in str(e), "Error should mention Excel or file format"
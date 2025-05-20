# data_integration/connectors/__init__.py
"""
Connector modules for accessing different data sources.
"""

from .base_connector import BaseConnector
from .excel_connector import ExcelConnector
from .csv_connector import CSVConnector

# Dictionary mapping file extensions to appropriate connectors
FILE_EXTENSION_MAPPING = {
    '.xlsx': ExcelConnector,
    '.xls': ExcelConnector,
    '.xlsm': ExcelConnector,
    '.csv': CSVConnector,
    '.tsv': CSVConnector,
    '.txt': CSVConnector,
}


def get_connector_for_file(file_path, **kwargs):
    """
    Factory method to get the appropriate connector for a given file path.

    Args:
        file_path: Path to the data file
        **kwargs: Additional parameters to pass to the connector

    Returns:
        Appropriate connector instance for the file type
    """
    import os
    _, ext = os.path.splitext(file_path.lower())

    if ext in FILE_EXTENSION_MAPPING:
        connector_class = FILE_EXTENSION_MAPPING[ext]
        # Include file_path in the connection parameters
        connection_params = kwargs.copy()
        connection_params['file_path'] = file_path
        return connector_class(connection_params)
    else:
        raise ValueError(f"Unsupported file extension: {ext}")


__all__ = ['BaseConnector', 'ExcelConnector', 'CSVConnector', 'get_connector_for_file']
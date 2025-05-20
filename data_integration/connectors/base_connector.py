# data_integration/connectors/base_connector.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import pandas as pd
import logging

# Import error handling components
from data_integration.errors.error_handler import ErrorHandler

logger = logging.getLogger(__name__)


class BaseConnector(ABC):
    """
    Abstract base class for all data source connectors.
    Defines the interface that all connector implementations must follow.
    """

    def __init__(self, connection_params: Optional[Dict[str, Any]] = None):
        """
        Initialize the connector with optional connection parameters.

        Args:
            connection_params: Dictionary containing connection parameters specific to the connector
        """
        self.connection_params = connection_params or {}
        self._connection = None
        self._is_connected = False

        # Initialize error handler
        self.error_handler = ErrorHandler(
            log_errors=True,
            raise_errors=True
        )

    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the data source.

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """
        Close connection to the data source.

        Returns:
            True if disconnection successful, False otherwise
        """
        pass

    @property
    def is_connected(self) -> bool:
        """
        Check if connector is currently connected.

        Returns:
            True if connected, False otherwise
        """
        return self._is_connected

    @abstractmethod
    def get_data(self,
                 query: Optional[str] = None,
                 params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Retrieve data from the source and return as DataFrame.

        Args:
            query: Query string or identifier for the data to retrieve
            params: Additional parameters to control the data retrieval

        Returns:
            DataFrame containing the requested data
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """
        Test if the connection to the data source can be established successfully.

        Returns:
            True if connection test successful, False otherwise
        """
        pass

    def __enter__(self):
        """Support for context manager protocol"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support for context manager protocol"""
        self.disconnect()

    def handle_connection_error(self, error: Exception, additional_info: Optional[Dict[str, Any]] = None) -> None:
        """
        Handle a connection error with consistent error reporting.

        Args:
            error: The exception that occurred
            additional_info: Additional context information
        """
        # Prepare source name
        source_name = self.__class__.__name__

        # Create context with appropriate information
        context = (additional_info or {}).copy()

        # Add connection params for context (sensitive info will be redacted)
        context['connector_type'] = source_name

        # Let the error handler process this
        self.error_handler.handle_connection_error(
            error,
            source_name,
            self.connection_params
        )

    def handle_data_load_error(self, error: Exception, query: Optional[str] = None,
                               params: Optional[Dict[str, Any]] = None) -> None:
        """
        Handle a data loading error with consistent error reporting.

        Args:
            error: The exception that occurred
            query: Query or identifier for the data
            params: Parameters used for loading
        """
        # Prepare source name
        source_name = self.__class__.__name__

        # Let the error handler process this
        self.error_handler.handle_data_load_error(
            error,
            source_name,
            query,
            params
        )
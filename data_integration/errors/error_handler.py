# data_integration/utils/error_handler.py

import traceback
import logging
import sys
import os
from typing import Dict, Any, Optional, Callable, Type, List, Union
import json
import datetime
import pandas as pd

logger = logging.getLogger(__name__)


class DataIntegrationError(Exception):
    """Base exception class for all data integration errors"""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.timestamp = datetime.datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary format"""
        result = {
            'error_type': self.__class__.__name__,
            'message': self.message,
            'timestamp': self.timestamp
        }
        if self.details:
            result['details'] = self.details
        return result

    def __str__(self) -> str:
        """String representation of the error"""
        if self.details:
            return f"{self.message} - Details: {json.dumps(self.details, default=str)}"
        return self.message


class ConnectionError(DataIntegrationError):
    """Error raised when connection to a data source fails"""
    pass


class DataLoadError(DataIntegrationError):
    """Error raised when loading data fails"""
    pass


class ValidationError(DataIntegrationError):
    """Error raised when data validation fails"""

    def __init__(self, message: str, validation_results: Optional[Dict[str, Any]] = None,
                 details: Optional[Dict[str, Any]] = None):
        combined_details = (details or {}).copy()
        if validation_results:
            combined_details['validation_results'] = validation_results
        super().__init__(message, combined_details)
        self.validation_results = validation_results


class ConfigurationError(DataIntegrationError):
    """Error raised when configuration is invalid"""
    pass


class ErrorHandler:
    """
    Central error handling facility for data integration components.
    Provides consistent error handling, logging, and recovery options.
    """

    def __init__(self,
                 log_errors: bool = True,
                 error_log_path: Optional[str] = None,
                 raise_errors: bool = True):
        """
        Initialize the error handler.

        Args:
            log_errors: Whether to log errors to logger
            error_log_path: Optional path to write error log files
            raise_errors: Whether to raise exceptions or return error objects
        """
        self.log_errors = log_errors
        self.error_log_path = error_log_path
        self.raise_errors = raise_errors

        # Create error log directory if specified
        if error_log_path:
            os.makedirs(error_log_path, exist_ok=True)

    def handle_error(self,
                     error: Union[Exception, str],
                     error_type: Optional[Type[Exception]] = None,
                     context: Optional[Dict[str, Any]] = None) -> Optional[Exception]:
        """
        Handle an error consistently.

        Args:
            error: Exception instance or error message
            error_type: Type of exception to raise if error is a string
            context: Additional context information for the error

        Returns:
            Exception object if raise_errors is False, otherwise raises the exception
        """
        # Create exception object if string was provided
        if isinstance(error, str):
            error_class = error_type or DataIntegrationError
            error_obj = error_class(error, context)
        else:
            error_obj = error

        # Log the error if requested
        if self.log_errors:
            self._log_error(error_obj, context)

        # Write to error log file if path is specified
        if self.error_log_path:
            self._write_error_log(error_obj, context)

        # Raise or return the error
        if self.raise_errors:
            raise error_obj
        else:
            return error_obj

    def handle_connection_error(self,
                                error: Union[Exception, str],
                                source_name: str,
                                connection_params: Optional[Dict[str, Any]] = None) -> Optional[ConnectionError]:
        """
        Handle a connection error.

        Args:
            error: Exception instance or error message
            source_name: Name of the data source
            connection_params: Connection parameters (sensitive info will be redacted)

        Returns:
            ConnectionError object if raise_errors is False, otherwise raises the exception
        """
        # Create context dictionary
        context = {
            'source_name': source_name
        }

        # Add redacted connection params if provided
        if connection_params:
            redacted_params = self._redact_sensitive_info(connection_params)
            context['connection_params'] = redacted_params

        # Create error message if string not provided
        if not isinstance(error, str):
            error_msg = f"Failed to connect to {source_name}: {str(error)}"
        else:
            error_msg = error

        # Handle the error
        return self.handle_error(error_msg, ConnectionError, context)

    def handle_data_load_error(self,
                               error: Union[Exception, str],
                               source_name: str,
                               query: Optional[str] = None,
                               params: Optional[Dict[str, Any]] = None) -> Optional[DataLoadError]:
        """
        Handle a data loading error.

        Args:
            error: Exception instance or error message
            source_name: Name of the data source
            query: Query or identifier for the data
            params: Parameters used for loading

        Returns:
            DataLoadError object if raise_errors is False, otherwise raises the exception
        """
        # Create context dictionary
        context = {
            'source_name': source_name
        }

        if query:
            context['query'] = query

        if params:
            context['params'] = params

        # Create error message if string not provided
        if not isinstance(error, str):
            error_msg = f"Failed to load data from {source_name}: {str(error)}"
        else:
            error_msg = error

        # Handle the error
        return self.handle_error(error_msg, DataLoadError, context)

    def handle_validation_error(self,
                                error: Union[Exception, str],
                                validation_results: Optional[Dict[str, Any]] = None,
                                data_source: Optional[str] = None) -> Optional[ValidationError]:
        """
        Handle a validation error.

        Args:
            error: Exception instance or error message
            validation_results: Results from validation
            data_source: Source of the data being validated

        Returns:
            ValidationError object if raise_errors is False, otherwise raises the exception
        """
        # Create context dictionary
        context = {}
        if data_source:
            context['data_source'] = data_source

        # Create error message if string not provided
        if not isinstance(error, str):
            error_msg = f"Data validation failed: {str(error)}"
        else:
            error_msg = error

        # Create ValidationError
        validation_error = ValidationError(error_msg, validation_results, context)

        # Log and handle the error
        if self.log_errors:
            self._log_error(validation_error, context)

        if self.error_log_path:
            self._write_error_log(validation_error, context)

        if self.raise_errors:
            raise validation_error
        else:
            return validation_error

    def _log_error(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """Log an error with context"""
        # Format error message
        if isinstance(error, DataIntegrationError):
            error_msg = str(error)
        else:
            if context:
                error_msg = f"{str(error)} - Context: {json.dumps(context, default=str)}"
            else:
                error_msg = str(error)

        # Log with stack trace
        logger.error(error_msg, exc_info=True)

    def _write_error_log(self, error: Exception, context: Optional[Dict[str, Any]] = None) -> None:
        """Write error details to log file"""
        try:
            # Create timestamp for filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            # Determine error type for filename
            if isinstance(error, DataIntegrationError):
                error_type = error.__class__.__name__
            else:
                error_type = "Error"

            # Create filename
            filename = f"{timestamp}_{error_type}.json"
            filepath = os.path.join(self.error_log_path, filename)

            # Prepare error details
            error_details = {
                'timestamp': datetime.datetime.now().isoformat(),
                'error_type': error.__class__.__name__,
                'message': str(error),
                'traceback': traceback.format_exc()
            }

            # Add context if provided
            if context:
                error_details['context'] = context

            # Add error-specific details
            if isinstance(error, DataIntegrationError) and error.details:
                error_details['details'] = error.details

            # Write to file
            with open(filepath, 'w') as f:
                json.dump(error_details, f, indent=2, default=str)

        except Exception as e:
            logger.error(f"Failed to write error log: {str(e)}")

    def _redact_sensitive_info(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact sensitive information from dictionaries"""
        redacted = data.copy()

        # List of keys that might contain sensitive information
        sensitive_keys = ['password', 'api_key', 'secret', 'token', 'auth', 'key']

        # Redact sensitive values
        for key in redacted:
            for sensitive_key in sensitive_keys:
                if sensitive_key.lower() in key.lower():
                    redacted[key] = '*****'

        return redacted


def safe_dataframe_operation(func: Callable, *args, **kwargs) -> pd.DataFrame:
    """
    Safely execute a pandas operation with better error handling.

    Args:
        func: Function to execute
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        DataFrame from the function

    Raises:
        DataIntegrationError: If an error occurs during execution
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        # Get function name for better error reporting
        func_name = getattr(func, '__name__', str(func))

        # Create error message with context
        error_msg = f"Error executing {func_name}: {str(e)}"

        # Create detailed error
        details = {
            'function': func_name,
            'args': str(args),
            'kwargs': {k: v for k, v in kwargs.items() if k != 'password'}
        }

        # Raise custom error
        raise DataIntegrationError(error_msg, details)


def retry_operation(func: Callable,
                    max_attempts: int = 3,
                    retry_delay: float = 1.0,
                    exception_types: Optional[List[Type[Exception]]] = None,
                    *args, **kwargs) -> Any:
    """
    Retry an operation multiple times with exponential backoff.

    Args:
        func: Function to execute
        max_attempts: Maximum number of attempts
        retry_delay: Initial delay between retries (seconds)
        exception_types: Types of exceptions to retry on (defaults to all)
        *args: Arguments for the function
        **kwargs: Keyword arguments for the function

    Returns:
        Result from the function

    Raises:
        Exception: The last exception raised by the function
    """
    import time

    # Default to all exceptions if not specified
    if exception_types is None:
        exception_types = (Exception,)

    last_exception = None

    for attempt in range(max_attempts):
        try:
            return func(*args, **kwargs)
        except exception_types as e:
            last_exception = e

            # Log the failure
            if attempt < max_attempts - 1:
                logger.warning(
                    f"Attempt {attempt + 1}/{max_attempts} failed: {str(e)}. Retrying in {retry_delay:.1f} seconds.")

                # Wait before retrying
                time.sleep(retry_delay)

                # Increase delay for next attempt (exponential backoff)
                retry_delay *= 2
            else:
                logger.error(f"All {max_attempts} attempts failed. Last error: {str(e)}")

    # If we get here, all attempts failed
    if last_exception:
        raise last_exception
    else:
        raise RuntimeError(f"Operation failed after {max_attempts} attempts with no exception")
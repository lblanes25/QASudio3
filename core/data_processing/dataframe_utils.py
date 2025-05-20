import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)

def set_dataframe_value(df, row_idx, col_name, value):
    """
    Safely set a value in a DataFrame with appropriate type handling.
    
    Args:
        df: DataFrame to modify
        row_idx: Row index
        col_name: Column name
        value: Value to set
        
    Returns:
        None (modifies df in place)
    """
    # Create the column if it doesn't exist
    if col_name not in df.columns:
        # Try to infer the best data type based on the first value
        if isinstance(value, bool):
            df[col_name] = False  # Initialize with default boolean
        elif isinstance(value, (int, float, np.number)) and not isinstance(value, bool):
            df[col_name] = np.nan  # Initialize with NaN for numeric
        elif isinstance(value, str):
            df[col_name] = ""  # Initialize with empty string
        else:
            df[col_name] = None  # Default to None
    
    # Handle the common case of strings and numeric columns
    try:
        current_dtype = df[col_name].dtype
        
        # If column is numeric but value is string, convert column to object type
        if pd.api.types.is_numeric_dtype(current_dtype) and isinstance(value, str):
            logger.debug(f"Converting column {col_name} from {current_dtype} to object type")
            # Make a copy of the column as object type
            temp_values = df[col_name].astype(object).values
            # Update the specific row
            temp_values[row_idx] = value
            # Assign back to DataFrame
            df[col_name] = temp_values
        # If column is string/object but value is numeric, just set it
        elif pd.api.types.is_object_dtype(current_dtype) and isinstance(value, (int, float, np.number)):
            df.at[row_idx, col_name] = str(value)
        # If column is boolean but value is not, convert if possible
        elif pd.api.types.is_bool_dtype(current_dtype) and not isinstance(value, bool):
            if isinstance(value, str) and value.lower() in ('true', 'false'):
                df.at[row_idx, col_name] = value.lower() == 'true'
            elif isinstance(value, (int, float)) and value in (0, 1):
                df.at[row_idx, col_name] = bool(value)
            else:
                # Convert column to object type
                temp_values = df[col_name].astype(object).values
                temp_values[row_idx] = value
                df[col_name] = temp_values
        # Otherwise just set the value
        else:
            df.at[row_idx, col_name] = value
            
    except Exception as e:
        logger.warning(f"Error setting {value} in {col_name} at index {row_idx}: {str(e)}")
        # Fallback method: create new column with object dtype
        try:
            # Create a new series with all the data
            temp_series = df[col_name].copy()
            # Convert to object type to allow mixed types
            temp_series = temp_series.astype(object)
            # Update the value
            temp_series.iloc[row_idx] = value
            # Assign back to DataFrame
            df[col_name] = temp_series
        except Exception as e:
            logger.error(f"Failed to set value even with fallback method: {str(e)}")
            # Last resort: just try to set it directly and accept any warnings
            df.at[row_idx, col_name] = value

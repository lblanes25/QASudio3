import pandas as pd
import numpy as np
from datetime import datetime


def test_fix_processor():
    # Location of your excel_formula_processor.py file
    filepath = '../core/formula_engine/excel_formula_processor.py'

    print(f"Reading {filepath}...")
    with open(filepath, 'r') as f:
        content = f.read()

    # Check if prepare_data_for_excel already exists
    if 'def prepare_data_for_excel' in content:
        print("prepare_data_for_excel method already exists, checking placement...")

        # Check for any syntax errors or misplaced code
        lines = content.split('\n')
        indentation_errors = []
        method_starts = []

        # Find method definitions and check indentation
        for i, line in enumerate(lines):
            if line.strip().startswith('def '):
                method_starts.append((i, line.strip()))

                # Check if previous line has correct indentation
                if i > 0 and lines[i - 1].strip() and not lines[i - 1].startswith('    '):
                    indentation_errors.append((i - 1, lines[i - 1]))

        if indentation_errors:
            print("Found indentation errors:")
            for line_num, line in indentation_errors:
                print(f"Line {line_num + 1}: {line}")

        print("Method definitions found:")
        for line_num, method in method_starts:
            print(f"Line {line_num + 1}: {method}")
    else:
        print("Adding prepare_data_for_excel method...")

        # Find a good place to insert the method - after the __exit__ method
        exit_pos = content.find('def __exit__')
        if exit_pos > 0:
            # Find the end of the __exit__ method
            end_pos = content.find('def ', exit_pos + 1)
            if end_pos > 0:
                # Insert our method
                new_method = """
    def prepare_data_for_excel(self, df: pd.DataFrame) -> pd.DataFrame:
        \"\"\"
        Prepare DataFrame for Excel by converting problematic data types.

        Args:
            df: Input DataFrame

        Returns:
            DataFrame with Excel-compatible data types
        \"\"\"
        # Create a copy to avoid modifying the original
        excel_df = df.copy()

        # Process each column
        for col in excel_df.columns:
            # Check if column contains datetime objects
            if pd.api.types.is_datetime64_any_dtype(excel_df[col]):
                # Convert timestamps to ISO format strings that Excel recognizes
                excel_df[col] = excel_df[col].dt.strftime('%Y-%m-%d')
                logger.debug(f"Converted timestamp column {col} to string format")

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
                        lambda x: x.strftime('%Y-%m-%d') if isinstance(x, pd.Timestamp) else x
                    )

        return excel_df
"""
                content = content[:end_pos] + new_method + content[end_pos:]

                print("Method added successfully")

                # Write the updated file
                with open(filepath, 'w') as f:
                    f.write(content)

                print(f"Updated {filepath}")
            else:
                print("Could not find end of __exit__ method")
        else:
            print("Could not find __exit__ method")

    return True


if __name__ == "__main__":
    test_fix_processor()
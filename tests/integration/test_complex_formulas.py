# Updated test_complex_formulas.py
import pandas as pd
from core.formula_engine.excel_formula_processor import ExcelFormulaProcessor
import time


def test_complex_formulas():
    print("Testing complex Excel formulas with fixed processor...")

    # Create a more diverse test DataFrame
    data = {
        'Numbers': [1, 2, 3, 4, 5],
        'Negatives': [-5, -4, -3, -2, -1],
        'Decimals': [1.5, 2.5, 3.5, 4.5, 5.5],
        'Text': ['apple', 'banana', 'cherry', 'date', 'elderberry'],
        'Dates': pd.date_range(start='2023-01-01', periods=5).tolist(),
        'Mixed': [10, 'text', None, True, 3.14],
        'WithSpaces': ['a b', 'c d', 'e f', 'g h', 'i j']
    }
    df = pd.DataFrame(data)

    # Define complex formulas to test various Excel functions
    formulas = {
        # Mathematical operations
        'BasicMath': '=([Numbers] * 2) + ([Decimals] / 2) - ABS([Negatives])',

        # Text functions
        'TextManipulation': '=UPPER(LEFT([Text], 1)) & LOWER(RIGHT([Text], 2))',

        # Logical functions
        'Logical': '=IF([Numbers] > 3, "High", "Low")',

        # Date functions - should work now with proper date formatting
        'DateCalc': '=YEAR([Dates]) & "-" & MONTH([Dates])',

        # Nested functions
        'Nested': '=IF(AND([Numbers] > 2, [Decimals] < 5), ROUND([Numbers] * [Decimals], 1), 0)',

        # VLOOKUP simulation (using exact match)
        'LookupTest': '=VLOOKUP([Numbers], {1,100;2,200;3,300;4,400;5,500}, 2, FALSE)',
    }

    # Initialize processor with visible=True to observe Excel during testing
    processor = ExcelFormulaProcessor(visible=True)

    try:
        start_time = time.time()
        with processor:
            print("Excel started successfully, processing formulas...")

            # Process the formulas
            result_df = processor.process_formulas(df, formulas)

            # Print results
            print("\nResults:")
            print(result_df[['Numbers', 'Text', 'Dates', 'BasicMath', 'TextManipulation', 'Logical', 'DateCalc']])

            end_time = time.time()
            print(f"\nProcessing completed in {end_time - start_time:.2f} seconds")

            # Check for any real errors (non-empty strings in error columns)
            error_columns = [col for col in result_df.columns if
                             col.endswith('_Error') and (result_df[col].astype(str) != '').any()]
            if error_columns:
                print("\nErrors detected in:")
                for col in error_columns:
                    base_col = col.replace('_Error', '')
                    errors = result_df[result_df[col].astype(str) != '']
                    if not errors.empty:
                        print(f"  - {base_col}: {len(errors)} errors")
                        print(errors[[base_col, col]].head())
            else:
                print("\nNo errors detected! All formulas worked successfully.")

            return result_df
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = test_complex_formulas()
    print("\nTest completed successfully" if result is not None else "\nTest failed")
import pandas as pd
from core.formula_engine.excel_formula_processor import ExcelFormulaProcessor


def test_excel_connection():
    print("Testing Excel connection...")

    # Create a simple test DataFrame
    data = {
        'A': [1, 2, 3, 4, 5],
        'B': [10, 20, 30, 40, 50]
    }
    df = pd.DataFrame(data)

    # Define a simple formula to test
    formulas = {
        'Sum': '=SUM([A],[B])',
        'Product': '=([A]*[B])'
    }

    # Set visible=True to see Excel during execution
    processor = ExcelFormulaProcessor(visible=True)

    try:
        # Use context manager to ensure proper cleanup
        with processor:
            print("Excel started successfully")

            # Process the formulas
            result_df = processor.process_formulas(df, formulas)

            # Print results
            print("\nResults:")
            print(result_df)

            return True
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_excel_connection()
    print(f"\nTest completed. Success: {success}")
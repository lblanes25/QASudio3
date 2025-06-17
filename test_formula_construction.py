#!/usr/bin/env python3
"""
Test to see how formulas are constructed after LOOKUP replacement
"""

import pandas as pd
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.lookup.smart_lookup_manager import SmartLookupManager
from core.formula_engine.excel_formula_processor import ExcelFormulaProcessor

# Create test data
primary_df = pd.DataFrame({
    'ID': [1],
    'Leader': ['John']
})

hr_df = pd.DataFrame({
    'Name': ['John'],
    'Title': ['Manager']
})

# Save HR data
import os
os.makedirs('test_data', exist_ok=True)
hr_df.to_excel('test_data/hr.xlsx', index=False)

# Create lookup manager
lookup_manager = SmartLookupManager()
lookup_manager.add_file('test_data/hr.xlsx', alias='hr')

# Test the formula parsing
processor = ExcelFormulaProcessor(visible=False, lookup_manager=lookup_manager)

# Get the first row of data
row_data = primary_df.iloc[0]

# Test formula
original_formula = "=LOOKUP([Leader], 'Name', 'Title') = 'Manager'"
print(f"Original formula: {original_formula}")

# Parse LOOKUP calls
parsed_formula = processor._parse_lookup_calls(original_formula, row_data)
print(f"After LOOKUP parsing: {parsed_formula}")

# Apply row context (replace column references)
headers = list(primary_df.columns)
final_formula = processor._apply_row_context(parsed_formula, 2, headers)  # Row 2 in Excel
print(f"Final Excel formula: {final_formula}")

# Cleanup
import shutil
shutil.rmtree('test_data', ignore_errors=True)
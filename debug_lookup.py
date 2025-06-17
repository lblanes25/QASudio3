#!/usr/bin/env python3
"""
Debug script to understand why LOOKUP is not finding matches
"""

import pandas as pd
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from core.lookup.smart_lookup_manager import SmartLookupManager

# Create simple test data
hr_df = pd.DataFrame({
    'Name': ['John', 'Jane', 'Bob'],
    'Title': ['Manager', 'Director', 'Manager']
})

print("Original HR DataFrame:")
print(hr_df)
print(f"\nName column type: {hr_df['Name'].dtype}")
print(f"Name column values: {hr_df['Name'].tolist()}")

# Save and reload to simulate the issue
hr_df.to_excel('test_hr.xlsx', index=False)

# Load it back
loaded_df = pd.read_excel('test_hr.xlsx')
print("\nLoaded HR DataFrame:")
print(loaded_df)
print(f"\nLoaded Name column type: {loaded_df['Name'].dtype}")
print(f"Loaded Name column values: {loaded_df['Name'].tolist()}")

# Test direct DataFrame lookup
print("\nDirect DataFrame lookup test:")
lookup_value = 'John'
matches = loaded_df[loaded_df['Name'] == lookup_value]
print(f"Searching for '{lookup_value}' in Name column")
print(f"Matches found: {len(matches)}")
if not matches.empty:
    print(f"Result: {matches.iloc[0]['Title']}")

# Test with SmartLookupManager
print("\n\nSmartLookupManager test:")
manager = SmartLookupManager()
manager.add_file('test_hr.xlsx')

# Force load the file
df = manager._ensure_loaded('test_hr.xlsx')
print(f"\nDataFrame in manager:")
print(df)

# Check the index
if 'test_hr.xlsx' in manager.value_indices and 'Name' in manager.value_indices['test_hr.xlsx']:
    index = manager.value_indices['test_hr.xlsx']['Name']
    print(f"\nIndex for Name column:")
    print(index)
    print(f"\nIndex keys: {index.index.tolist()}")

# Test the lookup
result = manager.smart_lookup('John', 'Name', 'Title')
print(f"\nLookup result for 'John': {result}")

# Debug the _perform_lookup directly
print("\nDirect _perform_lookup test:")
result2 = manager._perform_lookup(df, 'John', 'Name', 'Title', 'test_hr.xlsx')
print(f"Direct _perform_lookup result: {result2}")

# Check if index lookup works
print("\nManual index lookup:")
if 'test_hr.xlsx' in manager.value_indices and 'Name' in manager.value_indices['test_hr.xlsx']:
    index = manager.value_indices['test_hr.xlsx']['Name']
    if 'John' in index.index:
        print(f"'John' found in index")
        print(f"Result: {index.loc['John', 'Title']}")
    else:
        print(f"'John' NOT found in index")
        print(f"Index values: {list(index.index)}")

# Check what's in the file metadata
print(f"\nFile metadata:")
for fp, meta in manager.file_metadata.items():
    print(f"  {fp}: {meta}")

# Cleanup
import os
if os.path.exists('test_hr.xlsx'):
    os.remove('test_hr.xlsx')
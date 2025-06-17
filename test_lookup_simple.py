#!/usr/bin/env python3
"""
Simple test to verify LOOKUP function fix
"""

import os
import sys
import logging
import pandas as pd
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from core.lookup.smart_lookup_manager import SmartLookupManager
from core.formula_engine.excel_formula_processor import ExcelFormulaProcessor


def main():
    logger.info("=== Simple LOOKUP Test ===")
    
    # Create test data
    primary_df = pd.DataFrame({
        'ID': [1, 2, 3],
        'Leader': ['John', 'Jane', 'Bob']
    })
    
    hr_df = pd.DataFrame({
        'Name': ['John', 'Jane', 'Bob'],
        'Title': ['Manager', 'Director', 'Manager']
    })
    
    # Save HR data
    os.makedirs('test_data', exist_ok=True)
    hr_df.to_excel('test_data/hr.xlsx', index=False)
    
    # Create lookup manager
    lookup_manager = SmartLookupManager()
    lookup_manager.add_file('test_data/hr.xlsx', alias='hr')
    
    # Enable tracking to see what's happening
    lookup_manager.enable_tracking()
    
    # Test formula with LOOKUP
    formula_map = {
        'IsManager': "=LOOKUP([Leader], 'Name', 'Title') = 'Manager'"
    }
    
    # Process formula
    logger.info(f"Processing formula: {formula_map['IsManager']}")
    
    with ExcelFormulaProcessor(visible=False, lookup_manager=lookup_manager) as processor:
        result_df = processor.process_formulas(primary_df, formula_map)
        
    logger.info("\nResults:")
    print(result_df)
    
    # Show the actual loaded data
    logger.info("\nHR Data loaded:")
    loaded_df = lookup_manager._ensure_loaded('test_data/hr.xlsx')
    if loaded_df is not None:
        print(loaded_df)
        logger.info(f"Column types: {loaded_df.dtypes}")
        logger.info(f"Name column values: {loaded_df['Name'].tolist()}")
        
    # Test a direct lookup
    logger.info("\nDirect lookup test:")
    test_result = lookup_manager.smart_lookup('John', 'Name', 'Title')
    logger.info(f"Lookup 'John' in Name column: {test_result}")
    
    # Check lookup operations
    if lookup_manager.get_tracked_operations():
        logger.info("\nLookup operations:")
        for op in lookup_manager.get_tracked_operations():
            logger.info(f"  {op['lookup_value']} -> {op['result']}")
    
    # Cleanup
    import shutil
    shutil.rmtree('test_data', ignore_errors=True)


if __name__ == "__main__":
    main()
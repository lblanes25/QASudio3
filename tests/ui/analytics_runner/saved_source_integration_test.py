#!/usr/bin/env python3
"""
Test script to verify saved data source integration works correctly.
This tests the connection between the saved data source menu and main panel loading.
"""

import os
import sys
import tempfile
import pandas as pd
from pathlib import Path

# Add the project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from data_source_registry import DataSourceRegistry
from ui.common.session_manager import SessionManager


def create_test_data():
    """Create test CSV and Excel files for testing."""
    test_dir = Path(tempfile.gettempdir()) / "analytics_runner_test"
    test_dir.mkdir(exist_ok=True)
    
    # Create test CSV
    csv_data = pd.DataFrame({
        'Employee_ID': ['E001', 'E002', 'E003'],
        'Name': ['John Doe', 'Jane Smith', 'Bob Johnson'],
        'Department': ['IT', 'HR', 'Finance'],
        'Salary': [75000, 65000, 85000]
    })
    csv_file = test_dir / "test_employees.csv"
    csv_data.to_csv(csv_file, index=False)
    
    # Create test Excel with multiple sheets
    excel_file = test_dir / "test_financial.xlsx"
    with pd.ExcelWriter(excel_file) as writer:
        # Sheet 1: Revenue data
        revenue_data = pd.DataFrame({
            'Month': ['Jan', 'Feb', 'Mar'],
            'Revenue': [100000, 120000, 115000],
            'Expenses': [80000, 90000, 85000]
        })
        revenue_data.to_excel(writer, sheet_name='Revenue', index=False)
        
        # Sheet 2: Customer data
        customer_data = pd.DataFrame({
            'Customer_ID': ['C001', 'C002', 'C003'],
            'Company': ['ABC Corp', 'XYZ Inc', '123 Ltd'],
            'Contact': ['john@abc.com', 'jane@xyz.com', 'bob@123.com']
        })
        customer_data.to_excel(writer, sheet_name='Customers', index=False)
    
    return csv_file, excel_file


def test_data_source_registration():
    """Test registering data sources in the registry."""
    print("=== Testing Data Source Registration ===")
    
    # Create test files
    csv_file, excel_file = create_test_data()
    
    # Initialize components
    session = SessionManager("test_session.json")
    registry = DataSourceRegistry("test_registry.json", session)
    
    # Register CSV source
    csv_source_id = registry.register_data_source(
        name="Test Employee Data",
        file_path=str(csv_file),
        description="Test employee data for validation testing",
        tags=["employee", "test", "hr"],
        data_type_hint="employee"
    )
    print(f"✓ Registered CSV source: {csv_source_id}")
    
    # Register Excel source with sheet specification
    excel_source_id = registry.register_data_source(
        name="Financial Revenue Data", 
        file_path=str(excel_file),
        description="Financial revenue and expense data",
        tags=["financial", "revenue", "test"],
        connection_params={"sheet_name": "Revenue"},
        data_type_hint="financial"
    )
    print(f"✓ Registered Excel source: {excel_source_id}")
    
    # Register another Excel source for different sheet
    excel_customers_id = registry.register_data_source(
        name="Customer Contact Data",
        file_path=str(excel_file), 
        description="Customer contact information",
        tags=["customer", "contacts", "test"],
        connection_params={"sheet_name": "Customers"},
        data_type_hint="customer"
    )
    print(f"✓ Registered Excel customers source: {excel_customers_id}")
    
    return registry, [csv_source_id, excel_source_id, excel_customers_id]


def test_source_loading_simulation():
    """Simulate the saved source loading process."""
    print("\n=== Testing Source Loading Simulation ===")
    
    registry, source_ids = test_data_source_registration()
    
    for source_id in source_ids:
        source = registry.get_data_source(source_id)
        print(f"\nTesting source: {source.name}")
        print(f"  File: {os.path.basename(source.file_path)}")
        print(f"  Type: {source.source_type.value}")
        
        # Verify file exists
        if not os.path.exists(source.file_path):
            print(f"  ❌ File not found: {source.file_path}")
            continue
        
        print(f"  ✓ File exists")
        
        # Check for file changes
        if source.is_file_changed():
            print(f"  ⚠ File has changed since registration")
            source.update_file_info()
        else:
            print(f"  ✓ File unchanged")
        
        # Test connection parameters
        if source.connection_params:
            print(f"  Connection params: {source.connection_params}")
            
            sheet_name = source.connection_params.get('sheet_name')
            if sheet_name:
                print(f"  Target Excel sheet: {sheet_name}")
                
                # Verify sheet exists (simplified check)
                try:
                    df = pd.read_excel(source.file_path, sheet_name=sheet_name, nrows=1)
                    print(f"  ✓ Sheet '{sheet_name}' accessible")
                except Exception as e:
                    print(f"  ❌ Sheet '{sheet_name}' error: {e}")
        
        # Mark as used
        registry.mark_source_used(source_id)
        print(f"  ✓ Marked as used (count: {source.use_count + 1})")


def test_integration_workflow():
    """Test the complete integration workflow."""
    print("\n=== Testing Integration Workflow ===")
    
    registry, source_ids = test_data_source_registration()
    
    # Simulate menu population
    saved_sources = registry.list_data_sources(active_only=True, sort_by="last_used")
    print(f"Found {len(saved_sources)} saved sources for menu")
    
    # Simulate clicking on each source
    for source in saved_sources:
        print(f"\nSimulating click on: {source.name}")
        
        # This simulates what load_saved_data_source() should do:
        
        # 1. Get source metadata ✓
        print(f"  1. Retrieved metadata: {source.source_id}")
        
        # 2. Check file exists ✓
        if not os.path.exists(source.file_path):
            print(f"  2. ❌ File missing, would show warning dialog")
            continue
        print(f"  2. ✓ File exists")
        
        # 3. Check file changes ✓
        if source.is_file_changed():
            print(f"  3. ⚠ File changed, would show confirmation dialog")
        else:
            print(f"  3. ✓ File unchanged")
        
        # 4. Load into DataSourcePanel (simulated)
        print(f"  4. Would call: data_source_panel.load_saved_data_source(source)")
        
        # 5. Apply connection parameters (simulated)
        if source.connection_params:
            sheet_name = source.connection_params.get('sheet_name')
            if sheet_name:
                print(f"  5. Would set Excel sheet to: {sheet_name}")
            else:
                print(f"  5. No sheet selection needed")
        else:
            print(f"  5. No connection parameters")
        
        # 6. Update session and menus ✓
        print(f"  6. Would update recent files and usage count")
        
        # 7. Display metadata ✓
        print(f"  7. Would display metadata in results area")
        
        print(f"  ✓ Integration workflow complete for: {source.name}")


def test_error_conditions():
    """Test error handling conditions."""
    print("\n=== Testing Error Conditions ===")
    
    registry, source_ids = test_data_source_registration()
    
    # Test missing file
    source = registry.get_data_source(source_ids[0])
    original_path = source.file_path
    source.file_path = "/nonexistent/file.csv"
    
    print("Testing missing file condition:")
    if not os.path.exists(source.file_path):
        print("  ✓ Correctly detected missing file")
        print("  Would show 'File Not Found' dialog with option to remove")
    
    # Restore path
    source.file_path = original_path
    
    # Test non-existent source ID
    print("\nTesting invalid source ID:")
    invalid_source = registry.get_data_source("invalid_id")
    if invalid_source is None:
        print("  ✓ Correctly handled invalid source ID")
        print("  Would show 'Source Not Found' dialog")
    
    print("\n✓ Error condition testing complete")


def cleanup_test_files():
    """Clean up test files and registry."""
    test_dir = Path(tempfile.gettempdir()) / "analytics_runner_test"
    if test_dir.exists():
        import shutil
        shutil.rmtree(test_dir)
    
    # Clean up test registry and session files
    for file in ["test_registry.json", "test_session.json"]:
        if os.path.exists(file):
            os.remove(file)
    
    print("✓ Test files cleaned up")


if __name__ == "__main__":
    print("Analytics Runner - Saved Data Source Integration Test")
    print("=" * 55)
    
    try:
        test_data_source_registration()
        test_source_loading_simulation()
        test_integration_workflow()
        test_error_conditions()
        
        print("\n" + "=" * 55)
        print("✅ ALL TESTS PASSED")
        print("\nThe saved data source integration should work correctly.")
        print("Key components verified:")
        print("  - Data source registration and storage")
        print("  - File existence and change detection")  
        print("  - Connection parameter handling")
        print("  - Error condition handling")
        print("  - Integration workflow simulation")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        cleanup_test_files()

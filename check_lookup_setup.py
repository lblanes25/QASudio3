#!/usr/bin/env python3
"""
Check if all lookup-related files and classes are properly set up
"""

import os
import sys
from pathlib import Path

print("Checking LOOKUP functionality setup...\n")

# Check if required directories exist
required_dirs = [
    "core/lookup",
    "core/formula_engine",
    "core/rule_engine",
    "services",
    "data/rules"
]

missing_dirs = []
for dir_path in required_dirs:
    if not os.path.exists(dir_path):
        missing_dirs.append(dir_path)
        print(f"❌ Missing directory: {dir_path}")
    else:
        print(f"✓ Directory exists: {dir_path}")

# Check if required files exist
required_files = [
    "core/lookup/smart_lookup_manager.py",
    "core/formula_engine/excel_formula_processor.py",
    "core/rule_engine/rule_evaluator.py",
    "services/validation_service.py",
    "services/progress_tracking_pipeline.py"
]

missing_files = []
for file_path in required_files:
    if not os.path.exists(file_path):
        missing_files.append(file_path)
        print(f"❌ Missing file: {file_path}")
    else:
        print(f"✓ File exists: {file_path}")

print("\n" + "="*50 + "\n")

# Try to import and check ValidationPipeline
try:
    from services.validation_service import ValidationPipeline
    print("✓ Successfully imported ValidationPipeline")
    
    # Check if __init__ accepts lookup_manager
    import inspect
    sig = inspect.signature(ValidationPipeline.__init__)
    params = list(sig.parameters.keys())
    
    if 'lookup_manager' in params:
        print("✓ ValidationPipeline.__init__ has 'lookup_manager' parameter")
    else:
        print("❌ ValidationPipeline.__init__ is missing 'lookup_manager' parameter")
        print(f"   Available parameters: {params}")
        
except ImportError as e:
    print(f"❌ Failed to import ValidationPipeline: {e}")

print("\n" + "="*50 + "\n")

# Try to import SmartLookupManager
try:
    from core.lookup.smart_lookup_manager import SmartLookupManager
    print("✓ Successfully imported SmartLookupManager")
except ImportError as e:
    print(f"❌ Failed to import SmartLookupManager: {e}")

# Check Python version
print(f"\nPython version: {sys.version}")

# Summary
print("\n" + "="*50)
print("SUMMARY:")
print("="*50)

if missing_dirs or missing_files:
    print("\n⚠️  Some required files/directories are missing!")
    print("\nMissing directories:")
    for d in missing_dirs:
        print(f"  - {d}")
    print("\nMissing files:")
    for f in missing_files:
        print(f"  - {f}")
    print("\nMake sure you copied ALL project files to the new PC.")
else:
    print("\n✓ All required files and directories are present.")
    
print("\nIf you're still getting the error, check:")
print("1. The services/validation_service.py file has the latest version")
print("2. No old .pyc files are cached (delete __pycache__ directories)")
print("3. You're running from the correct project directory")
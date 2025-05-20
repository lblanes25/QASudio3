#!/usr/bin/env python

import inspect
import os
import sys

# Print current directory and Python path for context
print(f"Current directory: {os.getcwd()}")
print("Python path:")
for p in sys.path:
    print(f"  {p}")

# Import the module directly
print("\nImporting module...")
import reporting.generation.report_generator_original

# Print module file location
module_file = inspect.getfile(reporting.generation.report_generator_original)
print(f"Module file: {module_file}")
print(f"Module file size: {os.path.getsize(module_file)} bytes")

# Reload the module to ensure we have the latest version
print("\nReloading module...")
import importlib

importlib.reload(reporting.generation.report_generator_original)

# Import and inspect the class
from reporting.generation.report_generator_original import ReportGenerator

# Create an instance
instance = ReportGenerator()

# Print the object and its dir
print(f"\nInstance type: {type(instance)}")
print(f"Module: {instance.__class__.__module__}")

# Print class definition
print("\nClass definition:")
print(inspect.getsource(ReportGenerator))

print("\nMethods:")
# Check for the specific methods we need
required_methods = [
    '_analyze_formula_components',
    '_calculate_score',
    'generate_excel',
    '_generate_formula_explanation',
    '_format_rule_explanation',
    '_add_calculation_columns',
    'generate_html'
]

for method in required_methods:
    has_method = hasattr(instance, method)
    print(f"  Has {method}? {has_method}")

    # If the method exists, print its source code
    if has_method:
        method_obj = getattr(instance.__class__, method)
        print(f"  Method source:")
        print(inspect.getsource(method_obj))

# Print all attributes
print("\nAll attributes:")
all_attrs = [attr for attr in dir(instance) if not attr.startswith('__')]
print(all_attrs)
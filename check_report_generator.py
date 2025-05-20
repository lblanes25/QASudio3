# check_report_generator.py
import sys
import os

# Import the actual implementation
from reporting.generation.report_generator_original import ReportGenerator

# Create an instance
instance = ReportGenerator()

# Print class details
print(f"ReportGenerator class from: {ReportGenerator.__module__}")
print(f"Module file: {sys.modules[ReportGenerator.__module__].__file__}")

# Check if methods exist on the class
print("\nChecking methods on class:")
for method in ['_analyze_formula_components', '_calculate_score', 'generate_excel',
               '_generate_formula_explanation', '_format_rule_explanation',
               'generate_html', '_extract_column_references']:
    print(f"  Has {method}? {hasattr(instance, method)}")

# Print all method names
print("\nAll methods:")
methods = [name for name in dir(instance) if callable(getattr(instance, name)) and not name.startswith('__')]
print(methods)
# fix_report_generator.py
import sys
import os

# Add the project root to the path if needed
# sys.path.insert(0, os.path.abspath('.'))

# Import both the test and the actual implementation
from reporting.generation.report_generator_original import ReportGenerator as ActualReportGenerator
from tests.test_report_generator import report_generator as TestFixture

# Check if they are the same class
actual_instance = ActualReportGenerator()
test_instance = TestFixture()

print(f"Actual ReportGenerator type: {type(actual_instance)}")
print(f"Test ReportGenerator type: {type(test_instance)}")
print(f"Are they the same class? {type(actual_instance) == type(test_instance)}")

# Print module paths
print(f"Actual module: {ActualReportGenerator.__module__}")
print(f"Module file: {sys.modules[ActualReportGenerator.__module__].__file__}")

# Check if methods exist on the actual class
print("\nChecking methods on actual class:")
for method in ['_analyze_formula_components', '_calculate_score', 'generate_excel',
               '_generate_formula_explanation', '_format_rule_explanation']:
    print(f"  Has {method}? {hasattr(actual_instance, method)}")
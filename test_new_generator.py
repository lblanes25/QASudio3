# Import our new class
from reporting.generation.report_generator import ReportGenerator

# Create an instance
instance = ReportGenerator()

# Check methods
print("Methods:")
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
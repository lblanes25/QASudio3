#!/usr/bin/env python3
"""
How to use the template-free summary generator.
"""

# To use the template-free generator in your code:

# Option 1: Direct usage
from reporting.generation.template_free_summary_generator import generate_template_free_summary

# In your report generation code, replace the template-based call with:
output_file = generate_template_free_summary(
    rule_results=rule_results,
    output_path="output/summary_report.xlsx",
    responsible_party_column="Responsible Party"
)

# Option 2: Modify template_integration.py
# In template_integration.py, find where it calls the template processor and add:
"""
# Add this import at the top
from reporting.generation.template_free_summary_generator import generate_template_free_summary

# Then in the generate_template_based_report function, add this option:
def generate_template_based_report(..., use_template_free=False):
    if use_template_free:
        return {
            'excel': generate_template_free_summary(rule_results, excel_path, responsible_party_column)
        }
    # ... existing template code ...
"""

# Option 3: Quick test
if __name__ == "__main__":
    print("Template-free summary generator is ready to use!")
    print("\nTo generate a summary report without templates:")
    print("1. Import: from reporting.generation.template_free_summary_generator import generate_template_free_summary")
    print("2. Call: generate_template_free_summary(rule_results, 'output.xlsx')")
    print("\nThis creates a clean Excel file from scratch with all three sections:")
    print("- Section 1: IAG Overall Results")
    print("- Section 2: Audit Leader Overall Results")  
    print("- Section 3: Detailed Test Results")
    print("\nNo template duplication issues!")
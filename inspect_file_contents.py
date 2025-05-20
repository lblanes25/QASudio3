# inspect_file_contents.py
import os

file_path = os.path.join('reporting', 'generation', 'report_generator_original.py')

print(f"Checking file: {file_path}")
print(f"File exists: {os.path.exists(file_path)}")
print(f"File size: {os.path.getsize(file_path)} bytes")

# Read the first 100 characters and the last 100 characters to verify it's the expected file
with open(file_path, 'r') as f:
    content = f.read()
    print(f"File length: {len(content)} characters")
    print(f"First 100 chars: {content[:100]}")
    print(f"Last 100 chars: {content[-100:]}")

    # Check for key methods
    methods = [
        "_calculate_score",
        "_analyze_formula_components",
        "_generate_formula_explanation",
        "generate_excel"
    ]

    for method in methods:
        if method in content:
            print(f"Method '{method}' FOUND in file")
        else:
            print(f"Method '{method}' NOT FOUND in file")
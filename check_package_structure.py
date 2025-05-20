# check_package_structure.py
import os
import sys

# Check project structure
project_dirs = ['reporting', 'reporting/generation', 'tests']
for directory in project_dirs:
    if os.path.exists(directory):
        init_file = os.path.join(directory, '__init__.py')
        has_init = os.path.exists(init_file)
        print(f"Directory {directory} exists: Yes, has __init__.py: {has_init}")
    else:
        print(f"Directory {directory} exists: No")

# Print Python path
print("\nPython path:")
for path in sys.path:
    print(f"  {path}")
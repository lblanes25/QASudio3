import os

EXCLUDED_DIRS = {'.claude', '.venv', '.api', '.git', '.idea', '.pytest_cache', '_pycache__', '__pycache__',}


def print_tree(start_path='.', prefix=''):
    try:
        entries = sorted(os.listdir(start_path))
    except PermissionError:
        return  # Skip directories you can't access

    entries = [e for e in entries if e not in EXCLUDED_DIRS]

    for i, entry in enumerate(entries):
        full_path = os.path.join(start_path, entry)
        connector = '└── ' if i == len(entries) - 1 else '├── '
        print(prefix + connector + entry)
        if os.path.isdir(full_path) and entry not in EXCLUDED_DIRS:
            extension = '    ' if i == len(entries) - 1 else '│   '
            print_tree(full_path, prefix + extension)


# Run the function on the current directory
print_tree('.')

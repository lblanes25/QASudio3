#!/usr/bin/env python3
"""
Import Statement Updater for QA Analytics Framework
Updates import statements after project reorganization.
"""

import os
import re
import logging
from pathlib import Path
from datetime import datetime
import argparse

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ImportUpdater:
    """Updates import statements after project reorganization"""
    
    def __init__(self, project_root: Path, dry_run: bool = True):
        self.project_root = Path(project_root)
        self.dry_run = dry_run
        self.updates_made = []
        self.errors = []
        
        # Define import mappings (old_import -> new_import)
        self.import_mappings = {
            # Common components
            'from ui.common.stylesheet import': 'from ui.common.stylesheet import',
            'from ui.common.session_manager import': 'from ui.common.session_manager import',
            'from ui.common.error_handler import': 'from ui.common.error_handler import',
            'from ui.common import stylesheet': 'from ui.common import stylesheet',
            'from ui.common import session_manager': 'from ui.common from ui.common import session_manager',
            
            # Widget imports
            'from ui.common.widgets.file_selector_widget import': 'from ui.common.widgets.file_selector_widget import',
            'from ui.common.widgets.progress_widget import': 'from ui.common.widgets.progress_widget import',
            'from ui.common.widgets.results_table_widget import': 'from ui.common.widgets.results_table_widget import',
            'from ui.common.widgets.log_widget import': 'from ui.common.widgets.log_widget import',
            'from ui.common.widgets.pre_validation_widget import': 'from ui.common.widgets.pre_validation_widget import',
            
            # Dialog imports
            'from ui.analytics_runner.dialogs.save_data_source_dialog import': 'from ui.analytics_runner.dialogs.save_data_source_dialog import',
            'from ui.analytics_runner.dialogs.debug_panel import': 'from ui.analytics_runner.dialogs.debug_panel import',
            
            # Rule builder imports
            'from ui.rule_builder.editors.simple_rule_editor import': 'from ui.rule_builder.editors.simple_rule_editor import',
            'from ui.rule_builder.editors.advanced_rule_editor import': 'from ui.rule_builder.editors.advanced_rule_editor import',
            'from ui.rule_builder.panels.data_loader_panel import': 'from ui.rule_builder.panels.data_loader_panel import',
            'from ui.rule_builder.panels.rule_preview_panel import': 'from ui.rule_builder.panels.rule_preview_panel import',
            'from ui.rule_builder.panels.rule_test_panel import': 'from ui.rule_builder.panels.rule_test_panel import',
            
            # Convenience imports
            'AnalyticsRunnerStylesheet': 'AnalyticsRunnerStylesheet',  # Class name stays same
            'SessionManager': 'SessionManager',  # Class name stays same
        }
        
        # Files that need special handling
        self.special_files = {
            'ui/analytics_runner/main_application.py': self.update_main_application,
            'ui/rule_builder/main_window.py': self.update_rule_builder_main,
        }
    
    def find_python_files(self):
        """Find all Python files in the project"""
        python_files = []
        
        for root, dirs, files in os.walk(self.project_root):
            # Skip certain directories
            skip_dirs = {'.git', '__pycache__', '.pytest_cache', 'backup_', '.venv', 'venv'}
            dirs[:] = [d for d in dirs if not any(skip in d for skip in skip_dirs)]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(Path(root) / file)
        
        return python_files
    
    def update_file_imports(self, file_path: Path):
        """Update imports in a single file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Apply import mappings
            for old_import, new_import in self.import_mappings.items():
                if old_import in content:
                    content = content.replace(old_import, new_import)
                    logger.debug(f"In {file_path}: {old_import} -> {new_import}")
            
            # Special file handling
            rel_path = file_path.relative_to(self.project_root)
            if str(rel_path) in self.special_files:
                content = self.special_files[str(rel_path)](content, file_path)
            
            # Check if changes were made
            if content != original_content:
                if self.dry_run:
                    logger.info(f"DRY RUN: Would update imports in {rel_path}")
                else:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    logger.info(f"Updated imports in {rel_path}")
                
                self.updates_made.append(str(rel_path))
                return True
            
            return False
            
        except Exception as e:
            error_msg = f"Error updating {file_path}: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False
    
    def update_main_application(self, content: str, file_path: Path) -> str:
        """Special handling for main_application.py"""
        
        # Update specific imports for main application
        updates = [
            # Common imports at top
            ('from ui.common.stylesheet import AnalyticsRunnerStylesheet', 
             'from ui.common.stylesheet import AnalyticsRunnerStylesheet'),
            ('from ui.common.session_manager import SessionManager', 
             'from ui.common.session_manager import SessionManager'),
            ('from ui.common.error_handler import', 
             'from ui.common.error_handler import'),
             
            # Panel imports
            ('from data_source_panel import DataSourcePanel', 
             'from .data_source_panel import DataSourcePanel'),
            ('from rule_selector_panel import RuleSelectorPanel', 
             'from .rule_selector_panel import RuleSelectorPanel'),
            ('from data_source_registry import DataSourceRegistry', 
             'from .data_source_registry import DataSourceRegistry'),
             
            # Dialog imports
            ('from ui.analytics_runner.dialogs.save_data_source_dialog import SaveDataSourceDialog', 
             'from .dialogs.save_data_source_dialog import SaveDataSourceDialog'),
            ('from ui.analytics_runner.dialogs.debug_panel import DebugPanel', 
             'from .dialogs.debug_panel import DebugPanel'),
        ]
        
        for old, new in updates:
            content = content.replace(old, new)
        
        return content
    
    def update_rule_builder_main(self, content: str, file_path: Path) -> str:
        """Special handling for rule builder main_window.py"""
        
        updates = [
            # Editor imports
            ('from ui.rule_builder.editors.simple_rule_editor import SimpleRuleEditor', 
             'from .editors.simple_rule_editor import SimpleRuleEditor'),
            ('from ui.rule_builder.editors.advanced_rule_editor import AdvancedRuleEditor', 
             'from .editors.advanced_rule_editor import AdvancedRuleEditor'),
             
            # Panel imports
            ('from ui.rule_builder.panels.data_loader_panel import DataLoaderPanel', 
             'from .panels.data_loader_panel import DataLoaderPanel'),
            ('from ui.rule_builder.panels.rule_preview_panel import RulePreviewPanel', 
             'from .panels.rule_preview_panel import RulePreviewPanel'),
            ('from ui.rule_builder.panels.rule_test_panel import RuleTestPanel', 
             'from .panels.rule_test_panel import RuleTestPanel'),
             
            # Common imports
            ('from stylesheet import Stylesheet', 
             'from ui.common.stylesheet import AnalyticsRunnerStylesheet as Stylesheet'),
        ]
        
        for old, new in updates:
            content = content.replace(old, new)
        
        return content
    
    def update_path_references(self):
        """Update hardcoded path references in code"""
        logger.info("Updating hardcoded path references...")
        
        path_updates = {
            # Session file paths
            '"data/sessions/session.json"': '"data/sessions/session.json"',
            "'data/sessions/session.json'": "'data/sessions/session.json'",
            
            # Data source paths
            '"data/sessions/data_sources.json"': '"data/sessions/data_sources.json"',
            "'data/sessions/data_sources.json'": "'data/sessions/data_sources.json'",
            
            # Rule paths
            '"data/rules"': '"data/rules"',
            "'data/rules'": "'data/rules'",
            '"data/rules/"': '"data/rules/"',
            "'data/rules/'": "'data/rules/'",
            
            # Log paths
            '"data/logs/"': '"data/logs/"',
            "'data/logs/'": "'data/logs/'",
        }
        
        python_files = self.find_python_files()
        
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                for old_path, new_path in path_updates.items():
                    content = content.replace(old_path, new_path)
                
                if content != original_content:
                    if self.dry_run:
                        rel_path = file_path.relative_to(self.project_root)
                        logger.info(f"DRY RUN: Would update paths in {rel_path}")
                    else:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        rel_path = file_path.relative_to(self.project_root)
                        logger.info(f"Updated paths in {rel_path}")
                
            except Exception as e:
                logger.error(f"Error updating paths in {file_path}: {e}")
    
    def create_migration_guide(self):
        """Create a guide for manual import updates"""
        guide_content = '''# Import Update Guide

After reorganization, you may need to manually update some imports.

## Common Import Patterns

### Before:
```python
from ui.common.stylesheet import AnalyticsRunnerStylesheet
from ui.common.session_manager import SessionManager
from ui.common.error_handler import ErrorHandler
```

### After:
```python
from ui.common.stylesheet import AnalyticsRunnerStylesheet
from ui.common.session_manager import SessionManager
from ui.common.error_handler import ErrorHandler
```

### Or use convenience imports:
```python
from ui.common import AnalyticsRunnerStylesheet, SessionManager, ErrorHandler
```

## Widget Imports

### Before:
```python
from ui.common.widgets.file_selector_widget import FileSelector
from ui.common.widgets.progress_widget import ProgressWidget
```

### After:
```python
from ui.common.widgets.file_selector_widget import FileSelector
from ui.common.widgets.progress_widget import ProgressWidget
```

## Panel Imports (within analytics_runner)

### Before:
```python
from data_source_panel import DataSourcePanel
from rule_selector_panel import RuleSelectorPanel
```

### After:
```python
from .data_source_panel import DataSourcePanel
from .rule_selector_panel import RuleSelectorPanel
```

## Dialog Imports

### Before:
```python
from ui.analytics_runner.dialogs.save_data_source_dialog import SaveDataSourceDialog
from ui.analytics_runner.dialogs.debug_panel import DebugPanel
```

### After:
```python
from .dialogs.save_data_source_dialog import SaveDataSourceDialog
from .dialogs.debug_panel import DebugPanel
```

## Path Updates

- Session files: `"data/sessions/session.json"` → `"data/sessions/session.json"`
- Data sources: `"data/sessions/data_sources.json"` → `"data/sessions/data_sources.json"`
- Rules: `"data/rules"` → `"data/rules"`
- Logs: `"data/logs/"` → `"data/logs/"`

## Testing After Update

1. Run tests: `python -m pytest tests/`
2. Start analytics runner: `python ui/analytics_runner/main_application.py`
3. Start rule builder: `python ui/rule_builder/main.py`
4. Check for import errors in logs
'''
        
        if not self.dry_run:
            guide_path = self.project_root / 'IMPORT_UPDATE_GUIDE.md'
            with open(guide_path, 'w') as f:
                f.write(guide_content)
            logger.info("Created IMPORT_UPDATE_GUIDE.md")
        else:
            logger.info("DRY RUN: Would create IMPORT_UPDATE_GUIDE.md")
    
    def run_updates(self):
        """Run all import updates"""
        logger.info("Starting import statement updates...")
        
        # Find all Python files
        python_files = self.find_python_files()
        logger.info(f"Found {len(python_files)} Python files")
        
        # Update imports in each file
        updated_count = 0
        for file_path in python_files:
            if self.update_file_imports(file_path):
                updated_count += 1
        
        # Update path references
        self.update_path_references()
        
        # Create migration guide
        self.create_migration_guide()
        
        # Print summary
        logger.info("=" * 50)
        logger.info("IMPORT UPDATE SUMMARY")
        logger.info("=" * 50)
        
        if self.dry_run:
            logger.info("DRY RUN COMPLETED - No files were actually modified")
        else:
            logger.info(f"Updated imports in {updated_count} files")
        
        if self.errors:
            logger.warning(f"Encountered {len(self.errors)} errors:")
            for error in self.errors:
                logger.warning(f"  - {error}")
        
        if not self.dry_run:
            logger.info("\nNext steps:")
            logger.info("1. Test the application")
            logger.info("2. Check IMPORT_UPDATE_GUIDE.md for manual updates")
            logger.info("3. Run tests to verify everything works")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Update import statements after reorganization')
    parser.add_argument('--project-root', '-p', default='.', help='Project root directory')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be changed')
    parser.add_argument('--force', action='store_true', help='Actually update the imports')
    
    args = parser.parse_args()
    
    if not args.force and not args.dry_run:
        print("This script will update import statements in your Python files.")
        print("Use --dry-run to see what would be changed, or --force to apply changes.")
        return 1
    
    try:
        updater = ImportUpdater(
            project_root=Path(args.project_root).resolve(),
            dry_run=args.dry_run
        )
        
        updater.run_updates()
        return 0
        
    except Exception as e:
        logger.error(f"Import update failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

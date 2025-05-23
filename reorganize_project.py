#!/usr/bin/env python3
"""
Project Reorganization Script for QA Analytics Framework
Safely reorganizes the project structure to reduce confusion and improve maintainability.
"""

import os
import shutil
import logging
from pathlib import Path
from datetime import datetime
import json
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'reorganization_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ProjectReorganizer:
    """Handles the safe reorganization of the QA Analytics Framework project"""
    
    def __init__(self, project_root: Path, dry_run: bool = True):
        self.project_root = Path(project_root)
        self.dry_run = dry_run
        self.backup_dir = self.project_root / f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.moves_performed = []
        self.errors = []
        
        logger.info(f"Initializing project reorganization")
        logger.info(f"Project root: {self.project_root}")
        logger.info(f"Dry run mode: {self.dry_run}")
        
    def create_backup(self):
        """Create a full backup before making changes"""
        if self.dry_run:
            logger.info("DRY RUN: Would create backup directory")
            return
            
        try:
            # Create backup of critical files
            critical_files = [
                'ui/analytics_runner/main_application.py',
                'ui/analytics_runner/session_manager.py',
                'ui/analytics_runner/analytics_runner_stylesheet.py',
                'data/sessions/session.json',
                'data/sessions/data_sources.json'
            ]
            
            self.backup_dir.mkdir(exist_ok=True)
            logger.info(f"Created backup directory: {self.backup_dir}")
            
            for file_path in critical_files:
                src = self.project_root / file_path
                if src.exists():
                    dst = self.backup_dir / file_path
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
                    logger.info(f"Backed up: {file_path}")
                    
        except Exception as e:
            logger.error(f"Error creating backup: {e}")
            raise
    
    def create_new_structure(self):
        """Create the new directory structure"""
        new_dirs = [
            'ui/common',
            'ui/common/widgets',
            'ui/analytics_runner/dialogs',
            'ui/rule_builder/editors',
            'ui/rule_builder/panels',
            'tests/unit/core',
            'tests/unit/data_integration',
            'tests/unit/business_logic',
            'tests/unit/services',
            'tests/integration',
            'tests/ui/analytics_runner',
            'tests/ui/rule_builder',
            'data/rules',
            'data/sessions',
            'data/logs',
            'data/temp',
        ]
        
        for dir_path in new_dirs:
            full_path = self.project_root / dir_path
            if self.dry_run:
                logger.info(f"DRY RUN: Would create directory: {dir_path}")
            else:
                try:
                    full_path.mkdir(parents=True, exist_ok=True)
                    # Create __init__.py files for Python packages
                    if 'ui/' in dir_path or 'tests/' in dir_path:
                        init_file = full_path / '__init__.py'
                        if not init_file.exists():
                            init_file.touch()
                    logger.info(f"Created directory: {dir_path}")
                except Exception as e:
                    logger.error(f"Error creating directory {dir_path}: {e}")
                    self.errors.append(f"Directory creation failed: {dir_path} - {e}")
    
    def safe_move(self, src_path: str, dst_path: str, description: str = ""):
        """Safely move a file or directory"""
        src = self.project_root / src_path
        dst = self.project_root / dst_path
        
        if not src.exists():
            logger.warning(f"Source does not exist: {src_path}")
            return False
            
        if dst.exists():
            logger.warning(f"Destination already exists: {dst_path}")
            return False
            
        if self.dry_run:
            logger.info(f"DRY RUN: Would move {src_path} → {dst_path} ({description})")
            return True
            
        try:
            # Ensure destination directory exists
            dst.parent.mkdir(parents=True, exist_ok=True)
            
            # Move the file/directory
            shutil.move(str(src), str(dst))
            logger.info(f"Moved: {src_path} → {dst_path} ({description})")
            self.moves_performed.append((src_path, dst_path, description))
            return True
            
        except Exception as e:
            error_msg = f"Error moving {src_path} to {dst_path}: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False
    
    def safe_copy(self, src_path: str, dst_path: str, description: str = ""):
        """Safely copy a file (for consolidation)"""
        src = self.project_root / src_path
        dst = self.project_root / dst_path
        
        if not src.exists():
            logger.warning(f"Source does not exist: {src_path}")
            return False
            
        if self.dry_run:
            logger.info(f"DRY RUN: Would copy {src_path} → {dst_path} ({description})")
            return True
            
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(src), str(dst))
            logger.info(f"Copied: {src_path} → {dst_path} ({description})")
            return True
            
        except Exception as e:
            error_msg = f"Error copying {src_path} to {dst_path}: {e}"
            logger.error(error_msg)
            self.errors.append(error_msg)
            return False
    
    def move_common_components(self):
        """Move shared UI components to ui/common/"""
        logger.info("=" * 50)
        logger.info("PHASE 1: Moving Common Components")
        logger.info("=" * 50)
        
        moves = [
            # Core common files
            ('ui/analytics_runner/analytics_runner_stylesheet.py', 'ui/common/stylesheet.py', 'Unified stylesheet'),
            ('ui/analytics_runner/session_manager.py', 'ui/common/session_manager.py', 'Shared session management'),
            ('ui/analytics_runner/error_handler.py', 'ui/common/error_handler.py', 'Shared error handling'),
            
            # Reusable widgets
            ('ui/analytics_runner/file_selector_widget.py', 'ui/common/widgets/file_selector_widget.py', 'Reusable file selector'),
            ('ui/analytics_runner/progress_widget.py', 'ui/common/widgets/progress_widget.py', 'Reusable progress widget'),
            ('ui/analytics_runner/results_table_widget.py', 'ui/common/widgets/results_table_widget.py', 'Reusable results table'),
            ('ui/analytics_runner/log_widget.py', 'ui/common/widgets/log_widget.py', 'Reusable log widget'),
            ('ui/analytics_runner/pre_validation_widget.py', 'ui/common/widgets/pre_validation_widget.py', 'Reusable validation widget'),
        ]
        
        for src, dst, desc in moves:
            self.safe_move(src, dst, desc)
    
    def move_analytics_runner_components(self):
        """Reorganize Analytics Runner components"""
        logger.info("=" * 50)
        logger.info("PHASE 2: Reorganizing Analytics Runner")
        logger.info("=" * 50)
        
        moves = [
            # Move dialogs
            ('ui/analytics_runner/save_data_source_dialog.py', 'ui/analytics_runner/dialogs/save_data_source_dialog.py', 'Dialog component'),
            ('ui/analytics_runner/debug_panel.py', 'ui/analytics_runner/dialogs/debug_panel.py', 'Dialog component'),
        ]
        
        for src, dst, desc in moves:
            self.safe_move(src, dst, desc)
    
    def move_rule_builder_components(self):
        """Reorganize Rule Builder components"""
        logger.info("=" * 50)
        logger.info("PHASE 3: Reorganizing Rule Builder")
        logger.info("=" * 50)
        
        moves = [
            # Move editors
            ('ui/rule_builder/simple_rule_editor.py', 'ui/rule_builder/editors/simple_rule_editor.py', 'Rule editor'),
            ('ui/rule_builder/advanced_rule_editor.py', 'ui/rule_builder/editors/advanced_rule_editor.py', 'Rule editor'),
            
            # Move panels  
            ('ui/rule_builder/data_loader_panel.py', 'ui/rule_builder/panels/data_loader_panel.py', 'Data panel'),
            ('ui/rule_builder/rule_preview_panel.py', 'ui/rule_builder/panels/rule_preview_panel.py', 'Preview panel'),
            ('ui/rule_builder/rule_test_panel.py', 'ui/rule_builder/panels/rule_test_panel.py', 'Test panel'),
        ]
        
        for src, dst, desc in moves:
            self.safe_move(src, dst, desc)
    
    def move_test_files(self):
        """Reorganize test files"""
        logger.info("=" * 50)
        logger.info("PHASE 4: Reorganizing Tests")
        logger.info("=" * 50)
        
        # Move integration tests
        integration_tests = [
            'tests/test_validation_pipeline.py',
            'tests/test_data_integration.py', 
            'tests/test_analytics_aggregator.py',
            'tests/test_excel_connection.py',
            'tests/test_complex_formulas.py',
            'tests/test_rule_engine.py',
            'tests/test_yaml_rule_loading.py',
        ]
        
        for test_file in integration_tests:
            if (self.project_root / test_file).exists():
                filename = Path(test_file).name
                self.safe_move(test_file, f'tests/integration/{filename}', 'Integration test')
        
        # Move UI tests from analytics_runner
        ui_test_patterns = [
            'ui/analytics_runner/test_*.py',
            'ui/analytics_runner/*_test.py',
        ]
        
        analytics_runner_dir = self.project_root / 'ui/analytics_runner'
        if analytics_runner_dir.exists():
            for file_path in analytics_runner_dir.iterdir():
                if file_path.is_file() and ('test_' in file_path.name or file_path.name.endswith('_test.py')):
                    rel_path = file_path.relative_to(self.project_root)
                    self.safe_move(str(rel_path), f'tests/ui/analytics_runner/{file_path.name}', 'UI test')
    
    def consolidate_data_files(self):
        """Consolidate data files into data/ directory"""
        logger.info("=" * 50)
        logger.info("PHASE 5: Consolidating Data Files")
        logger.info("=" * 50)
        
        # Move rules
        if (self.project_root / 'rules').exists():
            self.safe_move('rules', 'data/rules', 'Rule storage')
        
        # Consolidate session files
        session_files = [
            'data/sessions/session.json',
            'ui/analytics_runner/session.json',
            'data/sessions/data_sources.json',
            'ui/analytics_runner/data_sources.json',
        ]
        
        for session_file in session_files:
            if (self.project_root / session_file).exists():
                filename = Path(session_file).name
                # Check if we already moved this file
                target = f'data/sessions/{filename}'
                if not (self.project_root / target).exists():
                    self.safe_copy(session_file, target, 'Session data')
        
        # Move logs
        log_dirs = [
            'logs',
            'ui/analytics_runner/logs',
        ]
        
        for log_dir in log_dirs:
            log_path = self.project_root / log_dir
            if log_path.exists() and log_path.is_dir():
                for log_file in log_path.iterdir():
                    if log_file.is_file():
                        rel_path = log_file.relative_to(self.project_root)
                        self.safe_copy(str(rel_path), f'data/logs/{log_file.name}', 'Log file')
    
    def cleanup_empty_directories(self):
        """Remove empty directories and backup folders"""
        logger.info("=" * 50)
        logger.info("PHASE 6: Cleaning Up")
        logger.info("=" * 50)
        
        # Directories to clean up
        cleanup_dirs = [
            'ui/analytics_runner/session_backups',
            'session_backups',
            'test_output',
        ]
        
        for cleanup_dir in cleanup_dirs:
            dir_path = self.project_root / cleanup_dir
            if dir_path.exists():
                if self.dry_run:
                    logger.info(f"DRY RUN: Would remove directory: {cleanup_dir}")
                else:
                    try:
                        shutil.rmtree(dir_path)
                        logger.info(f"Removed directory: {cleanup_dir}")
                    except Exception as e:
                        logger.warning(f"Could not remove {cleanup_dir}: {e}")
        
        # Remove duplicate files
        duplicate_files = [
            'ui/analytics_runner/session.json',  # After moving to data/sessions
            'ui/analytics_runner/data_sources.json',
        ]
        
        for dup_file in duplicate_files:
            file_path = self.project_root / dup_file
            if file_path.exists():
                if self.dry_run:
                    logger.info(f"DRY RUN: Would remove duplicate: {dup_file}")
                else:
                    try:
                        file_path.unlink()
                        logger.info(f"Removed duplicate: {dup_file}")
                    except Exception as e:
                        logger.warning(f"Could not remove {dup_file}: {e}")
    
    def create_import_helpers(self):
        """Create __init__.py files with import helpers"""
        logger.info("=" * 50)
        logger.info("PHASE 7: Creating Import Helpers")
        logger.info("=" * 50)
        
        # UI Common init file
        common_init = '''"""
Common UI components for QA Analytics Framework
"""

from .stylesheet import AnalyticsRunnerStylesheet
from .session_manager import SessionManager

try:
    from .error_handler import ErrorHandler
    __all__ = ['AnalyticsRunnerStylesheet', 'SessionManager', 'ErrorHandler']
except ImportError:
    __all__ = ['AnalyticsRunnerStylesheet', 'SessionManager']
'''
        
        # Widgets init file
        widgets_init = '''"""
Reusable UI widgets
"""

# Import widgets as they become available
try:
    from .file_selector_widget import FileSelector
    from .progress_widget import ProgressWidget
    from .results_table_widget import ResultsTableWidget
    from .log_widget import LogWidget
    
    __all__ = ['FileSelector', 'ProgressWidget', 'ResultsTableWidget', 'LogWidget']
except ImportError:
    # Some widgets may not exist yet
    __all__ = []
'''
        
        if not self.dry_run:
            # Write ui/common/__init__.py
            common_init_path = self.project_root / 'ui/common/__init__.py'
            with open(common_init_path, 'w') as f:
                f.write(common_init)
            logger.info("Created: ui/common/__init__.py")
            
            # Write ui/common/widgets/__init__.py
            widgets_init_path = self.project_root / 'ui/common/widgets/__init__.py'
            with open(widgets_init_path, 'w') as f:
                f.write(widgets_init)
            logger.info("Created: ui/common/widgets/__init__.py")
        else:
            logger.info("DRY RUN: Would create import helper files")
    
    def create_gitignore_updates(self):
        """Create or update .gitignore for the new structure"""
        logger.info("=" * 50)
        logger.info("PHASE 8: Updating .gitignore")
        logger.info("=" * 50)
        
        gitignore_additions = '''
# Data directory (runtime files)
data/sessions/*.json
data/logs/*.log
data/temp/*
!data/sessions/.gitkeep
!data/logs/.gitkeep
!data/temp/.gitkeep

# Backup directories
backup_*/
*_backup*/

# Session files
session*.json
'''
        
        if not self.dry_run:
            gitignore_path = self.project_root / '.gitignore'
            with open(gitignore_path, 'a') as f:
                f.write(gitignore_additions)
            logger.info("Updated .gitignore")
            
            # Create .gitkeep files
            for keepdir in ['data/sessions', 'data/logs', 'data/temp']:
                keepfile = self.project_root / keepdir / '.gitkeep'
                keepfile.parent.mkdir(parents=True, exist_ok=True)
                keepfile.touch()
        else:
            logger.info("DRY RUN: Would update .gitignore")
    
    def run_reorganization(self):
        """Run the complete reorganization process"""
        logger.info("Starting project reorganization...")
        
        try:
            # Create backup
            self.create_backup()
            
            # Create new structure
            self.create_new_structure()
            
            # Move files in phases
            self.move_common_components()
            self.move_analytics_runner_components()
            self.move_rule_builder_components()
            self.move_test_files()
            self.consolidate_data_files()
            
            # Cleanup and finalize
            self.cleanup_empty_directories()
            self.create_import_helpers()
            self.create_gitignore_updates()
            
            # Summary
            self.print_summary()
            
        except Exception as e:
            logger.error(f"Reorganization failed: {e}")
            raise
    
    def print_summary(self):
        """Print summary of changes"""
        logger.info("=" * 60)
        logger.info("REORGANIZATION SUMMARY")
        logger.info("=" * 60)
        
        if self.dry_run:
            logger.info("DRY RUN COMPLETED - No files were actually moved")
        else:
            logger.info(f"Successfully moved {len(self.moves_performed)} items")
            
        if self.errors:
            logger.warning(f"Encountered {len(self.errors)} errors:")
            for error in self.errors:
                logger.warning(f"  - {error}")
        
        logger.info("\nNext steps:")
        logger.info("1. Update import statements in Python files")
        logger.info("2. Test the application to ensure everything works")
        logger.info("3. Commit the reorganized structure")
        logger.info("4. Remove backup directory when satisfied")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='Reorganize QA Analytics Framework project structure')
    parser.add_argument('--project-root', '-p', default='.', help='Project root directory (default: current)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--force', action='store_true', help='Actually perform the reorganization')
    
    args = parser.parse_args()
    
    if not args.force and not args.dry_run:
        print("This script will reorganize your project structure.")
        print("Use --dry-run to see what would be changed, or --force to apply changes.")
        print("It's recommended to run with --dry-run first!")
        return 1
    
    try:
        reorganizer = ProjectReorganizer(
            project_root=Path(args.project_root).resolve(),
            dry_run=args.dry_run
        )
        
        reorganizer.run_reorganization()
        return 0
        
    except Exception as e:
        logger.error(f"Reorganization failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

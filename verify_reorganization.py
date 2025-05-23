#!/usr/bin/env python3
"""
Verification Script for Project Reorganization
Checks that the reorganized project structure is working correctly.
"""

import sys
import os
import importlib
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


class ReorganizationVerifier:
    """Verifies the reorganized project structure"""
    
    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)
        self.errors = []
        self.warnings = []
        self.success_count = 0
        self.total_tests = 0
    
    def test_directory_structure(self):
        """Test that expected directories exist"""
        logger.info("Testing directory structure...")
        
        expected_dirs = [
            'ui/common',
            'ui/common/widgets', 
            'ui/analytics_runner',
            'ui/analytics_runner/dialogs',
            'ui/rule_builder/editors',
            'ui/rule_builder/panels',
            'tests/integration',
            'tests/ui/analytics_runner',
            'data/rules',
            'data/sessions',
            'data/logs',
        ]
        
        for dir_path in expected_dirs:
            self.total_tests += 1
            full_path = self.project_root / dir_path
            if full_path.exists():
                logger.info(f"✓ Directory exists: {dir_path}")
                self.success_count += 1
            else:
                error_msg = f"✗ Missing directory: {dir_path}"
                logger.error(error_msg)
                self.errors.append(error_msg)
    
    def test_file_locations(self):
        """Test that key files are in expected locations"""
        logger.info("Testing file locations...")
        
        expected_files = [
            'ui/common/stylesheet.py',
            'ui/common/session_manager.py',
            'ui/analytics_runner/main_application.py',
            'ui/analytics_runner/data_source_panel.py',
            'ui/rule_builder/main.py',
            'ui/rule_builder/main_window.py',
        ]
        
        for file_path in expected_files:
            self.total_tests += 1
            full_path = self.project_root / file_path
            if full_path.exists():
                logger.info(f"✓ File exists: {file_path}")
                self.success_count += 1
            else:
                error_msg = f"✗ Missing file: {file_path}"
                logger.error(error_msg)
                self.errors.append(error_msg)
    
    def test_imports(self):
        """Test that imports work correctly"""
        logger.info("Testing imports...")
        
        # Add project root to Python path
        sys.path.insert(0, str(self.project_root))
        
        import_tests = [
            ('ui.common.stylesheet', 'AnalyticsRunnerStylesheet'),
            ('ui.common.session_manager', 'SessionManager'),
            ('core.rule_engine.rule_manager', 'ValidationRule'),
            ('services.validation_service', 'ValidationPipeline'),
        ]
        
        for module_name, class_name in import_tests:
            self.total_tests += 1
            try:
                module = importlib.import_module(module_name)
                if hasattr(module, class_name):
                    logger.info(f"✓ Import works: {module_name}.{class_name}")
                    self.success_count += 1
                else:
                    error_msg = f"✗ Class not found: {module_name}.{class_name}"
                    logger.error(error_msg)
                    self.errors.append(error_msg)
            except ImportError as e:
                error_msg = f"✗ Import failed: {module_name} - {e}"
                logger.error(error_msg)
                self.errors.append(error_msg)
    
    def test_ui_imports(self):
        """Test UI-specific imports"""
        logger.info("Testing UI imports...")
        
        # Try importing main UI components
        ui_tests = [
            'ui.analytics_runner.main_application',
            'ui.analytics_runner.data_source_panel',
            'ui.rule_builder.main_window',
        ]
        
        for module_name in ui_tests:
            self.total_tests += 1
            try:
                importlib.import_module(module_name)
                logger.info(f"✓ UI import works: {module_name}")
                self.success_count += 1
            except ImportError as e:
                # This might fail due to PySide6 dependencies, so it's a warning
                warning_msg = f"⚠ UI import issue: {module_name} - {e}"
                logger.warning(warning_msg)
                self.warnings.append(warning_msg)
    
    def test_data_directories(self):
        """Test that data directories are set up correctly"""
        logger.info("Testing data directories...")
        
        # Check for .gitkeep files or existing data
        data_checks = [
            ('data/rules', 'Rule storage directory'),
            ('data/sessions', 'Session storage directory'),
            ('data/logs', 'Log storage directory'),
        ]
        
        for dir_path, description in data_checks:
            self.total_tests += 1
            full_path = self.project_root / dir_path
            if full_path.exists():
                # Check if directory has content or .gitkeep
                contents = list(full_path.iterdir())
                if contents:
                    logger.info(f"✓ {description} ready: {dir_path}")
                    self.success_count += 1
                else:
                    # Create .gitkeep if missing
                    gitkeep = full_path / '.gitkeep'
                    gitkeep.touch()
                    logger.info(f"✓ {description} prepared: {dir_path}")
                    self.success_count += 1
            else:
                error_msg = f"✗ Missing {description}: {dir_path}"
                logger.error(error_msg)
                self.errors.append(error_msg)
    
    def test_no_duplicates(self):
        """Test that old duplicate files are gone"""
        logger.info("Testing for duplicate files...")
        
        # Files that should NOT exist after reorganization
        unwanted_files = [
            'ui/analytics_runner/analytics_runner_stylesheet.py',
            'ui/analytics_runner/session_manager.py',
            'data/sessions/session.json',  # Should be in data/sessions/
            'data/sessions/data_sources.json',  # Should be in data/sessions/
        ]
        
        for file_path in unwanted_files:
            self.total_tests += 1
            full_path = self.project_root / file_path
            if not full_path.exists():
                logger.info(f"✓ Duplicate removed: {file_path}")
                self.success_count += 1
            else:
                warning_msg = f"⚠ Duplicate still exists: {file_path}"
                logger.warning(warning_msg)
                self.warnings.append(warning_msg)
    
    def run_verification(self):
        """Run all verification tests"""
        logger.info("=" * 60)
        logger.info("REORGANIZATION VERIFICATION")
        logger.info("=" * 60)
        
        # Run all tests
        self.test_directory_structure()
        self.test_file_locations()
        self.test_data_directories()
        self.test_no_duplicates()
        self.test_imports()
        self.test_ui_imports()
        
        # Print summary
        self.print_summary()
        
        # Return success status
        return len(self.errors) == 0
    
    def print_summary(self):
        """Print verification summary"""
        logger.info("=" * 60)
        logger.info("VERIFICATION SUMMARY")
        logger.info("=" * 60)
        
        logger.info(f"Tests passed: {self.success_count}/{self.total_tests}")
        
        if self.warnings:
            logger.info(f"Warnings: {len(self.warnings)}")
            for warning in self.warnings:
                logger.warning(f"  {warning}")
        
        if self.errors:
            logger.info(f"Errors: {len(self.errors)}")
            for error in self.errors:
                logger.error(f"  {error}")
        else:
            logger.info("🎉 All critical tests passed!")
        
        if self.warnings and not self.errors:
            logger.info("✅ Reorganization appears successful with minor warnings")
        elif not self.errors:
            logger.info("✅ Reorganization completed successfully!")
        else:
            logger.info("❌ Reorganization has issues that need attention")
        
        logger.info("\nNext steps:")
        if self.errors:
            logger.info("1. Fix the errors listed above")
            logger.info("2. Re-run this verification script")
        else:
            logger.info("1. Test the applications manually:")
            logger.info("   - python ui/analytics_runner/main_application.py")
            logger.info("   - python ui/rule_builder/main.py")
            logger.info("2. Run your test suite")
            logger.info("3. Commit the reorganized structure")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Verify project reorganization')
    parser.add_argument('--project-root', '-p', default='.', help='Project root directory')
    
    args = parser.parse_args()
    
    try:
        verifier = ReorganizationVerifier(Path(args.project_root).resolve())
        success = verifier.run_verification()
        return 0 if success else 1
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        return 1


if __name__ == "__main__":
    exit(main())

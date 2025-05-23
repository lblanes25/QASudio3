"""
Test suite for DataSourceRegistry
Verifies core functionality including save, load, search, and validation operations.
"""

import os
import tempfile
import json
import unittest
from pathlib import Path
from unittest.mock import Mock

from data_source_registry import (
    DataSourceRegistry, DataSourceMetadata, DataSourceType,
    create_registry, register_current_data_source
)


class TestDataSourceRegistry(unittest.TestCase):
    """Test cases for DataSourceRegistry functionality."""
    
    def setUp(self):
        """Set up test environment."""
        # Create temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        self.registry_file = os.path.join(self.test_dir, "test_registry.json")
        
        # Create test data files
        self.csv_file = os.path.join(self.test_dir, "test_data.csv")
        self.excel_file = os.path.join(self.test_dir, "test_data.xlsx")
        
        # Create sample CSV file
        with open(self.csv_file, 'w') as f:
            f.write("Name,Age,City\nJohn,30,New York\nJane,25,Boston\n")
        
        # Create sample Excel file (minimal)
        with open(self.excel_file, 'wb') as f:
            f.write(b"PK\x03\x04")  # Minimal ZIP header for .xlsx
        
        # Create registry
        self.registry = DataSourceRegistry(self.registry_file)
    
    def tearDown(self):
        """Clean up test environment."""
        import shutil
        shutil.rmtree(self.test_dir)
    
    def test_registry_initialization(self):
        """Test registry initialization."""
        self.assertIsInstance(self.registry, DataSourceRegistry)
        self.assertEqual(len(self.registry._sources), 0)
        self.assertTrue(self.registry.registry_file.exists())
    
    def test_register_csv_data_source(self):
        """Test registering a CSV data source."""
        source_id = self.registry.register_data_source(
            name="Test CSV",
            file_path=self.csv_file,
            description="Test CSV file",
            tags=["test", "csv"],
            data_type_hint="employee"
        )
        
        self.assertIsNotNone(source_id)
        self.assertEqual(len(self.registry._sources), 1)
        
        # Verify metadata
        metadata = self.registry.get_data_source(source_id)
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.name, "Test CSV")
        self.assertEqual(metadata.source_type, DataSourceType.CSV)
        self.assertIn("test", metadata.tags)
        self.assertEqual(metadata.data_type_hint, "employee")
    
    def test_register_excel_data_source(self):
        """Test registering an Excel data source."""
        source_id = self.registry.register_data_source(
            name="Test Excel",
            file_path=self.excel_file,
            connection_params={"sheet_name": "Sheet1"},
            data_type_hint="financial"
        )
        
        metadata = self.registry.get_data_source(source_id)
        self.assertEqual(metadata.source_type, DataSourceType.EXCEL)
        self.assertEqual(metadata.connection_params["sheet_name"], "Sheet1")
    
    def test_duplicate_name_prevention(self):
        """Test prevention of duplicate names."""
        # Register first source
        self.registry.register_data_source("Test Source", self.csv_file)
        
        # Try to register with same name
        with self.assertRaises(ValueError):
            self.registry.register_data_source("Test Source", self.excel_file)
    
    def test_overwrite_existing(self):
        """Test overwriting existing data source."""
        # Register first source
        source_id1 = self.registry.register_data_source("Test Source", self.csv_file)
        
        # Overwrite with same name
        source_id2 = self.registry.register_data_source(
            "Test Source", 
            self.excel_file,
            overwrite_existing=True
        )
        
        # Should be same ID
        self.assertEqual(source_id1, source_id2)
        
        # Should be Excel type now
        metadata = self.registry.get_data_source(source_id1)
        self.assertEqual(metadata.source_type, DataSourceType.EXCEL)
    
    def test_nonexistent_file(self):
        """Test handling of non-existent files."""
        with self.assertRaises(FileNotFoundError):
            self.registry.register_data_source(
                "Missing File",
                "/path/to/nonexistent/file.csv"
            )
    
    def test_update_data_source(self):
        """Test updating data source metadata."""
        source_id = self.registry.register_data_source("Test Source", self.csv_file)
        
        # Update metadata
        success = self.registry.update_data_source(
            source_id,
            description="Updated description",
            tags=["updated", "test"],
            is_favorite=True
        )
        
        self.assertTrue(success)
        
        metadata = self.registry.get_data_source(source_id)
        self.assertEqual(metadata.description, "Updated description")
        self.assertIn("updated", metadata.tags)
        self.assertTrue(metadata.is_favorite)
    
    def test_list_data_sources(self):
        """Test listing data sources with filters."""
        # Register multiple sources
        csv_id = self.registry.register_data_source("CSV Source", self.csv_file, tags=["csv"])
        excel_id = self.registry.register_data_source("Excel Source", self.excel_file, tags=["excel"])
        self.registry.update_data_source(csv_id, is_favorite=True)
        
        # Test basic listing
        all_sources = self.registry.list_data_sources()
        self.assertEqual(len(all_sources), 2)
        
        # Test type filter
        csv_sources = self.registry.list_data_sources(source_type=DataSourceType.CSV)
        self.assertEqual(len(csv_sources), 1)
        self.assertEqual(csv_sources[0].name, "CSV Source")
        
        # Test favorites filter
        favorites = self.registry.list_data_sources(favorites_only=True)
        self.assertEqual(len(favorites), 1)
        self.assertEqual(favorites[0].name, "CSV Source")
        
        # Test tag filter
        csv_tagged = self.registry.list_data_sources(tags=["csv"])
        self.assertEqual(len(csv_tagged), 1)
    
    def test_search_sources(self):
        """Test searching data sources."""
        # Register test sources
        self.registry.register_data_source(
            "Employee Data", 
            self.csv_file,
            description="HR employee information",
            tags=["hr", "employee"]
        )
        self.registry.register_data_source(
            "Financial Report",
            self.excel_file,
            description="Q1 financial data",
            tags=["finance", "quarterly"]
        )
        
        # Test name search
        results = self.registry.search_sources("Employee")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Employee Data")
        
        # Test description search
        results = self.registry.search_sources("financial")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].name, "Financial Report")
        
        # Test tag search
        results = self.registry.search_sources("hr")
        self.assertEqual(len(results), 1)
        
        # Test case insensitive
        results = self.registry.search_sources("EMPLOYEE")
        self.assertEqual(len(results), 1)
    
    def test_mark_source_used(self):
        """Test usage tracking."""
        source_id = self.registry.register_data_source("Test Source", self.csv_file)
        
        # Initially no usage
        metadata = self.registry.get_data_source(source_id)
        self.assertEqual(metadata.use_count, 0)
        self.assertIsNone(metadata.last_used)
        
        # Mark as used
        success = self.registry.mark_source_used(source_id)
        self.assertTrue(success)
        
        # Check usage updated
        metadata = self.registry.get_data_source(source_id)
        self.assertEqual(metadata.use_count, 1)
        self.assertIsNotNone(metadata.last_used)
    
    def test_delete_data_source(self):
        """Test deleting data sources."""
        source_id = self.registry.register_data_source("Test Source", self.csv_file)
        self.assertEqual(len(self.registry._sources), 1)
        
        # Delete source
        success = self.registry.delete_data_source(source_id)
        self.assertTrue(success)
        self.assertEqual(len(self.registry._sources), 0)
        
        # Try to delete non-existent source (should return False without error)
        fake_id = "non-existent-id"
        success = self.registry.delete_data_source(fake_id)
        self.assertFalse(success)

    def test_validate_sources(self):
        """Test source validation."""
        # Register source
        source_id = self.registry.register_data_source("Test Source", self.csv_file)

        # Should be valid initially
        validation_result = self.registry.validate_sources()
        self.assertIn(source_id, validation_result['valid'])
        self.assertEqual(len(validation_result['missing']), 0)

        # Remove file
        os.remove(self.csv_file)

        # Should be missing now
        validation_result = self.registry.validate_sources()
        self.assertIn(source_id, validation_result['missing'])

        # Source should be inactive
        metadata = self.registry.get_data_source(source_id)
        self.assertFalse(metadata.is_active)

    def test_cleanup_invalid_sources(self):
        """Test cleanup of invalid sources."""
        # Register source
        source_id = self.registry.register_data_source("Test Source", self.csv_file)
        self.assertEqual(len(self.registry._sources), 1)

        # Remove file
        os.remove(self.csv_file)

        # Cleanup invalid sources
        removed_count = self.registry.cleanup_invalid_sources()
        self.assertEqual(removed_count, 1)
        self.assertEqual(len(self.registry._sources), 0)

    def test_persistence(self):
        """Test registry persistence across instances."""
        # Register source in first instance
        source_id = self.registry.register_data_source("Test Source", self.csv_file)

        # Create new registry instance
        new_registry = DataSourceRegistry(self.registry_file)

        # Should load existing data
        self.assertEqual(len(new_registry._sources), 1)
        metadata = new_registry.get_data_source(source_id)
        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.name, "Test Source")

    def test_export_import_registry(self):
        """Test export and import functionality."""
        # Register sources
        self.registry.register_data_source("Source 1", self.csv_file)
        self.registry.register_data_source("Source 2", self.excel_file)

        # Export registry
        export_file = os.path.join(self.test_dir, "export.json")
        success = self.registry.export_registry(export_file)
        self.assertTrue(success)
        self.assertTrue(os.path.exists(export_file))

        # Create new registry and import
        new_registry_file = os.path.join(self.test_dir, "new_registry.json")
        new_registry = DataSourceRegistry(new_registry_file)

        imported, skipped = new_registry.import_registry(export_file)
        self.assertEqual(imported, 2)
        self.assertEqual(skipped, 0)
        self.assertEqual(len(new_registry._sources), 2)

    def test_get_registry_stats(self):
        """Test registry statistics."""
        # Register sources
        csv_id = self.registry.register_data_source("CSV Source", self.csv_file)
        excel_id = self.registry.register_data_source("Excel Source", self.excel_file)
        self.registry.update_data_source(csv_id, is_favorite=True)
        self.registry.mark_source_used(csv_id)
        self.registry.mark_source_used(csv_id)  # Use twice

        stats = self.registry.get_registry_stats()

        self.assertEqual(stats['total_sources'], 2)
        self.assertEqual(stats['active_sources'], 2)
        self.assertEqual(stats['favorite_sources'], 1)
        self.assertEqual(stats['type_counts']['csv'], 1)
        self.assertEqual(stats['type_counts']['excel'], 1)
        self.assertEqual(len(stats['most_used']), 2)

    def test_convenience_functions(self):
        """Test convenience functions."""
        # Test create_registry
        registry = create_registry(self.registry_file)
        self.assertIsInstance(registry, DataSourceRegistry)

        # Test register_current_data_source
        source_id = register_current_data_source(
            registry,
            "Test Source",
            self.csv_file,
            connection_params={"delimiter": ","}
        )

        self.assertIsNotNone(source_id)
        metadata = registry.get_data_source(source_id)
        self.assertEqual(metadata.connection_params["delimiter"], ",")


def run_tests():
    """Run all tests."""
    unittest.main()


if __name__ == "__main__":
    run_tests()
"""
Data Source Registry for Analytics Runner
Manages saved data source configurations with metadata and connection parameters.
"""

import json
import os
import logging
import datetime
import uuid
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum

logger = logging.getLogger(__name__)


class DataSourceType(Enum):
    """Supported data source types."""
    CSV = "csv"
    EXCEL = "excel"
    DATABASE = "database"  # Future implementation
    API = "api"  # Future implementation


@dataclass
class DataSourceMetadata:
    """Metadata for a registered data source."""
    
    # Required fields
    source_id: str
    name: str
    source_type: DataSourceType
    file_path: str
    
    # Optional metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)
    
    # File information
    file_size: int = 0
    last_modified: Optional[str] = None
    checksum: Optional[str] = None
    
    # Connection parameters
    connection_params: Dict[str, Any] = field(default_factory=dict)
    
    # Validation settings
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    pre_validation_enabled: bool = True
    data_type_hint: str = "generic"
    
    # Usage tracking
    created_date: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    last_used: Optional[str] = None
    use_count: int = 0
    
    # Status
    is_favorite: bool = False
    is_active: bool = True
    
    def __post_init__(self):
        """Post-initialization processing."""
        # Ensure source_id is set
        if not self.source_id:
            self.source_id = str(uuid.uuid4())
        
        # Convert string enum to DataSourceType if needed
        if isinstance(self.source_type, str):
            self.source_type = DataSourceType(self.source_type)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        data['source_type'] = self.source_type.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DataSourceMetadata':
        """Create instance from dictionary."""
        # Handle enum conversion
        if 'source_type' in data:
            data['source_type'] = DataSourceType(data['source_type'])
        
        return cls(**data)
    
    def update_file_info(self):
        """Update file information from current file state."""
        try:
            if os.path.exists(self.file_path):
                stat = os.stat(self.file_path)
                self.file_size = stat.st_size
                self.last_modified = datetime.datetime.fromtimestamp(stat.st_mtime).isoformat()
                
                # Calculate checksum for change detection
                import hashlib
                with open(self.file_path, 'rb') as f:
                    # Read in chunks for large files
                    hash_obj = hashlib.md5()
                    for chunk in iter(lambda: f.read(4096), b""):
                        hash_obj.update(chunk)
                    self.checksum = hash_obj.hexdigest()
            else:
                # File no longer exists
                self.is_active = False
                
        except Exception as e:
            logger.warning(f"Error updating file info for {self.name}: {e}")
    
    def is_file_changed(self) -> bool:
        """Check if the source file has changed since last registration."""
        if not os.path.exists(self.file_path):
            return True
        
        try:
            import hashlib
            with open(self.file_path, 'rb') as f:
                hash_obj = hashlib.md5()
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_obj.update(chunk)
                current_checksum = hash_obj.hexdigest()
            
            return current_checksum != self.checksum
        except Exception:
            return True
    
    def mark_used(self):
        """Mark the data source as used."""
        self.last_used = datetime.datetime.now().isoformat()
        self.use_count += 1


class DataSourceRegistry:
    """
    Registry for managing saved data source configurations.
    
    Features:
    - Save and load data source configurations
    - Metadata tracking and validation
    - File change detection
    - Search and filtering capabilities
    - Import/export of configurations
    - Automatic cleanup of invalid sources
    """
    
    def __init__(self, registry_file: str = "data_sources.json", session_manager=None):
        """
        Initialize the data source registry.
        
        Args:
            registry_file: Path to the registry storage file
            session_manager: Optional session manager for integration
        """
        self.registry_file = Path(registry_file)
        self.session_manager = session_manager
        self._sources: Dict[str, DataSourceMetadata] = {}
        
        # Ensure registry directory exists
        self.registry_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing registry
        self._load_registry()
        
        # Create empty registry file if it doesn't exist
        if not self.registry_file.exists():
            self._save_registry()

        logger.info(f"Data source registry initialized with {len(self._sources)} sources")

    def _load_registry(self):
        """Load the registry from file."""
        try:
            if self.registry_file.exists():
                with open(self.registry_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # Load each data source
                sources_data = data.get('sources', {})
                for source_id, source_data in sources_data.items():
                    try:
                        metadata = DataSourceMetadata.from_dict(source_data)
                        self._sources[source_id] = metadata
                    except Exception as e:
                        logger.warning(f"Error loading data source {source_id}: {e}")

                logger.info(f"Loaded {len(self._sources)} data sources from registry")
            else:
                logger.info("No existing registry found, starting with empty registry")

        except Exception as e:
            logger.error(f"Error loading registry: {e}")
            self._sources = {}

    def _save_registry(self):
        """Save the registry to file."""
        try:
            # Prepare data for serialization
            registry_data = {
                'version': '1.0',
                'created': datetime.datetime.now().isoformat(),
                'sources': {
                    source_id: metadata.to_dict()
                    for source_id, metadata in self._sources.items()
                }
            }

            # Create backup if file exists
            if self.registry_file.exists():
                backup_file = self.registry_file.with_suffix('.backup')
                if backup_file.exists():
                    backup_file.unlink()
                self.registry_file.rename(backup_file)

            # Save registry
            with open(self.registry_file, 'w', encoding='utf-8') as f:
                json.dump(registry_data, f, indent=2, ensure_ascii=False)

            logger.debug(f"Registry saved with {len(self._sources)} sources")

        except Exception as e:
            logger.error(f"Error saving registry: {e}")
            raise

    def register_data_source(self,
                           name: str,
                           file_path: str,
                           description: str = "",
                           tags: Optional[List[str]] = None,
                           connection_params: Optional[Dict[str, Any]] = None,
                           validation_rules: Optional[Dict[str, Any]] = None,
                           data_type_hint: str = "generic",
                           overwrite_existing: bool = False) -> str:
        """
        Register a new data source.

        Args:
            name: Display name for the data source
            file_path: Path to the data file
            description: Optional description
            tags: Optional list of tags
            connection_params: Connection parameters (sheet name, etc.)
            validation_rules: Custom validation rules
            data_type_hint: Hint for data type (generic, employee, financial, etc.)
            overwrite_existing: Whether to overwrite if name exists

        Returns:
            Source ID of the registered data source

        Raises:
            ValueError: If data source name already exists and overwrite_existing is False
            FileNotFoundError: If the specified file doesn't exist
        """
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Data source file not found: {file_path}")

        # Check for existing name
        existing_source = self.get_source_by_name(name)
        if existing_source and not overwrite_existing:
            raise ValueError(f"Data source with name '{name}' already exists")

        # Determine source type from file extension
        file_ext = Path(file_path).suffix.lower()
        if file_ext in ['.csv', '.txt']:
            source_type = DataSourceType.CSV
        elif file_ext in ['.xlsx', '.xls']:
            source_type = DataSourceType.EXCEL
        else:
            # Default to CSV for unknown types
            source_type = DataSourceType.CSV
            logger.warning(f"Unknown file type {file_ext}, defaulting to CSV")

        # Create metadata
        source_id = str(uuid.uuid4())
        if existing_source:
            source_id = existing_source.source_id  # Reuse ID if overwriting

        metadata = DataSourceMetadata(
            source_id=source_id,
            name=name,
            source_type=source_type,
            file_path=os.path.abspath(file_path),
            description=description,
            tags=tags or [],
            connection_params=connection_params or {},
            validation_rules=validation_rules or {},
            data_type_hint=data_type_hint
        )

        # Update file information
        metadata.update_file_info()

        # Store in registry
        self._sources[source_id] = metadata

        # Save registry
        self._save_registry()

        # Update session manager if available
        if self.session_manager:
            self.session_manager.add_recent_file(file_path)

        logger.info(f"Registered data source: {name} ({source_id})")
        return source_id

    def update_data_source(self,
                          source_id: str,
                          name: Optional[str] = None,
                          description: Optional[str] = None,
                          tags: Optional[List[str]] = None,
                          connection_params: Optional[Dict[str, Any]] = None,
                          validation_rules: Optional[Dict[str, Any]] = None,
                          data_type_hint: Optional[str] = None,
                          is_favorite: Optional[bool] = None) -> bool:
        """
        Update an existing data source.

        Args:
            source_id: ID of the data source to update
            name: New name (optional)
            description: New description (optional)
            tags: New tags (optional)
            connection_params: New connection parameters (optional)
            validation_rules: New validation rules (optional)
            data_type_hint: New data type hint (optional)
            is_favorite: New favorite status (optional)

        Returns:
            True if updated successfully, False if source not found
        """
        if source_id not in self._sources:
            logger.warning(f"Data source not found for update: {source_id}")
            return False

        metadata = self._sources[source_id]

        # Update fields if provided
        if name is not None:
            metadata.name = name
        if description is not None:
            metadata.description = description
        if tags is not None:
            metadata.tags = tags
        if connection_params is not None:
            metadata.connection_params.update(connection_params)
        if validation_rules is not None:
            metadata.validation_rules.update(validation_rules)
        if data_type_hint is not None:
            metadata.data_type_hint = data_type_hint
        if is_favorite is not None:
            metadata.is_favorite = is_favorite

        # Update file information
        metadata.update_file_info()

        # Save registry
        self._save_registry()

        logger.info(f"Updated data source: {metadata.name}")
        return True

    def get_data_source(self, source_id: str) -> Optional[DataSourceMetadata]:
        """
        Get a data source by ID.

        Args:
            source_id: ID of the data source

        Returns:
            DataSourceMetadata or None if not found
        """
        return self._sources.get(source_id)

    def get_source_by_name(self, name: str) -> Optional[DataSourceMetadata]:
        """
        Get a data source by name.

        Args:
            name: Name of the data source

        Returns:
            DataSourceMetadata or None if not found
        """
        for metadata in self._sources.values():
            if metadata.name == name:
                return metadata
        return None

    def list_data_sources(self,
                         source_type: Optional[DataSourceType] = None,
                         tags: Optional[List[str]] = None,
                         favorites_only: bool = False,
                         active_only: bool = True,
                         sort_by: str = "name") -> List[DataSourceMetadata]:
        """
        List data sources with optional filtering and sorting.

        Args:
            source_type: Filter by source type
            tags: Filter by tags (data source must have all specified tags)
            favorites_only: Only return favorite data sources
            active_only: Only return active data sources
            sort_by: Sort field ("name", "last_used", "use_count", "created_date")

        Returns:
            List of DataSourceMetadata objects
        """
        sources = list(self._sources.values())

        # Apply filters
        if source_type:
            sources = [s for s in sources if s.source_type == source_type]

        if tags:
            sources = [s for s in sources if all(tag in s.tags for tag in tags)]

        if favorites_only:
            sources = [s for s in sources if s.is_favorite]

        if active_only:
            sources = [s for s in sources if s.is_active]

        # Sort
        if sort_by == "name":
            sources.sort(key=lambda x: x.name.lower())
        elif sort_by == "last_used":
            sources.sort(key=lambda x: x.last_used or "", reverse=True)
        elif sort_by == "use_count":
            sources.sort(key=lambda x: x.use_count, reverse=True)
        elif sort_by == "created_date":
            sources.sort(key=lambda x: x.created_date, reverse=True)

        return sources

    def delete_data_source(self, source_id: str) -> bool:
        """
        Delete a data source from the registry.

        Args:
            source_id: ID of the data source to delete

        Returns:
            True if deleted successfully, False if not found
        """
        if source_id not in self._sources:
            logger.warning(f"Data source not found for deletion: {source_id}")
            return False

        metadata = self._sources[source_id]
        del self._sources[source_id]

        # Save registry
        self._save_registry()

        logger.info(f"Deleted data source: {metadata.name}")
        return True

    def mark_source_used(self, source_id: str) -> bool:
        """
        Mark a data source as used (updates usage tracking).

        Args:
            source_id: ID of the data source

        Returns:
            True if marked successfully, False if not found
        """
        if source_id not in self._sources:
            return False

        self._sources[source_id].mark_used()
        self._save_registry()

        return True

    def validate_sources(self) -> Dict[str, List[str]]:
        """
        Validate all registered data sources.

        Returns:
            Dictionary with 'valid', 'changed', and 'missing' source lists
        """
        valid_sources = []
        changed_sources = []
        missing_sources = []

        for source_id, metadata in self._sources.items():
            if not os.path.exists(metadata.file_path):
                missing_sources.append(source_id)
                metadata.is_active = False
            elif metadata.is_file_changed():
                changed_sources.append(source_id)
                # Update file info for changed files
                metadata.update_file_info()
            else:
                valid_sources.append(source_id)

        # Save if any changes were made
        if changed_sources or missing_sources:
            self._save_registry()

        return {
            'valid': valid_sources,
            'changed': changed_sources,
            'missing': missing_sources
        }

    def cleanup_invalid_sources(self) -> int:
        """
        Remove invalid (missing file) data sources from registry.

        Returns:
            Number of sources removed
        """
        invalid_sources = []

        for source_id, metadata in self._sources.items():
            if not os.path.exists(metadata.file_path):
                invalid_sources.append(source_id)

        # Remove invalid sources
        for source_id in invalid_sources:
            del self._sources[source_id]

        if invalid_sources:
            self._save_registry()
            logger.info(f"Cleaned up {len(invalid_sources)} invalid data sources")

        return len(invalid_sources)

    def export_registry(self, export_path: str, include_inactive: bool = False) -> bool:
        """
        Export the registry to a file.

        Args:
            export_path: Path to export file
            include_inactive: Whether to include inactive sources

        Returns:
            True if exported successfully, False otherwise
        """
        try:
            # Filter sources if needed
            if include_inactive:
                sources_to_export = self._sources
            else:
                sources_to_export = {
                    sid: metadata for sid, metadata in self._sources.items()
                    if metadata.is_active
                }

            export_data = {
                'version': '1.0',
                'exported': datetime.datetime.now().isoformat(),
                'source_count': len(sources_to_export),
                'sources': {
                    source_id: metadata.to_dict()
                    for source_id, metadata in sources_to_export.items()
                }
            }

            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            logger.info(f"Exported {len(sources_to_export)} data sources to {export_path}")
            return True

        except Exception as e:
            logger.error(f"Error exporting registry: {e}")
            return False

    def import_registry(self, import_path: str, merge: bool = True) -> Tuple[int, int]:
        """
        Import data sources from a file.

        Args:
            import_path: Path to import file
            merge: Whether to merge with existing sources (True) or replace (False)

        Returns:
            Tuple of (imported_count, skipped_count)
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            imported_sources = import_data.get('sources', {})
            imported_count = 0
            skipped_count = 0

            # Clear existing if not merging
            if not merge:
                self._sources.clear()

            # Import each source
            for source_id, source_data in imported_sources.items():
                try:
                    metadata = DataSourceMetadata.from_dict(source_data)

                    # Check for conflicts if merging
                    if merge and source_id in self._sources:
                        existing_name = self._sources[source_id].name
                        if existing_name != metadata.name:
                            # Create new ID for conflicting source
                            metadata.source_id = str(uuid.uuid4())
                            source_id = metadata.source_id

                    self._sources[source_id] = metadata
                    imported_count += 1

                except Exception as e:
                    logger.warning(f"Error importing source {source_id}: {e}")
                    skipped_count += 1

            # Save registry
            self._save_registry()

            logger.info(f"Imported {imported_count} data sources, skipped {skipped_count}")
            return imported_count, skipped_count

        except Exception as e:
            logger.error(f"Error importing registry: {e}")
            return 0, 0

    def search_sources(self,
                      query: str,
                      search_fields: Optional[List[str]] = None) -> List[DataSourceMetadata]:
        """
        Search data sources by text query.

        Args:
            query: Search query
            search_fields: Fields to search in (default: name, description, tags)

        Returns:
            List of matching DataSourceMetadata objects
        """
        if not query.strip():
            return []

        query_lower = query.lower()

        if search_fields is None:
            search_fields = ['name', 'description', 'tags']

        matching_sources = []

        for metadata in self._sources.values():
            match_found = False

            for field in search_fields:
                if field == 'name' and query_lower in metadata.name.lower():
                    match_found = True
                    break
                elif field == 'description' and query_lower in metadata.description.lower():
                    match_found = True
                    break
                elif field == 'tags':
                    for tag in metadata.tags:
                        if query_lower in tag.lower():
                            match_found = True
                            break
                elif field == 'file_path' and query_lower in metadata.file_path.lower():
                    match_found = True
                    break

            if match_found:
                matching_sources.append(metadata)

        # Sort by relevance (exact name matches first)
        matching_sources.sort(key=lambda x: (
            query_lower != x.name.lower(),  # Exact name matches first
            not x.name.lower().startswith(query_lower),  # Name starts with query
            x.name.lower()  # Alphabetical
        ))

        return matching_sources

    def get_registry_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the registry.

        Returns:
            Dictionary with registry statistics
        """
        total_sources = len(self._sources)
        active_sources = len([s for s in self._sources.values() if s.is_active])
        favorite_sources = len([s for s in self._sources.values() if s.is_favorite])

        # Count by type
        type_counts = {}
        for source_type in DataSourceType:
            type_counts[source_type.value] = len([
                s for s in self._sources.values()
                if s.source_type == source_type
            ])

        # Most used sources
        most_used = sorted(
            self._sources.values(),
            key=lambda x: x.use_count,
            reverse=True
        )[:5]

        return {
            'total_sources': total_sources,
            'active_sources': active_sources,
            'inactive_sources': total_sources - active_sources,
            'favorite_sources': favorite_sources,
            'type_counts': type_counts,
            'most_used': [{'name': s.name, 'use_count': s.use_count} for s in most_used],
            'registry_file': str(self.registry_file),
            'registry_size': self.registry_file.stat().st_size if self.registry_file.exists() else 0
        }


# Convenience functions for common operations
def create_registry(registry_file: str = "data_sources.json", session_manager=None) -> DataSourceRegistry:
    """Create a new data source registry instance."""
    return DataSourceRegistry(registry_file, session_manager)


def register_current_data_source(registry: DataSourceRegistry,
                                name: str,
                                file_path: str,
                                connection_params: Optional[Dict[str, Any]] = None,
                                **kwargs) -> str:
    """
    Convenience function to register the current data source.

    Args:
        registry: DataSourceRegistry instance
        name: Display name for the data source
        file_path: Path to the data file
        connection_params: Connection parameters (sheet name, etc.)
        **kwargs: Additional metadata

    Returns:
        Source ID of the registered data source
    """
    return registry.register_data_source(
        name=name,
        file_path=file_path,
        connection_params=connection_params,
        **kwargs
    )
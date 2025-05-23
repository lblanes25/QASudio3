"""
Session Manager for Analytics Runner
Handles application state persistence and user preferences.
"""

import json
import os
import logging
from pathlib import Path
from typing import Any, List, Dict, Optional

logger = logging.getLogger(__name__)


class SessionManager:
    """
    Manages session state, user preferences, and application configuration.

    Features:
    - Persistent storage of application state
    - Recent files tracking
    - User preferences management
    - Configuration validation
    - Automatic backup and recovery
    """

    def __init__(self, config_file: str = "session.json", backup_count: int = 3):
        """
        Initialize the session manager.

        Args:
            config_file: Name of the configuration file
            backup_count: Number of backup files to maintain
        """
        self.config_file = Path(config_file)
        self.backup_count = backup_count
        self.config = self._load_config()

        # Ensure required directories exist
        self._ensure_directories()

        logger.info(f"Session manager initialized with config: {self.config_file}")

    def _load_config(self) -> Dict[str, Any]:
        """
        Load configuration from file with fallback to defaults.

        Returns:
            Configuration dictionary
        """
        default_config = {
            # Application state
            'window_geometry': None,
            'splitter_state': None,
            'active_mode': 0,

            # File management
            'last_data_directory': str(Path.home()),
            'last_output_directory': './output',
            'recent_files': [],
            'recent_rule_sets': [],

            # User preferences
            'max_recent_files': 10,
            'auto_save_session': True,
            'confirm_exit': True,
            'log_level': 'INFO',

            # Validation settings
            'default_parallel_execution': False,
            'max_worker_threads': 4,
            'default_output_formats': ['excel', 'json'],

            # UI preferences
            'theme': 'default',
            'font_size': 9,
            'show_tooltips': True,
            'remember_window_state': True,

            # Performance settings
            'preview_row_limit': 100,
            'result_display_limit': 1000,
            'auto_refresh_logs': True,

            # Advanced settings
            'enable_debug_mode': False,
            'backup_results': True,
            'session_timeout_minutes': 120
        }

        try:
            if self.config_file.exists():
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)

                # Merge with defaults to ensure all keys exist
                merged_config = default_config.copy()
                merged_config.update(loaded_config)

                # Validate loaded configuration
                validated_config = self._validate_config(merged_config)

                logger.info(f"Configuration loaded successfully from {self.config_file}")
                return validated_config
            else:
                logger.info("No existing configuration found, using defaults")
                return default_config

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading configuration: {e}")
            logger.info("Attempting to restore from backup...")

            # Try to restore from backup
            restored_config = self._restore_from_backup()
            if restored_config:
                return restored_config

            logger.warning("Using default configuration")
            return default_config

    def _validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize configuration values.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Validated configuration dictionary
        """
        # Validate numeric values
        if config.get('max_recent_files', 0) < 1:
            config['max_recent_files'] = 10

        if config.get('max_worker_threads', 0) < 1:
            config['max_worker_threads'] = 4

        if config.get('preview_row_limit', 0) < 10:
            config['preview_row_limit'] = 100

        if config.get('result_display_limit', 0) < 100:
            config['result_display_limit'] = 1000

        # Validate paths
        last_data_dir = config.get('last_data_directory', '')
        if not os.path.exists(last_data_dir):
            config['last_data_directory'] = str(Path.home())

        # Validate recent files (remove non-existent files)
        recent_files = config.get('recent_files', [])
        valid_recent_files = [f for f in recent_files if os.path.exists(f)]
        config['recent_files'] = valid_recent_files[:config['max_recent_files']]

        # Validate output formats
        valid_formats = ['excel', 'html', 'json', 'csv']
        output_formats = config.get('default_output_formats', [])
        config['default_output_formats'] = [f for f in output_formats if f in valid_formats]
        if not config['default_output_formats']:
            config['default_output_formats'] = ['excel', 'json']

        return config

    def _restore_from_backup(self) -> Optional[Dict[str, Any]]:
        """
        Attempt to restore configuration from backup files.

        Returns:
            Restored configuration dictionary or None if failed
        """
        for i in range(1, self.backup_count + 1):
            backup_file = self.config_file.with_suffix(f'.backup{i}')
            if backup_file.exists():
                try:
                    with open(backup_file, 'r', encoding='utf-8') as f:
                        config = json.load(f)

                    logger.info(f"Configuration restored from backup: {backup_file}")
                    return self._validate_config(config)

                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Backup file {backup_file} is corrupted: {e}")
                    continue

        return None

    def _ensure_directories(self):
        """Ensure required directories exist."""
        directories = [
            self.config.get('last_output_directory', './output'),
        ]

        for directory in directories:
            try:
                Path(directory).mkdir(parents=True, exist_ok=True)
            except OSError as e:
                logger.warning(f"Could not create directory {directory}: {e}")

    def save_config(self):
        """Save current configuration to file with backup."""
        try:
            # Create backup of existing config
            if self.config_file.exists():
                self._create_backup()

            # Save current configuration
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)

            logger.debug(f"Configuration saved to {self.config_file}")

        except IOError as e:
            logger.error(f"Error saving configuration: {e}")

    def _create_backup(self):
        """Create a backup of the current configuration file."""
        try:
            # Shift existing backups
            for i in range(self.backup_count, 1, -1):
                old_backup = self.config_file.with_suffix(f'.backup{i-1}')
                new_backup = self.config_file.with_suffix(f'.backup{i}')

                if old_backup.exists():
                    if new_backup.exists():
                        new_backup.unlink()
                    old_backup.rename(new_backup)

            # Create new backup
            backup_file = self.config_file.with_suffix('.backup1')
            if backup_file.exists():
                backup_file.unlink()

            self.config_file.rename(backup_file)

        except OSError as e:
            logger.warning(f"Error creating configuration backup: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value
        """
        return self.config.get(key, default)

    def set(self, key: str, value: Any, auto_save: bool = True):
        """
        Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set
            auto_save: Whether to automatically save to disk
        """
        self.config[key] = value

        if auto_save and self.config.get('auto_save_session', True):
            self.save_config()

    def update(self, updates: Dict[str, Any], auto_save: bool = True):
        """
        Update multiple configuration values.

        Args:
            updates: Dictionary of key-value pairs to update
            auto_save: Whether to automatically save to disk
        """
        self.config.update(updates)

        if auto_save and self.config.get('auto_save_session', True):
            self.save_config()

    def add_recent_file(self, file_path: str):
        """
        Add a file to the recent files list.

        Args:
            file_path: Path to the file
        """
        file_path = os.path.abspath(file_path)

        # Remove if already exists
        recent_files = self.config.get('recent_files', [])
        if file_path in recent_files:
            recent_files.remove(file_path)

        # Add to front of list
        recent_files.insert(0, file_path)

        # Keep only the maximum number of recent files
        max_recent = self.config.get('max_recent_files', 10)
        self.config['recent_files'] = recent_files[:max_recent]

        # Update last data directory
        self.config['last_data_directory'] = os.path.dirname(file_path)

        # Auto-save if enabled
        if self.config.get('auto_save_session', True):
            self.save_config()

        logger.debug(f"Added recent file: {os.path.basename(file_path)}")

    def add_recent_rule_set(self, rule_set_path: str):
        """
        Add a rule set to the recent rule sets list.

        Args:
            rule_set_path: Path to the rule set
        """
        rule_set_path = os.path.abspath(rule_set_path)

        # Remove if already exists
        recent_rule_sets = self.config.get('recent_rule_sets', [])
        if rule_set_path in recent_rule_sets:
            recent_rule_sets.remove(rule_set_path)

        # Add to front of list
        recent_rule_sets.insert(0, rule_set_path)

        # Keep only the maximum number of recent rule sets
        max_recent = self.config.get('max_recent_files', 10)
        self.config['recent_rule_sets'] = recent_rule_sets[:max_recent]

        # Auto-save if enabled
        if self.config.get('auto_save_session', True):
            self.save_config()

        logger.debug(f"Added recent rule set: {os.path.basename(rule_set_path)}")

    def clear_recent_files(self):
        """Clear the recent files list."""
        self.config['recent_files'] = []
        if self.config.get('auto_save_session', True):
            self.save_config()
        logger.info("Recent files list cleared")

    def clear_recent_rule_sets(self):
        """Clear the recent rule sets list."""
        self.config['recent_rule_sets'] = []
        if self.config.get('auto_save_session', True):
            self.save_config()
        logger.info("Recent rule sets list cleared")

    def export_config(self, export_path: str) -> bool:
        """
        Export configuration to a file.

        Args:
            export_path: Path to export the configuration

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)

            logger.info(f"Configuration exported to {export_path}")
            return True

        except IOError as e:
            logger.error(f"Error exporting configuration: {e}")
            return False

    def import_config(self, import_path: str) -> bool:
        """
        Import configuration from a file.

        Args:
            import_path: Path to import the configuration from

        Returns:
            True if successful, False otherwise
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)

            # Validate imported configuration
            validated_config = self._validate_config(imported_config)

            # Update current configuration
            self.config.update(validated_config)

            # Save the updated configuration
            self.save_config()

            logger.info(f"Configuration imported from {import_path}")
            return True

        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error importing configuration: {e}")
            return False

    def reset_to_defaults(self):
        """Reset configuration to default values."""
        logger.info("Resetting configuration to defaults")

        # Create backup before reset
        if self.config_file.exists():
            backup_path = self.config_file.with_suffix('.reset_backup')
            try:
                self.config_file.rename(backup_path)
                logger.info(f"Current configuration backed up to {backup_path}")
            except OSError as e:
                logger.warning(f"Could not create reset backup: {e}")

        # Reload with defaults
        self.config = self._load_config()
        self.save_config()

    def get_session_info(self) -> Dict[str, Any]:
        """
        Get information about the current session.

        Returns:
            Dictionary with session information
        """
        return {
            'config_file': str(self.config_file),
            'config_exists': self.config_file.exists(),
            'recent_files_count': len(self.config.get('recent_files', [])),
            'recent_rule_sets_count': len(self.config.get('recent_rule_sets', [])),
            'auto_save_enabled': self.config.get('auto_save_session', True),
            'backup_count': self.backup_count,
            'last_data_directory': self.config.get('last_data_directory', ''),
            'last_output_directory': self.config.get('last_output_directory', ''),
        }

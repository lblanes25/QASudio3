# services/rule_loader.py

"""Rule configuration loading functionality."""

import logging
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import jsonschema

from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
from services.validation_constants import (
    DEFAULT_RULES_DIR, YAML_VALIDATION_COMMENT,
    SEVERITY_LEVELS, VALIDATION_MESSAGES
)

logger = logging.getLogger(__name__)


class RuleConfigurationLoader:
    """Handles loading and validation of rule configurations."""
    
    # YAML schema for rule validation
    RULE_SCHEMA = {
        "type": "object",
        "required": ["version", "rule"],
        "properties": {
            "version": {"type": "string"},
            "rule": {
                "type": "object",
                "required": ["id", "name", "description", "risk_level"],
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "risk_level": {"type": "integer", "minimum": 1, "maximum": 5},
                    "category": {"type": "string"},
                    "analytic_id": {"type": "string"},
                    "entity_id_column": {"type": "string"},
                    "responsible_party_column": {"type": "string"},
                    "formula": {
                        "type": "object",
                        "required": ["type", "excel_formula"],
                        "properties": {
                            "type": {"type": "string", "enum": ["excel"]},
                            "excel_formula": {"type": "string"},
                            "inputs": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        }
                    },
                    "compliance_determination": {
                        "type": "object",
                        "properties": {
                            "compliant_values": {"type": "array"},
                            "partially_compliant_values": {"type": "array"},
                            "non_compliant_values": {"type": "array"}
                        }
                    },
                    "output_columns": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "metadata": {"type": "object"}
                }
            }
        }
    }
    
    def __init__(self, rule_manager: Optional[ValidationRuleManager] = None):
        """
        Initialize the rule configuration loader.
        
        Args:
            rule_manager: Rule manager to add loaded rules to
        """
        self.rule_manager = rule_manager or ValidationRuleManager()
        self._loaded_configs = {}
        
    def load_from_directory(self, directory: str = DEFAULT_RULES_DIR) -> Dict[str, Any]:
        """
        Load rule configurations from a directory.
        
        Args:
            directory: Directory containing YAML rule files
            
        Returns:
            Summary of loaded rules
        """
        rules_dir = Path(directory)
        
        if not rules_dir.exists():
            logger.warning(f"Rules directory does not exist: {directory}")
            return {
                'status': 'error',
                'message': f'Rules directory not found: {directory}',
                'rules_loaded': 0
            }
        
        loaded_rules = []
        failed_files = []
        
        # Load YAML files
        yaml_files = list(rules_dir.glob("*.yaml")) + list(rules_dir.glob("*.yml"))
        
        for config_file in yaml_files:
            try:
                rule = self._load_single_configuration(config_file)
                if rule:
                    loaded_rules.append({
                        'file': str(config_file.name),
                        'rule_id': rule.id,
                        'rule_name': rule.name
                    })
            except Exception as e:
                logger.error(f"Failed to load rule from {config_file}: {str(e)}")
                failed_files.append({
                    'file': str(config_file.name),
                    'error': str(e)
                })
        
        return {
            'status': 'success' if not failed_files else 'partial',
            'rules_loaded': len(loaded_rules),
            'loaded_rules': loaded_rules,
            'failed_files': failed_files
        }
    
    def validate_configuration(self, config_path: str) -> Tuple[bool, List[str]]:
        """
        Validate a rule configuration file.
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        try:
            # Read the file
            with open(config_path, 'r') as f:
                if config_path.endswith('.json'):
                    config = json.load(f)
                else:
                    config = yaml.safe_load(f)
            
            # Validate against schema
            # YAML schema validation ensures rules have required fields
            try:
                jsonschema.validate(config, self.RULE_SCHEMA)
            except jsonschema.ValidationError as e:
                errors.append(f"Schema validation failed: {e.message}")
                return False, errors
            
            # Additional validation
            rule_config = config.get('rule', {})
            
            # Check risk level
            risk_level = rule_config.get('risk_level')
            if risk_level and not (1 <= risk_level <= 5):
                errors.append(f"Invalid risk level: {risk_level}. Must be between 1 and 5.")
            
            # Validate formula if present
            if 'formula' in rule_config:
                formula_errors = self._validate_formula(rule_config['formula'])
                errors.extend(formula_errors)
            
            # Validate compliance determination
            if 'compliance_determination' in rule_config:
                cd_errors = self._validate_compliance_determination(
                    rule_config['compliance_determination']
                )
                errors.extend(cd_errors)
            
        except Exception as e:
            errors.append(f"Failed to load configuration: {str(e)}")
        
        return len(errors) == 0, errors
    
    def reload_configurations(self) -> Dict[str, Any]:
        """
        Reload all previously loaded configurations.
        
        Returns:
            Summary of reload operation
        """
        # Clear existing rules
        self.rule_manager.clear_rules()
        
        reloaded = []
        failed = []
        
        # Reload each configuration
        for config_path, config_data in self._loaded_configs.items():
            try:
                rule = self._create_rule_from_config(config_data, Path(config_path))
                self.rule_manager.add_rule(rule)
                reloaded.append(config_path)
            except Exception as e:
                logger.error(f"Failed to reload {config_path}: {str(e)}")
                failed.append({
                    'path': config_path,
                    'error': str(e)
                })
        
        return {
            'status': 'success' if not failed else 'partial',
            'reloaded_count': len(reloaded),
            'failed_count': len(failed),
            'failed_configs': failed
        }
    
    def get_configuration_summary(self) -> Dict[str, Any]:
        """
        Get summary of loaded rule configurations.
        
        Returns:
            Configuration summary
        """
        rules = self.rule_manager.list_rules()
        
        # Group by various attributes
        by_category = {}
        by_risk_level = {}
        by_analytic = {}
        
        for rule in rules:
            # By category
            category = rule.metadata.get('category', 'Uncategorized')
            by_category[category] = by_category.get(category, 0) + 1
            
            # By risk level
            risk_level = rule.metadata.get('risk_level', 3)
            risk_key = f"Level {risk_level}"
            by_risk_level[risk_key] = by_risk_level.get(risk_key, 0) + 1
            
            # By analytic
            analytic_id = rule.metadata.get('analytic_id', 'General')
            by_analytic[analytic_id] = by_analytic.get(analytic_id, 0) + 1
        
        return {
            'total_rules': len(rules),
            'by_category': by_category,
            'by_risk_level': by_risk_level,
            'by_analytic': by_analytic,
            'configuration_paths': list(self._loaded_configs.keys())
        }
    
    # Private helper methods
    
    def _load_single_configuration(self, config_path: Path) -> Optional[ValidationRule]:
        """Load a single rule configuration file."""
        try:
            # Read the file
            with open(config_path, 'r') as f:
                if config_path.suffix == '.json':
                    config = json.load(f)
                else:
                    config = yaml.safe_load(f)
            
            # Validate configuration
            is_valid, errors = self.validate_configuration(str(config_path))
            if not is_valid:
                logger.error(f"Invalid configuration {config_path}: {errors}")
                return None
            
            # Create rule
            rule = self._create_rule_from_config(config, config_path)
            
            # Add to manager
            self.rule_manager.add_rule(rule)
            
            # Store configuration for reload
            self._loaded_configs[str(config_path)] = config
            
            logger.info(f"Loaded rule {rule.id} from {config_path}")
            return rule
            
        except Exception as e:
            logger.error(f"Error loading {config_path}: {str(e)}")
            raise
    
    def _create_rule_from_config(self, config: Dict[str, Any], 
                               config_path: Path) -> ValidationRule:
        """Create a ValidationRule from configuration."""
        rule_config = config['rule']
        
        # Create base rule with correct parameters
        rule = ValidationRule(
            rule_id=rule_config['id'],
            name=rule_config['name'],
            description=rule_config['description'],
            formula=rule_config.get('formula', {}).get('excel_formula', ''),
            analytic_id=rule_config.get('analytic_id'),
            category=rule_config.get('category', 'General'),
            responsible_party_column=rule_config.get('responsible_party_column')
        )
        
        # Set additional metadata
        rule.metadata.update({
            'config_path': str(config_path),
            'version': config.get('version', '1.0'),
            'risk_level': rule_config.get('risk_level', 3),
            'entity_id_column': rule_config.get('entity_id_column', DEFAULT_ENTITY_ID_COLUMN)
        })
        
        # Add any additional metadata
        if 'metadata' in rule_config:
            rule.metadata.update(rule_config['metadata'])
        
        # Store formula inputs in metadata if provided
        if 'formula' in rule_config and 'inputs' in rule_config['formula']:
            rule.metadata['formula_inputs'] = rule_config['formula']['inputs']
        
        # Set compliance determination in metadata
        if 'compliance_determination' in rule_config:
            cd = rule_config['compliance_determination']
            rule.metadata['compliance_determination'] = {
                'compliant_values': cd.get('compliant_values', []),
                'partially_compliant_values': cd.get('partially_compliant_values', []),
                'non_compliant_values': cd.get('non_compliant_values', [])
            }
        
        # Set output columns in metadata
        if 'output_columns' in rule_config:
            rule.metadata['output_columns'] = rule_config['output_columns']
        
        return rule
    
    def _validate_formula(self, formula_config: Dict[str, Any]) -> List[str]:
        """Validate formula configuration."""
        errors = []
        
        formula_type = formula_config.get('type')
        if formula_type != 'excel':
            errors.append(f"Unsupported formula type: {formula_type}")
        
        excel_formula = formula_config.get('excel_formula', '')
        if not excel_formula:
            errors.append("Excel formula is empty")
        else:
            # Basic validation - check for balanced parentheses
            if excel_formula.count('(') != excel_formula.count(')'):
                errors.append("Unbalanced parentheses in formula")
        
        return errors
    
    def _validate_compliance_determination(self, cd_config: Dict[str, Any]) -> List[str]:
        """Validate compliance determination configuration."""
        errors = []
        
        # Check for overlapping values
        compliant = set(cd_config.get('compliant_values', []))
        partial = set(cd_config.get('partially_compliant_values', []))
        non_compliant = set(cd_config.get('non_compliant_values', []))
        
        # Check compliant vs partial
        overlap = compliant & partial
        if overlap:
            errors.append(f"Values in both compliant and partial: {overlap}")
        
        # Check compliant vs non-compliant
        overlap = compliant & non_compliant
        if overlap:
            errors.append(f"Values in both compliant and non-compliant: {overlap}")
        
        # Check partial vs non-compliant
        overlap = partial & non_compliant
        if overlap:
            errors.append(f"Values in both partial and non-compliant: {overlap}")
        
        return errors
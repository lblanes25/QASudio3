from typing import Dict, List, Any, Optional, Tuple, Union, TypedDict
import pandas as pd
import uuid
import json
import datetime
import logging
from pathlib import Path

# Import our rule parser
from .rule_parser import ValidationRuleParser

logger = logging.getLogger(__name__)


class ValidationRuleMetadata(TypedDict, total=False):
    """TypedDict for validation rule metadata"""
    description: str
    owner: str
    category: str
    created_by: str
    created_at: str
    modified_by: str
    modified_at: str
    version: str
    tags: List[str]
    threshold: float  # Threshold for compliance determination


class ValidationRule:
    """
    Represents a validation rule using Excel formula syntax.
    Includes metadata, versioning, and validation capabilities.

    Used as the core model for analytics in the QA Analytics Framework.
    """

    # Define valid severity levels
    SEVERITY_LEVELS = ["critical", "high", "medium", "low", "info"]
    # Define common rule categories
    COMMON_CATEGORIES = ["data_quality", "compliance", "timing", "completeness",
                         "consistency", "fraud", "regulatory", "custom"]

    def __init__(
            self,
            rule_id: Optional[str] = None,
            analytic_id: Optional[str] = None,  # Added analytic_id
            name: str = "",
            title: str = "",  # Added title
            formula: str = "",
            description: str = "",
            threshold: float = 1.0,  # Default 100% compliance
            severity: str = "medium",
            category: str = "data_quality",
            tags: Optional[List[str]] = None,
            responsible_party_column: Optional[str] = None,
            relevant_report: Optional[str] = None,  # Added relevant report
            metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize a validation rule.

        Args:
            rule_id: Unique identifier for the rule, generated if not provided
            analytic_id: Identifier for the analytic (e.g., business ID like "QA-123")
            name: Technical name for the rule (code-friendly)
            title: Human-readable title for the rule (display-friendly)
            formula: Excel formula implementing the rule
            description: Detailed description of what the rule validates
            threshold: Compliance threshold (0-1) where 1 means 100% compliance required
            severity: Rule severity level (critical, high, medium, low, info)
            category: Rule category for classification
            tags: List of tags for filtering and organization
            responsible_party_column: Column identifying responsible parties
            relevant_report: Reference to the relevant report for this analytic
            metadata: Additional metadata about the rule
        """
        self.rule_id = rule_id or str(uuid.uuid4())
        self.name = name
        self.formula = formula
        self.description = description
        self.threshold = max(0.0, min(1.0, threshold))  # Ensure between 0 and 1

        # Initialize metadata
        self.metadata = metadata or {}

        # Add standardized fields to metadata
        if severity and severity.lower() in self.SEVERITY_LEVELS:
            self.metadata['severity'] = severity.lower()
        else:
            self.metadata['severity'] = "medium"

        if category:
            self.metadata['category'] = category

        if tags:
            self.metadata['tags'] = tags
        elif 'tags' not in self.metadata:
            self.metadata['tags'] = []

        if responsible_party_column:
            self.metadata['responsible_party_column'] = responsible_party_column

        # Add analytics-specific metadata
        if analytic_id:
            self.metadata['analytic_id'] = analytic_id

        if title:
            self.metadata['title'] = title
        else:
            # Default title to name if not provided
            self.metadata['title'] = name

        if relevant_report:
            self.metadata['relevant_report'] = relevant_report

        self.parser = ValidationRuleParser()

        # Add creation metadata if not present
        if 'created_at' not in self.metadata:
            self.metadata['created_at'] = datetime.datetime.now().isoformat()

    def validate(self) -> Tuple[bool, Optional[str]]:
        """
        Validate the rule's formula syntax.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.name:
            return False, "Rule must have a name"

        if not self.formula:
            return False, "Rule must have a formula"

        # Check formula syntax
        if not self.parser.is_valid_formula(self.formula):
            return False, "Invalid formula syntax"

        return True, None

    def validate_with_dataframe(self, df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
        """
        Validate the rule's formula with a specific DataFrame.

        Args:
            df: DataFrame to validate formula against

        Returns:
            Tuple of (is_valid, error_message)
        """
        return self.parser.validate_formula_with_dataframe(self.formula, df)

    def get_required_columns(self) -> List[str]:
        """
        Get list of column names referenced in the formula.

        Returns:
            List of column names
        """
        return self.parser.extract_column_references(self.formula)

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert rule to dictionary format for serialization.

        Returns:
            Dictionary representation of the rule
        """
        return {
            'rule_id': self.rule_id,
            'name': self.name,
            'formula': self.formula,
            'description': self.description,
            'threshold': self.threshold,
            'metadata': self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ValidationRule':
        """
        Create rule from dictionary representation.

        Args:
            data: Dictionary with rule data

        Returns:
            ValidationRule instance
        """
        # Extract metadata to use for initializing fields
        metadata = data.get('metadata', {})

        # Create the rule with base fields
        rule = cls(
            rule_id=data.get('rule_id'),
            name=data.get('name', ''),
            formula=data.get('formula', ''),
            description=data.get('description', ''),
            threshold=data.get('threshold', 1.0),
            # Extract standardized fields from metadata if present
            analytic_id=metadata.get('analytic_id'),
            title=metadata.get('title', ''),
            severity=metadata.get('severity', 'medium'),
            category=metadata.get('category', 'data_quality'),
            tags=metadata.get('tags', []),
            responsible_party_column=metadata.get('responsible_party_column'),
            relevant_report=metadata.get('relevant_report'),
            # Pass remaining metadata
            metadata=metadata
        )

        return rule

    # Helper properties for all metadata fields
    @property
    def analytic_id(self) -> Optional[str]:
        """Get analytic ID"""
        return self.metadata.get('analytic_id')

    @analytic_id.setter
    def analytic_id(self, value: str) -> None:
        """Set analytic ID"""
        self.metadata['analytic_id'] = value

    @property
    def title(self) -> str:
        """Get rule title"""
        return self.metadata.get('title', self.name)

    @title.setter
    def title(self, value: str) -> None:
        """Set rule title"""
        self.metadata['title'] = value

    @property
    def relevant_report(self) -> Optional[str]:
        """Get relevant report reference"""
        return self.metadata.get('relevant_report')

    @relevant_report.setter
    def relevant_report(self, value: str) -> None:
        """Set relevant report reference"""
        self.metadata['relevant_report'] = value

    @property
    def severity(self) -> str:
        """Get rule severity level"""
        return self.metadata.get('severity', 'medium')

    @severity.setter
    def severity(self, value: str) -> None:
        """Set rule severity level"""
        if value.lower() in self.SEVERITY_LEVELS:
            self.metadata['severity'] = value.lower()
        else:
            raise ValueError(f"Invalid severity level. Must be one of: {', '.join(self.SEVERITY_LEVELS)}")

    @property
    def category(self) -> str:
        """Get rule category"""
        return self.metadata.get('category', 'data_quality')

    @category.setter
    def category(self, value: str) -> None:
        """Set rule category"""
        self.metadata['category'] = value

    @property
    def tags(self) -> List[str]:
        """Get rule tags"""
        return self.metadata.get('tags', [])

    @tags.setter
    def tags(self, value: List[str]) -> None:
        """Set rule tags"""
        self.metadata['tags'] = value

    @property
    def responsible_party_column(self) -> Optional[str]:
        """Get responsible party column name"""
        return self.metadata.get('responsible_party_column')

    @responsible_party_column.setter
    def responsible_party_column(self, value: str) -> None:
        """Set responsible party column name"""
        self.metadata['responsible_party_column'] = value

class ValidationRuleManager:
    """
    Manages validation rules including storage, retrieval, and versioning.
    """

    def __init__(self, rules_directory: Optional[str] = None):
        """
        Initialize the rule manager.

        Args:
            rules_directory: Directory to store rule files
        """
        self.rules_directory = Path(rules_directory) if rules_directory else Path("data/rules")
        self.rules: Dict[str, ValidationRule] = {}
        self.parser = ValidationRuleParser()

        # Create directory if it doesn't exist
        self.rules_directory.mkdir(parents=True, exist_ok=True)

    def add_rule(self, rule: ValidationRule) -> str:
        """
        Add a rule to the manager.

        Args:
            rule: ValidationRule to add

        Returns:
            Rule ID of the added rule
        """
        # Validate rule before adding
        is_valid, error = rule.validate()
        if not is_valid:
            raise ValueError(f"Invalid rule: {error}")

        # Store the rule
        self.rules[rule.rule_id] = rule

        # Save to file
        self._save_rule_to_file(rule)

        return rule.rule_id

    def get_rule(self, rule_id: str) -> Optional[ValidationRule]:
        """
        Get a rule by ID.

        Args:
            rule_id: ID of the rule to retrieve

        Returns:
            ValidationRule if found, None otherwise
        """
        # Check if rule is loaded in memory
        if rule_id in self.rules:
            return self.rules[rule_id]

        # Try to load from file
        rule_path = self.rules_directory / f"{rule_id}.json"
        if rule_path.exists():
            return self._load_rule_from_file(rule_path)

        return None

    def update_rule(self, rule: ValidationRule) -> None:
        """
        Update an existing rule.

        Args:
            rule: Updated ValidationRule
        """
        # Validate rule before updating
        is_valid, error = rule.validate()
        if not is_valid:
            raise ValueError(f"Invalid rule: {error}")

        # Update modification metadata
        rule.metadata['modified_at'] = datetime.datetime.now().isoformat()

        # Store the rule
        self.rules[rule.rule_id] = rule

        # Save to file
        self._save_rule_to_file(rule)

    def delete_rule(self, rule_id: str) -> bool:
        """
        Delete a rule.

        Args:
            rule_id: ID of the rule to delete

        Returns:
            True if rule was deleted, False if not found
        """
        # Remove from memory if present
        if rule_id in self.rules:
            del self.rules[rule_id]

        # Remove file if exists
        rule_path = self.rules_directory / f"{rule_id}.json"
        if rule_path.exists():
            rule_path.unlink()
            return True

        return False

    def list_rules(self) -> List[ValidationRule]:
        """
        List all available rules.

        Returns:
            List of ValidationRule objects
        """
        # Load any rules from disk that aren't in memory
        self._load_all_rules()

        return list(self.rules.values())

    def _save_rule_to_file(self, rule: ValidationRule) -> None:
        """
        Save a rule to a JSON file.

        Args:
            rule: Rule to save
        """
        rule_path = self.rules_directory / f"{rule.rule_id}.json"

        try:
            with open(rule_path, 'w') as f:
                json.dump(rule.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"Error saving rule {rule.rule_id} to file: {str(e)}")

    def _load_rule_from_file(self, file_path: Path) -> Optional[ValidationRule]:
        """
        Load a rule from a JSON file.

        Args:
            file_path: Path to rule JSON file

        Returns:
            ValidationRule if loaded successfully, None otherwise
        """
        try:
            with open(file_path, 'r') as f:
                rule_data = json.load(f)
                rule = ValidationRule.from_dict(rule_data)
                self.rules[rule.rule_id] = rule
                return rule
        except Exception as e:
            logger.error(f"Error loading rule from {file_path}: {str(e)}")
            return None

    def _load_all_rules(self) -> None:
        """Load all rule files from the rules directory"""
        for rule_file in self.rules_directory.glob("*.json"):
            rule_id = rule_file.stem
            if rule_id not in self.rules:
                self._load_rule_from_file(rule_file)
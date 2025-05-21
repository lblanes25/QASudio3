from PySide6.QtCore import Signal, QObject

import yaml
import json

# Import your existing QA Analytics Framework components
from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
from core.rule_engine.rule_parser import ValidationRuleParser


class RuleModel(QObject):
    """Data model that wraps the ValidationRule class."""

    # Signal emitted when rule data changes
    rule_changed = Signal()

    def __init__(self, rule_manager=None):
        super().__init__()

        # Initialize with a ValidationRuleManager instance
        self.rule_manager = rule_manager or ValidationRuleManager()

        # Initialize rule parser for validation
        self.rule_parser = ValidationRuleParser()

        # Initialize with a new rule
        self.reset_rule()

    def reset_rule(self):
        """Reset to a new empty rule."""
        # Create a new ValidationRule instance
        self.current_rule = ValidationRule(
            name="",
            formula="",
            description="",
            threshold=1.0,
            severity="medium",
            category="data_quality",
            tags=[]
        )

        # Emit signal to update UI
        self.rule_changed.emit()

    def set_rule(self, rule):
        """Set the current rule to an existing ValidationRule instance."""
        if isinstance(rule, ValidationRule):
            self.current_rule = rule
            # Emit signal to update UI
            self.rule_changed.emit()
        else:
            raise TypeError("Expected ValidationRule instance")

    def load_rule_by_id(self, rule_id):
        """Load a rule from the rule manager by ID."""
        rule = self.rule_manager.get_rule(rule_id)
        if rule:
            self.current_rule = rule
            # Emit signal to update UI
            self.rule_changed.emit()
            return True
        return False

    def save_rule(self):
        """Save the current rule to the rule manager."""
        # Validate rule before saving
        is_valid, error = self.validate()
        if not is_valid:
            return False, error

        try:
            # If rule_id is set, update existing rule
            if hasattr(self.current_rule, 'rule_id') and self.current_rule.rule_id:
                self.rule_manager.update_rule(self.current_rule)
            else:
                # Add as new rule
                rule_id = self.rule_manager.add_rule(self.current_rule)
                self.current_rule.rule_id = rule_id

            return True, None
        except Exception as e:
            return False, str(e)

    def validate(self):
        """Validate the current rule."""
        # Use ValidationRule's built-in validation
        return self.current_rule.validate()

    def validate_with_dataframe(self, df):
        """Validate the rule against a DataFrame."""
        return self.current_rule.validate_with_dataframe(df)

    def to_dict(self):
        """Convert rule to dictionary format."""
        return self.current_rule.to_dict()

    def to_yaml(self):
        """Convert rule to YAML string."""
        rule_dict = self.to_dict()
        return yaml.dump({'rules': [rule_dict]}, default_flow_style=False)

    def to_json(self):
        """Convert rule to JSON string."""
        rule_dict = self.to_dict()
        return json.dumps({'rules': [rule_dict]}, indent=2)

    def update_from_dict(self, rule_dict):
        """Update rule fields from a dictionary."""
        # Update current rule fields
        if 'name' in rule_dict:
            self.current_rule.name = rule_dict['name']

        if 'formula' in rule_dict:
            self.current_rule.formula = rule_dict['formula']

        if 'description' in rule_dict:
            self.current_rule.description = rule_dict['description']

        if 'threshold' in rule_dict:
            self.current_rule.threshold = rule_dict['threshold']

        if 'severity' in rule_dict:
            self.current_rule.severity = rule_dict['severity']

        if 'category' in rule_dict:
            self.current_rule.category = rule_dict['category']

        if 'tags' in rule_dict:
            self.current_rule.tags = rule_dict['tags']

        if 'metadata' in rule_dict:
            self.current_rule.metadata = rule_dict['metadata']

        # If rule_id is provided, update it
        if 'rule_id' in rule_dict:
            self.current_rule.rule_id = rule_dict['rule_id']

        # Emit signal to update UI
        self.rule_changed.emit()

    def extract_column_references(self, formula=None):
        """Extract column references from formula."""
        formula_to_check = formula if formula is not None else self.current_rule.formula
        # Use ValidationRuleParser to extract column references
        return self.rule_parser.extract_column_references(formula_to_check)

    def is_valid_formula(self, formula):
        """Check if a formula is syntactically valid."""
        # Use ValidationRuleParser to validate formula
        return self.rule_parser.is_valid_formula(formula)

    # Expose properties for easier access to ValidationRule fields
    @property
    def rule_id(self):
        return getattr(self.current_rule, 'rule_id', None)

    @property
    def name(self):
        return self.current_rule.name

    @name.setter
    def name(self, value):
        self.current_rule.name = value
        self.rule_changed.emit()

    @property
    def formula(self):
        return self.current_rule.formula

    @formula.setter
    def formula(self, value):
        self.current_rule.formula = value
        self.rule_changed.emit()

    @property
    def description(self):
        return self.current_rule.description

    @description.setter
    def description(self, value):
        self.current_rule.description = value
        self.rule_changed.emit()

    @property
    def threshold(self):
        return self.current_rule.threshold

    @threshold.setter
    def threshold(self, value):
        self.current_rule.threshold = value
        self.rule_changed.emit()

    @property
    def severity(self):
        return self.current_rule.severity

    @severity.setter
    def severity(self, value):
        self.current_rule.severity = value
        self.rule_changed.emit()

    @property
    def category(self):
        return self.current_rule.category

    @category.setter
    def category(self, value):
        self.current_rule.category = value
        self.rule_changed.emit()

    @property
    def tags(self):
        return self.current_rule.tags

    @tags.setter
    def tags(self, value):
        self.current_rule.tags = value
        self.rule_changed.emit()
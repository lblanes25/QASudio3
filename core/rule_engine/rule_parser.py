import re
from typing import Dict, List, Any, Optional, Tuple, Union
import pandas as pd
import logging

logger = logging.getLogger(__name__)


class ValidationRuleParser:
    """
    Parser for validation rules that use Excel formula syntax.
    Validates rule syntax and extracts metadata from rules.
    """

    def __init__(self):
        # Regular expressions for detecting common Excel formula patterns
        self.excel_pattern = re.compile(r'^\s*=', re.IGNORECASE)  # Starts with "="
        self.column_ref_pattern = re.compile(r'\[([^\]]+)\]')  # Matches [ColumnName]

    def is_valid_formula(self, formula: str) -> bool:
        """
        Check if a string appears to be a valid Excel formula.

        Args:
            formula: The formula string to validate

        Returns:
            True if the formula appears valid, False otherwise
        """
        if not isinstance(formula, str):
            return False

        # Basic check - should start with "="
        if not self.excel_pattern.match(formula):
            return False

        # Check for balanced parentheses
        if not self._has_balanced_parentheses(formula):
            return False

        # Check for balanced brackets
        if not self._has_balanced_brackets(formula):
            return False

        return True

    def extract_column_references(self, formula: str) -> List[str]:
        """
        Extract column references from an Excel formula.

        Args:
            formula: The formula containing column references like [ColumnName]

        Returns:
            List of column names referenced in the formula
        """
        if not isinstance(formula, str):
            return []

        # Find all [ColumnName] patterns
        return self.column_ref_pattern.findall(formula)

    def validate_formula_with_dataframe(self, formula: str, df: pd.DataFrame) -> Tuple[bool, Optional[str]]:
        """
        Validate that a formula's column references exist in the given DataFrame.

        Args:
            formula: The formula to validate
            df: DataFrame to check column existence

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not self.is_valid_formula(formula):
            return False, "Invalid formula syntax"

        column_refs = self.extract_column_references(formula)
        missing_columns = [col for col in column_refs if col not in df.columns]

        if missing_columns:
            return False, f"Formula references non-existent columns: {', '.join(missing_columns)}"

        return True, None

    def _has_balanced_parentheses(self, formula: str) -> bool:
        """Check if formula has balanced parentheses"""
        count = 0
        for char in formula:
            if char == '(':
                count += 1
            elif char == ')':
                count -= 1
                if count < 0:
                    return False
        return count == 0

    def _has_balanced_brackets(self, formula: str) -> bool:
        """Check if formula has balanced brackets"""
        count = 0
        for char in formula:
            if char == '[':
                count += 1
            elif char == ']':
                count -= 1
                if count < 0:
                    return False
        return count == 0
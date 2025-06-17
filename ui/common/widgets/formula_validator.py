"""
Formula Validator for real-time LOOKUP validation.
Part of Phase 2, Task 3 for Secondary Source File Integration.
"""

import re
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from difflib import get_close_matches

from PySide6.QtCore import QObject, Signal

from core.lookup.smart_lookup_manager import SmartLookupManager


class FormulaValidator(QObject):
    """Provides real-time validation feedback for LOOKUP formulas."""
    
    # Signal emitted when validation completes
    validationResult = Signal(dict)
    
    def __init__(self, session_manager=None, parent=None):
        """
        Initialize the formula validator.
        
        Args:
            session_manager: Optional session manager for accessing recent files
            parent: Parent QObject
        """
        super().__init__(parent)
        self.session_manager = session_manager
        # Regex pattern for LOOKUP function calls
        self.lookup_pattern = re.compile(
            r'LOOKUP\(([^,]+)(?:,\s*[\'"]([^"\']+)[\'"])?(?:,\s*[\'"]([^"\']+)[\'"])?\)'
        )
    
    def validate_lookup_formula(self, formula: str, lookup_manager: SmartLookupManager):
        """
        Validate LOOKUP formula and provide inline feedback.
        
        Args:
            formula: The formula text to validate
            lookup_manager: The SmartLookupManager instance to check against
        """
        if not formula or not lookup_manager:
            return
        
        feedback = []
        
        # Find all LOOKUP calls in the formula
        for match in self.lookup_pattern.finditer(formula):
            lookup_value_expr = match.group(1).strip()
            arg1 = match.group(2)  # Could be search_column or return_column
            arg2 = match.group(3)  # Could be return_column
            
            # Determine which columns to check
            search_col = arg1 if arg2 else None
            return_col = arg2 if arg2 else arg1
            
            if return_col:
                # Check if column exists
                files_with_col = lookup_manager.column_index.get(return_col, [])
                
                if files_with_col:
                    # Found the column
                    file_info = lookup_manager.file_metadata.get(files_with_col[0], {})
                    alias = lookup_manager.file_aliases.get(files_with_col[0], Path(files_with_col[0]).stem)
                    
                    feedback_item = {
                        'column': return_col,
                        'status': 'found',
                        'message': f"✓ '{return_col}' found in {alias} ({file_info.get('row_count', 0):,} rows)",
                        'file': files_with_col[0],
                        'match_start': match.start(),
                        'match_end': match.end()
                    }
                    
                    # If we have both columns, check if they're in the same file
                    if search_col:
                        search_files = lookup_manager.column_index.get(search_col, [])
                        common_files = set(files_with_col) & set(search_files)
                        if common_files:
                            common_file = list(common_files)[0]
                            common_alias = lookup_manager.file_aliases.get(common_file, Path(common_file).stem)
                            feedback_item['message'] = f"✓ Both '{search_col}' and '{return_col}' found in {common_alias}"
                        elif search_files:
                            # Columns exist but in different files
                            feedback_item['warning'] = f"'{search_col}' and '{return_col}' are in different files"
                    
                    feedback.append(feedback_item)
                else:
                    # Column not found
                    feedback.append({
                        'column': return_col,
                        'status': 'missing',
                        'message': f"✗ '{return_col}' not found in any loaded file",
                        'suggestion': self.get_missing_columns_message(return_col, lookup_manager),
                        'match_start': match.start(),
                        'match_end': match.end()
                    })
                    
                # Also check search column if specified
                if search_col and search_col != return_col:
                    search_files = lookup_manager.column_index.get(search_col, [])
                    if not search_files:
                        feedback.append({
                            'column': search_col,
                            'status': 'missing',
                            'message': f"✗ '{search_col}' not found in any loaded file",
                            'suggestion': self.get_missing_columns_message(search_col, lookup_manager),
                            'match_start': match.start(),
                            'match_end': match.end()
                        })
        
        # Emit the validation result
        self.validationResult.emit({
            'formula': formula,
            'feedback': feedback,
            'has_errors': any(f['status'] == 'missing' for f in feedback)
        })
    
    def get_missing_columns_message(self, column: str, manager: SmartLookupManager) -> str:
        """
        Generate specific message about what columns are needed.
        
        Args:
            column: The missing column name
            manager: The SmartLookupManager instance
            
        Returns:
            Actionable suggestion message
        """
        # Check similar columns
        all_columns = list(manager.column_index.keys())
        similar = get_close_matches(column, all_columns, n=3, cutoff=0.6)
        
        if similar:
            # We have similar columns loaded
            files_info = []
            for col in similar:
                files = manager.column_index[col]
                for f in files[:2]:  # Show max 2 files per column
                    alias = manager.file_aliases.get(f, Path(f).stem)
                    files_info.append(f"'{col}' in {alias}")
            return f"Did you mean: {', '.join(files_info)}?"
        else:
            # Need to load a file with this column
            # Check recent files that might have it
            suggestions = []
            
            if self.session_manager and hasattr(self.session_manager, 'get_recent_files'):
                recent_files = self.session_manager.get_recent_files()
            else:
                # Fallback to checking common file patterns
                recent_files = self._find_potential_files(column)
            
            for filepath in recent_files[:5]:  # Check last 5 recent files
                if os.path.exists(filepath):
                    # Quick check if we can peek at columns
                    try:
                        columns = manager._peek_columns(filepath)
                        if column in columns:
                            suggestions.append(f"Load {Path(filepath).name} (has '{column}')")
                        else:
                            # Check for partial matches
                            matches = get_close_matches(column, columns, n=1, cutoff=0.6)
                            if matches:
                                suggestions.append(f"Load {Path(filepath).name} (has '{matches[0]}')")
                    except:
                        pass
            
            if suggestions:
                return f"Suggestions: {'; '.join(suggestions[:2])}"
            else:
                return f"Load a file containing '{column}' column"
    
    def _find_potential_files(self, column: str) -> List[str]:
        """
        Find potential files based on column name patterns.
        
        Args:
            column: The column name to search for
            
        Returns:
            List of potential file paths
        """
        # Common patterns for file names based on column types
        patterns = []
        column_lower = column.lower()
        
        if any(term in column_lower for term in ['employee', 'manager', 'reviewer', 'level', 'department']):
            patterns.extend(['hr', 'employee', 'staff', 'personnel'])
        elif any(term in column_lower for term in ['vendor', 'supplier']):
            patterns.extend(['vendor', 'supplier', 'procurement'])
        elif any(term in column_lower for term in ['product', 'item', 'sku']):
            patterns.extend(['product', 'inventory', 'catalog'])
        
        # Look in common directories
        potential_files = []
        search_dirs = ['.', './data', './files', './lookup']
        
        for dir_path in search_dirs:
            if os.path.exists(dir_path):
                for pattern in patterns:
                    for ext in ['.xlsx', '.csv', '.xls']:
                        # Try different naming conventions
                        candidates = [
                            f"{pattern}_master{ext}",
                            f"{pattern}_data{ext}",
                            f"{pattern}s{ext}",
                            f"{pattern}{ext}"
                        ]
                        for candidate in candidates:
                            full_path = os.path.join(dir_path, candidate)
                            if os.path.exists(full_path):
                                potential_files.append(full_path)
        
        return potential_files
    
    def get_column_location_info(self, column: str, lookup_manager: SmartLookupManager) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about where a column can be found.
        
        Args:
            column: The column name to look for
            lookup_manager: The SmartLookupManager instance
            
        Returns:
            Dictionary with column location details or None
        """
        files = lookup_manager.column_index.get(column, [])
        if not files:
            return None
        
        # Get details about the first file containing this column
        filepath = files[0]
        metadata = lookup_manager.file_metadata.get(filepath, {})
        alias = lookup_manager.file_aliases.get(filepath, Path(filepath).stem)
        
        return {
            'column': column,
            'file': filepath,
            'alias': alias,
            'row_count': metadata.get('row_count', 0),
            'file_count': len(files),
            'all_files': [lookup_manager.file_aliases.get(f, Path(f).stem) for f in files]
        }
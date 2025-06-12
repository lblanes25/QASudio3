#!/usr/bin/env python3
"""
Enhanced fix for template duplication issue.
This version has better detection and clearing of template content.
"""

def get_enhanced_clear_template_methods():
    """Return enhanced template clearing methods."""
    return '''
    def _clear_template_placeholders(self, ws):
        """
        Clear template placeholder content before inserting dynamic data.
        This prevents duplication of template sections.
        """
        logger.info("Clearing template placeholder content")
        
        # Clear Section 3 template content more aggressively
        # Look for multiple indicators of template content
        template_rows_to_clear = set()
        
        # Search for various template indicators
        for row in range(20, 50):
            for col in range(1, 15):
                cell_value = self._safe_read_cell(ws, f'{get_column_letter(col)}{row}')
                if cell_value:
                    cell_str = str(cell_value)
                    # Check for template keywords
                    if any(keyword in cell_str for keyword in [
                        "Audit Leader Average Test Results",
                        "Area", 
                        "IAG-Wide Analytic",
                        "Analytic Error Threshold",
                        "Risk Level (Weight",
                        "Budget Per Sample",
                        "Total Budget",
                        "Analytic ID",
                        "Manual Samples Tested"
                    ]):
                        # Mark this row and several rows around it for clearing
                        for offset in range(-1, 10):  # Clear this row and next 9 rows
                            if 20 <= row + offset <= 50:
                                template_rows_to_clear.add(row + offset)
                        break
        
        # Clear all identified template rows
        if template_rows_to_clear:
            logger.info(f"Clearing {len(template_rows_to_clear)} template rows: {sorted(template_rows_to_clear)}")
            for row in sorted(template_rows_to_clear):
                for col in range(1, 20):
                    cell_ref = f'{get_column_letter(col)}{row}'
                    try:
                        cell = ws[cell_ref]
                        if not isinstance(cell, MergedCell):
                            # Clear the value but preserve formatting
                            cell.value = None
                    except:
                        pass
        
        # Also clear specific template patterns
        self._clear_specific_template_patterns(ws)
    
    def _clear_specific_template_patterns(self, ws):
        """Clear specific known template patterns."""
        # Clear the blue analytics section template if it exists
        for row in range(30, 40):
            for col in range(3, 15):
                cell_value = self._safe_read_cell(ws, f'{get_column_letter(col)}{row}')
                if cell_value == "Analytics" or cell_value == "Not Applicable":
                    # This is likely template content
                    for clear_col in range(3, 15):
                        try:
                            cell = ws[f'{get_column_letter(clear_col)}{row}']
                            if not isinstance(cell, MergedCell):
                                cell.value = None
                        except:
                            pass
'''

def apply_enhanced_fix():
    """Apply the enhanced fix to the existing file."""
    import shutil
    from pathlib import Path
    
    file_path = Path("reporting/generation/dynamic_summary_template_processor.py")
    
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        return False
    
    # Read the existing file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Find the existing _clear_template_placeholders method
    start_marker = "def _clear_template_placeholders(self, ws):"
    end_marker = "def _clear_other_template_sections(self, ws):"
    
    start_pos = content.find(start_marker)
    end_pos = content.find(end_marker)
    
    if start_pos == -1 or end_pos == -1:
        print("Error: Could not find the methods to replace")
        return False
    
    # Replace with enhanced version
    new_methods = get_enhanced_clear_template_methods()
    
    # Extract everything before and after the method
    before = content[:start_pos].rstrip() + "\n"
    after = "\n    " + content[end_pos:]
    
    # Combine with new methods
    new_content = before + new_methods + after
    
    # Backup and write
    backup_path = file_path.with_suffix('.py.backup2')
    shutil.copy2(file_path, backup_path)
    print(f"Created backup: {backup_path}")
    
    with open(file_path, 'w') as f:
        f.write(new_content)
    
    print(f"Applied enhanced fix to {file_path}")
    print("\nEnhancements:")
    print("1. More aggressive template detection")
    print("2. Clears rows around template keywords")
    print("3. Specifically targets blue analytics section")
    print("4. Better logging of what's being cleared")
    
    return True

if __name__ == "__main__":
    apply_enhanced_fix()
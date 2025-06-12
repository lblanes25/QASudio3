#!/usr/bin/env python3
"""
Fix for template duplication issue in dynamic_summary_template_processor.py

This script patches the existing processor to clear template placeholder content
before inserting dynamic data, preventing the duplication issue.
"""

import sys
from pathlib import Path

def create_template_clearing_methods():
    """Return the new methods to add for template clearing."""
    return '''
    # ==========================================
    # TEMPLATE CLEARING METHODS
    # ==========================================
    
    def _clear_template_placeholders(self, ws):
        """
        Clear template placeholder content before inserting dynamic data.
        This prevents duplication of template sections.
        """
        logger.info("Clearing template placeholder content")
        
        # Find and clear Section 3 template content
        # Look for "Audit Leader Average Test Results" in the template
        template_section3_row = None
        for row in range(20, 50):  # Search in reasonable range
            cell_value = self._safe_read_cell(ws, f'A{row}')
            if cell_value and "Audit Leader Average Test Results" in str(cell_value):
                template_section3_row = row
                logger.info(f"Found template Section 3 at row {row}")
                break
        
        if template_section3_row:
            # Clear the template content from this row onwards
            # We need to clear until we find the next major section or end of content
            rows_to_clear = []
            for row in range(template_section3_row, template_section3_row + 20):
                # Check if this row has template content (Area, Analytics, etc.)
                has_template_content = False
                for col in range(1, 15):  # Check first 14 columns
                    cell_value = self._safe_read_cell(ws, f'{get_column_letter(col)}{row}')
                    if cell_value and any(keyword in str(cell_value) for keyword in 
                                         ["Area", "IAG-Wide Analytic", "Analytic Error Threshold",
                                          "Risk Level", "Budget", "Analytic ID", "Manual Samples"]):
                        has_template_content = True
                        break
                
                if has_template_content:
                    rows_to_clear.append(row)
            
            # Clear the identified rows
            for row in rows_to_clear:
                logger.debug(f"Clearing template row {row}")
                for col in range(1, 20):  # Clear first 19 columns
                    cell_ref = f'{get_column_letter(col)}{row}'
                    try:
                        # Preserve formatting but clear content
                        cell = ws[cell_ref]
                        if not isinstance(cell, MergedCell):
                            cell.value = None
                    except:
                        pass
        
        # Also clear any other template placeholders that might cause issues
        self._clear_other_template_sections(ws)
    
    def _clear_other_template_sections(self, ws):
        """Clear other template sections that might interfere with dynamic content."""
        # Clear empty audit leader rows in Section 2
        for row in range(15, 20):
            cell_b = self._safe_read_cell(ws, f'B{row}')
            if cell_b is None or str(cell_b).strip() == "":
                # This is likely a template placeholder row for audit leaders
                cell_c = self._safe_read_cell(ws, f'C{row}')
                if cell_c and "Total Weighted Score" in str(cell_c):
                    logger.debug(f"Clearing template audit leader row {row}")
                    # Clear the row but preserve column C's label
                    for col in [1, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]:
                        cell_ref = f'{get_column_letter(col)}{row}'
                        try:
                            cell = ws[cell_ref]
                            if not isinstance(cell, MergedCell):
                                cell.value = None
                        except:
                            pass
'''

def get_modified_generate_method():
    """Return the modified generate_summary_report method."""
    return '''
        # IMPORTANT: Clear template placeholders BEFORE adding dynamic content
        self._clear_template_placeholders(ws)
'''

def apply_fix():
    """Apply the fix to the existing file."""
    file_path = Path("reporting/generation/dynamic_summary_template_processor.py")
    
    if not file_path.exists():
        print(f"Error: {file_path} not found")
        return False
    
    # Read the existing file
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Check if already patched
    if "_clear_template_placeholders" in content:
        print("File already appears to be patched")
        return True
    
    print("Applying template duplication fix...")
    
    # 1. Add the clearing methods after _cleanup_none_values method
    insertion_point = content.find("def _cleanup_none_values")
    if insertion_point == -1:
        print("Error: Could not find _cleanup_none_values method")
        return False
    
    # Find the end of the _cleanup_none_values method
    next_method = content.find("\n    def ", insertion_point + 1)
    if next_method == -1:
        next_method = len(content)
    
    # Insert the new methods
    new_methods = create_template_clearing_methods()
    content = content[:next_method] + "\n" + new_methods + "\n" + content[next_method:]
    
    # 2. Add the clearing call in generate_summary_report
    # Find where we load the worksheet
    ws_line = content.find("ws = wb.active")
    if ws_line == -1:
        print("Error: Could not find ws = wb.active")
        return False
    
    # Find the next line after ws = wb.active
    next_line = content.find("\n", ws_line) + 1
    
    # Insert the clearing call
    clearing_call = "\n        # IMPORTANT: Clear template placeholders BEFORE adding dynamic content\n        self._clear_template_placeholders(ws)\n"
    content = content[:next_line] + clearing_call + content[next_line:]
    
    # Write the modified content back
    backup_path = file_path.with_suffix('.py.backup')
    file_path.rename(backup_path)
    print(f"Created backup: {backup_path}")
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print(f"Successfully patched {file_path}")
    print("\nThe fix does the following:")
    print("1. Adds methods to clear template placeholder content")
    print("2. Calls the clearing method before inserting dynamic data")
    print("3. This prevents duplication of template sections in generated reports")
    
    return True

if __name__ == "__main__":
    success = apply_fix()
    sys.exit(0 if success else 1)
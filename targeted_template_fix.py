#!/usr/bin/env python3
"""
Targeted fix for the specific template duplication issue.
This directly addresses the rows 22-34 that contain template content.
"""

def create_targeted_fix():
    """Create a targeted fix for the template issue."""
    
    fix_code = '''
    def _clear_template_placeholders(self, ws):
        """
        Clear template placeholder content before inserting dynamic data.
        This prevents duplication of template sections.
        """
        logger.info("Clearing template placeholder content")
        
        # Specifically clear rows 21-34 which contain the template Section 3
        # This is based on the actual template structure observed
        logger.info("Clearing template rows 21-34")
        for row in range(21, 35):
            for col in range(1, 20):  # Clear columns A through S
                cell_ref = f'{get_column_letter(col)}{row}'
                try:
                    cell = ws[cell_ref]
                    if not isinstance(cell, MergedCell):
                        # Only clear if it contains template-like content
                        if cell.value:
                            value_str = str(cell.value)
                            # Check if this looks like template content
                            if any(keyword in value_str for keyword in [
                                "Audit Leader Average Test Results",
                                "Area",
                                "IAG-Wide Analytic", 
                                "Analytic Error Threshold",
                                "Risk Level",
                                "Budget",
                                "Analytic ID",
                                "Manual Samples",
                                "Rule 1 Title"
                            ]):
                                logger.debug(f"Clearing template content at {cell_ref}: {value_str[:30]}")
                                cell.value = None
                except Exception as e:
                    logger.debug(f"Could not clear {cell_ref}: {e}")
        
        # Also clear any "Analytics" placeholders in the 30s rows
        for row in range(30, 40):
            for col in range(3, 15):
                cell_ref = f'{get_column_letter(col)}{row}'
                try:
                    cell = ws[cell_ref]
                    if not isinstance(cell, MergedCell) and cell.value:
                        if str(cell.value) in ["Analytics", "Not Applicable", "2%", "3"]:
                            cell.value = None
                except:
                    pass
        
        # Clear empty audit leader placeholder rows
        self._clear_other_template_sections(ws)
'''
    
    return fix_code

def show_manual_fix_instructions():
    """Show instructions for manually applying the fix."""
    
    print("MANUAL FIX INSTRUCTIONS")
    print("="*60)
    print("\nThe issue is that the template clearing isn't aggressive enough.")
    print("The template has content in rows 22-34 that needs to be cleared.")
    print("\nTo fix this, replace the _clear_template_placeholders method in")
    print("dynamic_summary_template_processor.py with this version:\n")
    
    print(create_targeted_fix())
    
    print("\n\nAlternatively, you can modify the existing method to:")
    print("1. Specifically clear rows 21-34")
    print("2. Look for the exact template keywords shown in the comparison")
    print("3. Clear the cells containing those keywords")
    
    print("\nThe key is to clear ALL template content before Section 3 is written,")
    print("so there's no duplication when the dynamic content is added at row 35+")

if __name__ == "__main__":
    show_manual_fix_instructions()
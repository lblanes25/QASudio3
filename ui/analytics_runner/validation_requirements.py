"""
Validation Requirements Model
Tracks what's needed for validation independently of UI state
"""

from typing import List, Optional


class ValidationRequirements:
    """Track validation requirements independently of UI state"""
    
    def __init__(self):
        # Core requirements
        self.data_source_valid: bool = False
        self.data_source_path: Optional[str] = None
        self.sheet_name: Optional[str] = None
        self.selected_rules: List[str] = []
        
        # Optional configuration
        self.responsible_party_column: Optional[str] = None
        self.analytic_id: str = ""
        self.output_dir: str = "./output"
        self.execution_mode: str = "Sequential"
        
        # Report options
        self.generate_excel_report: bool = True
        self.generate_leader_reports: bool = True
        
    @property
    def can_validate(self) -> bool:
        """Check if all requirements are met for validation"""
        return self.data_source_valid and len(self.selected_rules) > 0
        
    @property
    def has_responsible_party(self) -> bool:
        """Check if responsible party is configured"""
        return self.responsible_party_column is not None and self.responsible_party_column != "None"
        
    @property
    def validation_ready_message(self) -> str:
        """Get a message explaining validation readiness"""
        if not self.data_source_valid:
            return "Select a valid data source"
        elif len(self.selected_rules) == 0:
            return "Select at least one validation rule"
        else:
            return f"Ready to validate {len(self.selected_rules)} rules"
            
    def get_summary(self) -> dict:
        """Get a summary of current configuration"""
        return {
            'data_source': self.data_source_path or "Not selected",
            'sheet': self.sheet_name or "N/A",
            'rules_count': len(self.selected_rules),
            'responsible_party': self.responsible_party_column or "None",
            'can_validate': self.can_validate,
            'generate_reports': {
                'excel': self.generate_excel_report,
                'leader_splits': self.generate_leader_reports and self.has_responsible_party
            }
        }
        
    def reset(self):
        """Reset all requirements to initial state"""
        self.__init__()
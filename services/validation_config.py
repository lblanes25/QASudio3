# services/validation_config.py

"""Configuration classes for validation service."""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from pathlib import Path
import pandas as pd

from services.validation_constants import (
    DEFAULT_OUTPUT_DIR, DEFAULT_ARCHIVE_DIR, MAX_PARALLEL_WORKERS,
    DEFAULT_OUTPUT_FORMAT, SUPPORTED_OUTPUT_FORMATS, DEFAULT_RULES_DIR
)


@dataclass
class ValidationConfig:
    """Configuration for validation pipeline."""
    
    # Directory settings
    output_dir: Path = field(default_factory=lambda: Path(DEFAULT_OUTPUT_DIR))
    archive_dir: Optional[Path] = field(default_factory=lambda: Path(DEFAULT_ARCHIVE_DIR))
    rules_dir: Path = field(default_factory=lambda: Path(DEFAULT_RULES_DIR))
    
    # Performance settings
    max_workers: int = MAX_PARALLEL_WORKERS
    use_parallel: bool = False
    batch_size: int = 1000
    
    # Rule configuration
    rule_config_paths: List[str] = field(default_factory=list)
    rule_ids: Optional[List[str]] = None
    use_all_rules: bool = False
    min_severity: Optional[str] = None
    exclude_rule_types: Optional[List[str]] = None
    
    # Column settings
    entity_id_column: str = 'AuditEntityID'
    responsible_party_column: Optional[str] = None
    
    # Schema validation
    expected_schema: Optional[Union[List[str], str]] = None
    
    def __post_init__(self):
        """Ensure directories exist."""
        self.output_dir = Path(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if self.archive_dir:
            self.archive_dir = Path(self.archive_dir)
            self.archive_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class ReportConfig:
    """Configuration for report generation."""
    
    # Report settings
    report_config_path: Optional[str] = None
    template_path: Optional[str] = None
    output_formats: List[str] = field(default_factory=lambda: ['json', 'excel'])
    
    # Report content
    analytic_id: Optional[str] = None
    analytic_title: Optional[str] = None
    include_summary: bool = True
    include_details: bool = True
    include_guide: bool = True
    
    # Leader reports
    generate_leader_reports: bool = False
    leader_report_dir: Optional[str] = None
    
    # Excel formatting
    max_col_width: int = 50
    min_col_width: int = 10
    default_col_width: int = 15
    
    def __post_init__(self):
        """Validate output formats."""
        invalid_formats = [fmt for fmt in self.output_formats if fmt not in SUPPORTED_OUTPUT_FORMATS]
        if invalid_formats:
            raise ValueError(f"Unsupported output formats: {invalid_formats}. "
                           f"Supported formats: {SUPPORTED_OUTPUT_FORMATS}")


@dataclass
class ValidationRequest:
    """Request object for validation to avoid excessive parameters."""
    
    # Data source
    data_source: Union[str, pd.DataFrame]
    data_source_params: Optional[Dict[str, Any]] = None
    
    # Configuration
    validation_config: ValidationConfig = field(default_factory=ValidationConfig)
    report_config: ReportConfig = field(default_factory=ReportConfig)
    
    # Pre-validation
    pre_validation: Optional[Dict[str, Any]] = None
    
    @property
    def is_dataframe(self) -> bool:
        """Check if data source is a DataFrame."""
        return isinstance(self.data_source, pd.DataFrame)
    
    @property
    def data_source_path(self) -> Optional[str]:
        """Get data source path if it's a string."""
        return self.data_source if isinstance(self.data_source, str) else None


@dataclass  
class ValidationResult:
    """Result object from validation."""
    
    # Status
    status: str  # 'SUCCESS', 'FAILED', 'PARTIAL'
    timestamp: str
    
    # Summary statistics
    total_rules: int = 0
    passed_rules: int = 0
    failed_rules: int = 0
    skipped_rules: int = 0
    
    # Compliance counts
    compliance_counts: Dict[str, int] = field(default_factory=dict)
    compliance_rate: float = 0.0
    
    # Detailed results
    rule_results: Dict[str, Any] = field(default_factory=dict)
    summary: Dict[str, Any] = field(default_factory=dict)
    
    # Execution info
    execution_time: float = 0.0
    data_source: str = 'Unknown'
    responsible_party_column: Optional[str] = None
    
    # Output files
    output_files: List[str] = field(default_factory=list)
    
    # Errors
    errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'status': self.status,
            'timestamp': self.timestamp,
            'summary': {
                'total_rules': self.total_rules,
                'passed_rules': self.passed_rules,
                'failed_rules': self.failed_rules,
                'skipped_rules': self.skipped_rules,
                'compliance_counts': self.compliance_counts,
                'compliance_rate': self.compliance_rate
            },
            'rule_results': self.rule_results,
            'execution_time': self.execution_time,
            'data_source': self.data_source,
            'responsible_party_column': self.responsible_party_column,
            'output_files': self.output_files,
            'errors': self.errors
        }
# services/validation_pipeline_compat.py

"""
Backward compatibility wrapper for ValidationPipeline.
This allows existing code to work with the refactored ValidationPipeline.
"""

import pandas as pd
from typing import Dict, List, Any, Optional, Union
from pathlib import Path

from services.validation_service import ValidationPipeline as RefactoredPipeline
from services.validation_config import ValidationConfig, ReportConfig, ValidationRequest
from core.rule_engine.rule_manager import ValidationRuleManager
from core.rule_engine.rule_evaluator import RuleEvaluator
from data_integration.io.importer import DataImporter


class ValidationPipeline:
    """
    Backward-compatible wrapper that accepts old-style initialization
    but uses the refactored ValidationPipeline internally.
    """
    
    def __init__(self,
                 rule_manager: Optional[ValidationRuleManager] = None,
                 evaluator: Optional[RuleEvaluator] = None,
                 data_importer: Optional[DataImporter] = None,
                 output_dir: Optional[str] = None,
                 archive_dir: Optional[str] = None,
                 max_workers: int = 4,
                 rule_config_paths: Optional[List[str]] = None,
                 report_config_path: Optional[str] = None):
        """Initialize with old-style parameters."""
        # Create config from old parameters
        config = ValidationConfig(
            output_dir=Path(output_dir) if output_dir else Path("./output"),
            archive_dir=Path(archive_dir) if archive_dir else None,
            max_workers=max_workers,
            rule_config_paths=rule_config_paths or []
        )
        
        # Initialize the refactored pipeline
        self._pipeline = RefactoredPipeline(config)
        
        # If a rule_manager was provided, use it
        if rule_manager:
            self._pipeline.rule_manager = rule_manager
            self._pipeline.evaluator = RuleEvaluator(rule_manager=rule_manager)
        
        # Store attributes for backward compatibility
        self.rule_manager = self._pipeline.rule_manager
        self.evaluator = self._pipeline.evaluator
        self.data_importer = self._pipeline.data_importer
        self.data_validator = self._pipeline.data_validator
        self.output_dir = config.output_dir
        self.archive_dir = config.archive_dir
        self.max_workers = config.max_workers
        self.rule_config_paths = config.rule_config_paths
    
    def validate_data_source(self,
                            data_source: Union[str, pd.DataFrame],
                            rule_ids: Optional[List[str]] = None,
                            analytic_id: Optional[str] = None,
                            responsible_party_column: Optional[str] = None,
                            data_source_params: Optional[Dict[str, Any]] = None,
                            pre_validation: Optional[Dict[str, Any]] = None,
                            output_formats: Optional[List[str]] = None,
                            min_severity: Optional[str] = None,
                            exclude_rule_types: Optional[List[str]] = None,
                            expected_schema: Optional[Union[List[str], str]] = None,
                            use_parallel: bool = False,
                            report_config: Optional[str] = None,
                            use_all_rules: bool = False,
                            analytic_title: Optional[str] = None) -> Dict[str, Any]:
        """Run validation with old-style parameters."""
        # Create request from old parameters
        validation_config = ValidationConfig(
            output_dir=self.output_dir,
            rule_ids=rule_ids,
            use_all_rules=use_all_rules,
            min_severity=min_severity,
            exclude_rule_types=exclude_rule_types,
            responsible_party_column=responsible_party_column,
            expected_schema=expected_schema,
            use_parallel=use_parallel,
            max_workers=self.max_workers
        )
        
        # Map old output formats to new ones
        mapped_formats = []
        if output_formats:
            for fmt in output_formats:
                if fmt == 'iag_excel':
                    mapped_formats.append('excel')
                else:
                    mapped_formats.append(fmt)
        
        report_config_obj = ReportConfig(
            analytic_id=analytic_id,
            analytic_title=analytic_title,
            output_formats=mapped_formats or ['json'],
            report_config_path=report_config
        )
        
        request = ValidationRequest(
            data_source=data_source,
            data_source_params=data_source_params,
            validation_config=validation_config,
            report_config=report_config_obj,
            pre_validation=pre_validation
        )
        
        # Call new pipeline
        try:
            result = self._pipeline.validate_data_source(request)
            
            # Convert result to old format
            return self._convert_to_legacy_format(result, analytic_id, responsible_party_column)
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise
    
    def generate_excel_report(self, validation_results_path: str, output_path: str) -> None:
        """Generate Excel report."""
        self._pipeline.generate_excel_report(validation_results_path, output_path)
    
    def split_report_by_leader(self, master_file_path: str, 
                             output_dir: Optional[str] = None) -> Dict[str, str]:
        """Split report by leader."""
        return self._pipeline.split_report_by_leader(master_file_path, output_dir)
    
    def get_rule_configuration_summary(self) -> Dict[str, Any]:
        """Get rule configuration summary."""
        return self._pipeline.get_rule_configuration_summary()
    
    def reload_rule_configurations(self) -> Dict[str, Any]:
        """Reload rule configurations."""
        return self._pipeline.reload_rule_configurations()
    
    def _convert_to_legacy_format(self, result, analytic_id: Optional[str],
                                responsible_party_column: Optional[str]) -> Dict[str, Any]:
        """Convert new result format to legacy format."""
        legacy_result = result.to_dict()
        
        # Add legacy fields
        legacy_result['valid'] = result.status == 'SUCCESS'
        legacy_result['analytic_id'] = analytic_id
        legacy_result['responsible_party_column'] = responsible_party_column
        
        # Ensure backward compatibility fields
        if 'data_metrics' not in legacy_result:
            legacy_result['data_metrics'] = {
                'row_count': 0,
                'column_count': 0,
                'columns': [],
                'total_unique_entities': 0
            }
        
        if 'schema_validation' not in legacy_result:
            legacy_result['schema_validation'] = {
                'valid': True,
                'errors': []
            }
        
        if not legacy_result.get('output_files'):
            legacy_result['output_files'] = []
        
        return legacy_result
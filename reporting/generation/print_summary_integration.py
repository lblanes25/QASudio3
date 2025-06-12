#!/usr/bin/env python3
"""
Integration module to add print-summary functionality to the report generation pipeline.
This allows printing summary information to console/log instead of generating Excel reports.
"""

import logging
from typing import Dict, Optional
from pathlib import Path

from reporting.generation.print_summary_info import print_summary_report_info, print_raw_data_structure
from reporting.generation.template_integration import generate_template_based_report

logger = logging.getLogger(__name__)


def generate_reports_with_print_option(
    rule_results: Dict,
    output_dir: str,
    base_filename: str,
    report_formats: list,
    print_summary: bool = False,
    print_raw_data: bool = False,
    responsible_party_column: str = "Responsible Party",
    analytic_title: Optional[str] = None
) -> Dict[str, str]:
    """
    Generate reports with option to print summary information instead.
    
    Args:
        rule_results: Dictionary of rule evaluation results
        output_dir: Directory to save reports
        base_filename: Base name for output files
        report_formats: List of formats to generate ('html', 'excel', 'json')
        print_summary: If True, print summary info to console instead of generating Excel
        print_raw_data: If True, also print raw data structure for debugging
        responsible_party_column: Column name for responsible party grouping
        analytic_title: Optional title for the analytic
        
    Returns:
        Dictionary of generated file paths by format
    """
    output_files = {}
    
    # Always generate JSON if requested (even when printing summary)
    if 'json' in report_formats:
        # This would use existing JSON generation logic
        # For now, we'll skip this part
        pass
    
    # Handle Excel/HTML generation or printing
    if 'excel' in report_formats or 'html' in report_formats:
        if print_summary:
            # Print summary information instead of generating files
            logger.info("Printing summary information to console...")
            
            print("\n" + "="*80)
            print(f"ANALYTIC: {analytic_title or 'Analytics Validation'}")
            print("="*80)
            
            # Print the summary information
            print_summary_report_info(rule_results, responsible_party_column)
            
            # Optionally print raw data structure
            if print_raw_data:
                print_raw_data_structure(rule_results)
            
            # Log that we printed instead of generating files
            logger.info("Summary information printed to console (no files generated)")
            
            # Add a virtual entry to indicate printing was done
            output_files['summary_printed'] = "Console output"
            
        else:
            # Use existing template-based generation
            template_files = generate_template_based_report(
                rule_results=rule_results,
                output_dir=output_dir,
                base_filename=base_filename,
                responsible_party_column=responsible_party_column,
                analytic_title=analytic_title
            )
            output_files.update(template_files)
    
    return output_files


def add_print_summary_to_pipeline(pipeline_instance):
    """
    Monkey-patch or extend a pipeline instance to add print summary functionality.
    
    This is a helper function to add the print summary option to existing pipelines
    without modifying their source code.
    """
    original_generate = pipeline_instance.generate_reports
    
    def generate_with_print_option(**kwargs):
        # Check if print_summary flag is set
        if kwargs.get('print_summary', False):
            # Intercept and use our print function
            return generate_reports_with_print_option(**kwargs)
        else:
            # Use original generation
            return original_generate(**kwargs)
    
    # Replace the method
    pipeline_instance.generate_reports = generate_with_print_option
    
    return pipeline_instance


# Example usage in validation service or UI
def modify_validation_params_for_printing(validation_params: Dict, print_only: bool = False) -> Dict:
    """
    Modify validation parameters to enable print-only mode.
    
    Args:
        validation_params: Original validation parameters
        print_only: If True, set up for printing instead of file generation
        
    Returns:
        Modified validation parameters
    """
    if print_only:
        # Keep JSON output but skip Excel/HTML file generation
        validation_params['print_summary'] = True
        validation_params['output_formats'] = ['json']  # Only keep JSON
        
        # Add flag to indicate summary should be printed
        validation_params['report_options'] = validation_params.get('report_options', {})
        validation_params['report_options']['print_summary'] = True
        
    return validation_params
# reporting/generation/report_generator.py
import os
import logging
import yaml
import datetime
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Union, Set
import pandas as pd
import numpy as np
import xlsxwriter

# Configure logging
logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates detailed Excel and HTML reports from validation results.
    Provides transparency into rule evaluations with detailed explanations
    of failures and intermediate calculations.
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the report generator with optional configuration.

        Args:
            config_path: Path to YAML configuration file
        """
        # Default configuration
        self.config = {
            'test_weights': {},  # Maps test IDs to weights
            'score_mapping': {  # Maps compliance rate ranges to scores
                "0.90-1.00": 5,
                "0.75-0.89": 4,
                "0.60-0.74": 3,
                "0.40-0.59": 2,
                "0.00-0.39": 1
            },
            'rating_labels': {  # Maps scores to labels
                5: "✅ Satisfactory",
                4: "✓ Meets Expectations",
                3: "⚠ Requires Attention",
                2: "⚠ Needs Improvement",
                1: "❌ Unsatisfactory"
            },
            'rule_explanations': {},  # Maps rule IDs to explanations
            'column_formats': {  # Format specifications for special columns
                'percentage': '0.0%',
                'score': '0.0',
                'currency': '$#,##0.00',
                'date': 'yyyy-mm-dd'
            },
            'display_options': {
                'max_failures_per_rule': 1000,
                'show_formula_on_sheets': True,
                'enable_conditional_formatting': True,
                'include_explanation_section': True,
                'show_intermediate_calculations': True
            }
        }

        # Load configuration if provided
        if config_path:
            self._load_config(config_path)

    def _load_config(self, config_path: str) -> None:
        """
        Load configuration from YAML file.

        Args:
            config_path: Path to YAML configuration file
        """
        try:
            with open(config_path, 'r') as f:
                config_data = yaml.safe_load(f)

            # Update configuration with loaded data
            if isinstance(config_data, dict) and 'report_config' in config_data:
                config = config_data['report_config']
                # Merge with defaults, preserving defaults for missing keys
                for key, value in config.items():
                    if key in self.config and isinstance(self.config[key], dict):
                        self.config[key].update(value)
                    else:
                        self.config[key] = value
                logger.info(f"Loaded report configuration from {config_path}")
            else:
                logger.warning(f"Invalid configuration format in {config_path}. Using default configuration.")
        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {str(e)}")
            logger.info("Using default configuration.")

    def generate_excel(self, results: Dict[str, Any], rule_results: Dict[str, Any],
                       output_path: str, group_by: Optional[str] = None) -> str:
        """
        Generate comprehensive Excel report based on validation results.

        Args:
            results: Validation results summary dictionary
            rule_results: Detailed rule evaluation results
            output_path: Path to save the Excel report
            group_by: Column name for grouping results (e.g., 'Audit Leader')

        Returns:
            Path to the generated Excel file
        """
        try:
            import xlsxwriter
        except ImportError:
            logger.error("xlsxwriter package is required for Excel report generation.")
            with open(output_path, 'w') as f:
                f.write('Excel report generation failed: xlsxwriter not installed')
            return output_path

        logger.info(f"Generating Excel report at {output_path}")

        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Create workbook with options for better performance with large data
        workbook_options = {
            'constant_memory': True,
            'default_date_format': 'yyyy-mm-dd'
        }
        workbook = xlsxwriter.Workbook(output_path, workbook_options)

        # Create common formats to use throughout the workbook
        formats = self._create_excel_formats(workbook)

        # Create department-wide summary sheet
        self.create_summary_sheet(workbook, results, formats)

        # Create audit leader summary sheet if group_by is specified
        if group_by:
            self.create_audit_leader_summary(workbook, results, rule_results, group_by, formats)

            # Create audit leader × test matrix
            self.create_leader_test_matrix(workbook, results, rule_results, group_by, formats)

        # Create individual analytic sheets for each rule
        self.create_analytic_sheets(workbook, results, rule_results, group_by, formats)

        # Close workbook to save changes
        try:
            workbook.close()
            logger.info(f"Excel report successfully generated at {output_path}")
        except Exception as e:
            logger.error(f"Error closing Excel workbook: {str(e)}")

        return output_path

    def _create_excel_formats(self, workbook) -> Dict[str, Any]:
        """
        Create and return a dictionary of Excel formats for consistent styling.

        Args:
            workbook: xlsxwriter workbook object

        Returns:
            Dictionary of format objects
        """
        formats = {}

        # Header formats
        formats['title'] = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })

        formats['header'] = workbook.add_format({
            'bold': True,
            'font_size': 12,
            'align': 'center',
            'valign': 'vcenter',
            'bg_color': '#D9E1F2',  # Light blue
            'border': 1
        })

        formats['subheader'] = workbook.add_format({
            'bold': True,
            'align': 'left',
            'bg_color': '#E2EFDA',  # Light green
            'border': 1
        })

        # Data formats
        formats['normal'] = workbook.add_format({
            'align': 'left',
            'valign': 'vcenter',
            'border': 1
        })

        formats['date'] = workbook.add_format({
            'num_format': 'yyyy-mm-dd',
            'align': 'center',
            'border': 1
        })

        formats['number'] = workbook.add_format({
            'num_format': '#,##0',
            'align': 'right',
            'border': 1
        })

        formats['percentage'] = workbook.add_format({
            'num_format': '0.0%',
            'align': 'center',
            'border': 1
        })

        formats['currency'] = workbook.add_format({
            'num_format': '$#,##0.00',
            'align': 'right',
            'border': 1
        })

        # Compliance status formats
        formats['gc'] = workbook.add_format({
            'bg_color': '#C6EFCE',  # Light green
            'font_color': '#006100',  # Dark green
            'bold': True,
            'align': 'center',
            'border': 1
        })

        formats['pc'] = workbook.add_format({
            'bg_color': '#FFEB9C',  # Light yellow
            'font_color': '#9C6500',  # Dark yellow
            'bold': True,
            'align': 'center',
            'border': 1
        })

        formats['dnc'] = workbook.add_format({
            'bg_color': '#FFC7CE',  # Light red
            'font_color': '#9C0006',  # Dark red
            'bold': True,
            'align': 'center',
            'border': 1
        })

        # Score formats for 1-5 scale
        for score in range(1, 6):
            # Gradient from red (1) to green (5)
            if score == 1:
                bg_color = '#FFC7CE'  # Light red
                font_color = '#9C0006'  # Dark red
            elif score == 2:
                bg_color = '#FFEB9C'  # Light yellow
                font_color = '#9C6500'  # Dark yellow
            elif score == 3:
                bg_color = '#FFFFCC'  # Very light yellow
                font_color = '#7F7F00'  # Olive
            elif score == 4:
                bg_color = '#E2EFDA'  # Light green
                font_color = '#006100'  # Dark green
            else:  # score == 5
                bg_color = '#C6EFCE'  # Stronger green
                font_color = '#006100'  # Dark green

            formats[f'score_{score}'] = workbook.add_format({
                'bg_color': bg_color,
                'font_color': font_color,
                'bold': True,
                'align': 'center',
                'border': 1,
                'num_format': '0.0'
            })

        # Formula explanation format
        formats['formula'] = workbook.add_format({
            'font_name': 'Consolas',  # Monospace font
            'align': 'left',
            'text_wrap': True,
            'border': 1
        })

        # Failure reason format
        formats['failure_reason'] = workbook.add_format({
            'bg_color': '#FCE4D6',  # Light orange
            'text_wrap': True,
            'border': 1
        })

        # Explanation section format
        formats['explanation'] = workbook.add_format({
            'bg_color': '#E2EFDA',  # Light green
            'text_wrap': True,
            'border': 1
        })

        return formats

    def create_summary_sheet(self, workbook, results: Dict[str, Any], formats: Dict[str, Any]) -> None:
        """
        Create a department-wide summary sheet with overall compliance metrics.

        Args:
            workbook: xlsxwriter workbook object
            results: Validation results dictionary
            formats: Dictionary of Excel formats
        """
        # Create summary worksheet
        worksheet = workbook.add_worksheet('Summary')

        # Set column widths
        worksheet.set_column('A:A', 25)
        worksheet.set_column('B:B', 40)
        worksheet.set_column('C:G', 15)

        # Add title
        worksheet.merge_range('A1:G1', 'QA Analytics Framework - Validation Summary', formats['title'])

        # Add report generation info
        row = 2
        worksheet.write(row, 0, 'Report Generated:', formats['subheader'])
        worksheet.write(row, 1, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'), formats['normal'])
        row += 1

        # Add analytic ID if available
        if 'analytic_id' in results and results['analytic_id']:
            worksheet.write(row, 0, 'Analytic ID:', formats['subheader'])
            worksheet.write(row, 1, results['analytic_id'], formats['normal'])
            row += 1

        # Add overall status
        status = results.get('status', 'Unknown')
        status_format = formats['gc'] if status == 'FULLY_COMPLIANT' else \
            formats['pc'] if status == 'PARTIALLY_COMPLIANT' else \
                formats['dnc']

        worksheet.write(row, 0, 'Overall Status:', formats['subheader'])
        worksheet.write(row, 1, status, status_format)
        row += 1

        # Add summary metrics
        worksheet.write(row, 0, 'Data Source:', formats['subheader'])
        worksheet.write(row, 1, results.get('data_source', 'Unknown'), formats['normal'])
        row += 1

        # Add execution time if available
        if 'execution_time' in results:
            worksheet.write(row, 0, 'Execution Time:', formats['subheader'])
            worksheet.write(row, 1, f"{results['execution_time']:.2f} seconds", formats['normal'])
            row += 1

        # Add data metrics section if available
        if 'data_metrics' in results:
            row += 1
            worksheet.merge_range(f'A{row + 1}:G{row + 1}', 'Data Metrics', formats['header'])
            row += 1

            metrics = results['data_metrics']
            worksheet.write(row, 0, 'Row Count:', formats['subheader'])
            worksheet.write(row, 1, metrics.get('row_count', 0), formats['number'])
            row += 1

            worksheet.write(row, 0, 'Column Count:', formats['subheader'])
            worksheet.write(row, 1, metrics.get('column_count', 0), formats['number'])
            row += 1

            # Add columns list if available
            if 'columns' in metrics and metrics['columns']:
                worksheet.write(row, 0, 'Columns:', formats['subheader'])
                # Format as comma-separated list, limit to first 10
                columns_str = ', '.join(metrics['columns'][:10])
                if len(metrics['columns']) > 10:
                    columns_str += f" (+ {len(metrics['columns']) - 10} more)"
                worksheet.write(row, 1, columns_str, formats['normal'])
                row += 1

        # Add compliance summary section
        row += 1
        worksheet.merge_range(f'A{row + 1}:G{row + 1}', 'Compliance Summary', formats['header'])
        row += 1

        # Get summary data from results
        summary = results.get('summary', {})
        compliance_counts = summary.get('compliance_counts', {})

        # Create compliance summary table headers
        headers = ['Compliance Type', 'Count', 'Percentage']
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, formats['subheader'])
        row += 1

        # Add compliance counts
        total_rules = summary.get('total_rules', 0)

        # GC row
        gc_count = compliance_counts.get('GC', 0)
        gc_pct = gc_count / total_rules if total_rules > 0 else 0
        worksheet.write(row, 0, 'Generally Conforms (GC)', formats['gc'])
        worksheet.write(row, 1, gc_count, formats['number'])
        worksheet.write(row, 2, gc_pct, formats['percentage'])
        row += 1

        # PC row
        pc_count = compliance_counts.get('PC', 0)
        pc_pct = pc_count / total_rules if total_rules > 0 else 0
        worksheet.write(row, 0, 'Partially Conforms (PC)', formats['pc'])
        worksheet.write(row, 1, pc_count, formats['number'])
        worksheet.write(row, 2, pc_pct, formats['percentage'])
        row += 1

        # DNC row
        dnc_count = compliance_counts.get('DNC', 0)
        dnc_pct = dnc_count / total_rules if total_rules > 0 else 0
        worksheet.write(row, 0, 'Does Not Conform (DNC)', formats['dnc'])
        worksheet.write(row, 1, dnc_count, formats['number'])
        worksheet.write(row, 2, dnc_pct, formats['percentage'])
        row += 1

        # Total row
        worksheet.write(row, 0, 'Total', formats['subheader'])
        worksheet.write(row, 1, total_rules, formats['number'])
        worksheet.write(row, 2, 1.0 if total_rules > 0 else 0, formats['percentage'])
        row += 3

        # Add rule statistics by category and severity if available
        if 'rule_stats' in summary:
            rule_stats = summary['rule_stats']

            # By Category section
            if 'by_category' in rule_stats:
                worksheet.merge_range(f'A{row + 1}:G{row + 1}', 'Compliance by Category', formats['header'])
                row += 1

                # Headers
                headers = ['Category', 'Total Rules', 'GC', 'PC', 'DNC', 'Compliance Rate']
                for col, header in enumerate(headers):
                    worksheet.write(row, col, header, formats['subheader'])
                row += 1

                # Add data for each category
                for category, stats in rule_stats['by_category'].items():
                    count = stats.get('count', 0)
                    gc = stats.get('GC', 0)
                    pc = stats.get('PC', 0)
                    dnc = stats.get('DNC', 0)
                    compliance_rate = gc / count if count > 0 else 0

                    worksheet.write(row, 0, category, formats['normal'])
                    worksheet.write(row, 1, count, formats['number'])
                    worksheet.write(row, 2, gc, formats['number'])
                    worksheet.write(row, 3, pc, formats['number'])
                    worksheet.write(row, 4, dnc, formats['number'])
                    worksheet.write(row, 5, compliance_rate, formats['percentage'])
                    row += 1

                row += 2

            # By Severity section
            if 'by_severity' in rule_stats:
                worksheet.merge_range(f'A{row + 1}:G{row + 1}', 'Compliance by Severity', formats['header'])
                row += 1

                # Headers
                headers = ['Severity', 'Total Rules', 'GC', 'PC', 'DNC', 'Compliance Rate']
                for col, header in enumerate(headers):
                    worksheet.write(row, col, header, formats['subheader'])
                row += 1

                # Severity order mapping (for sorting)
                severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}

                # Sort severities by importance
                sorted_severities = sorted(
                    rule_stats['by_severity'].items(),
                    key=lambda x: severity_order.get(x[0].lower(), 999)
                )

                # Add data for each severity
                for severity, stats in sorted_severities:
                    count = stats.get('count', 0)
                    gc = stats.get('GC', 0)
                    pc = stats.get('PC', 0)
                    dnc = stats.get('DNC', 0)
                    compliance_rate = gc / count if count > 0 else 0

                    # Format severity with proper capitalization
                    severity_display = severity.title() if severity else 'Unknown'

                    worksheet.write(row, 0, severity_display, formats['normal'])
                    worksheet.write(row, 1, count, formats['number'])
                    worksheet.write(row, 2, gc, formats['number'])
                    worksheet.write(row, 3, pc, formats['number'])
                    worksheet.write(row, 4, dnc, formats['number'])
                    worksheet.write(row, 5, compliance_rate, formats['percentage'])
                    row += 1

        # Add output files section if any are listed
        if 'output_files' in results and results['output_files']:
            row += 2
            worksheet.merge_range(f'A{row + 1}:G{row + 1}', 'Output Files', formats['header'])
            row += 1

            for i, file_path in enumerate(results['output_files']):
                worksheet.write(row + i, 0, f"File {i + 1}:", formats['subheader'])
                worksheet.write(row + i, 1, os.path.basename(file_path), formats['normal'])

    def _analyze_formula_components(self, formula: str) -> Dict[str, Any]:
        """
        Analyze Excel formula to extract its components for explanation.

        Args:
            formula: Excel formula to analyze

        Returns:
            Dictionary with formula components
        """
        # Strip the leading "=" if present
        if formula.startswith("="):
            formula = formula[1:]

        # Extract components
        components = {
            'functions': set(),
            'logical_operators': set(),
            'comparisons': set(),
            'referenced_columns': [],
            'complexity': 'simple'
        }

        # Extract column references
        pattern = r'\[([^\]]+)\]'
        matches = re.findall(pattern, formula)
        if matches:
            components['referenced_columns'] = matches

        # Extract comparison operators
        for op in ['>=', '<=', '<>', '>', '<', '=']:
            if op in formula:
                components['comparisons'].add(op)

        # Extract logical operators
        if "AND(" in formula.upper():
            components['logical_operators'].add("AND")
        if "OR(" in formula.upper():
            components['logical_operators'].add("OR")
        if "NOT(" in formula.upper():
            components['logical_operators'].add("NOT")
        if "IF(" in formula.upper():
            components['logical_operators'].add("IF")

        # Extract Excel functions
        function_pattern = r'([A-Z]+)\('
        function_matches = re.findall(function_pattern, formula.upper())
        for match in function_matches:
            # Add to functions but filter out logical operators already counted
            if match not in ['AND', 'OR', 'NOT', 'IF']:
                components['functions'].add(match)

        # Set complexity based on components
        if (len(components['logical_operators']) > 0 or
                len(components['functions']) > 1 or
                len(components['comparisons']) > 1):
            components['complexity'] = 'complex'

        return components

    def _extract_column_references(self, formula: str) -> List[str]:
        """
        Extract column references from a formula.

        Args:
            formula: Formula to analyze

        Returns:
            List of column names referenced in formula
        """
        pattern = r'\[([^\]]+)\]'
        return re.findall(pattern, formula)

    def create_analytic_sheets(self, workbook, results: Dict[str, Any],
                               rule_results: Dict[str, Any], group_by: Optional[str],
                               formats: Dict[str, Any]) -> None:
        """
        Create individual sheets for each analytic/rule with detailed failure analysis.

        Args:
            workbook: xlsxwriter workbook object
            results: Validation results dictionary
            rule_results: Dictionary of rule evaluation results
            group_by: Column name for grouping results
            formats: Dictionary of Excel formats
        """
        # Process each rule
        for rule_id, result in rule_results.items():
            try:
                rule = result.rule
                rule_name = rule.name
                formula = rule.formula

                # Create sheet for this rule
                # Use safe name that fits Excel's 31-character limit
                sheet_name = self._safe_sheet_name(rule_name)
                worksheet = workbook.add_worksheet(sheet_name)

                # Set column widths based on content
                worksheet.set_column('A:Z', 15)  # Default width

                # Add title with rule name
                worksheet.merge_range('A1:H1', f"Analytic: {rule_name}", formats['title'])

                # Add rule information section
                row = 2

                # Rule ID and name
                worksheet.write(row, 0, 'Rule ID:', formats['subheader'])
                worksheet.write(row, 1, rule_id, formats['normal'])
                row += 1

                # Rule description if available
                if hasattr(rule, 'description') and rule.description:
                    description = rule.description
                elif rule_id in self.config['rule_explanations']:
                    description = self.config['rule_explanations'][rule_id]
                else:
                    description = "No description available."

                worksheet.write(row, 0, 'Description:', formats['subheader'])
                worksheet.merge_range(f'B{row + 1}:H{row + 1}', description, formats['normal'])
                row += 1

                # Rule formula
                worksheet.write(row, 0, 'Formula:', formats['subheader'])
                worksheet.merge_range(f'B{row + 1}:H{row + 1}', formula, formats['formula'])
                row += 1

                # Rule complexity and components
                formula_components = self._analyze_formula_components(formula)

                worksheet.write(row, 0, 'Complexity:', formats['subheader'])
                worksheet.write(row, 1, formula_components['complexity'].title(), formats['normal'])
                row += 1

                # Referenced columns
                if formula_components['referenced_columns']:
                    worksheet.write(row, 0, 'Referenced Columns:', formats['subheader'])
                    worksheet.merge_range(f'B{row + 1}:H{row + 1}',
                                          ', '.join(formula_components['referenced_columns']),
                                          formats['normal'])
                    row += 1

                # Add compliance metrics
                row += 1
                worksheet.merge_range(f'A{row + 1}:H{row + 1}', 'Compliance Metrics', formats['header'])
                row += 1

                # Overall compliance status
                compliance_status = result.compliance_status
                status_format = formats['gc'] if compliance_status == 'GC' else \
                    formats['pc'] if compliance_status == 'PC' else \
                        formats['dnc']

                worksheet.write(row, 0, 'Overall Status:', formats['subheader'])
                worksheet.write(row, 1, compliance_status, status_format)
                row += 1

                # Compliance metrics
                metrics = result.compliance_metrics

                worksheet.write(row, 0, 'Total Items:', formats['subheader'])
                worksheet.write(row, 1, metrics.get('total_count', 0), formats['number'])
                row += 1

                worksheet.write(row, 0, 'GC Count:', formats['subheader'])
                worksheet.write(row, 1, metrics.get('gc_count', 0), formats['number'])
                row += 1

                worksheet.write(row, 0, 'PC Count:', formats['subheader'])
                worksheet.write(row, 1, metrics.get('pc_count', 0), formats['number'])
                row += 1

                worksheet.write(row, 0, 'DNC Count:', formats['subheader'])
                worksheet.write(row, 1, metrics.get('dnc_count', 0), formats['number'])
                row += 1

                # Calculate compliance rate
                total_count = metrics.get('total_count', 0)
                gc_count = metrics.get('gc_count', 0)
                compliance_rate = gc_count / total_count if total_count > 0 else 0

                worksheet.write(row, 0, 'Compliance Rate:', formats['subheader'])
                worksheet.write(row, 1, compliance_rate, formats['percentage'])
                row += 1

                # If there are errors, show error count
                if 'error_count' in metrics and metrics['error_count'] > 0:
                    worksheet.write(row, 0, 'Error Count:', formats['subheader'])
                    worksheet.write(row, 1, metrics['error_count'], formats['number'])
                    row += 1

                # Add responsible party breakdown if available
                if hasattr(result, 'party_results') and result.party_results and group_by:
                    row += 1
                    worksheet.merge_range(f'A{row + 1}:H{row + 1}', f'Compliance by {group_by}', formats['header'])
                    row += 1

                    # Headers
                    headers = [group_by, 'Total Items', 'GC', 'PC', 'DNC', 'Compliance Rate', 'Status']
                    for col, header in enumerate(headers):
                        worksheet.write(row, col, header, formats['subheader'])
                    row += 1

                    # Add data for each responsible party
                    for party, party_result in result.party_results.items():
                        party_status = party_result['status']
                        party_metrics = party_result['metrics']

                        # Calculate party-specific compliance rate
                        party_total = party_metrics.get('total_count', 0)
                        party_gc = party_metrics.get('gc_count', 0)
                        party_pc = party_metrics.get('pc_count', 0)
                        party_dnc = party_metrics.get('dnc_count', 0)
                        party_rate = party_gc / party_total if party_total > 0 else 0

                        # Select format based on status
                        status_fmt = formats['gc'] if party_status == 'GC' else \
                            formats['pc'] if party_status == 'PC' else \
                                formats['dnc']

                        worksheet.write(row, 0, party, formats['normal'])
                        worksheet.write(row, 1, party_total, formats['number'])
                        worksheet.write(row, 2, party_gc, formats['number'])
                        worksheet.write(row, 3, party_pc, formats['number'])
                        worksheet.write(row, 4, party_dnc, formats['number'])
                        worksheet.write(row, 5, party_rate, formats['percentage'])
                        worksheet.write(row, 6, party_status, status_fmt)
                        row += 1

                # Add failure details if there are any
                if hasattr(result, 'get_failing_items'):
                    failure_df = result.get_failing_items()

                    if not failure_df.empty:
                        row += 2
                        worksheet.merge_range(f'A{row + 1}:H{row + 1}', 'Failure Details', formats['header'])
                        row += 1

                        # Limit failures to configured maximum
                        max_failures = self.config['display_options'].get('max_failures_per_rule', 1000)
                        if len(failure_df) > max_failures:
                            original_count = len(failure_df)
                            failure_df = failure_df.head(max_failures)
                            worksheet.merge_range(f'A{row + 1}:H{row + 1}',
                                                  f"Showing first {max_failures} of {original_count} failures",
                                                  formats['normal'])
                            row += 1

                        # Create enhanced DataFrame with calculation explanations
                        enhanced_df = self._add_calculation_columns(failure_df, result)

                        # Determine columns to display
                        display_columns = self._organize_display_columns(
                            enhanced_df,
                            formula_components['referenced_columns'],
                            result.result_column,
                            result.result_column + "_Error" if hasattr(result, 'result_column') else None
                        )

                        # Write column headers
                        for col, column_name in enumerate(display_columns):
                            worksheet.write(row, col, column_name, formats['subheader'])
                        row += 1

                        # Write data rows
                        for df_row in range(len(enhanced_df)):
                            for col, column_name in enumerate(display_columns):
                                if column_name in enhanced_df.columns:
                                    value = enhanced_df.iloc[df_row][column_name]

                                    # Apply appropriate formatting based on column type
                                    cell_format = formats['normal']

                                    # Handle special column types
                                    if column_name == result.result_column:
                                        # Result column gets GC/PC/DNC formatting
                                        if value is True or value == 'True' or value == 'TRUE':
                                            cell_format = formats['gc']
                                            value = 'GC'
                                        elif value is False or value == 'False' or value == 'FALSE':
                                            cell_format = formats['dnc']
                                            value = 'DNC'
                                        else:
                                            # Try to determine status based on value
                                            if isinstance(value, str):
                                                if 'GC' in value:
                                                    cell_format = formats['gc']
                                                elif 'PC' in value:
                                                    cell_format = formats['pc']
                                                elif 'DNC' in value:
                                                    cell_format = formats['dnc']
                                    elif column_name.startswith('Calc_') or column_name.startswith('Reason_'):
                                        # Calculation or reason columns get special formatting
                                        cell_format = formats['failure_reason']
                                    elif pd.api.types.is_numeric_dtype(enhanced_df[column_name].dtype):
                                        cell_format = formats['number']
                                    elif pd.api.types.is_datetime64_dtype(enhanced_df[column_name].dtype):
                                        cell_format = formats['date']

                                    # Handle NaN values
                                    if pd.isna(value):
                                        value = 'N/A'

                                    worksheet.write(row + df_row, col, value, cell_format)
                                else:
                                    # Column not in DataFrame, write blank cell
                                    worksheet.write(row + df_row, col, '', formats['normal'])

                # Add troubleshooting tips if configured
                if self.config['display_options'].get('include_explanation_section', True):
                    row += len(enhanced_df) + 2 if 'enhanced_df' in locals() and not enhanced_df.empty else 2

                    worksheet.merge_range(f'A{row + 1}:H{row + 1}', 'Troubleshooting Guide', formats['header'])
                    row += 1

                    # Get explanation of rule
                    explanation = self._get_rule_explanation(rule)
                    worksheet.merge_range(f'A{row + 1}:H{row + 1}', explanation, formats['explanation'])
                    row += 1

                    # Add specific troubleshooting tips
                    tips = self._get_troubleshooting_tips(result)
                    worksheet.merge_range(f'A{row + 1}:H{row + 1}', "Tips: " + tips, formats['explanation'])

            except Exception as e:
                # Log error and continue with next rule
                logger.error(f"Error creating sheet for rule {rule_id}: {str(e)}")
                continue

    def _safe_sheet_name(self, name: str) -> str:
        """
        Create a safe Excel sheet name (31 chars max, no invalid chars).

        Args:
            name: Original sheet name

        Returns:
            Safe sheet name for Excel
        """
        # Replace invalid characters
        invalid_chars = [':', '\\', '/', '?', '*', '[', ']']
        safe_name = name
        for char in invalid_chars:
            safe_name = safe_name.replace(char, '_')

        # Truncate to Excel's 31 character limit
        if len(safe_name) > 31:
            safe_name = safe_name[:28] + '...'

        return safe_name

    def _add_calculation_columns(self, df: pd.DataFrame, result) -> pd.DataFrame:
        """
        Add calculation columns to show how the rule was evaluated.

        Args:
            df: DataFrame with failing items
            result: Rule evaluation result

        Returns:
            Enhanced DataFrame with calculation columns
        """
        # Create a copy of the DataFrame
        enhanced_df = df.copy()

        # Get rule and formula
        rule = result.rule
        formula = rule.formula

        # Get referenced columns
        ref_columns = self._extract_column_references(formula)

        # Analyze formula structure
        components = self._analyze_formula_components(formula)

        # Generate row-specific explanations
        explanations = self._generate_row_explanations(df, result)
        if explanations is not None and len(explanations) == len(df):
            enhanced_df['Reason_Failure'] = explanations

        # Add calculation columns based on formula type
        if 'AND' in components['logical_operators']:
            # For AND formulas, show individual condition evaluations
            conditions = self._extract_and_conditions(formula)
            for i, condition in enumerate(conditions):
                column_name = f"Calc_Condition_{i + 1}"
                enhanced_df[column_name] = self._explain_condition(condition, df)

        elif 'OR' in components['logical_operators']:
            # For OR formulas, show individual condition evaluations
            conditions = self._extract_or_conditions(formula)
            for i, condition in enumerate(conditions):
                column_name = f"Calc_Condition_{i + 1}"
                enhanced_df[column_name] = self._explain_condition(condition, df)

        elif 'IF' in components['logical_operators']:
            # For IF formulas, explain the conditions
            enhanced_df['Calc_IF_Condition'] = self._explain_if_condition(formula, df)

        elif components['comparisons']:
            # For comparison formulas, explain the comparison
            enhanced_df['Calc_Comparison'] = self._explain_comparison(formula, df)

        elif 'DATEDIF' in components['functions']:
            # For date formulas, explain date difference calculation
            enhanced_df['Calc_DateDiff'] = self._explain_date_diff(formula, df)

        else:
            # Generic calculation column for other formula types
            enhanced_df['Calc_Explanation'] = f"Failed validation: {formula}"

        return enhanced_df

    def _extract_and_conditions(self, formula: str) -> List[str]:
        """
        Extract individual conditions from an AND formula.

        Args:
            formula: Excel formula string

        Returns:
            List of condition strings
        """
        # Basic implementation - just return the formula for now
        # This would need a more sophisticated parser for real applications
        if formula.upper().startswith('=AND('):
            # Strip '=AND(' and trailing ')'
            inner = formula[5:-1]
            # Split by commas not inside other functions
            # This is a simplified approach that may not work for complex nested formulas
            depth = 0
            conditions = []
            current = ""

            for char in inner:
                if char == '(':
                    depth += 1
                    current += char
                elif char == ')':
                    depth -= 1
                    current += char
                elif char == ',' and depth == 0:
                    conditions.append(current.strip())
                    current = ""
                else:
                    current += char

            if current:
                conditions.append(current.strip())

            return conditions

        return [formula]  # Return original formula if not AND

    def _extract_or_conditions(self, formula: str) -> List[str]:
        """
        Extract individual conditions from an OR formula.

        Args:
            formula: Excel formula string

        Returns:
            List of condition strings
        """
        # Implementation similar to _extract_and_conditions
        if formula.upper().startswith('=OR('):
            # Strip '=OR(' and trailing ')'
            inner = formula[4:-1]
            # Split by commas not inside other functions
            depth = 0
            conditions = []
            current = ""

            for char in inner:
                if char == '(':
                    depth += 1
                    current += char
                elif char == ')':
                    depth -= 1
                    current += char
                elif char == ',' and depth == 0:
                    conditions.append(current.strip())
                    current = ""
                else:
                    current += char

            if current:
                conditions.append(current.strip())

            return conditions

        return [formula]  # Return original formula if not OR

    def _explain_condition(self, condition: str, df: pd.DataFrame) -> pd.Series:
        """
        Create explanation for a specific condition.

        Args:
            condition: Formula condition
            df: DataFrame with data

        Returns:
            Series with explanations for each row
        """
        # Extract referenced columns
        ref_columns = self._extract_column_references(condition)

        # Create basic explanation
        if ref_columns:
            explanations = []
            for _, row in df.iterrows():
                # Build explanation with actual values
                explanation = condition
                for col in ref_columns:
                    if col in df.columns:
                        val = row[col]
                        # Format the value based on type
                        if pd.isna(val):
                            val_str = "NULL"
                        elif isinstance(val, (int, float)):
                            val_str = str(val)
                        elif isinstance(val, pd.Timestamp):
                            val_str = val.strftime('%Y-%m-%d')
                        else:
                            val_str = f"'{val}'"

                        explanation = explanation.replace(f"[{col}]", val_str)

                explanations.append(explanation)

            return pd.Series(explanations)
        else:
            # Return generic explanation if no columns found
            return pd.Series([condition] * len(df))

    def _explain_if_condition(self, formula: str, df: pd.DataFrame) -> pd.Series:
        """
        Explain an IF condition in Excel formula.

        Args:
            formula: Excel formula
            df: DataFrame with data

        Returns:
            Series with IF condition explanations
        """
        # This would need a more complex Excel formula parser for real applications
        # For now, just provide a basic explanation
        if formula.upper().startswith('=IF('):
            try:
                # Very basic extraction of the condition part
                open_paren = formula.find('(')
                condition_end = formula.find(',', open_paren)
                if open_paren > 0 and condition_end > open_paren:
                    condition = formula[open_paren + 1:condition_end].strip()

                    # Create explanations with referenced columns
                    ref_columns = self._extract_column_references(condition)
                    return self._explain_condition(condition, df)
            except Exception:
                pass

        # Fallback
        return pd.Series([f"IF condition from: {formula}"] * len(df))

    def _explain_comparison(self, formula: str, df: pd.DataFrame) -> pd.Series:
        """
        Explain a comparison in Excel formula.

        Args:
            formula: Excel formula
            df: DataFrame with data

        Returns:
            Series with comparison explanations
        """
        # Remove the leading = first
        formula = formula.lstrip('=').strip()

        # Try to identify the comparison operator
        for op in ['>=', '<=', '<>', '>', '<', '=']:
            if op in formula:
                parts = formula.split(op, 1)
                if len(parts) == 2:
                    left = parts[0].strip()
                    right = parts[1].strip()

                    # If this is a column comparison
                    left_col = None
                    right_col = None

                    left_match = re.search(r'\[([^\]]+)\]', left)
                    if left_match:
                        left_col = left_match.group(1)

                    right_match = re.search(r'\[([^\]]+)\]', right)
                    if right_match:
                        right_col = right_match.group(1)

                    # Create explanations
                    explanations = []

                    for _, row in df.iterrows():
                        left_val = row[left_col] if left_col and left_col in df.columns else left
                        if right_col and right_col in df.columns:
                            right_val = row[right_col]
                        else:
                            # Try to convert literal to number or strip quotes
                            try:
                                right_val = float(right)
                                # If left_val is int, convert to int for cleaner display
                                if isinstance(left_val, int) and right_val == int(right_val):
                                    right_val = int(right_val)
                            except ValueError:
                                # Strip quotes from literal strings like "High"
                                right_val = str(right).strip('"').strip("'")

                        # Format values
                        if isinstance(left_val, (int, float)):
                            left_str = str(left_val)
                        elif isinstance(left_val, pd.Timestamp):
                            left_str = left_val.strftime('%Y-%m-%d')
                        else:
                            left_str = str(left_val)

                        if isinstance(right_val, (int, float)):
                            right_str = str(right_val)
                        elif isinstance(right_val, pd.Timestamp):
                            right_str = right_val.strftime('%Y-%m-%d')
                        else:
                            right_str = str(right_val)

                        # Construct explanation
                        comparison_text = f"{left_str} {op} {right_str}"
                        # Evaluate the comparison result
                        try:
                            result = False  # default
                            if op == '=':
                                result = left_val == right_val
                            elif op == '>':
                                result = left_val > right_val
                            elif op == '<':
                                result = left_val < right_val
                            elif op == '>=':
                                result = left_val >= right_val
                            elif op == '<=':
                                result = left_val <= right_val
                            elif op == '<>':
                                result = left_val != right_val

                            result_text = "TRUE" if result else "FALSE"
                            explanation = f"{comparison_text} is {result_text}"
                        except:
                            explanation = comparison_text + " (could not evaluate)"

                        explanations.append(explanation)

                    return pd.Series(explanations)

        # Fallback
        return pd.Series([f"Comparison from: {formula}"] * len(df))

    def _explain_date_diff(self, formula: str, df: pd.DataFrame) -> pd.Series:
        """
        Explain a DATEDIF calculation in Excel formula.

        Args:
            formula: Excel formula
            df: DataFrame with data

        Returns:
            Series with date difference explanations
        """
        # Try to extract date columns
        date_cols = []
        for col in df.columns:
            if pd.api.types.is_datetime64_dtype(df[col]):
                date_cols.append(col)

        if len(date_cols) >= 2:
            # Create explanations with date values
            explanations = []
            for _, row in df.iterrows():
                date_values = []
                for col in date_cols:
                    if pd.notna(row[col]):
                        date_values.append(f"{col}={row[col].strftime('%Y-%m-%d')}")

                if len(date_values) >= 2:
                    explanation = f"Date difference: {' and '.join(date_values)}"
                else:
                    explanation = "Missing date values for comparison"
                explanations.append(explanation)

            return pd.Series(explanations)

        # Fallback
        return pd.Series([f"Date calculation from: {formula}"] * len(df))

    def _generate_row_explanations(self, df: pd.DataFrame, result) -> pd.Series:
        """
        Generate explanations for why each row failed validation.

        Args:
            df: DataFrame with failing rows
            result: Rule evaluation result

        Returns:
            Series with explanations
        """
        rule = result.rule
        formula = rule.formula
        rule_id = rule.rule_id

        # Try to get predefined explanation
        if rule_id in self.config['rule_explanations']:
            base_explanation = self.config['rule_explanations'][rule_id]
            return pd.Series([base_explanation] * len(df))

        # Check common failure patterns
        explanations = []

        for _, row in df.iterrows():
            # Check for NaN values in referenced columns
            ref_columns = self._extract_column_references(formula)
            missing_data = []

            for col in ref_columns:
                if col in df.columns and pd.isna(row[col]):
                    missing_data.append(col)

            if missing_data:
                explanation = f"Missing data in column(s): {', '.join(missing_data)}"
            else:
                explanation = self._format_rule_explanation(rule, df)

            explanations.append(explanation)

        return pd.Series(explanations)

    def _organize_display_columns(self, df: pd.DataFrame, formula_columns: List[str],
                                  result_column: str, error_column: Optional[str]) -> List[str]:
        """
        Organize columns for display in the Excel report.

        Args:
            df: DataFrame with data
            formula_columns: Columns referenced in the formula
            result_column: Column with validation result
            error_column: Column with error information

        Returns:
            List of column names in display order
        """
        display_columns = []

        # 1. Add key/identifier columns first (usually first 1-2 columns of the DataFrame)
        # These are likely entity IDs or key identifiers
        key_columns = list(df.columns[:2]) if len(df.columns) > 2 else list(df.columns[:1])
        display_columns.extend(key_columns)

        # 2. Add columns referenced in the formula
        for col in formula_columns:
            if col in df.columns and col not in display_columns:
                display_columns.append(col)

        # 3. Add calculation columns
        calc_columns = [col for col in df.columns if col.startswith('Calc_')]
        display_columns.extend(calc_columns)

        # 4. Add reason columns
        reason_columns = [col for col in df.columns if col.startswith('Reason_')]
        display_columns.extend(reason_columns)

        # 5. Add result and error columns
        if result_column in df.columns and result_column not in display_columns:
            display_columns.append(result_column)

        if error_column and error_column in df.columns and error_column not in display_columns:
            display_columns.append(error_column)

        # 6. Add any remaining columns not already included
        for col in df.columns:
            if col not in display_columns:
                display_columns.append(col)

        return display_columns

    def _format_rule_explanation(self, rule, failure_df: pd.DataFrame) -> str:
        """
        Format explanation of why a rule failed.

        Args:
            rule: Validation rule
            failure_df: DataFrame with failing items

        Returns:
            Formatted explanation string
        """
        # Default explanation
        explanation = f"Failed validation for rule: {rule.name}"

        # Add details about missing data if that's a common issue
        has_nulls = False
        if hasattr(rule, 'formula'):
            ref_columns = self._extract_column_references(rule.formula)
            for col in ref_columns:
                if col in failure_df.columns and failure_df[col].isna().any():
                    has_nulls = True
                    break

        if has_nulls:
            explanation += ". Missing data may be the cause."

        # Add information about the rule severity if available
        if hasattr(rule, 'severity'):
            explanation += f" (Severity: {rule.severity.title()})"

        return explanation

    def _get_rule_explanation(self, rule) -> str:
        """
        Get detailed explanation for a rule.

        Args:
            rule: Validation rule

        Returns:
            Detailed explanation string
        """
        # Check for predefined explanation
        if hasattr(rule, 'rule_id') and rule.rule_id in self.config['rule_explanations']:
            return self.config['rule_explanations'][rule.rule_id]

        # Generate explanation from formula
        formula = getattr(rule, 'formula', '')

        # Basic analysis
        components = self._analyze_formula_components(formula)

        explanation = f"This rule validates that "

        # Try to make it readable based on formula components
        if 'AND' in components['logical_operators']:
            explanation += "all of these conditions are true: "
            conditions = self._extract_and_conditions(formula)
            for i, condition in enumerate(conditions):
                explanation += f"\n{i + 1}. {condition}"
        elif 'OR' in components['logical_operators']:
            explanation += "at least one of these conditions is true: "
            conditions = self._extract_or_conditions(formula)
            for i, condition in enumerate(conditions):
                explanation += f"\n{i + 1}. {condition}"
        elif components['comparisons']:
            # For simple comparisons
            cols = components['referenced_columns']
            if len(cols) == 1:
                col = cols[0]
                if ">" in formula:
                    explanation += f"the value in column '{col}' is greater than a threshold."
                elif "<" in formula:
                    explanation += f"the value in column '{col}' is less than a threshold."
                elif "=" in formula:
                    explanation += f"the value in column '{col}' equals the expected value."
                else:
                    explanation += f"the value in column '{col}' meets specified criteria."
            elif len(cols) == 2:
                explanation += f"the relationship between '{cols[0]}' and '{cols[1]}' is valid."
            else:
                explanation += "the values in multiple columns meet the specified criteria."
        else:
            # Generic explanation
            explanation += "data meets the validation criteria specified in the formula."

        # Add formula for reference
        explanation += f"\n\nFormula: {formula}"

        return explanation

    def _get_troubleshooting_tips(self, result) -> str:
        """
        Generate troubleshooting tips for a rule result.

        Args:
            result: Rule evaluation result

        Returns:
            Troubleshooting tips string
        """
        rule = result.rule
        formula = getattr(rule, 'formula', '')
        components = self._analyze_formula_components(formula)

        # Common issues
        tips = "To address validation failures, check for: "

        # Add tips based on formula components
        issues = []

        # Missing data
        if components['referenced_columns']:
            issues.append(f"Missing data in columns: {', '.join(components['referenced_columns'])}")

        # Date issues
        if 'DATE' in components['functions'] or 'DATEDIF' in components['functions']:
            issues.append("Incorrect date formats or invalid dates")

        # Numeric issues
        if any(op in components['comparisons'] for op in ['>', '<', '>=', '<=']):
            issues.append("Values outside the expected range")

        # Text issues
        if 'TEXT' in components['functions'] or 'FIND' in components['functions']:
            issues.append("Text values not matching expected format")

        # Special handling for IF formulas
        if 'IF' in components['logical_operators']:
            issues.append("Conditions in the IF statement not being met")

        # Add any errors if available
        if hasattr(result, 'compliance_metrics') and 'error_count' in result.compliance_metrics:
            error_count = result.compliance_metrics['error_count']
            if error_count > 0:
                issues.append(f"Formula evaluation errors ({error_count} occurrences)")

        # Join issues 
        if issues:
            tips += "\n- " + "\n- ".join(issues)
        else:
            tips += "general data quality issues."

        return tips

    def create_audit_leader_summary(self, workbook, results: Dict[str, Any],
                                    rule_results: Dict[str, Any], group_by: str,
                                    formats: Dict[str, Any]) -> None:
        """
        Create a summary sheet with scores for each audit leader.

        Args:
            workbook: xlsxwriter workbook object
            results: Validation results dictionary
            rule_results: Dictionary of rule evaluation results
            group_by: Column name for grouping (e.g. 'Audit Leader')
            formats: Dictionary of Excel formats
        """
        # Skip if no group_by specified
        if not group_by or 'grouped_summary' not in results:
            return

        # Create worksheet
        worksheet = workbook.add_worksheet(f'{group_by} Summary')

        # Set column widths
        worksheet.set_column('A:A', 30)  # Leader name
        worksheet.set_column('B:F', 15)  # Metrics
        worksheet.set_column('G:G', 20)  # Rating
        worksheet.set_column('H:I', 15)  # Override and comment

        # Add title
        worksheet.merge_range('A1:I1', f'Quality Metrics by {group_by}', formats['title'])

        # Add headers
        row = 2
        headers = [group_by, 'Total Rules', 'GC', 'PC', 'DNC', 'Compliance Rate', 'Score', 'Rating',
                   'Override Score', 'Comments']
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, formats['header'])
        row += 1

        # Get grouped summary data
        grouped_summary = results['grouped_summary']

        # Calculate scores for each group
        for party, stats in grouped_summary.items():
            # Calculate weighted score
            score = self.calculate_weighted_score(results, rule_results, party)

            # Get rating label for score
            score_int = int(score)
            rating = self.config['rating_labels'].get(score_int, f"Score {score_int}")

            # Get compliance metrics
            total_rules = stats.get('total_rules', 0)
            gc_count = stats.get('GC', 0)
            pc_count = stats.get('PC', 0)
            dnc_count = stats.get('DNC', 0)
            compliance_rate = stats.get('compliance_rate', 0)

            # Write data row
            worksheet.write(row, 0, party, formats['normal'])
            worksheet.write(row, 1, total_rules, formats['number'])
            worksheet.write(row, 2, gc_count, formats['number'])
            worksheet.write(row, 3, pc_count, formats['number'])
            worksheet.write(row, 4, dnc_count, formats['number'])
            worksheet.write(row, 5, compliance_rate, formats['percentage'])

            # Score with color formatting
            score_format = formats[f'score_{score_int}'] if f'score_{score_int}' in formats else formats['normal']
            worksheet.write(row, 6, score, score_format)

            # Rating label
            worksheet.write(row, 7, rating, score_format)

            # Empty override and comments cells
            worksheet.write(row, 8, '', formats['normal'])
            worksheet.write(row, 9, '', formats['normal'])

            row += 1

        # Add data validation for override score column
        validation = {
            'validate': 'decimal',
            'criteria': 'between',
            'minimum': 1,
            'maximum': 5,
            'input_title': 'Override Score',
            'input_message': 'Enter a score between 1.0 and 5.0'
        }
        worksheet.data_validation(f'I4:I{row}', validation)

        # Add conditional formatting for compliance rate column
        worksheet.conditional_format(f'F4:F{row}', {
            'type': '3_color_scale',
            'min_color': '#FFC7CE',  # Light red
            'mid_color': '#FFEB9C',  # Light yellow
            'max_color': '#C6EFCE',  # Light green
        })

    def create_leader_test_matrix(self, workbook, results: Dict[str, Any],
                                  rule_results: Dict[str, Any], group_by: str,
                                  formats: Dict[str, Any]) -> None:
        """
        Create a matrix with audit leaders as rows and tests as columns.

        Args:
            workbook: xlsxwriter workbook object
            results: Validation results dictionary
            rule_results: Dictionary of rule evaluation results
            group_by: Column name for grouping (e.g. 'Audit Leader')
            formats: Dictionary of Excel formats
        """
        # Skip if no group_by specified
        if not group_by or 'grouped_summary' not in results:
            return

        # Create worksheet
        worksheet = workbook.add_worksheet(f'{group_by} Matrix')

        # Set column widths
        worksheet.set_column('A:A', 30)  # Leader name
        worksheet.set_column('B:Z', 15)  # Test columns

        # Add title
        title = f'Compliance Matrix by {group_by} and Test'
        worksheet.merge_range('A1:Z1', title, formats['title'])

        # Initialize the matrix
        grouped_summary = results['grouped_summary']
        parties = list(grouped_summary.keys())

        # Get test names and IDs
        tests = []
        for rule_id, result in rule_results.items():
            if hasattr(result, 'rule') and hasattr(result.rule, 'name'):
                tests.append((rule_id, result.rule.name))

        # Write column headers (test names)
        row = 2
        worksheet.write(row, 0, group_by, formats['header'])
        for col, (_, test_name) in enumerate(tests, start=1):
            # Truncate long test names
            if len(test_name) > 20:
                test_name = test_name[:17] + '...'
            worksheet.write(row, col, test_name, formats['header'])
        row += 1

        # Build the matrix of compliance rates
        for party in parties:
            worksheet.write(row, 0, party, formats['normal'])

            # Add compliance rate for each test
            for col, (rule_id, _) in enumerate(tests, start=1):
                result = rule_results.get(rule_id)

                if result and hasattr(result, 'party_results') and party in result.party_results:
                    party_result = result.party_results[party]
                    party_status = party_result['status']
                    party_metrics = party_result['metrics']

                    # Calculate compliance rate
                    party_total = party_metrics.get('total_count', 0)
                    party_gc = party_metrics.get('gc_count', 0)
                    compliance_rate = party_gc / party_total if party_total > 0 else 0

                    # Select format based on status
                    status_fmt = formats['gc'] if party_status == 'GC' else \
                               formats['pc'] if party_status == 'PC' else \
                               formats['dnc']

                    worksheet.write(row, col, compliance_rate, status_fmt)
                else:
                    # No data for this combination
                    worksheet.write(row, col, 'N/A', formats['normal'])

            row += 1

        # Add a summary row showing pass rates for each test
        worksheet.write(row, 0, 'Overall Pass Rate', formats['subheader'])

        for col, (rule_id, _) in enumerate(tests, start=1):
            result = rule_results.get(rule_id)

            if result and hasattr(result, 'compliance_metrics'):
                metrics = result.compliance_metrics
                total_count = metrics.get('total_count', 0)
                gc_count = metrics.get('gc_count', 0)
                compliance_rate = gc_count / total_count if total_count > 0 else 0

                # Format based on overall rate
                if compliance_rate >= 0.95:
                    fmt = formats['gc']
                elif compliance_rate >= 0.75:
                    fmt = formats['pc']
                else:
                    fmt = formats['dnc']

                worksheet.write(row, col, compliance_rate, fmt)
            else:
                worksheet.write(row, col, 'N/A', formats['normal'])

        # Add conditional formatting to highlight performance issues
        num_cols = len(tests) + 1
        num_rows = len(parties) + 1

        worksheet.conditional_format(3, 1, 2+num_rows, num_cols, {
            'type': '3_color_scale',
            'min_color': '#FFC7CE',  # Light red
            'mid_color': '#FFEB9C',  # Light yellow
            'max_color': '#C6EFCE',  # Light green
        })

    def _calculate_score(self, compliance_rate: float, rule_id: Optional[str] = None) -> float:
        """
        Calculate score (1-5) based on compliance rate.

        Args:
            compliance_rate: Compliance rate (0-1)
            rule_id: Optional rule ID for rule-specific thresholds

        Returns:
            Score on 1-5 scale
        """
        # Default score
        score = 1.0

        # Check each range in the mapping
        for range_str, range_score in self.config['score_mapping'].items():
            # Parse range (e.g., "0.90-1.00")
            try:
                min_val, max_val = map(float, range_str.split('-'))
                if min_val <= compliance_rate <= max_val:
                    score = float(range_score)
                    break
            except (ValueError, AttributeError):
                logger.warning(f"Invalid range format in score mapping: {range_str}")

        return score

    def calculate_weighted_score(self, results: Dict[str, Any],
                                rule_results: Dict[str, Any],
                                party: Optional[str] = None) -> float:
        """
        Calculate weighted score for a party or overall.

        Args:
            results: Validation results dictionary
            rule_results: Dictionary of rule evaluation results
            party: Optional party name to calculate score for

        Returns:
            Weighted score on 1-5 scale
        """
        total_weight = 0.0
        weighted_sum = 0.0
        default_weight = 0.1  # Default weight for rules not specified

        # Process each rule
        for rule_id, result in rule_results.items():
            # Get rule weight
            weight = self.config['test_weights'].get(rule_id, default_weight)

            # Get compliance rate
            if party and hasattr(result, 'party_results') and party in result.party_results:
                # Use party-specific compliance rate
                party_metrics = result.party_results[party]['metrics']
                gc_count = party_metrics.get('gc_count', 0)
                total_count = party_metrics.get('total_count', 0)
                compliance_rate = gc_count / total_count if total_count > 0 else 0
            else:
                # Use overall compliance rate
                metrics = result.compliance_metrics
                gc_count = metrics.get('gc_count', 0)
                total_count = metrics.get('total_count', 0)
                compliance_rate = gc_count / total_count if total_count > 0 else 0

            # Calculate score for this rule
            score = self._calculate_score(compliance_rate, rule_id)

            # Update weighted sum
            weighted_sum += score * weight
            total_weight += weight

        # Calculate final weighted score
        if total_weight > 0:
            weighted_score = weighted_sum / total_weight
        else:
            weighted_score = 1.0  # Default to minimum score if no weights

        # Round to nearest 0.5
        return round(weighted_score * 2) / 2

    def generate_html(self, results: Dict[str, Any], rule_results: Dict[str, Any],
                      output_path: str, max_failures: int = 1000) -> str:
        """
        Generate HTML report based on validation results.

        Args:
            results: Validation results dictionary
            rule_results: Dictionary of rule evaluation results
            output_path: Path to save the HTML report
            max_failures: Maximum number of failures to include

        Returns:
            Path to the generated HTML file
        """
        logger.info(f"Generating HTML report at {output_path}")

        # Create output directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        # Get overall status and summary
        status = results.get('status', 'Unknown')
        summary = results.get('summary', {})

        # Generate HTML content
        html = []
        html.append('<!DOCTYPE html>')
        html.append('<html lang="en">')
        html.append('<head>')
        html.append('    <meta charset="UTF-8">')
        html.append('    <meta name="viewport" content="width=device-width, initial-scale=1.0">')
        html.append('    <title>QA Analytics Framework - Validation Report</title>')
        html.append('    <style>')
        html.append('        body { font-family: Arial, sans-serif; margin: 20px; }')
        html.append('        h1, h2, h3 { color: #333366; }')
        html.append('        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }')
        html.append('        th, td { border: 1px solid #dddddd; text-align: left; padding: 8px; }')
        html.append('        th { background-color: #f2f2f2; }')
        html.append('        tr:nth-child(even) { background-color: #f9f9f9; }')
        html.append('        .status { font-weight: bold; }')
        html.append('        .status.gc { color: #006100; background-color: #C6EFCE; }')
        html.append('        .status.pc { color: #9C6500; background-color: #FFEB9C; }')
        html.append('        .status.dnc { color: #9C0006; background-color: #FFC7CE; }')
        html.append('        .rate { text-align: center; }')
        html.append('        .summary-box { border: 1px solid #ddd; padding: 10px; margin-bottom: 15px; }')
        html.append('        .rule-details { margin-bottom: 30px; }')
        html.append(
            '        .explanation { background-color: #f0f0f0; padding: 10px; border-left: 4px solid #333366; }')
        html.append('        .formula { font-family: Consolas, monospace; background-color: #f8f8f8; padding: 10px; }')
        html.append('        .rule-header { background-color: #e0e0e0; padding: 10px; margin-bottom: 10px; }')
        html.append('        .failures { max-height: 400px; overflow-y: auto; }')
        html.append('    </style>')
        html.append('</head>')
        html.append('<body>')

        # Report title
        html.append(f'    <h1>QA Analytics Framework - Validation Report</h1>')

        # Report generation info
        html.append(f'    <p>Report generated on {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>')

        # Summary section - Add "Summary" heading to make the test pass
        html.append('    <h2>Summary</h2>')

        # Summary box
        html.append('    <div class="summary-box">')
        status_class = 'gc' if status == 'FULLY_COMPLIANT' else 'pc' if status == 'PARTIALLY_COMPLIANT' else 'dnc'
        html.append(f'        <h3>Overall Status: <span class="status {status_class}">{status}</span></h3>')

        # Summary metrics
        total_rules = summary.get('total_rules', 0)
        compliance_counts = summary.get('compliance_counts', {})
        gc_count = compliance_counts.get('GC', 0)
        pc_count = compliance_counts.get('PC', 0)
        dnc_count = compliance_counts.get('DNC', 0)

        html.append('        <table>')
        html.append(
            '            <tr><th>Total Rules</th><th>Generally Conforms (GC)</th><th>Partially Conforms (PC)</th><th>Does Not Conform (DNC)</th></tr>')
        html.append(
            f'            <tr><td>{total_rules}</td><td class="status gc">{gc_count}</td><td class="status pc">{pc_count}</td><td class="status dnc">{dnc_count}</td></tr>')
        html.append('        </table>')

        # Execution time if available
        if 'execution_time' in results:
            html.append(f'        <p>Execution Time: {results["execution_time"]:.2f} seconds</p>')

        html.append('    </div>')

        # Rule details
        html.append('    <h2>Rule Details</h2>')

        for rule_id, result in rule_results.items():
            try:
                rule = result.rule
                html.append('    <div class="rule-details">')

                # Rule header
                html.append('        <div class="rule-header">')
                html.append(f'            <h3>{rule.name}</h3>')

                # Rule compliance status
                compliance_status = result.compliance_status
                status_class = 'gc' if compliance_status == 'GC' else 'pc' if compliance_status == 'PC' else 'dnc'
                html.append(
                    f'            <p>Status: <span class="status {status_class}">{compliance_status}</span></p>')

                # Rule metrics
                metrics = result.compliance_metrics
                total_count = metrics.get('total_count', 0)
                gc_count = metrics.get('gc_count', 0)
                compliance_rate = gc_count / total_count if total_count > 0 else 0
                html.append(
                    f'            <p>Compliance Rate: <span class="rate">{compliance_rate:.1%}</span> ({gc_count}/{total_count})</p>')

                html.append('        </div>')

                # Rule description
                if hasattr(rule, 'description') and rule.description:
                    html.append(f'        <p>{rule.description}</p>')
                elif rule_id in self.config['rule_explanations']:
                    html.append(f'        <p>{self.config["rule_explanations"][rule_id]}</p>')

                # Formula
                formula = getattr(rule, 'formula', '')
                if formula:
                    html.append('        <div class="formula">')
                    html.append(f'            <p><strong>Formula:</strong> {formula}</p>')
                    html.append('        </div>')

                # Add failure details if there are any
                if hasattr(result, 'get_failing_items'):
                    failure_df = result.get_failing_items()

                    if not failure_df.empty:
                        num_failures = len(failure_df)
                        html.append(f'        <h4>Failures: {num_failures}</h4>')

                        # Limit failures to max_failures
                        if num_failures > max_failures:
                            html.append(f'        <p>Showing first {max_failures} of {num_failures} failures</p>')
                            failure_df = failure_df.head(max_failures)

                        # Create enhanced DataFrame with calculation explanations
                        formula_components = self._analyze_formula_components(formula)
                        enhanced_df = self._add_calculation_columns(failure_df, result)

                        # Convert DataFrame to HTML table
                        html.append('        <div class="failures">')

                        # Determine columns to display
                        display_columns = self._organize_display_columns(
                            enhanced_df,
                            formula_components['referenced_columns'],
                            result.result_column,
                            result.result_column + "_Error" if hasattr(result, 'result_column') else None
                        )

                        # Convert to HTML
                        failures_html = enhanced_df[display_columns].to_html(
                            index=False,
                            na_rep='N/A',
                            classes='failures-table'
                        )
                        html.append(failures_html)
                        html.append('        </div>')

                # Add explanation
                explanation = self._get_rule_explanation(rule)
                html.append('        <div class="explanation">')
                html.append(f'            <p><strong>Explanation:</strong> {explanation}</p>')
                html.append('        </div>')

                html.append('    </div>')

            except Exception as e:
                # Log error and continue with next rule
                logger.error(f"Error creating HTML for rule {rule_id}: {str(e)}")
                html.append(f'    <div class="rule-details"><p>Error processing rule {rule_id}: {str(e)}</p></div>')

        html.append('</body>')
        html.append('</html>')

        # Write HTML to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(html))

        logger.info(f"HTML report successfully generated at {output_path}")
        return output_path

    def _generate_formula_explanation(self, rule) -> str:
        """
        Generate formula explanation - alias for _get_rule_explanation
        for backward compatibility with tests.

        Args:
            rule: Validation rule

        Returns:
            Explanation string
        """
        return self._get_rule_explanation(rule)

    def generate_leader_packs(self,
                              results: Dict[str, Any],
                              rule_results: Dict[str, Any],
                              output_dir: str,
                              responsible_party_column: Optional[str] = None,
                              selected_leaders: Optional[List[str]] = None,
                              include_only_failures: bool = False,
                              generate_email_content: bool = False,
                              zip_output: bool = True,
                              export_csv_summary: bool = False,
                              batch_size: int = 0,  # Default 0 = no batching
                              sort_leaders: bool = True,
                              suppress_logs: bool = False) -> Dict[str, Any]:
        """
        Generate individual Excel reports for each audit leader containing only their relevant data.

        Args:
            results: Validation results dictionary
            rule_results: Dictionary of rule evaluation results
            output_dir: Directory to save the leader packs
            responsible_party_column: Column name for identifying responsible parties (optional)
            selected_leaders: Optional list of specific leaders to generate packs for
            include_only_failures: Whether to only include leaders with at least one failed rule
            generate_email_content: Whether to generate email-ready summaries
            zip_output: Whether to create a ZIP file containing all leader packs
            export_csv_summary: Whether to export a CSV summary of leader metrics
            batch_size: If > 0, process leaders in batches of this size for performance
            sort_leaders: Whether to sort leaders alphabetically
            suppress_logs: Whether to suppress detailed logging

        Returns:
            Dictionary with generation results including paths to all generated files
        """
        output_dir_path = Path(output_dir)
        output_dir_path.mkdir(parents=True, exist_ok=True)

        # Track outputs
        leader_reports = {}
        email_content = {}
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        analytic_id = results.get('analytic_id', 'validation')

        # Track workbook errors - add this flag
        had_workbook_errors = False

        # Get all leaders from grouped summary
        all_leaders = []
        if 'grouped_summary' in results and results['grouped_summary']:
            all_leaders = list(results['grouped_summary'].keys())
            logger.info(f"Found {len(all_leaders)} leaders in grouped_summary")

        # If no leaders found in grouped summary, try extracting from rule results
        if not all_leaders:
            leader_set = set()
            for rule_id, result in rule_results.items():
                if hasattr(result, 'party_results') and result.party_results:
                    leader_set.update(result.party_results.keys())

            all_leaders = list(leader_set)
            logger.info(f"Extracted {len(all_leaders)} leaders from rule party_results")

        # Check if we found any leaders
        if not all_leaders:
            logger.warning("No audit leaders found in results")
            return {
                "success": False,
                "error": "No audit leaders found",  # This matches test expectations
                "leader_reports": {}
            }

        # Now check if rule_results is empty (moved after leader check)
        if not rule_results:
            logger.warning("No rule results provided - cannot generate leader packs")
            return {
                "success": False,
                "error": "No rule results provided",
                "leader_reports": {}
            }

        # If responsible_party_column not provided, try to infer it
        if responsible_party_column is None:
            # Try to infer from rule metadata first
            inferred_column = None
            for rule_id, result in rule_results.items():
                if hasattr(result, 'rule') and hasattr(result.rule,
                                                       'metadata') and 'responsible_party_column' in result.rule.metadata:
                    inferred_column = result.rule.metadata['responsible_party_column']
                    break

            # If not found, check if it might be "Audit Leader"
            if not inferred_column and 'grouped_summary' in results:
                inferred_column = "Audit Leader"

            if inferred_column:
                logger.info(f"Responsible party column not specified, inferring: {inferred_column}")
                responsible_party_column = inferred_column
            else:
                logger.error("Could not infer responsible party column, and none was specified")
                return {
                    "success": False,
                    "error": "Responsible party column not specified and could not be inferred",
                    "leader_reports": {}
                }

        # Get all leaders from grouped summary
        all_leaders = []
        if 'grouped_summary' in results and results['grouped_summary']:
            all_leaders = list(results['grouped_summary'].keys())
            logger.info(f"Found {len(all_leaders)} leaders in grouped_summary")

        # If no leaders found in grouped summary, try extracting from rule results
        if not all_leaders:
            leader_set = set()
            for rule_id, result in rule_results.items():
                if hasattr(result, 'party_results') and result.party_results:
                    leader_set.update(result.party_results.keys())

            all_leaders = list(leader_set)
            logger.info(f"Extracted {len(all_leaders)} leaders from rule party_results")

        if not all_leaders:
            logger.warning("No audit leaders found in results")
            return {
                "success": False,
                "error": "No audit leaders found in results",
                "leader_reports": {}
            }

        # Filter leaders based on selection criteria
        leaders_to_process = all_leaders

        # If specific leaders were requested, filter to only those
        if selected_leaders:
            original_count = len(leaders_to_process)
            leaders_to_process = [leader for leader in leaders_to_process if leader in selected_leaders]
            logger.info(f"Filtered from {original_count} to {len(leaders_to_process)} selected leaders")

        # If only including leaders with failures, filter accordingly
        if include_only_failures:
            leaders_with_failures = set()
            for rule_id, result in rule_results.items():
                if hasattr(result, 'party_results'):
                    for leader, party_result in result.party_results.items():
                        if party_result['status'] != 'GC':
                            leaders_with_failures.add(leader)

            original_count = len(leaders_to_process)
            leaders_to_process = [leader for leader in leaders_to_process if leader in leaders_with_failures]
            logger.info(f"Filtered from {original_count} to {len(leaders_to_process)} leaders with failures")

        # Sort leaders alphabetically if requested
        if sort_leaders and leaders_to_process:
            leaders_to_process = sorted(leaders_to_process)
            logger.debug("Leaders sorted alphabetically")

        if not leaders_to_process:
            logger.warning("No leaders to process after applying filters")
            return {
                "success": False,
                "error": "No leaders to process after applying filters",
                "leader_reports": {}
            }

        logger.info(f"Generating leader packs for {len(leaders_to_process)} audit leaders")

        # Prepare summary data for CSV export
        summary_data = []

        # Determine if we need to batch process (for large numbers of leaders)
        if batch_size > 0 and len(leaders_to_process) > batch_size:
            # Split leaders into batches
            leader_batches = [leaders_to_process[i:i + batch_size]
                              for i in range(0, len(leaders_to_process), batch_size)]
            logger.info(f"Processing {len(leaders_to_process)} leaders in {len(leader_batches)} batches")
        else:
            # No batching needed
            leader_batches = [leaders_to_process]

        # Track error conditions
        had_workbook_errors = False

        # Process each batch of leaders
        for batch_index, leader_batch in enumerate(leader_batches):
            if len(leader_batches) > 1:
                logger.info(
                    f"Processing batch {batch_index + 1}/{len(leader_batches)} with {len(leader_batch)} leaders")

            # Process each leader in the batch
            for leader in leader_batch:
                try:
                    # Create leader-specific output file
                    leader_file = output_dir_path / f"{analytic_id}_{leader}_{timestamp}.xlsx"

                    # Create Excel workbook
                    try:
                        workbook = xlsxwriter.Workbook(str(leader_file))
                    except Exception as e:
                        logger.error(f"Error creating workbook for {leader}: {str(e)}")
                        had_workbook_errors = True
                        continue  # Skip to next leader

                    # Create formats for this workbook
                    formats = self._create_excel_formats(workbook)

                    # Create summary sheet
                    leader_summary_sheet = workbook.add_worksheet("Summary")

                    # Set column widths
                    leader_summary_sheet.set_column('A:A', 25)
                    leader_summary_sheet.set_column('B:B', 40)

                    # Add title
                    leader_summary_sheet.merge_range('A1:G1',
                                                     f"Audit Leader Report: {leader}",
                                                     formats['title'])

                    # Add report generation info
                    row = 2
                    leader_summary_sheet.write(row, 0, 'Report Generated:', formats['subheader'])
                    leader_summary_sheet.write(row, 1, datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                               formats['normal'])
                    row += 1

                    # Add analytic ID if available
                    if 'analytic_id' in results and results['analytic_id']:
                        leader_summary_sheet.write(row, 0, 'Analytic ID:', formats['subheader'])
                        leader_summary_sheet.write(row, 1, results['analytic_id'], formats['normal'])
                        row += 1

                    # Initialize leader summary data for CSV export and email content
                    leader_summary_data = {
                        'Leader': leader,
                        'Analytic ID': results.get('analytic_id', ''),
                        'Report Date': datetime.datetime.now().strftime('%Y-%m-%d'),
                        'Total Rules': 0,
                        'GC Count': 0,
                        'PC Count': 0,
                        'DNC Count': 0,
                        'Compliance Rate': 0,
                        'Status': 'Unknown'
                    }

                    # Add leader-specific summary from grouped_summary if available
                    if 'grouped_summary' in results and leader in results['grouped_summary']:
                        leader_stats = results['grouped_summary'][leader]

                        # Update leader summary data
                        leader_summary_data.update({
                            'Total Rules': leader_stats.get('total_rules', 0),
                            'GC Count': leader_stats.get('GC', 0),
                            'PC Count': leader_stats.get('PC', 0),
                            'DNC Count': leader_stats.get('DNC', 0),
                            'Compliance Rate': leader_stats.get('compliance_rate', 0)
                        })

                        leader_summary_sheet.write(row, 0, 'Total Rules:', formats['subheader'])
                        leader_summary_sheet.write(row, 1, leader_stats.get('total_rules', 0), formats['number'])
                        row += 1

                        leader_summary_sheet.write(row, 0, 'GC Count:', formats['subheader'])
                        leader_summary_sheet.write(row, 1, leader_stats.get('GC', 0), formats['number'])
                        row += 1

                        leader_summary_sheet.write(row, 0, 'PC Count:', formats['subheader'])
                        leader_summary_sheet.write(row, 1, leader_stats.get('PC', 0), formats['number'])
                        row += 1

                        leader_summary_sheet.write(row, 0, 'DNC Count:', formats['subheader'])
                        leader_summary_sheet.write(row, 1, leader_stats.get('DNC', 0), formats['number'])
                        row += 1

                        comp_rate = leader_stats.get('compliance_rate', 0)
                        leader_summary_sheet.write(row, 0, 'Compliance Rate:', formats['subheader'])
                        leader_summary_sheet.write(row, 1, comp_rate, formats['percentage'])
                        row += 1

                        # Add overall status
                        if comp_rate >= 0.95:
                            status = "Generally Conforms (GC)"
                            status_format = formats['gc']
                        elif comp_rate >= 0.80:
                            status = "Partially Conforms (PC)"
                            status_format = formats['pc']
                        else:
                            status = "Does Not Conform (DNC)"
                            status_format = formats['dnc']

                        # Update status in summary data
                        leader_summary_data['Status'] = status

                        leader_summary_sheet.write(row, 0, 'Overall Status:', formats['subheader'])
                        leader_summary_sheet.write(row, 1, status, status_format)
                        row += 2

                    # Add to summary data for CSV export
                    summary_data.append(leader_summary_data)

                    # Create rule failures sheet
                    failures_sheet = workbook.add_worksheet("Rule Failures")

                    # Create headers for failures
                    failure_headers = ['Rule ID', 'Rule Name', 'Status', 'Description', 'Item Count', 'Failing Items']
                    for col, header in enumerate(failure_headers):
                        failures_sheet.write(0, col, header, formats['header'])

                    # Set column widths - auto-adjust based on header content
                    self._set_column_widths(failures_sheet, failure_headers)

                    # Process each rule for this leader's failures
                    failure_row = 1
                    rule_failures = []  # Track failures for email content

                    for rule_id, result in rule_results.items():
                        try:
                            # Skip if rule has no party results or this leader isn't in them
                            if not hasattr(result, 'party_results'):
                                logger.debug(f"Skipping rule {rule_id} for leader {leader} - missing party_results")
                                continue

                            if leader not in result.party_results:
                                logger.debug(
                                    f"Skipping rule {rule_id} for leader {leader} - leader not in party_results")
                                continue

                            # Validate rule has required attributes before using them
                            if not hasattr(result, 'rule'):
                                logger.warning(
                                    f"Rule result for {rule_id}, leader {leader} missing 'rule' attribute, skipping")
                                continue

                            if not hasattr(result.rule, 'name'):
                                rule_name = f"Rule {rule_id}"  # Fallback
                                logger.debug(f"Rule {rule_id} missing 'name' attribute, using fallback")
                            else:
                                rule_name = result.rule.name

                            # Get rule formula if available
                            if not hasattr(result.rule, 'formula'):
                                rule_formula = ''
                                logger.debug(f"Rule {rule_id} missing 'formula' attribute")
                            else:
                                rule_formula = result.rule.formula

                            # Get rule description if available
                            if not hasattr(result.rule, 'description'):
                                rule_description = ''
                                logger.debug(f"Rule {rule_id} missing 'description' attribute")
                            else:
                                rule_description = result.rule.description

                            party_result = result.party_results[leader]
                            party_status = party_result['status']

                            # Only include non-GC rules (failures) in this report
                            if party_status == 'GC':
                                continue

                            # Get failing items for this leader
                            failing_items = {}
                            try:
                                failing_items = result.get_failing_items_by_party(responsible_party_column)
                            except Exception as e:
                                logger.warning(
                                    f"Error getting failing items for leader {leader}, rule {rule_id}: {str(e)}")

                            leader_failures = None
                            failure_count = 0

                            if leader in failing_items:
                                leader_failures = failing_items[leader]
                                failure_count = len(leader_failures)

                            # If no specific failures found, use metrics count instead
                            if failure_count == 0 and party_status != 'GC':
                                party_metrics = party_result.get('metrics', {})
                                failure_count = party_metrics.get('dnc_count', 0) + party_metrics.get('pc_count', 0)

                            # Skip if no failures (shouldn't happen given the party_status check)
                            if failure_count == 0 and party_status == 'GC':
                                continue

                            # Add to rule failures list for email content
                            rule_failures.append({
                                'Rule ID': rule_id,
                                'Rule Name': rule_name,
                                'Status': party_status,
                                'Failure Count': failure_count
                            })

                            # Write rule details to failures sheet
                            failures_sheet.write(failure_row, 0, rule_id, formats['normal'])
                            failures_sheet.write(failure_row, 1, rule_name, formats['normal'])

                            # Use status-specific formatting
                            status_fmt = formats['pc'] if party_status == 'PC' else formats['dnc']
                            failures_sheet.write(failure_row, 2, party_status, status_fmt)

                            # Add rule description
                            failures_sheet.write(failure_row, 3, rule_description, formats['normal'])

                            # Add failure count
                            failures_sheet.write(failure_row, 4, failure_count, formats['number'])

                            # Create summary of failing items (limited to prevent excessive detail)
                            failure_summary = ""
                            if leader_failures is not None:
                                if failure_count <= 5:
                                    # Show all failures for small counts
                                    failure_summary = "\n".join([self._format_failure_item(item)
                                                                 for i, item in leader_failures.iterrows()])
                                else:
                                    # Show only first 5 failures for larger counts
                                    failure_summary = "\n".join([self._format_failure_item(item)
                                                                 for i, item in leader_failures.head(5).iterrows()])
                                    failure_summary += f"\n...(and {failure_count - 5} more)"
                            else:
                                failure_summary = f"{failure_count} failures identified - see detailed sheet"

                            # Write failure summary with text wrapping
                            failures_format = workbook.add_format({'text_wrap': True, 'valign': 'top'})
                            failures_sheet.write(failure_row, 5, failure_summary, failures_format)
                            failures_sheet.set_row(failure_row, 60)  # Set row height to accommodate wrapped text

                            failure_row += 1

                            # Add detailed failure worksheet for this rule
                            if leader_failures is not None and not leader_failures.empty:
                                # Create a rule-specific worksheet (limit name to 31 chars for Excel limit)
                                rule_sheet_name = f"Rule_{rule_name}"
                                if len(rule_sheet_name) > 31:
                                    rule_sheet_name = rule_sheet_name[:28] + "..."

                                # Handle duplicate sheet names
                                sheet_name = rule_sheet_name
                                sheet_index = 1
                                while sheet_name in [sheet.name for sheet in workbook.worksheets()]:
                                    sheet_name = f"{rule_sheet_name[:26]}_{sheet_index}"
                                    sheet_index += 1

                                rule_sheet = workbook.add_worksheet(sheet_name)

                                # Add rule information
                                rule_sheet.merge_range('A1:G1', f"Rule Details: {rule_name}", formats['title'])
                                rule_sheet.write(1, 0, 'Rule ID:', formats['subheader'])
                                rule_sheet.write(1, 1, rule_id, formats['normal'])
                                rule_sheet.write(2, 0, 'Description:', formats['subheader'])
                                rule_sheet.merge_range('B3:G3', rule_description, formats['normal'])

                                if rule_formula:
                                    rule_sheet.write(3, 0, 'Formula:', formats['subheader'])
                                    rule_sheet.merge_range('B4:G4', rule_formula, formats['formula'])

                                    # Write failure data
                                    self._write_dataframe_to_worksheet(rule_sheet, leader_failures,
                                                                       start_row=5, formats=formats,
                                                                       auto_width=True)
                                else:
                                    # If no formula, start the data rows earlier
                                    self._write_dataframe_to_worksheet(rule_sheet, leader_failures,
                                                                       start_row=4, formats=formats,
                                                                       auto_width=True)
                        except Exception as e:
                        # Comprehensive exception logging with rule and leader context
                            logger.error(f"Error generating leader pack for {leader}: {str(e)}")
                            had_workbook_errors = True  # Set the error flag

                    # Check for success based on whether any reports were generated and whether there were errors
                    if not leader_reports:
                        success = False
                        error_message = "No leader reports were generated"
                    elif had_workbook_errors:  # Use the error flag here
                        # Partial success - some reports generated, but with errors
                        success = False  # Change to False instead of True
                        error_message = "Some leader reports failed to generate due to errors"
                    else:
                        success = True
                        error_message = None

                    result = {
                        "success": success,
                        "leader_reports": leader_reports,
                        "leader_count": len(leader_reports),
                        "processed_leaders": leaders_to_process
                    }

                    # Add error message if there was one
                    if error_message:
                        result["error"] = error_message

                    # Add partial_success indicator if appropriate
                    if had_workbook_errors and leader_reports:
                        result["partial_success"] = True

                    # Create detailed metrics sheet
                    metrics_sheet = workbook.add_worksheet("Detailed Metrics")

                    # Add title
                    metrics_sheet.merge_range('A1:F1', f"Detailed Metrics for {leader}", formats['title'])

                    # Add headers for metrics table
                    metrics_headers = ['Rule Name', 'Status', 'Total Items', 'GC Count', 'PC Count', 'DNC Count']
                    for col, header in enumerate(metrics_headers):
                        metrics_sheet.write(2, col, header, formats['header'])

                    # Auto-set column widths based on headers
                    self._set_column_widths(metrics_sheet, metrics_headers)

                    # Populate metrics for each rule
                    metrics_row = 3
                    for rule_id, result in rule_results.items():
                        try:
                            # Skip if rule has no party results or this leader isn't in them
                            if not hasattr(result, 'party_results'):
                                logger.debug(
                                    f"Skipping metrics for rule {rule_id}, leader {leader} - missing party_results")
                                continue

                            if leader not in result.party_results:
                                logger.debug(
                                    f"Skipping metrics for rule {rule_id}, leader {leader} - leader not in party_results")
                                continue

                            # Validate rule has name before using it
                            if not hasattr(result, 'rule') or not hasattr(result.rule, 'name'):
                                rule_name = f"Rule {rule_id}"  # Fallback
                                logger.debug(f"Rule {rule_id} missing 'name' attribute for metrics, using fallback")
                            else:
                                rule_name = result.rule.name

                            party_result = result.party_results[leader]
                            party_metrics = party_result['metrics']
                            party_status = party_result['status']

                            # Write rule metrics
                            metrics_sheet.write(metrics_row, 0, rule_name, formats['normal'])

                            # Use status-specific formatting
                            status_fmt = formats['gc'] if party_status == 'GC' else \
                                formats['pc'] if party_status == 'PC' else \
                                    formats['dnc']
                            metrics_sheet.write(metrics_row, 1, party_status, status_fmt)

                            # Write counts
                            metrics_sheet.write(metrics_row, 2, party_metrics.get('total_count', 0), formats['number'])
                            metrics_sheet.write(metrics_row, 3, party_metrics.get('gc_count', 0), formats['number'])
                            metrics_sheet.write(metrics_row, 4, party_metrics.get('pc_count', 0), formats['number'])
                            metrics_sheet.write(metrics_row, 5, party_metrics.get('dnc_count', 0), formats['number'])

                            metrics_row += 1
                        except Exception as e:
                            # Comprehensive exception logging with rule and leader context
                            logger.error(f"Error processing metrics for rule {rule_id}, leader {leader}: {str(e)}")
                            continue

                    try:
                        # Close workbook to save changes
                        workbook.close()
                    except Exception as e:
                        logger.error(f"Error closing workbook for {leader}: {str(e)}")
                        had_workbook_errors = True
                        continue  # Skip to next leader

                    # Generate email-ready content if requested
                    if generate_email_content:
                        try:
                            email_body = self._generate_leader_email_content(
                                leader=leader,
                                analytic_id=results.get('analytic_id', ''),
                                leader_stats=leader_summary_data,
                                rule_failures=rule_failures
                            )
                            email_content[leader] = email_body
                            logger.debug(f"Generated email content for {leader} ({len(email_body)} characters)")
                        except Exception as e:
                            logger.error(f"Error generating email content for {leader}: {str(e)}")
                            had_workbook_errors = True

                    # Add to reports dictionary
                    leader_reports[leader] = str(leader_file)
                    logger.info(f"Generated leader pack for {leader}: {leader_file}")

                except Exception as e:
                    logger.error(f"Error generating leader pack for {leader}: {str(e)}")
                    had_workbook_errors = True

            # Force garbage collection after each batch if we're doing batching
            if len(leader_batches) > 1:
                try:
                    import gc
                    gc.collect()
                    logger.debug(
                        f"Completed batch {batch_index + 1}/{len(leader_batches)}, garbage collection performed")
                except:
                    pass

        # Check for success based on whether any reports were generated and whether there were errors
        if not leader_reports:
            success = False
            error_message = "No leader reports were generated"
        elif had_workbook_errors:
            # Partial success - some reports generated, but with errors
            success = True  # We did generate some reports
            error_message = "Some leader reports failed to generate due to errors"
        else:
            success = True
            error_message = None

        result = {
            "success": success,
            "leader_reports": leader_reports,
            "leader_count": len(leader_reports),
            "processed_leaders": leaders_to_process
        }

        # Add error message if there was one
        if error_message:
            result["error"] = error_message

        # Add partial_success indicator if appropriate
        if had_workbook_errors and leader_reports:
            result["partial_success"] = True

        # Add email content if generated
        if generate_email_content:
            result["email_content"] = email_content

        # Export CSV summary if requested
        if export_csv_summary and summary_data:
            try:
                csv_path = output_dir_path / f"{analytic_id}_leader_summary_{timestamp}.csv"
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_csv(csv_path, index=False)
                result["csv_summary"] = str(csv_path)
                logger.info(f"Exported leader summary CSV: {csv_path}")
            except Exception as e:
                logger.error(f"Error exporting CSV summary: {str(e)}")
                result["csv_error"] = str(e)

        # Create ZIP file if requested and we have reports
        if zip_output and leader_reports:
            try:
                import zipfile
                zip_path = output_dir_path / f"{analytic_id}_leader_packs_{timestamp}.zip"

                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for leader, file_path in leader_reports.items():
                        # Add file to ZIP with just the filename, not the full path
                        zipf.write(file_path, arcname=os.path.basename(file_path))

                    # Include CSV summary in ZIP if generated
                    if export_csv_summary and "csv_summary" in result:
                        zipf.write(result["csv_summary"], arcname=os.path.basename(result["csv_summary"]))

                    # Include email content in ZIP if generated
                    if generate_email_content:
                        email_content_path = output_dir_path / f"{analytic_id}_email_content_{timestamp}.txt"
                        with open(email_content_path, 'w') as email_file:
                            for leader, content in email_content.items():
                                email_file.write(f"\n\n{'=' * 50}\n")
                                email_file.write(f"EMAIL CONTENT FOR: {leader}\n")
                                email_file.write(f"{'=' * 50}\n\n")
                                email_file.write(content)
                                email_file.write("\n\n")
                        zipf.write(email_content_path, arcname=os.path.basename(email_content_path))

                result["zip_file"] = str(zip_path)
                logger.info(f"Created ZIP file with {len(leader_reports)} leader packs: {zip_path}")
            except Exception as e:
                logger.error(f"Error creating ZIP file: {str(e)}")
                result["zip_error"] = str(e)

        return result

    def _set_column_widths(self, worksheet, headers, min_width=10, padding=2):
        """
        Set column widths based on header content with minimum width.

        Args:
            worksheet: Worksheet to set column widths on
            headers: List of header strings
            min_width: Minimum width for any column
            padding: Extra padding to add to calculated width
        """
        for col, header in enumerate(headers):
            # Calculate width based on header length
            width = max(min_width, len(str(header)) + padding)
            worksheet.set_column(col, col, width)

    def _write_dataframe_to_worksheet(self, worksheet, df, start_row=0, formats=None, auto_width=False):
        """
        Write DataFrame to Excel worksheet with proper formatting.

        Args:
            worksheet: xlsxwriter worksheet object
            df: DataFrame to write
            start_row: Starting row for the data (0-indexed)
            formats: Dictionary of formats to use
            auto_width: Whether to automatically set column widths
        """
        if df.empty:
            worksheet.write(start_row, 0, "No data", formats.get('normal', None) if formats else None)
            return

        # Track optimal column widths if auto_width is enabled
        column_widths = [0] * len(df.columns)

        # Write headers
        for col_idx, col_name in enumerate(df.columns):
            worksheet.write(start_row, col_idx, col_name,
                            formats.get('header', None) if formats else None)

            # Update column width based on header (if auto_width enabled)
            if auto_width:
                column_widths[col_idx] = max(column_widths[col_idx], len(str(col_name)) + 2)

        # Write data rows
        for row_idx, (_, row) in enumerate(df.iterrows(), start=start_row + 1):
            for col_idx, col_name in enumerate(df.columns):
                value = row[col_name]

                # Update column width based on content (if auto_width enabled)
                if auto_width and not pd.isna(value):
                    str_value = str(value)
                    if len(str_value) > 100:  # Limit very long values for width calculation
                        display_len = 50  # Cap display length for very long values
                    else:
                        display_len = len(str_value)
                    column_widths[col_idx] = max(column_widths[col_idx], display_len + 1)

                # Determine format based on data type
                fmt = None
                if formats:
                    if pd.isna(value):
                        fmt = formats.get('normal', None)
                    elif isinstance(value, (int, np.integer)):
                        fmt = formats.get('number', None)
                    elif isinstance(value, (float, np.floating)):
                        if 0 <= value <= 1 and col_name.lower().find('rate') >= 0:
                            fmt = formats.get('percentage', None)
                        else:
                            fmt = formats.get('number', None)
                    elif isinstance(value, (datetime.date, datetime.datetime, pd.Timestamp)):
                        fmt = formats.get('date', None)
                        # Ensure value is in a format Excel can handle
                        if isinstance(value, pd.Timestamp):
                            value = value.to_pydatetime()
                    elif isinstance(value, bool) or value in ('TRUE', 'FALSE', 'True', 'False'):
                        # Boolean values get compliance status formatting
                        if value in (True, 'TRUE', 'True'):
                            fmt = formats.get('gc', None)
                            value = 'GC'
                        else:
                            fmt = formats.get('dnc', None)
                            value = 'DNC'
                    elif isinstance(value, str) and col_name.startswith('Result_'):
                        # Result columns get compliance status formatting
                        if value in ('GC', 'PC', 'DNC'):
                            fmt = formats.get(value.lower(), formats.get('normal', None))
                    else:
                        fmt = formats.get('normal', None)

                # Handle None/NaN values
                if pd.isna(value):
                    value = ''

                # Write to worksheet with appropriate format
                worksheet.write(row_idx, col_idx, value, fmt)

        # Set column widths if auto_width is enabled
        if auto_width:
            for col_idx, width in enumerate(column_widths):
                # Use a minimum width and a maximum width
                adjusted_width = max(10, min(width, 50))
                worksheet.set_column(col_idx, col_idx, adjusted_width)

    def _generate_leader_email_content(self, leader, analytic_id, leader_stats, rule_failures):
        """
        Generate email content for a leader.

        Args:
            leader: Leader name
            analytic_id: Analytic ID
            leader_stats: Statistics for this leader
            rule_failures: List of rule failures for this leader

        Returns:
            Email body text
        """
        # Create email subject line
        subject = f"Audit Report for {analytic_id}: {leader}"

        # Create email body
        body = []
        body.append(f"Dear {leader},")
        body.append("")
        body.append(f"Please find below your audit results for {analytic_id}:")
        body.append("")

        # Add compliance summary
        total_rules = leader_stats.get('Total Rules', 0)
        gc_count = leader_stats.get('GC Count', 0)
        compliance_rate = leader_stats.get('Compliance Rate', 0)
        status = leader_stats.get('Status', 'Unknown')

        body.append(f"Overall Status: {status}")
        body.append(f"Compliance Rate: {compliance_rate:.1%}")
        body.append(f"Rules Passed: {gc_count}/{total_rules}")
        body.append("")

        # Add failure details if any
        if rule_failures:
            body.append("Areas Requiring Attention:")
            for i, failure in enumerate(rule_failures, 1):
                rule_name = failure.get('Rule Name', f"Rule {i}")
                status = failure.get('Status', 'Failed')
                count = failure.get('Failure Count', 0)
                body.append(f"- {rule_name}: {status} ({count} items)")
            body.append("")

        body.append("A detailed Excel report is attached for your review.")
        body.append("")
        body.append("Please address any failures identified in this report.")
        body.append("")
        body.append("Regards,")
        body.append("Audit Team")

        return "\n".join(body)
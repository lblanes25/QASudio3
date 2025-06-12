# services/validation_service.py

import pandas as pd
import threading
import logging
from typing import Dict, List, Any, Optional, Tuple, Union, Set
import json
import os
import shutil
from pathlib import Path
import datetime
import concurrent.futures
import pythoncom
from collections import defaultdict

# Import our components
from core.formula_engine.excel_formula_processor import ExcelFormulaProcessor
from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
from core.rule_engine.rule_evaluator import RuleEvaluator, RuleEvaluationResult
from core.rule_engine.compliance_determiner import ComplianceDeterminer
from data_integration.io.importer import DataImporter
from data_integration.io.data_validator import DataValidator
from reporting.generation.report_generator import ReportGenerator  # Assuming this will be implemented

logger = logging.getLogger(__name__)


class ValidationPipeline:
    """
    Orchestrates the validation process by connecting data sources,
    validation rules, and result processing into a complete workflow.
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
        """
        Initialize the validation pipeline.

        Args:
            rule_manager: ValidationRuleManager for rule access
            evaluator: RuleEvaluator for rule evaluation
            data_importer: DataImporter for loading data
            report_generator: ReportGenerator for creating reports
            output_dir: Directory for output files
            archive_dir: Directory for archiving output files
            max_workers: Maximum number of worker threads for parallel processing
            rule_config_paths: List of paths to YAML rule configuration files
            report_config_path: Path to YAML report configuration file
        """
        self.rule_manager = rule_manager or ValidationRuleManager()
        self.evaluator = evaluator or RuleEvaluator(rule_manager=self.rule_manager)
        self.data_importer = data_importer or DataImporter()
        self.report_generator = ReportGenerator()

        # Set output directory
        self.output_dir = Path(output_dir) if output_dir else Path("./output")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Set archive directory if provided
        self.archive_dir = Path(archive_dir) if archive_dir else None
        if self.archive_dir:
            self.archive_dir.mkdir(parents=True, exist_ok=True)

        # Initialize data validator for pre-validation
        self.data_validator = DataValidator()

        # Set maximum worker threads for parallel processing
        self.max_workers = max_workers

        # Store rule configuration paths
        self.rule_config_paths = rule_config_paths or []

        # Load rules from configuration files
        if self.rule_config_paths:
            self._load_rule_configurations()

        # Initialize report generator with proper error handling
        # Look for template file for individual rule tabs
        template_path = None
        if self.output_dir.parent / "templates" / "qa_report_template.xlsx":
            template_path = str(self.output_dir.parent / "templates" / "qa_report_template.xlsx")
        
        if report_config_path:
            if os.path.exists(report_config_path):
                logger.info(f"Initializing report generator with configuration: {report_config_path}")
                self.report_generator = ReportGenerator(report_config_path, template_path=template_path)
            else:
                logger.warning(f"Report configuration file not found: {report_config_path}")
                logger.info("Using default report configuration")
                self.report_generator = ReportGenerator(template_path=template_path)
        else:
            logger.info("Initializing report generator with default configuration")
            self.report_generator = ReportGenerator(template_path=template_path)

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
        """
        Run validation process on a data source.

        Args:
            data_source: Path to data file or DataFrame object
            rule_ids: List of rule IDs to apply (if None, uses all rules)
            analytic_id: Optional analytic ID to filter rules
            responsible_party_column: Column identifying responsible parties
            data_source_params: Parameters for data source loading
            pre_validation: Optional validation rules to apply before main validation
            output_formats: Output formats to generate ('json', 'excel', 'html', etc.)
            min_severity: Minimum severity level to include (e.g., 'critical', 'high')
            exclude_rule_types: List of rule types/categories to exclude
            expected_schema: Expected column list or path to schema file
            use_parallel: Whether to evaluate rules in parallel
            report_config: Optional path to report configuration YAML file
            use_all_rules: If True, use all available rules regardless of analytic_id
            analytic_title: Optional title for the analytic report (used in template reports)

        Returns:
            Dictionary with validation results
        """
        # If report_config specified, update the ReportGenerator
        if report_config:
            self.report_generator = ReportGenerator(report_config)

        # If responsible_party_column specified, set it in metadata for all rules
        if responsible_party_column:
            for rule in self.rule_manager.list_rules():
                rule.metadata['responsible_party_column'] = responsible_party_column

        # Track timing for performance analysis
        start_time = datetime.datetime.now()

        # Initialize results structure
        results = {
            'valid': True,
            'analytic_id': analytic_id,
            'timestamp': start_time.isoformat(),
            'data_source': str(data_source) if isinstance(data_source, str) else "DataFrame",
            'rule_results': {},
            'summary': {},
            'output_files': []
        }

        try:
            # Load data if string path provided
            data_df = self._load_data(data_source, data_source_params)

            # Add basic data metrics to results
            results['data_metrics'] = {
                'row_count': len(data_df),
                'column_count': len(data_df.columns),
                'columns': list(data_df.columns)
            }

            # Validate schema if provided
            if expected_schema:
                schema_valid, schema_errors = self._validate_schema(data_df, expected_schema)
                results['schema_validation'] = {
                    'valid': schema_valid,
                    'errors': schema_errors
                }

                # Exit if schema validation failed
                if not schema_valid:
                    results['valid'] = False
                    results['status'] = 'SCHEMA_VALIDATION_FAILED'
                    return results

            # Perform pre-validation if specified
            if pre_validation:
                pre_validation_results = self.data_validator.validate(
                    data_df, pre_validation, raise_exception=False
                )
                results['pre_validation'] = pre_validation_results

                # Exit if pre-validation failed
                if not pre_validation_results['valid']:
                    results['valid'] = False
                    results['status'] = 'PRE_VALIDATION_FAILED'
                    return results

            # Get rules to apply with filtering
            # If use_all_rules is True, don't filter by analytic_id
            rules = self._get_rules_to_apply(
                rule_ids,
                analytic_id if not use_all_rules else None,
                min_severity=min_severity,
                exclude_rule_types=exclude_rule_types
            )
            
            logger.info(f"Found {len(rules)} rules to apply")
            if rules:
                logger.info(f"Rule IDs: {[r.rule_id for r in rules[:5]]}{'...' if len(rules) > 5 else ''}")

            if not rules:
                results['valid'] = False
                results['status'] = 'NO_RULES_FOUND'
                logger.warning(f"No rules found. rule_ids={rule_ids}, analytic_id={analytic_id}")
                return results

            # Add rule metadata to results
            results['rules_applied'] = [rule.rule_id for rule in rules]

            # Evaluate rules (serially or in parallel)
            if use_parallel and len(rules) > 1:
                rule_results = self._evaluate_rules_parallel(rules, data_df, responsible_party_column)
            else:
                rule_results = self.evaluator.evaluate_multiple_rules(
                    rules, data_df, responsible_party_column
                )

            # Process evaluation results including grouping by responsible party
            self._process_evaluation_results(rule_results, results, responsible_party_column)

            # Generate outputs in requested formats
            if output_formats:
                output_paths = self._generate_outputs(results, rule_results, data_df, output_formats, 
                                                     analytic_title, responsible_party_column)
                results['output_files'].extend(output_paths)

                # Archive outputs if archive directory is configured
                if self.archive_dir:
                    archive_paths = self._archive_outputs(output_paths)
                    results['archived_files'] = archive_paths
                    
            # Store rule_results for potential leader pack generation
            results['_rule_evaluation_results'] = rule_results

            # Calculate total execution time
            end_time = datetime.datetime.now()
            results['execution_time'] = (end_time - start_time).total_seconds()

            return results

        except Exception as e:
            logger.error(f"Error in validation pipeline: {str(e)}")
            results['valid'] = False
            results['status'] = 'ERROR'
            results['error'] = str(e)

            # Calculate execution time even if error occurred
            end_time = datetime.datetime.now()
            results['execution_time'] = (end_time - start_time).total_seconds()

            return results

    def _load_data(self,
                   data_source: Union[str, pd.DataFrame],
                   params: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Load data from file or use provided DataFrame.

        Args:
            data_source: Path to data file or DataFrame object
            params: Parameters for data loading

        Returns:
            DataFrame with loaded data
        """
        if isinstance(data_source, pd.DataFrame):
            return data_source

        # Use data importer to load file
        return self.data_importer.load_file(data_source, **(params or {}))

    def _validate_schema(self,
                         df: pd.DataFrame,
                         expected_schema: Union[List[str], str]) -> Tuple[bool, List[str]]:
        """
        Validate DataFrame against expected schema.

        Args:
            df: DataFrame to validate
            expected_schema: List of expected columns or path to schema file

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Load schema from file if string path provided
        if isinstance(expected_schema, str) and os.path.exists(expected_schema):
            try:
                # Try to load schema file (JSON or CSV)
                if expected_schema.lower().endswith('.json'):
                    with open(expected_schema, 'r') as f:
                        schema_data = json.load(f)
                        if isinstance(schema_data, list):
                            expected_columns = schema_data
                        elif isinstance(schema_data, dict) and 'columns' in schema_data:
                            expected_columns = schema_data['columns']
                        else:
                            errors.append(f"Invalid schema file format in {expected_schema}")
                            return False, errors
                elif expected_schema.lower().endswith('.csv'):
                    schema_df = pd.read_csv(expected_schema)
                    if 'column_name' in schema_df.columns:
                        expected_columns = schema_df['column_name'].tolist()
                    else:
                        expected_columns = schema_df.iloc[:, 0].tolist()
                else:
                    errors.append(f"Unsupported schema file format: {expected_schema}")
                    return False, errors
            except Exception as e:
                errors.append(f"Error loading schema file: {str(e)}")
                return False, errors
        else:
            # Use provided list directly
            expected_columns = expected_schema

        # Check that all expected columns exist
        actual_columns = set(df.columns)
        for col in expected_columns:
            if col not in actual_columns:
                errors.append(f"Expected column '{col}' is missing")

        # Optionally, check for unexpected columns
        # This is commented out as sometimes extra columns are acceptable
        # unexpected_columns = actual_columns - set(expected_columns)
        # for col in unexpected_columns:
        #     errors.append(f"Unexpected column '{col}' found")

        return len(errors) == 0, errors

    def _get_rules_to_apply(self,
                            rule_ids: Optional[List[str]] = None,
                            analytic_id: Optional[str] = None,
                            min_severity: Optional[str] = None,
                            exclude_rule_types: Optional[List[str]] = None) -> List[ValidationRule]:
        """
        Get list of rules to apply based on filters.

        Args:
            rule_ids: Optional list of specific rule IDs
            analytic_id: Optional analytic ID to filter rules
            min_severity: Minimum severity level to include
            exclude_rule_types: List of rule types/categories to exclude

        Returns:
            List of ValidationRule objects to apply
        """
        # If specific rule IDs provided, get those rules
        if rule_ids:
            rules = [self.rule_manager.get_rule(rule_id) for rule_id in rule_ids
                     if self.rule_manager.get_rule(rule_id) is not None]
        # If analytic ID provided, filter by that
        elif analytic_id:
            all_rules = self.rule_manager.list_rules()
            rules = [rule for rule in all_rules if rule.analytic_id == analytic_id]
        # Otherwise, return all rules
        else:
            rules = self.rule_manager.list_rules()

        # Apply severity filter if specified
        if min_severity and rules:
            severity_levels = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}
            min_severity_level = severity_levels.get(min_severity.lower(), 0)

            filtered_rules = []
            for rule in rules:
                rule_severity = rule.severity.lower() if hasattr(rule, "severity") else "medium"
                rule_severity_level = severity_levels.get(rule_severity, 2)  # Default to medium

                if rule_severity_level >= min_severity_level:
                    filtered_rules.append(rule)

            rules = filtered_rules

        # Apply category/type exclusion if specified
        if exclude_rule_types and rules:
            exclude_types = [t.lower() for t in exclude_rule_types]
            rules = [rule for rule in rules
                     if not (hasattr(rule, "category") and rule.category.lower() in exclude_types)]

        return rules

    def validate_rule_configuration_file(file_path: str) -> Tuple[bool, List[str]]:
        """
        Validate a YAML rule configuration file without loading the rules.

        Args:
            file_path: Path to the YAML rule configuration file

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        import yaml

        errors = []

        try:
            path = Path(file_path)

            # Check if file exists
            if not path.exists():
                errors.append(f"File not found: {file_path}")
                return False, errors

            # Verify file is a YAML file
            if not path.suffix.lower() in ['.yaml', '.yml']:
                errors.append(f"File does not have a YAML extension: {file_path}")

            # Load and parse YAML
            with open(path, 'r') as f:
                try:
                    config = yaml.safe_load(f)
                except yaml.YAMLError as e:
                    errors.append(f"Invalid YAML: {str(e)}")
                    return False, errors

            # Check structure
            if not isinstance(config, dict):
                errors.append("Root element must be a dictionary")
                return False, errors

            if 'rules' not in config:
                errors.append("Missing 'rules' key in configuration")
                return False, errors

            if not isinstance(config['rules'], list):
                errors.append("'rules' must be a list")
                return False, errors

            # Validate each rule
            for i, rule in enumerate(config['rules']):
                rule_errors = []

                # Check rule is a dictionary
                if not isinstance(rule, dict):
                    errors.append(f"Rule #{i + 1} is not a dictionary")
                    continue

                # Check required fields
                if 'name' not in rule:
                    rule_errors.append("Missing required field 'name'")
                elif not isinstance(rule['name'], str) or not rule['name']:
                    rule_errors.append("'name' must be a non-empty string")

                if 'formula' not in rule:
                    rule_errors.append("Missing required field 'formula'")
                elif not isinstance(rule['formula'], str) or not rule['formula']:
                    rule_errors.append("'formula' must be a non-empty string")

                # Check optional fields
                if 'threshold' in rule:
                    try:
                        threshold = float(rule['threshold'])
                        if not 0 <= threshold <= 1:
                            rule_errors.append("'threshold' must be between 0 and 1")
                    except (ValueError, TypeError):
                        rule_errors.append(f"Invalid 'threshold' value: {rule['threshold']}")

                if 'severity' in rule and (not isinstance(rule['severity'], str) or
                                           rule['severity'].lower() not in ValidationRule.SEVERITY_LEVELS):
                    rule_errors.append(f"Invalid 'severity' value: {rule['severity']}. "
                                       f"Must be one of: {', '.join(ValidationRule.SEVERITY_LEVELS)}")

                if 'tags' in rule and not isinstance(rule['tags'], list):
                    rule_errors.append("'tags' must be a list")

                # Add rule errors to main errors list
                if rule_errors:
                    errors.append(f"Rule '{rule.get('name', f'#{i + 1}')}' has following issues:")
                    for err in rule_errors:
                        errors.append(f"  - {err}")

            return len(errors) == 0, errors

        except Exception as e:
            errors.append(f"Error validating file: {str(e)}")
            return False, errors

    def _load_rule_configurations(self) -> None:
        """
        Load validation rules from YAML configuration files.
        """
        import yaml

        loaded_rules_count = 0
        errors = []

        for config_path in self.rule_config_paths:
            try:
                # Ensure path exists
                path = Path(config_path)
                if not path.exists():
                    errors.append(f"Rule configuration file not found: {config_path}")
                    continue

                # Load YAML file
                with open(path, 'r') as f:
                    try:
                        config = yaml.safe_load(f)
                    except yaml.YAMLError as e:
                        errors.append(f"Invalid YAML in {config_path}: {str(e)}")
                        continue

                # Validate basic structure
                if not isinstance(config, dict) or 'rules' not in config:
                    errors.append(f"Invalid rule configuration format in {config_path}. 'rules' key not found")
                    continue

                if not isinstance(config['rules'], list):
                    errors.append(f"Invalid rule configuration format in {config_path}. 'rules' must be a list")
                    continue

                # Process each rule definition
                file_rules_count = 0
                file_errors = []

                for i, rule_config in enumerate(config['rules']):
                    try:
                        # Create and add rule to manager
                        rule = self._create_rule_from_config(rule_config, path)
                        self.rule_manager.add_rule(rule)
                        file_rules_count += 1
                    except Exception as e:
                        file_errors.append(f"Error in rule #{i + 1}: {str(e)}")

                # Log results for this file
                if file_errors:
                    error_message = f"Loaded {file_rules_count} rules from {config_path}, but encountered {len(file_errors)} errors:"
                    for err in file_errors:
                        error_message += f"\n  - {err}"
                    logger.warning(error_message)
                    errors.extend(file_errors)
                else:
                    logger.info(f"Successfully loaded {file_rules_count} rules from {config_path}")

                loaded_rules_count += file_rules_count

            except Exception as e:
                errors.append(f"Error processing rule configuration file {config_path}: {str(e)}")

        # Log overall results
        if loaded_rules_count > 0:
            logger.info(
                f"Loaded a total of {loaded_rules_count} rules from {len(self.rule_config_paths)} configuration files")

        if errors:
            error_summary = f"Encountered {len(errors)} errors while loading rule configurations:"
            for err in errors:
                error_summary += f"\n  - {err}"
            logger.error(error_summary)

    def _create_rule_from_config(self, rule_config: Dict[str, Any], config_path: Path) -> ValidationRule:
        """
        Create a ValidationRule instance from a configuration dictionary.

        Args:
            rule_config: Dictionary containing rule configuration
            config_path: Path to the source configuration file (for error context)

        Returns:
            ValidationRule instance

        Raises:
            ValueError: If the rule configuration is invalid
        """
        # Validate required fields
        required_fields = ['name', 'formula']
        for field in required_fields:
            if field not in rule_config:
                raise ValueError(f"Required field '{field}' missing from rule configuration")

        # Extract rule attributes with validation
        name = rule_config['name']
        if not name or not isinstance(name, str):
            raise ValueError(f"Rule name must be a non-empty string")

        formula = rule_config['formula']
        if not formula or not isinstance(formula, str):
            raise ValueError(f"Rule formula must be a non-empty string")

        # Optional fields with defaults
        description = rule_config.get('description', '')
        if not isinstance(description, str):
            raise ValueError(f"Rule description must be a string")

        threshold = rule_config.get('threshold', 1.0)
        try:
            threshold = float(threshold)
            if not 0 <= threshold <= 1:
                raise ValueError(f"Threshold must be between 0 and 1")
        except (ValueError, TypeError):
            raise ValueError(f"Invalid threshold value: {threshold}")

        severity = rule_config.get('severity', 'medium')
        if not isinstance(severity, str) or severity.lower() not in ValidationRule.SEVERITY_LEVELS:
            raise ValueError(
                f"Invalid severity level: {severity}. Must be one of: {', '.join(ValidationRule.SEVERITY_LEVELS)}")

        category = rule_config.get('category', 'data_quality')
        if not isinstance(category, str):
            raise ValueError(f"Category must be a string")

        tags = rule_config.get('tags', [])
        if not isinstance(tags, list):
            # Try to convert to list if it's a string
            if isinstance(tags, str):
                tags = [tags]
            else:
                raise ValueError(f"Tags must be a list of strings")

        # Generate a rule_id if not provided (based on file and rule name)
        rule_id = rule_config.get('rule_id')
        if not rule_id:
            # Create deterministic ID based on file name and rule name
            file_stem = config_path.stem
            rule_id = f"{file_stem}_{name}"

        # Extract metadata fields
        metadata = {}
        for key, value in rule_config.items():
            if key not in ['rule_id', 'name', 'formula', 'description',
                           'threshold', 'severity', 'category', 'tags']:
                metadata[key] = value

        # Create the ValidationRule
        return ValidationRule(
            rule_id=rule_id,
            name=name,
            formula=formula,
            description=description,
            threshold=threshold,
            severity=severity,
            category=category,
            tags=tags,
            metadata=metadata
        )

    def get_rule_configuration_summary(self) -> Dict[str, Any]:
        """
        Get a summary of rule configurations loaded from YAML files.

        Returns:
            Dictionary with summary information
        """
        rules = self.rule_manager.list_rules()

        # Count rules by category
        rules_by_category = {}
        for rule in rules:
            category = rule.category
            if category not in rules_by_category:
                rules_by_category[category] = 0
            rules_by_category[category] += 1

        # Count rules by severity
        rules_by_severity = {}
        for rule in rules:
            severity = rule.severity
            if severity not in rules_by_severity:
                rules_by_severity[severity] = 0
            rules_by_severity[severity] += 1

        # Count rules by tag
        tag_counts = {}
        for rule in rules:
            for tag in rule.tags:
                if tag not in tag_counts:
                    tag_counts[tag] = 0
                tag_counts[tag] += 1

        return {
            'total_rules': len(rules),
            'config_files': len(self.rule_config_paths),
            'rules_by_category': rules_by_category,
            'rules_by_severity': rules_by_severity,
            'tag_counts': tag_counts
        }

    def reload_rule_configurations(self) -> Dict[str, Any]:
        """
        Reload all rule configurations from YAML files.
        Useful when configuration files have been updated.

        Returns:
            Dictionary with reload results
        """
        # Keep track of previous rules
        previous_rules = {rule.rule_id: rule for rule in self.rule_manager.list_rules()}

        # Clear all rules from manager (alternative: replace specific rules)
        for rule_id in list(previous_rules.keys()):
            self.rule_manager.delete_rule(rule_id)

        # Record start time
        start_time = datetime.datetime.now()

        # Load rules from configuration files
        self._load_rule_configurations()

        # Get current rules
        current_rules = {rule.rule_id: rule for rule in self.rule_manager.list_rules()}

        # Calculate changes
        added_rules = [rule_id for rule_id in current_rules if rule_id not in previous_rules]
        removed_rules = [rule_id for rule_id in previous_rules if rule_id not in current_rules]
        kept_rules = [rule_id for rule_id in current_rules if rule_id in previous_rules]

        # Record end time and calculate duration
        end_time = datetime.datetime.now()
        duration = (end_time - start_time).total_seconds()

        return {
            'previous_rules_count': len(previous_rules),
            'current_rules_count': len(current_rules),
            'added_rules': added_rules,
            'added_count': len(added_rules),
            'removed_rules': removed_rules,
            'removed_count': len(removed_rules),
            'kept_rules': kept_rules,
            'kept_count': len(kept_rules),
            'duration_seconds': duration
        }

    def _evaluate_rules_parallel(self,
                                 rules: List[ValidationRule],
                                 data_df: pd.DataFrame,
                                 responsible_party_column: Optional[str] = None) -> Dict[str, RuleEvaluationResult]:
        """
        Evaluate rules in parallel using thread pool, with COM safety measures.
        """
        results = {}

        # Limit the number of worker threads to avoid Excel instance explosion
        max_workers = min(self.max_workers, 4)  # Cap at 4 workers regardless of setting

        logger.info(f"Evaluating {len(rules)} rules with {max_workers} worker threads")

        # Use thread pool to evaluate rules in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit tasks but keep track of future objects
            futures = []
            for rule in rules:
                # Create a copy of the DataFrame for each rule to avoid threading issues
                rule_df = data_df.copy()
                futures.append(executor.submit(self._evaluate_single_rule, rule, rule_df, responsible_party_column))

            # Process futures as they complete
            for future in concurrent.futures.as_completed(futures):
                try:
                    rule_id, result = future.result()
                    if result:
                        results[rule_id] = result
                except Exception as e:
                    logger.error(f"Exception in thread pool task: {str(e)}")

        # Force garbage collection after all threads complete
        try:
            import gc
            gc.collect()
        except:
            pass

        return results

    def _evaluate_single_rule(self, rule, data_df, responsible_party_column):
        """
        Worker function to evaluate a single rule with thread isolation.

        This isolates all COM operations to a single thread context.
        """
        try:
            # Initialize COM for this thread
            pythoncom.CoInitialize()
            logger.debug(f"COM initialized in thread {threading.current_thread().ident} for rule {rule.rule_id}")

            # Use with statement to ensure proper cleanup
            with ExcelFormulaProcessor(visible=False) as processor:
                # Create a dedicated evaluator for this thread
                thread_evaluator = RuleEvaluator(
                    rule_manager=self.rule_manager,
                    compliance_determiner=ComplianceDeterminer(),
                    excel_visible=False
                )

                # Evaluate the rule
                result = thread_evaluator.evaluate_rule(
                    rule, data_df, responsible_party_column
                )

                # Return the result
                return rule.rule_id, result

        except Exception as e:
            logger.error(f"Error evaluating rule {rule.rule_id}: {str(e)}")
            return rule.rule_id, None

        finally:
            # Clean up COM in this thread
            try:
                pythoncom.CoUninitialize()
                logger.debug(f"COM uninitialized in thread {threading.current_thread().ident} for rule {rule.rule_id}")
            except Exception as e:
                logger.error(f"Error uninitializing COM in thread {threading.current_thread().ident}: {str(e)}")

    def _process_evaluation_results(self,
                                    rule_results: Dict[str, RuleEvaluationResult],
                                    results: Dict[str, Any],
                                    responsible_party_column: Optional[str] = None) -> None:
        """
        Process and summarize rule evaluation results.

        Args:
            rule_results: Dictionary of rule evaluation results
            results: Results dictionary to update
            responsible_party_column: Column identifying responsible parties for grouping
        """
        # Track overall compliance
        overall_valid = True
        compliance_counts = {
            'GC': 0,  # Generally Conforms
            'PC': 0,  # Partially Conforms
            'DNC': 0  # Does Not Conform
        }

        # Group rules by category and severity for reporting
        rule_stats = {
            'by_category': defaultdict(lambda: {'count': 0, 'GC': 0, 'PC': 0, 'DNC': 0}),
            'by_severity': defaultdict(lambda: {'count': 0, 'GC': 0, 'PC': 0, 'DNC': 0})
        }

        # Group results by responsible party if specified
        grouped_summary = defaultdict(lambda: {'count': 0, 'GC': 0, 'PC': 0, 'DNC': 0})

        # Process each rule result
        for rule_id, result in rule_results.items():
            # Add result summary to results
            results['rule_results'][rule_id] = result.summary

            # Update compliance counts
            compliance_status = result.compliance_status
            compliance_counts[compliance_status] += 1

            # Update rule statistics
            rule = result.rule
            category = rule.category if hasattr(rule, 'category') else 'uncategorized'
            severity = rule.severity if hasattr(rule, 'severity') else 'medium'

            # Update category stats
            rule_stats['by_category'][category]['count'] += 1
            rule_stats['by_category'][category][compliance_status] += 1

            # Update severity stats
            rule_stats['by_severity'][severity]['count'] += 1
            rule_stats['by_severity'][severity][compliance_status] += 1

            # Update overall validity (valid only if all rules are GC)
            if compliance_status != 'GC':
                overall_valid = False

            # Process group results if responsible party column specified
            if responsible_party_column and hasattr(result, 'party_results'):
                for party, party_result in result.party_results.items():
                    grouped_summary[party]['count'] += 1
                    grouped_summary[party][party_result['status']] += 1

        # Update summary information
        results['valid'] = overall_valid
        results['summary'] = {
            'total_rules': len(rule_results),
            'compliance_counts': compliance_counts,
            'compliance_rate': compliance_counts['GC'] / len(rule_results) if rule_results else 0,
            'rule_stats': rule_stats
        }

        # Add grouped summary if present
        if grouped_summary:
            # Calculate compliance rates for each group
            formatted_groups = {}
            for party, counts in grouped_summary.items():
                if counts['count'] > 0:
                    formatted_groups[party] = {
                        'total_rules': counts['count'],
                        'GC': counts['GC'],
                        'PC': counts['PC'],
                        'DNC': counts['DNC'],
                        'compliance_rate': counts['GC'] / counts['count']
                    }

            results['grouped_summary'] = formatted_groups

        # Set overall status
        if overall_valid:
            results['status'] = 'FULLY_COMPLIANT'
        elif compliance_counts['DNC'] > 0:
            results['status'] = 'NON_COMPLIANT'
        else:
            results['status'] = 'PARTIALLY_COMPLIANT'

    def _generate_outputs(self,
                          results: Dict[str, Any],
                          rule_results: Dict[str, RuleEvaluationResult],
                          data_df: pd.DataFrame,
                          output_formats: List[str],
                          analytic_title: Optional[str] = None,
                          responsible_party_column: Optional[str] = None) -> List[str]:
        """
        Generate output files in requested formats.

        Args:
            results: Validation results
            rule_results: Rule evaluation results
            data_df: Input DataFrame
            output_formats: List of output formats to generate

        Returns:
            List of generated output file paths
        """
        # Create timestamp string for filenames
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        analytic_id = results.get('analytic_id', 'validation')

        output_paths = []

        # Generate outputs in each requested format
        for format in output_formats:
            if format.lower() == 'excel_template':
                # Generate using template-based report generator
                excel_path = self.output_dir / f"{analytic_id}_{timestamp}_template_report.xlsx"
                
                try:
                    # Initialize template generator if not already done
                    if not hasattr(self, 'template_report_generator'):
                        from reporting.generation.template_report_generator import TemplateBasedReportGenerator
                        template_path = self.output_dir.parent / "templates" / "qa_report_template.xlsx"
                        self.template_report_generator = TemplateBasedReportGenerator(template_path)
                    
                    # Use responsible_party_column if provided, otherwise try to detect
                    group_by = responsible_party_column
                    if not group_by:
                        # Try to get from rule metadata
                        for result in rule_results.values():
                            if hasattr(result.rule, 'metadata') and 'responsible_party_column' in result.rule.metadata:
                                group_by = result.rule.metadata['responsible_party_column']
                                break
                    
                    logger.info(f"Generating template-based Excel report: {excel_path}")
                    report_path = self.template_report_generator.generate_excel_from_template(
                        results=results,
                        rule_results=rule_results,
                        output_path=str(excel_path),
                        analytic_id=analytic_id,
                        analytic_title=analytic_title,
                        group_by=group_by
                    )
                    output_paths.append(report_path)
                    logger.info(f"Template-based Excel report generated successfully")
                    
                except Exception as e:
                    logger.error(f"Error generating template report: {str(e)}", exc_info=True)
                    # Fall back to regular Excel generation
                    logger.info("Falling back to standard Excel report")
                    format = 'excel'  # Process as regular Excel
                    
            if format.lower() == 'json':
                # Export results to JSON
                json_path = self.output_dir / f"{analytic_id}_{timestamp}_results.json"
                with open(json_path, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                output_paths.append(str(json_path))

            elif format.lower() == 'excel':
                # Generate standard Excel report
                excel_path = self.output_dir / f"{analytic_id}_{timestamp}_detailed_report.xlsx"

                # Determine group_by column for responsible party aggregation
                group_by = None
                # Look for responsible_party_column in rule metadata
                for result in rule_results.values():
                    if hasattr(result.rule, 'metadata') and 'responsible_party_column' in result.rule.metadata:
                        group_by = result.rule.metadata['responsible_party_column']
                        break

                # If no metadata found, check 'grouped_summary' in results
                if not group_by and 'grouped_summary' in results:
                    # The presence of grouped_summary implies grouping was done
                    # Try to determine the column name from context
                    for rule_id, result in rule_results.items():
                        party_results = getattr(result, 'party_results', None)
                        if party_results:
                            for party_col in data_df.columns:
                                if any(party in data_df[party_col].values for party in party_results.keys()):
                                    group_by = party_col
                                    break
                        if group_by:
                            break

                # Generate the report using ReportGenerator
                try:
                    logger.info(f"Generating detailed Excel report: {excel_path}")
                    report_path = self.report_generator.generate_excel(
                        results,
                        rule_results,
                        str(excel_path),
                        group_by=group_by
                    )
                    output_paths.append(report_path)
                    logger.info(f"Excel report generated successfully")
                except Exception as e:
                    logger.error(f"Error generating detailed Excel report: {str(e)}")
                    # Fall back to simple Excel export
                    logger.info(f"Falling back to basic Excel export")
                    self._export_to_excel(results, rule_results, data_df, excel_path)
                    output_paths.append(str(excel_path))

            elif format.lower() == 'html':
                # Create filename for HTML report
                html_path = self.output_dir / f"{analytic_id}_{timestamp}_report.html"

                # Generate HTML report using ReportGenerator
                try:
                    logger.info(f"Generating HTML report: {html_path}")
                    report_path = self.report_generator.generate_html(
                        results,
                        rule_results,
                        str(html_path),
                        max_failures=1000  # Limit failures for performance
                    )
                    output_paths.append(report_path)
                    logger.info(f"HTML report generated successfully")
                except Exception as e:
                    logger.error(f"Error generating HTML report: {str(e)}")
                    # No fallback for HTML - just log the error

            elif format.lower() == 'csv':
                # Export summary results to CSV
                csv_path = self.output_dir / f"{analytic_id}_{timestamp}_summary.csv"
                self._export_to_csv(results, csv_path)
                output_paths.append(str(csv_path))

        return output_paths

    def _archive_outputs(self, output_paths: List[str]) -> List[str]:
        """
        Archive output files to the archive directory.

        Args:
            output_paths: List of paths to output files

        Returns:
            List of archived file paths
        """
        if not self.archive_dir:
            return []

        # Create timestamped subdirectory in archive
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_subdir = self.archive_dir / timestamp
        archive_subdir.mkdir(exist_ok=True)

        archived_paths = []

        # Copy each file to archive
        for path in output_paths:
            src_path = Path(path)
            if src_path.exists():
                dst_path = archive_subdir / src_path.name
                shutil.copy2(src_path, dst_path)
                archived_paths.append(str(dst_path))

        return archived_paths

    def _export_to_excel(self,
                         results: Dict[str, Any],
                         rule_results: Dict[str, RuleEvaluationResult],
                         data_df: pd.DataFrame,
                         output_path: Path) -> None:
        """
        Export detailed results to Excel file.

        Args:
            results: Validation results
            rule_results: Rule evaluation results
            data_df: Input DataFrame
            output_path: Path for Excel output file
        """
        try:
            # Create Excel writer
            with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
                # Create summary sheet
                summary_data = {
                    'Metric': ['Status', 'Total Rules', 'GC Count', 'PC Count', 'DNC Count',
                               'Compliance Rate', 'Execution Time'],
                    'Value': [
                        results['status'],
                        results['summary']['total_rules'],
                        results['summary']['compliance_counts']['GC'],
                        results['summary']['compliance_counts']['PC'],
                        results['summary']['compliance_counts']['DNC'],
                        f"{results['summary']['compliance_rate']:.2%}",
                        f"{results['execution_time']:.2f} seconds"
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)

                # Create Rules sheet with detailed rule results
                rules_data = []
                for rule_id, rule_result in results['rule_results'].items():
                    rules_data.append({
                        'Rule ID': rule_id,
                        'Rule Name': rule_result['rule_name'],
                        'Status': rule_result['compliance_status'],
                        'Total Items': rule_result['total_items'],
                        'GC Count': rule_result['gc_count'],
                        'PC Count': rule_result['pc_count'],
                        'DNC Count': rule_result['dnc_count'],
                        'Compliance Rate': rule_result['compliance_rate']
                    })

                if rules_data:
                    rules_df = pd.DataFrame(rules_data)
                    rules_df.to_excel(writer, sheet_name='Rules', index=False)

                # Export a sample of the input data
                data_sample = data_df.head(100)  # Just first 100 rows as sample
                data_sample.to_excel(writer, sheet_name='Data Sample', index=False)

                # Create Compliance Breakdown by Category
                if 'rule_stats' in results['summary']:
                    # By Category
                    category_data = []
                    for category, stats in results['summary']['rule_stats']['by_category'].items():
                        compliance_rate = stats['GC'] / stats['count'] if stats['count'] > 0 else 0
                        category_data.append({
                            'Category': category,
                            'Total Rules': stats['count'],
                            'GC': stats['GC'],
                            'PC': stats['PC'],
                            'DNC': stats['DNC'],
                            'Compliance Rate': compliance_rate
                        })

                    if category_data:
                        category_df = pd.DataFrame(category_data)
                        category_df.to_excel(writer, sheet_name='By Category', index=False)

                    # By Severity
                    severity_data = []
                    for severity, stats in results['summary']['rule_stats']['by_severity'].items():
                        compliance_rate = stats['GC'] / stats['count'] if stats['count'] > 0 else 0
                        severity_data.append({
                            'Severity': severity,
                            'Total Rules': stats['count'],
                            'GC': stats['GC'],
                            'PC': stats['PC'],
                            'DNC': stats['DNC'],
                            'Compliance Rate': compliance_rate
                        })

                    if severity_data:
                        severity_df = pd.DataFrame(severity_data)
                        severity_df.to_excel(writer, sheet_name='By Severity', index=False)

                # Add Responsible Party breakdown if available
                if 'grouped_summary' in results and results['grouped_summary']:
                    party_data = []
                    for party, stats in results['grouped_summary'].items():
                        party_data.append({
                            'Responsible Party': party,
                            'Total Rules': stats['total_rules'],
                            'GC': stats['GC'],
                            'PC': stats['PC'],
                            'DNC': stats['DNC'],
                            'Compliance Rate': stats['compliance_rate']
                        })

                    if party_data:
                        party_df = pd.DataFrame(party_data)
                        party_df.to_excel(writer, sheet_name='By Responsible Party', index=False)

                # Export detailed results for each rule
                for rule_id, result in rule_results.items():
                    # Get failures only
                    failure_df = result.get_failing_items()
                    if not failure_df.empty:
                        # Limit to first 1000 rows if very large
                        if len(failure_df) > 1000:
                            failure_df = failure_df.head(1000)

                        # Excel sheet names have 31 char limit
                        sheet_name = f"Rule_{rule_id[-20:]}" if len(rule_id) > 20 else f"Rule_{rule_id}"
                        failure_df.to_excel(writer, sheet_name=sheet_name, index=False)

                # Add styling to make the report more readable
                workbook = writer.book
                # Add formats for different compliance statuses
                gc_format = workbook.add_format({'bg_color': '#C6EFCE', 'font_color': '#006100'})
                pc_format = workbook.add_format({'bg_color': '#FFEB9C', 'font_color': '#9C6500'})
                dnc_format = workbook.add_format({'bg_color': '#FFC7CE', 'font_color': '#9C0006'})

                # Apply conditional formatting to Rules sheet
                if rules_data:
                    rules_sheet = writer.sheets['Rules']
                    rules_sheet.conditional_format('C2:C1000', {'type': 'text',
                                                                'criteria': 'containing',
                                                                'value': 'GC',
                                                                'format': gc_format})
                    rules_sheet.conditional_format('C2:C1000', {'type': 'text',
                                                                'criteria': 'containing',
                                                                'value': 'PC',
                                                                'format': pc_format})
                    rules_sheet.conditional_format('C2:C1000', {'type': 'text',
                                                                'criteria': 'containing',
                                                                'value': 'DNC',
                                                                'format': dnc_format})

        except Exception as e:
            logger.error(f"Error exporting results to Excel: {str(e)}")
            raise

    def _export_to_csv(self, results: Dict[str, Any], output_path: Path) -> None:
        """
        Export summary results to CSV file.

        Args:
            results: Validation results
            output_path: Path for CSV output file
        """
        try:
            # Extract rule results for CSV export
            csv_data = []
            for rule_id, rule_result in results['rule_results'].items():
                csv_data.append({
                    'Rule ID': rule_id,
                    'Rule Name': rule_result['rule_name'],
                    'Status': rule_result['compliance_status'],
                    'Total Items': rule_result['total_items'],
                    'GC Count': rule_result['gc_count'],
                    'PC Count': rule_result['pc_count'],
                    'DNC Count': rule_result['dnc_count'],
                    'Compliance Rate': rule_result['compliance_rate'],
                    'Analytic ID': results.get('analytic_id', ''),
                    'Timestamp': results.get('timestamp', '')
                })

            if csv_data:
                # Convert to DataFrame and export to CSV
                csv_df = pd.DataFrame(csv_data)
                csv_df.to_csv(output_path, index=False)

        except Exception as e:
            logger.error(f"Error exporting results to CSV: {str(e)}")
            raise

    def aggregate_analytics(
            self,
            result_paths: List[str],
            output_formats: Optional[List[str]] = None,
            weights_config: Optional[str] = None,
            output_dir: Optional[str] = None,
            report_config: Optional[str] = None,
            return_report: bool = False
    ) -> Dict[str, Any]:
        """
        Aggregate results from multiple analytics runs.

        Args:
            result_paths: Paths to JSON result files from previous validation runs
            output_formats: Output formats to generate ('json', 'excel', etc.)
            weights_config: Path to weights configuration file
            output_dir: Directory for output files (defaults to self.output_dir)
            report_config: Path to report configuration YAML file
            return_report: Whether to include the full report structure in the return value

        Returns:
            Dictionary with aggregation results and output file paths
        """
        from business_logic.aggregation.analytics_aggregator import (
            aggregate_analytics_results,
            load_weights_configuration,
            create_summary_report
        )
        from datetime import datetime  # Fixed missing import

        logger.info(f"Aggregating results from {len(result_paths)} analytics runs")

        # Load result files
        result_dicts = []
        for path in result_paths:
            try:
                with open(path, 'r') as f:
                    result = json.load(f)
                    result_dicts.append(result)
                    logger.debug(f"Successfully loaded results from {path}")
            except Exception as e:
                logger.error(f"Error loading results from {path}: {str(e)}")

        if not result_dicts:
            return {
                'success': False,
                'error': 'No valid result files loaded'
            }

        # Load weights configuration if specified
        weights_config_dict = None
        if weights_config:
            weights_config_dict = load_weights_configuration(weights_config)

        # Set output directory
        if output_dir:
            output_dir_path = Path(output_dir)
        else:
            output_dir_path = self.output_dir

        output_dir_path.mkdir(parents=True, exist_ok=True)

        # Perform aggregation
        summary = aggregate_analytics_results(
            result_dicts=result_dicts,
            weights_config=weights_config_dict
        )

        # Add robust logging after aggregation
        logger.info(f"Aggregation complete. Leaders: {len(summary.leader_summary)}, Rules: {len(summary.rule_details)}")

        # Create summary report
        report = create_summary_report(summary)

        # Generate outputs in requested formats
        output_paths = []
        if output_formats:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for fmt in output_formats:
                if fmt.lower() == 'json':
                    # Export aggregated results to JSON
                    json_path = output_dir_path / f"aggregated_results_{timestamp}.json"
                    summary.export_to_file(str(json_path))
                    output_paths.append(str(json_path))
                    logger.info(f"Exported aggregated results to {json_path}")

                elif fmt.lower() == 'excel':
                    # Create Excel report
                    excel_path = output_dir_path / f"aggregated_report_{timestamp}.xlsx"

                    try:
                        # Explicit exception handling for ReportGenerator
                        if not hasattr(self, 'report_generator') or self.report_generator is None:
                            if report_config:
                                self.report_generator = ReportGenerator(report_config)
                            else:
                                self.report_generator = ReportGenerator()  # Default to empty config
                        elif report_config:  # Update existing report generator with new config
                            self.report_generator = ReportGenerator(report_config)

                        # This would need to be implemented in ReportGenerator
                        report_path = self.report_generator.generate_aggregate_excel(
                            summary=summary,
                            output_path=str(excel_path)
                        )
                        output_paths.append(report_path)
                        logger.info(f"Generated Excel report at {report_path}")
                    except Exception as e:
                        logger.error(f"Error generating Excel report: {str(e)}")
                        logger.debug(f"Excel error details: {e}", exc_info=True)
                else:
                    # Report format validation - log unsupported formats
                    logger.warning(f"Unsupported output format: {fmt}")

        # Return aggregation results with optional full report
        result = {
            'success': True,
            'timestamp': datetime.now().isoformat(),
            'leader_count': len(summary.leader_summary),
            'rule_count': len(summary.rule_details),
            'department_summary': summary.department_summary,
            'output_files': output_paths
        }

        # Include full report if requested
        if return_report:
            result['report'] = report

        return result

    def generate_leader_packs(self,
                              results: Dict[str, Any],
                              rule_results: Dict[str, RuleEvaluationResult],
                              responsible_party_column: Optional[str] = None,
                              output_dir: Optional[str] = None,
                              selected_leaders: Optional[List[str]] = None,
                              include_only_failures: bool = False,
                              generate_email_content: bool = False,
                              zip_output: bool = True,
                              export_csv_summary: bool = False,
                              suppress_logs: bool = False) -> Dict[str, Any]:
        """
        Generate individual Excel reports for each audit leader containing only their relevant data.
        This method produces per-leader Excel reports summarizing compliance results, for distribution
        or documentation purposes.

        Args:
            results: Validation results dictionary (from validate_data_source)
            rule_results: Dictionary of rule evaluation results
            responsible_party_column: Column name for identifying responsible parties
            output_dir: Directory to save the leader packs (defaults to self.output_dir)
            selected_leaders: Optional list of specific leaders to generate packs for
            include_only_failures: Whether to only include leaders with at least one failed rule
            generate_email_content: Whether to generate email-ready summaries
            zip_output: Whether to create a ZIP file containing all leader packs
            export_csv_summary: Whether to export a CSV summary of leader metrics
            suppress_logs: Whether to suppress detailed logging (for automated workflows)

        Returns:
            Dictionary with generation results including paths to all generated files
        """
        # Configure logging
        log_level = logging.INFO
        if suppress_logs:
            log_level = logging.WARNING

        # Use default output directory if not specified
        if output_dir is None:
            output_dir = self.output_dir

        # Validate rule_results has content
        if not rule_results:
            error_msg = "No rule evaluation results provided"
            if not suppress_logs:
                logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg
            }

        # If responsible_party_column not specified, try to find it in results
        inferred_column = False
        if responsible_party_column is None:
            # Look for responsible_party_column in rule metadata
            for rule_id, result in rule_results.items():
                if (hasattr(result, 'rule') and
                        hasattr(result.rule, 'metadata') and
                        'responsible_party_column' in result.rule.metadata):
                    responsible_party_column = result.rule.metadata['responsible_party_column']
                    inferred_column = True
                    break

        # If we still don't have responsible_party_column, use default
        if responsible_party_column is None:
            # Try a common default based on context
            if 'grouped_summary' in results and results['grouped_summary']:
                # Name the column "Audit Leader" as a default
                responsible_party_column = "Audit Leader"
                inferred_column = True

                if not suppress_logs:
                    logger.warning(f"No responsible_party_column specified, using default: {responsible_party_column}")
            else:
                error_msg = "No responsible_party_column specified and couldn't determine from context"
                if not suppress_logs:
                    logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg
                }

        # Log the responsible party column if it was inferred
        if inferred_column and not suppress_logs:
            logger.info(f"Using responsible party column: {responsible_party_column} (inferred from context)")

        # Check if report_generator is available
        if not hasattr(self, 'report_generator'):
            # Initialize with default settings
            self.report_generator = ReportGenerator()

        # Call the report generator to create leader packs
        return self.report_generator.generate_leader_packs(
            results=results,
            rule_results=rule_results,
            output_dir=output_dir,
            responsible_party_column=responsible_party_column,
            selected_leaders=selected_leaders,
            include_only_failures=include_only_failures,
            generate_email_content=generate_email_content,
            zip_output=zip_output,
            export_csv_summary=export_csv_summary,
            sort_leaders=True,  # Always sort leaders for consistency
            suppress_logs=suppress_logs  # Pass through log suppression flag
        )
    
    def generate_iag_summary_report(
        self,
        results: Dict[str, Any],
        rule_results: Dict[str, Any],
        responsible_party_column: str,
        output_path: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> Union[Path, Dict[str, Any]]:
        """
        Generate IAG and AL Results and Ratings Summary report.
        
        Args:
            results: Validation results from validate_data_source()
            rule_results: Rule evaluation results dictionary
            responsible_party_column: Column for audit leader grouping
            output_path: Optional output path (auto-generated if None)
            **kwargs: Additional options passed to IAGSummaryGenerator:
                - review_year_name: Header text (e.g., "2024 Q3 Compliance Review")
                - analytics_metadata: Dict with error thresholds, risk levels, etc.
                - manual_overrides: Dict for manual rating overrides
                
        Returns:
            Path to generated IAG summary Excel file, or error dict if failed
        """
        try:
            # Generate default output path if not provided
            if not output_path:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                analytic_id = results.get('analytic_id', 'validation')
                output_path = self.output_dir / f"{analytic_id}_{timestamp}_IAG_Summary.xlsx"
            
            # Ensure output_path is a Path object
            output_path = Path(output_path)
            
            # Log generation start
            logger.info(f"Generating IAG summary report for {len(rule_results)} rules")
            
            # Check if report_generator is available
            if not hasattr(self, 'report_generator'):
                self.report_generator = ReportGenerator()
            
            # Generate the IAG summary report
            report_path = self.report_generator.generate_iag_summary_excel(
                results=results,
                rule_results=rule_results,
                output_path=output_path,
                responsible_party_column=responsible_party_column,
                **kwargs
            )
            
            logger.info(f"IAG summary report generated successfully: {report_path}")
            return report_path
            
        except Exception as e:
            error_msg = f"Failed to generate IAG summary report: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }
    
    def generate_comprehensive_iag_report(
        self,
        results: Dict[str, Any],
        rule_results: Dict[str, Any],
        responsible_party_column: str,
        output_path: Optional[Union[str, Path]] = None,
        **kwargs
    ) -> Union[Path, Dict[str, Any]]:
        """
        Generate comprehensive IAG report with summary and individual analytic tabs.
        
        This method generates a complete Excel workbook containing:
        1. IAG Summary tab with overall results and ratings
        2. Individual analytic tabs for each rule (QA-ID format)
        
        Args:
            results: Validation results from validate_data_source()
            rule_results: Rule evaluation results dictionary
            responsible_party_column: Column for audit leader grouping
            output_path: Optional output path (auto-generated if None)
            **kwargs: Additional options for report generation
                
        Returns:
            Path to generated comprehensive IAG Excel file, or error dict if failed
        """
        try:
            # Generate default output path if not provided
            if not output_path:
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                analytic_id = results.get('analytic_id', 'validation')
                output_path = self.output_dir / f"{analytic_id}_{timestamp}_Comprehensive_IAG.xlsx"
            
            # Ensure output_path is a Path object
            output_path = Path(output_path)
            
            # Get source data for detailed results
            data_source = results.get('data_source')
            if isinstance(data_source, str):
                # Load the data file
                source_data = self.data_importer.load_file(data_source)
            elif isinstance(data_source, pd.DataFrame):
                source_data = data_source
            else:
                # Try to get from first rule result
                first_result = next(iter(rule_results.values()))
                if hasattr(first_result, 'result_df'):
                    source_data = first_result.result_df
                else:
                    raise ValueError("Could not determine source data for detailed results")
            
            # Log generation start
            logger.info(f"Generating comprehensive IAG report with {len(rule_results)} individual analytic tabs")
            
            # Check if report_generator is available
            if not hasattr(self, 'report_generator'):
                self.report_generator = ReportGenerator()
            
            # Generate the comprehensive report
            report_path = self.report_generator.generate_comprehensive_iag_workbook(
                results=results,
                rule_results=rule_results,
                source_data=source_data,
                responsible_party_column=responsible_party_column,
                output_path=str(output_path),
                **kwargs
            )
            
            logger.info(f"Comprehensive IAG report generated successfully: {report_path}")
            return Path(report_path)
            
        except Exception as e:
            error_msg = f"Failed to generate comprehensive IAG report: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {
                "success": False,
                "error": error_msg
            }
"""
Progress Tracking Pipeline - Real-time progress monitoring wrapper for ValidationPipeline
Provides rule-by-rule progress updates with minimal overhead
"""

import logging
import time
import threading
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime
import pandas as pd

from services.validation_service import ValidationPipeline
from core.rule_engine.rule_manager import ValidationRule
from core.rule_engine.rule_evaluator import RuleEvaluationResult

logger = logging.getLogger(__name__)


class ProgressTrackingEvaluator:
    """
    Wrapper for RuleEvaluator that tracks progress during rule evaluation.
    """
    
    def __init__(self, base_evaluator, progress_callback: Optional[Callable] = None, lookup_manager: Optional[Any] = None):
        self.base_evaluator = base_evaluator
        self.progress_callback = progress_callback
        self.lookup_manager = lookup_manager
        self._total_rules = 0
        self._completed_rules = 0
        self._current_rule_name = ""
        self._start_time = time.time()
        self._cancel_requested = threading.Event()
        
    def cancel(self):
        """Request cancellation."""
        self._cancel_requested.set()
        
    def evaluate_rule(self, rule, data_df, responsible_party_column=None, lookup_manager=None):
        """
        Evaluate a single rule - delegates to base evaluator.
        This method is needed for compatibility when the ProgressTrackingEvaluator
        replaces the pipeline's evaluator.
        """
        # Use the lookup_manager passed in or the one from initialization
        lm = lookup_manager or self.lookup_manager
        return self.base_evaluator.evaluate_rule(rule, data_df, responsible_party_column, lm)
    
    # Delegate other methods to maintain full compatibility
    @property
    def rule_manager(self):
        """Access to rule manager through base evaluator."""
        return self.base_evaluator.rule_manager
        
    def evaluate_multiple_rules(
        self,
        rules: List[Union[str, ValidationRule]],
        data_df: pd.DataFrame,
        responsible_party_column: Optional[str] = None
    ) -> Dict[str, RuleEvaluationResult]:
        """
        Evaluate multiple rules with progress tracking.
        """
        results = {}
        self._total_rules = len(rules)
        self._completed_rules = 0
        
        for i, rule in enumerate(rules):
            # Check cancellation
            if self._cancel_requested.is_set():
                logger.info("Rule evaluation cancelled by user")
                break
                
            # Get rule details
            if isinstance(rule, str):
                rule_obj = self.base_evaluator.rule_manager.get_rule(rule)
                rule_id = rule
                rule_name = rule_obj.name if rule_obj else f"Rule {rule}"
            else:
                rule_id = rule.rule_id
                rule_name = rule.name
                
            self._current_rule_name = rule_name
            
            # Update progress before rule execution
            if self.progress_callback:
                progress = int((i / self._total_rules) * 100)
                elapsed = time.time() - self._start_time
                
                # Estimate time remaining
                if i > 0:
                    avg_time_per_rule = elapsed / i
                    remaining_rules = self._total_rules - i
                    eta_seconds = avg_time_per_rule * remaining_rules
                    eta_str = f" (ETA: {int(eta_seconds)}s)" if eta_seconds < 300 else ""
                else:
                    eta_str = ""
                    
                status = f"Processing rule {i+1}/{self._total_rules}: {rule_name}{eta_str}"
                self.progress_callback(progress, status)
                
            try:
                # Evaluate the rule using base evaluator
                result = self.base_evaluator.evaluate_rule(rule, data_df, responsible_party_column, self.lookup_manager)
                results[rule_id] = result
                
            except Exception as e:
                logger.error(f"Error evaluating rule {rule_id}: {str(e)}")
                # Continue with other rules
                
            self._completed_rules = i + 1
            
        # Final progress update
        if self.progress_callback:
            self.progress_callback(100, f"Completed {self._completed_rules}/{self._total_rules} rules")
            
        return results


class ProgressTrackingPipeline:
    """
    Wrapper for ValidationPipeline that provides real-time progress tracking.
    
    Features:
    - Rule-by-rule progress updates
    - Overall percentage completion
    - Current rule information
    - Time estimation
    - Thread-safe operation
    - Graceful cancellation
    """
    
    def __init__(self, validation_pipeline: ValidationPipeline):
        """
        Initialize progress tracking wrapper.
        
        Args:
            validation_pipeline: The underlying ValidationPipeline instance
        """
        self.pipeline = validation_pipeline
        self._cancel_requested = threading.Event()
        self._lock = threading.Lock()
        self._progress_evaluator = None
        self._last_rule_results = None  # Store rule results for leader pack generation
        
    def cancel(self):
        """Request cancellation of the validation process."""
        self._cancel_requested.set()
        if self._progress_evaluator:
            self._progress_evaluator.cancel()
        logger.info("Cancellation requested for validation pipeline")
        
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested."""
        return self._cancel_requested.is_set()
        
    def validate_data_source_with_progress(
        self,
        data_source_path: str,
        source_type: str,
        rule_ids: Optional[List[str]] = None,
        selected_sheet: Optional[str] = None,
        use_parallel: bool = False,
        responsible_party_column: Optional[str] = None,
        progress_callback: Optional[Callable[[int, str], None]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute validation with progress tracking.
        
        Args:
            data_source_path: Path to the data source file
            source_type: Type of data source (excel, csv, etc.)
            rule_ids: Optional list of specific rule IDs to run
            progress_callback: Callback function(progress: int, status: str)
            **kwargs: Additional arguments passed to ValidationPipeline
            
        Returns:
            Validation results dictionary
        """
        # Reset state
        self._cancel_requested.clear()
        start_time = time.time()
        
        try:
            # Store original evaluator
            original_evaluator = self.pipeline.evaluator
            
            # Create progress tracking evaluator
            self._progress_evaluator = ProgressTrackingEvaluator(
                original_evaluator, 
                progress_callback,
                self.pipeline.lookup_manager
            )
            
            # Temporarily replace the pipeline's evaluator
            self.pipeline.evaluator = self._progress_evaluator
            
            # Initial progress
            if progress_callback:
                progress_callback(0, "Starting validation...")
                
            # Prepare data source params if sheet is specified
            data_source_params = None
            if selected_sheet:
                data_source_params = {'sheet_name': selected_sheet}
                
            # Execute validation with progress tracking
            results = self.pipeline.validate_data_source(
                data_source=data_source_path,  # Note: parameter is 'data_source' not 'data_source_path'
                data_source_params=data_source_params,
                rule_ids=rule_ids,
                use_parallel=use_parallel,
                responsible_party_column=responsible_party_column,
                **kwargs
            )
            
            # Check if cancelled
            if self.is_cancelled():
                results['status'] = 'CANCELLED'
                results['message'] = 'Validation cancelled by user'
                
            # Final progress update
            if progress_callback:
                elapsed = time.time() - start_time
                if results.get('status') == 'CANCELLED':
                    progress_callback(
                        100,
                        f"Validation cancelled after {elapsed:.1f}s"
                    )
                else:
                    rule_count = len(results.get('rule_results', {}))
                    progress_callback(
                        100, 
                        f"Validation complete in {elapsed:.1f}s - "
                        f"{rule_count} rules processed"
                    )
                    
            return results
            
        except Exception as e:
            logger.error(f"Error during validation: {str(e)}")
            if progress_callback:
                progress_callback(
                    -1,  # Use -1 to indicate error
                    f"Error: {str(e)}"
                )
            raise
            
        finally:
            # Restore original evaluator
            if hasattr(self, 'pipeline') and hasattr(self.pipeline, 'evaluator'):
                self.pipeline.evaluator = original_evaluator
            self._progress_evaluator = None


# Example usage with ValidationWorker
"""
Example integration with ValidationWorker in main_application.py:

class ValidationWorkerSignals(QObject):
    # ... existing signals ...
    progressUpdated = Signal(int)     # Progress percentage (0-100, or -1 for error)
    statusUpdated = Signal(str)       # Status message
    ruleStarted = Signal(str, int, int)  # Rule name, current index, total count

class ValidationWorker(QRunnable):
    def __init__(self, ...):
        # ... existing init code ...
        
    def run(self):
        try:
            # Create progress tracking wrapper
            progress_pipeline = ProgressTrackingPipeline(self.pipeline)
            
            # Define progress callback that emits signals
            def progress_callback(progress: int, status: str):
                self.signals.progressUpdated.emit(progress)
                self.signals.statusUpdated.emit(status)
                
                # Parse rule info from status if available
                if "Processing rule" in status and "/" in status:
                    # Extract rule number and name
                    parts = status.split(":")
                    if len(parts) > 1:
                        rule_info = parts[0].replace("Processing rule", "").strip()
                        rule_name = parts[1].split("(")[0].strip()
                        
                        # Extract current and total
                        if "/" in rule_info:
                            current, total = rule_info.split("/")
                            try:
                                current_idx = int(current)
                                total_count = int(total)
                                self.signals.ruleStarted.emit(rule_name, current_idx, total_count)
                            except ValueError:
                                pass
                
            # Connect cancellation if needed
            # self.cancel_requested.connect(progress_pipeline.cancel)
                
            # Run validation with progress tracking
            results = progress_pipeline.validate_data_source_with_progress(
                data_source_path=self.data_source_path,
                source_type=self.source_type,
                rule_ids=self.rule_ids,
                selected_sheet=self.selected_sheet,
                progress_callback=progress_callback,
                use_all_rules=self.use_all_rules
            )
            
            # ... rest of existing validation handling ...
            
        except Exception as e:
            # ... error handling ...
"""
"""
Cancellable Validation Worker - Enhanced ValidationWorker with execution management
Provides thread-safe cancellation and status tracking for validation operations
"""

import logging
import threading
import datetime
import uuid
import os
import json
from typing import Optional, List, Dict, Any
from PySide6.QtCore import QRunnable, QObject, Signal

from services.progress_tracking_pipeline import ProgressTrackingPipeline
from services.validation_service import ValidationPipeline

logger = logging.getLogger(__name__)


class CancellableWorkerSignals(QObject):
    """Enhanced signals for cancellable validation worker"""
    # Existing signals
    started = Signal()
    finished = Signal()
    error = Signal(str)
    result = Signal(dict)
    progress = Signal(int, str)
    
    # Report generation signals
    reportStarted = Signal()
    reportProgress = Signal(int, str)
    reportCompleted = Signal(dict)
    reportError = Signal(str)
    
    # Real-time progress tracking signals
    progressUpdated = Signal(int)
    statusUpdated = Signal(str)
    ruleStarted = Signal(str, int, int)
    
    # Execution management signals
    cancelled = Signal(str)  # Cancellation reason
    statusChanged = Signal(str)  # Active/Cancelled/Completed/Error
    sessionStarted = Signal(str, str)  # Session ID, timestamp


class ExecutionStatus:
    """Execution status constants"""
    PENDING = "Pending"
    ACTIVE = "Active"
    PAUSED = "Paused"
    CANCELLED = "Cancelled"
    COMPLETED = "Completed"
    ERROR = "Error"


class CancellableValidationWorker(QRunnable):
    """
    Enhanced validation worker with execution management capabilities.
    
    Features:
    - Thread-safe cancellation using threading.Event
    - Execution session tracking with unique IDs
    - Status monitoring and reporting
    - Proper resource cleanup on cancellation
    """
    
    def __init__(self, 
                 pipeline: Optional[ValidationPipeline] = None,
                 data_source: str = None,
                 sheet_name: Optional[str] = None,
                 analytic_id: Optional[str] = None,
                 rule_ids: Optional[List[str]] = None,
                 generate_reports: bool = True,
                 report_formats: Optional[List[str]] = None,
                 output_dir: Optional[str] = None,
                 use_parallel: bool = False,
                 responsible_party_column: Optional[str] = None,
                 generate_leader_packs: bool = False,
                 analytic_title: Optional[str] = None,
                 use_template: bool = False):
        super().__init__()
        
        # Validation parameters
        self.pipeline = pipeline
        self.data_source = data_source
        self.sheet_name = sheet_name
        self.analytic_id = analytic_id or "Simple_Validation"
        self.rule_ids = rule_ids
        self.generate_reports = generate_reports
        self.report_formats = report_formats or ['iag_excel']  # Updated to use new IAG format
        self.output_dir = output_dir or './output'
        self.use_parallel = use_parallel
        self.responsible_party_column = responsible_party_column
        self.generate_individual_reports = generate_leader_packs  # Use clearer name internally
        self.analytic_title = analytic_title
        self.use_template = use_template
        
        # Execution management
        self._cancel_event = threading.Event()
        self._pause_event = threading.Event()  # For future implementation
        self._status = ExecutionStatus.PENDING
        self._session_id = str(uuid.uuid4())[:8]  # Short session ID
        self._start_time = None
        
        # Signals
        self.signals = CancellableWorkerSignals()
        
        # Progress tracking
        self._progress_pipeline = None
        
    def cancel(self, reason: str = "User requested"):
        """
        Request cancellation of the validation process.
        
        Args:
            reason: Reason for cancellation (for logging)
        """
        self._cancel_event.set()
        self._status = ExecutionStatus.CANCELLED
        logger.info(f"Cancellation requested for session {self._session_id}: {reason}")
        
    def pause(self):
        """Pause execution (placeholder for future implementation)"""
        self._pause_event.set()
        logger.info(f"Pause requested for session {self._session_id}")
        
    def resume(self):
        """Resume execution (placeholder for future implementation)"""
        self._pause_event.clear()
        logger.info(f"Resume requested for session {self._session_id}")
        
    def is_cancelled(self) -> bool:
        """Check if cancellation has been requested"""
        return self._cancel_event.is_set()
        
    def get_status(self) -> str:
        """Get current execution status"""
        return self._status
        
    def get_session_id(self) -> str:
        """Get execution session ID"""
        return self._session_id
        
    def run(self):
        """Run the validation process with cancellation support."""
        try:
            # Initialize execution
            self._start_time = datetime.datetime.now()
            self._status = ExecutionStatus.ACTIVE
            
            # Emit session start
            self.signals.sessionStarted.emit(
                self._session_id,
                self._start_time.strftime("%Y-%m-%d %H:%M:%S")
            )
            self.signals.started.emit()
            self.signals.statusChanged.emit(self._status)
            
            # Check for early cancellation
            if self.is_cancelled():
                self._handle_cancellation("Cancelled before start")
                return
                
            # Define enhanced progress callback
            def progress_callback(progress: int, status: str):
                # Check for cancellation during progress
                if self.is_cancelled():
                    return
                    
                self.signals.progressUpdated.emit(progress)
                self.signals.statusUpdated.emit(status)
                
                # Parse rule info from status if available
                if "Processing rule" in status and "/" in status:
                    parts = status.split(":")
                    if len(parts) > 1:
                        rule_info = parts[0].replace("Processing rule", "").strip()
                        rule_name = parts[1].split("(")[0].strip()
                        
                        if "/" in rule_info:
                            current, total = rule_info.split("/")
                            try:
                                current_idx = int(current)
                                total_count = int(total)
                                self.signals.ruleStarted.emit(rule_name, current_idx, total_count)
                            except ValueError:
                                pass
            
            # Import here to avoid circular imports
            from services.validation_service import ValidationPipeline
            from core.rule_engine.rule_manager import ValidationRuleManager
            import os
            
            # Create pipeline if not provided
            if not self.pipeline:
                os.makedirs(self.output_dir, exist_ok=True)
                logger.info(f"Session {self._session_id}: Created output directory: {self.output_dir}")
                
                rule_manager = ValidationRuleManager(rules_directory="./data/rules")
                self.pipeline = ValidationPipeline(
                    rule_manager=rule_manager,
                    output_dir=self.output_dir
                )
                
            # Create progress tracking wrapper with cancellation support
            self._progress_pipeline = ProgressTrackingPipeline(self.pipeline)
            
            # Connect our cancel event to the pipeline's cancel method
            if self.is_cancelled():
                self._progress_pipeline.cancel()
                self._handle_cancellation("Cancelled during initialization")
                return
                
            # Prepare validation parameters
            validation_params = {
                'data_source_path': self.data_source,
                'source_type': 'excel' if str(self.data_source).endswith(('.xlsx', '.xls')) else 'csv',
                'rule_ids': self.rule_ids,
                'selected_sheet': self.sheet_name,
                'analytic_id': self.analytic_id,
                'output_formats': ['json'],  # Only JSON during validation, Excel handled separately
                'use_parallel': getattr(self, 'use_parallel', False),  # Get from instance if set
                'responsible_party_column': getattr(self, 'responsible_party_column', None),
                'progress_callback': progress_callback,
                'analytic_title': self.analytic_title
            }
            
            # Excel format now uses template by default, no need to convert
            
            # Add use_all_rules flag if no specific rules selected
            if not self.rule_ids:
                validation_params['use_all_rules'] = True
                logger.info(f"Session {self._session_id}: No specific rules selected - will use all available rules")
                
            # Run validation with progress tracking
            logger.info(f"Session {self._session_id}: Starting validation")
            results = self._progress_pipeline.validate_data_source_with_progress(**validation_params)
            
            # Check if cancelled during validation
            if self.is_cancelled():
                self._handle_cancellation("Cancelled during validation")
                return
                
            # Check results status
            if results.get('status') == 'CANCELLED':
                self._handle_cancellation("Validation cancelled")
                return
                
            # Process results
            self._process_validation_results(results)
            
            # Mark as completed if not cancelled
            if not self.is_cancelled():
                self._status = ExecutionStatus.COMPLETED
                self.signals.statusChanged.emit(self._status)
                logger.info(f"Session {self._session_id}: Validation completed successfully")
                
        except Exception as e:
            self._status = ExecutionStatus.ERROR
            self.signals.statusChanged.emit(self._status)
            error_msg = f"Session {self._session_id}: Validation error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.signals.error.emit(str(e))
            
        finally:
            # Cleanup
            self._cleanup()
            self.signals.finished.emit()
            
    def _handle_cancellation(self, reason: str):
        """Handle cancellation event"""
        self._status = ExecutionStatus.CANCELLED
        self.signals.statusChanged.emit(self._status)
        self.signals.cancelled.emit(reason)
        logger.info(f"Session {self._session_id}: {reason}")
        
        # Cancel the progress pipeline if it exists
        if self._progress_pipeline:
            self._progress_pipeline.cancel()
            
    def _process_validation_results(self, results: Dict[str, Any]):
        """Process validation results and emit appropriate signals"""
        logger.info(f"Session {self._session_id}: Processing validation results")
        
        # Emit results
        self.signals.result.emit(results)
        
        # Handle new IAG report generation
        if self.generate_reports and 'iag_excel' in self.report_formats:
            self.signals.reportStarted.emit()
            
            try:
                # Save validation results JSON first
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                json_filename = f"{self.analytic_id}_{timestamp}_results.json"
                json_path = os.path.join(self.output_dir, json_filename)
                
                with open(json_path, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                
                logger.info(f"Session {self._session_id}: Saved validation results to {json_path}")
                
                # Generate IAG Excel report
                excel_filename = f"{self.analytic_id}_{timestamp}_report.xlsx"
                excel_path = os.path.join(self.output_dir, excel_filename)
                
                # Use the ValidationPipeline's report generation
                self.pipeline.generate_excel_report(json_path, excel_path)
                
                output_files = [json_path, excel_path]
                
                # Generate individual leader reports if requested
                if self.generate_individual_reports and self.responsible_party_column and self.responsible_party_column != "None":
                    logger.info(f"Session {self._session_id}: Generating individual leader reports")
                    
                    # Create subdirectory for leader reports
                    leader_dir = os.path.join(self.output_dir, f"leader_reports_{timestamp}")
                    os.makedirs(leader_dir, exist_ok=True)
                    
                    # Split the master report
                    leader_files = self.pipeline.split_report_by_leader(excel_path, leader_dir)
                    
                    # Don't add individual leader files to output_files - we'll show just the directory
                    
                    # Emit leader pack completion
                    leader_pack_info = {
                        'type': 'leader_packs',
                        'results': {
                            'success': True,
                            'leader_reports': leader_files,
                            'output_dir': leader_dir
                        }
                    }
                    self.signals.reportCompleted.emit(leader_pack_info)
                
                # Update results with output files
                results['output_files'] = output_files
                
                # Emit report completion
                report_info = {
                    'output_files': output_files,
                    'output_dir': self.output_dir,
                    'session_id': self._session_id,
                    'timestamp': timestamp
                }
                
                self.signals.reportCompleted.emit(report_info)
                logger.info(f"Session {self._session_id}: Reports generated: {output_files}")
                
            except Exception as e:
                error_msg = f"Report generation error: {str(e)}"
                logger.error(f"Session {self._session_id}: {error_msg}", exc_info=True)
                self.signals.reportError.emit(error_msg)
            
    def _cleanup(self):
        """Cleanup resources"""
        # This is where we'd ensure COM objects are released
        # The actual COM cleanup happens in ExcelFormulaProcessor's context manager
        logger.info(f"Session {self._session_id}: Cleanup completed")
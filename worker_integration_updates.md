# CancellableValidationWorker Integration Updates

## 1. Update CancellableValidationWorker Constructor

In `cancellable_validation_worker.py`, update the constructor to handle individual reports:

```python
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
             generate_leader_packs: bool = False,  # This is now individual reports
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
    self.report_formats = report_formats or ['iag_excel']  # Updated default
    self.output_dir = output_dir or './output'
    self.use_parallel = use_parallel
    self.responsible_party_column = responsible_party_column
    self.generate_individual_reports = generate_leader_packs  # Use clearer name internally
    self.analytic_title = analytic_title
    self.use_template = use_template
    
    # ... rest of initialization ...
```

## 2. Update Report Generation Logic

Replace the `_process_validation_results` method:

```python
def _process_validation_results(self, results: Dict[str, Any]):
    """Process validation results and emit appropriate signals"""
    logger.info(f"Session {self._session_id}: Processing validation results")
    
    # Emit results
    self.signals.result.emit(results)
    
    # Handle new report generation
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
                
                # Add leader files to output
                output_files.extend(leader_files.values())
                
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
```

## 3. Remove Old Report Generation Code

Remove or comment out the old leader pack generation section (lines 301-344 in the original):

```python
# DELETE THIS SECTION:
# Handle leader pack generation if requested
if self.generate_leader_packs and self.responsible_party_column and self.responsible_party_column != "None":
    logger.info(f"Session {self._session_id}: Generating leader packs")
    try:
        # ... old leader pack code ...
```

## 4. Update Validation Parameters

In the `run` method, update the validation parameters to use the new format:

```python
# Prepare validation parameters
validation_params = {
    'data_source_path': self.data_source,
    'source_type': 'excel' if str(self.data_source).endswith(('.xlsx', '.xls')) else 'csv',
    'rule_ids': self.rule_ids,
    'selected_sheet': self.sheet_name,
    'analytic_id': self.analytic_id,
    'output_formats': ['json'],  # Only JSON for validation, Excel handled separately
    'use_parallel': getattr(self, 'use_parallel', False),
    'responsible_party_column': getattr(self, 'responsible_party_column', None),
    'progress_callback': progress_callback,
    'analytic_title': self.analytic_title
}
```

## 5. Import Required Modules

Add these imports at the top of the file:

```python
import os
import json
import datetime
from typing import Optional, List, Dict, Any
```

## Summary of Changes:

1. **Updated report formats**: Changed default from `['excel', 'html']` to `['iag_excel']`
2. **New report generation flow**: 
   - First saves JSON results
   - Then generates IAG Excel report using `generate_excel_report()`
   - Optionally splits into individual leader reports using `split_report_by_leader()`
3. **Removed old code**: Deleted the old leader pack generation logic
4. **Better naming**: Internal variable `generate_individual_reports` is clearer than `generate_leader_packs`
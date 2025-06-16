# QA Studio Analytics Runner UI - Reporting Update Guide

## Changes Required for New IAG Reporting System

### 1. Update Checkbox Creation (main_application.py ~line 406-426)

Replace the current checkbox section with:

```python
# Excel report checkbox
self.excel_report_checkbox = QCheckBox("Generate Excel Report")
self.excel_report_checkbox.setChecked(True)
self.excel_report_checkbox.setStyleSheet("background-color: transparent;")
self.excel_report_checkbox.toggled.connect(self._on_report_option_changed)
checkbox_layout.addWidget(self.excel_report_checkbox)

# Remove HTML report checkbox completely
# self.html_report_checkbox = ...  DELETE THIS

# Individual Leader Reports checkbox (renamed and always visible)
self.leader_reports_checkbox = QCheckBox("Generate Individual Leader Reports")
self.leader_reports_checkbox.setChecked(True)  # Checked by default
self.leader_reports_checkbox.setEnabled(True)  # Always enabled
self.leader_reports_checkbox.setStyleSheet("background-color: transparent;")
self.leader_reports_checkbox.setToolTip("Creates individual Excel reports for each audit leader")
checkbox_layout.addWidget(self.leader_reports_checkbox)

# Remove the warning label - no longer needed
# self.leader_packs_warning = ...  DELETE THIS
```

### 2. Update Report Section Visibility (main_application.py ~line 464)

Change from:
```python
report_section.hide()  # Hidden initially
```

To:
```python
report_section.show()  # Always visible
```

### 3. Update start_validation Method (main_application.py ~line 3219-3226)

Replace the report generation options section:

```python
# Collect report generation options
generate_excel = self.excel_report_checkbox.isChecked()
generate_leader_reports = self.leader_reports_checkbox.isChecked() and responsible_party_column is not None

# Always generate JSON results
report_formats = ['json']
if generate_excel:
    report_formats.append('iag_excel')  # New format identifier

output_dir = self.output_dir_edit.text()

# Debug logging
self.log_message(f"Excel report generation: {generate_excel}")
self.log_message(f"Individual leader reports: {generate_leader_reports}")
self.log_message(f"Output directory: {output_dir}")
if generate_leader_reports and not responsible_party_column:
    self.log_message("Individual leader reports requested but no responsible party column selected - will generate master only", "WARNING")
```

### 4. Update Worker Creation (main_application.py ~line 3240)

Update the worker parameters:

```python
self.validation_worker = CancellableValidationWorker(
    pipeline=None,
    data_source=data_source_file,
    sheet_name=sheet_name,
    analytic_id=analytic_id,
    rule_ids=selected_rules,
    generate_reports=generate_excel,  # Changed from generate_reports
    report_formats=report_formats,
    output_dir=output_dir,
    use_parallel=use_parallel,
    responsible_party_column=responsible_party_column,
    generate_leader_reports=generate_leader_reports  # Changed from generate_leader_packs
)
```

### 5. Update CancellableValidationWorker (cancellable_validation_worker.py)

In the `__init__` method (~line 77), change parameter:
```python
generate_leader_reports: bool = False,  # Changed from generate_leader_packs
```

Update the instance variable (~line 93):
```python
self.generate_leader_reports = generate_leader_reports  # Changed from generate_leader_packs
```

### 6. Update Report Generation in Worker (cancellable_validation_worker.py ~line 280)

Replace the entire `_process_validation_results` method:

```python
def _process_validation_results(self, results: Dict[str, Any]):
    """Process validation results and emit appropriate signals"""
    logger.info(f"Session {self._session_id}: Processing validation results")
    
    # Emit results
    self.signals.result.emit(results)
    
    # Handle IAG Excel report generation
    if self.generate_reports and 'iag_excel' in self.report_formats:
        self.signals.reportStarted.emit()
        
        try:
            # Get the JSON results path
            json_path = None
            for output_file in results.get('output_files', []):
                if output_file.endswith('_results.json'):
                    json_path = output_file
                    break
            
            if json_path:
                # Generate IAG Excel report
                output_filename = json_path.replace('_results.json', '_iag_report.xlsx')
                self.pipeline.generate_excel_report(json_path, output_filename)
                
                # Add to output files
                if 'output_files' not in results:
                    results['output_files'] = []
                results['output_files'].append(output_filename)
                
                # Handle individual leader reports if requested
                if self.generate_leader_reports and self.responsible_party_column:
                    logger.info(f"Session {self._session_id}: Generating individual leader reports")
                    
                    leader_files = self.pipeline.split_report_by_leader(
                        output_filename,
                        os.path.join(self.output_dir, f"leader_reports_{self._session_id}")
                    )
                    
                    results['leader_reports'] = leader_files
                    results['output_files'].extend(list(leader_files.values()))
                    
                    self.signals.reportCompleted.emit({
                        'type': 'leader_reports',
                        'files': leader_files,
                        'session_id': self._session_id
                    })
                
                report_info = {
                    'files': results['output_files'],
                    'session_id': self._session_id,
                    'timestamp': datetime.datetime.now().isoformat()
                }
                
                self.signals.reportCompleted.emit(report_info)
                logger.info(f"Session {self._session_id}: Reports generated successfully")
            else:
                logger.error("No JSON results file found for report generation")
                
        except Exception as e:
            error_msg = f"Error generating reports: {str(e)}"
            logger.error(error_msg, exc_info=True)
            self.signals.reportError.emit(error_msg)
```

### 7. Update Results Display (main_application.py ~line 3291)

In `_on_validation_complete`, add handling for the new reports:

```python
def _on_validation_complete(self, results: dict):
    """Handle validation completion."""
    try:
        # ... existing code ...
        
        # Log output files
        if results.get('output_files'):
            self.log_message("Generated files:", "SUCCESS")
            for file in results['output_files']:
                self.log_message(f"  • {file}", "SUCCESS")
        
        # Log leader reports specifically
        if results.get('leader_reports'):
            self.log_message(f"Generated {len(results['leader_reports'])} individual leader reports:", "SUCCESS")
            for leader, filepath in results['leader_reports'].items():
                self.log_message(f"  • {leader}: {os.path.basename(filepath)}", "SUCCESS")
```

### 8. Remove Old Leader Packs References

Search and replace throughout the codebase:
- `generate_leader_packs` → `generate_leader_reports`
- `leader_packs_checkbox` → `leader_reports_checkbox`
- `leader_packs_warning` → Remove completely
- `_on_leader_packs_changed` → `_on_leader_reports_changed` (if exists)

### Summary of Key Changes:

1. **Removed HTML report option** - No longer needed
2. **Renamed "Audit Leader-Specific Workbooks"** to "Generate Individual Leader Reports"
3. **Made report options always visible** - Not hidden until after validation
4. **Both checkboxes checked by default**
5. **Connected to new IAG reporting methods**:
   - `generate_excel_report()` for master report
   - `split_report_by_leader()` for individual files
6. **Simplified logic** - No complex template handling needed

The new flow will be:
1. User selects data and rules
2. Checkboxes are already visible and checked
3. User clicks "Start Validation"
4. System validates data
5. If Excel report checked → Generate IAG master report
6. If Individual reports also checked → Split into leader files
7. All files saved with same timestamp in organized directories
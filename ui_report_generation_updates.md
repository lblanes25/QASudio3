# UI Report Generation Updates

## 1. Update the Report Generation Section UI

Replace the Report Generation section in `create_simple_mode_tab()` method:

```python
# Report Generation Options section (always visible)
report_section = QWidget()
self.report_section = report_section  # Store reference for visibility control
report_section.setStyleSheet(f"""
    QWidget {{
        background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
        border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR}40;
        border-radius: 6px;
        padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
    }}
""")
report_layout = QVBoxLayout(report_section)
report_layout.setContentsMargins(12, 12, 12, 12)
report_layout.setSpacing(8)

# Report options header
report_header = QLabel("Report Generation")
report_header.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
report_header.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.DARK_TEXT}; background-color: transparent;")
report_layout.addWidget(report_header)

# Checkbox frame for report formats
checkbox_frame = QWidget()
checkbox_frame.setStyleSheet("background-color: transparent;")
checkbox_layout = QVBoxLayout(checkbox_frame)
checkbox_layout.setContentsMargins(0, 0, 0, 0)
checkbox_layout.setSpacing(6)

# Excel report checkbox
self.excel_report_checkbox = QCheckBox("Generate Excel Report")
self.excel_report_checkbox.setChecked(True)  # Default checked
self.excel_report_checkbox.setStyleSheet("background-color: transparent;")
self.excel_report_checkbox.setToolTip("Generate comprehensive IAG Summary Report with all validation results")
self.excel_report_checkbox.toggled.connect(self._on_report_option_changed)
checkbox_layout.addWidget(self.excel_report_checkbox)

# Individual Leader Reports checkbox (replaces leader packs)
self.individual_reports_checkbox = QCheckBox("Generate Individual Leader Reports")
self.individual_reports_checkbox.setChecked(True)  # Default checked
self.individual_reports_checkbox.setStyleSheet("background-color: transparent;")
self.individual_reports_checkbox.setToolTip("Split the master report into individual Excel files for each responsible party")
self.individual_reports_checkbox.toggled.connect(self._on_individual_reports_changed)
checkbox_layout.addWidget(self.individual_reports_checkbox)

# Warning label for individual reports (hidden by default)
self.individual_reports_warning = QLabel("⚠️ Select a responsible party column to enable this feature")
self.individual_reports_warning.setStyleSheet(f"""
    color: {AnalyticsRunnerStylesheet.WARNING_COLOR};
    background-color: transparent;
    font-size: 12px;
    padding-left: 20px;
""")
self.individual_reports_warning.setVisible(False)
checkbox_layout.addWidget(self.individual_reports_warning)

report_layout.addWidget(checkbox_frame)

# Output directory selection (same as before)
output_dir_frame = QWidget()
output_dir_frame.setStyleSheet("background-color: transparent;")
output_dir_layout = QHBoxLayout(output_dir_frame)
output_dir_layout.setContentsMargins(0, 0, 0, 0)
output_dir_layout.setSpacing(8)

output_dir_label = QLabel("Output Directory:")
output_dir_label.setStyleSheet("background-color: transparent;")
output_dir_layout.addWidget(output_dir_label)

self.output_dir_edit = QLineEdit("./output")
self.output_dir_edit.setReadOnly(True)
output_dir_layout.addWidget(self.output_dir_edit)

self.output_dir_button = QPushButton("Browse")
self.output_dir_button.setProperty("buttonStyle", "secondary")
self.output_dir_button.clicked.connect(self.browse_output_directory)
self.output_dir_button.setMaximumWidth(80)
output_dir_layout.addWidget(self.output_dir_button)

report_layout.addWidget(output_dir_frame)

# Always visible now
simple_layout.addWidget(report_section)
```

## 2. Update Event Handlers

Replace the event handler methods:

```python
def _on_report_option_changed(self):
    """Handle report option checkbox changes."""
    # Enable/disable individual reports based on Excel report selection
    if not self.excel_report_checkbox.isChecked():
        self.individual_reports_checkbox.setChecked(False)
        self.individual_reports_checkbox.setEnabled(False)
        self.log_message("Individual reports require Excel report to be enabled", "INFO")
    else:
        self.individual_reports_checkbox.setEnabled(True)
    
    reports_enabled = self.excel_report_checkbox.isChecked()
    
    self.output_dir_edit.setEnabled(reports_enabled)
    self.output_dir_button.setEnabled(reports_enabled)
    
    if not reports_enabled:
        self.log_message("Report generation disabled - only JSON results will be saved", "INFO")

def _on_individual_reports_changed(self, checked: bool):
    """Handle individual reports checkbox changes."""
    if checked and self.responsible_party_combo.currentIndex() == 0:  # "None" selected
        self.individual_reports_warning.setVisible(True)
        self.log_message("Individual reports require a responsible party column to be selected", "WARNING")
    else:
        self.individual_reports_warning.setVisible(False)
        if checked:
            self.log_message("Individual Leader Reports will be generated", "INFO")
```

## 3. Update start_validation() Method

Replace the report generation logic in `start_validation()`:

```python
# Check individual reports settings
generate_individual_reports = (self.individual_reports_checkbox.isChecked() and 
                              responsible_party_column is not None and
                              self.excel_report_checkbox.isChecked())

if self.individual_reports_checkbox.isChecked() and not responsible_party_column:
    self.log_message("Individual reports requested but no responsible party column selected - will be skipped", "WARNING")

# Collect report generation options
generate_reports = self.excel_report_checkbox.isChecked()
report_formats = []
if self.excel_report_checkbox.isChecked():
    report_formats.append('iag_excel')  # New format identifier

# Always include JSON for results
report_formats.append('json')

output_dir = self.output_dir_edit.text()

# Debug logging
self.log_message(f"Report generation enabled: {generate_reports}")
self.log_message(f"Report formats requested: {report_formats}")
self.log_message(f"Output directory: {output_dir}")
if generate_individual_reports:
    self.log_message("Individual Leader Reports will be generated", "INFO")

# Create and start cancellable validation worker
self.validation_worker = CancellableValidationWorker(
    pipeline=None,  # Will be created in worker
    data_source=data_source_file,
    sheet_name=sheet_name,
    analytic_id=analytic_id,
    rule_ids=selected_rules,
    generate_reports=generate_reports,
    report_formats=report_formats,
    output_dir=output_dir,
    use_parallel=use_parallel,
    responsible_party_column=responsible_party_column,
    generate_individual_reports=generate_individual_reports  # New parameter
)
```

## 4. Update _on_responsible_party_changed()

Update to handle individual reports warning:

```python
def _on_responsible_party_changed(self, index: int):
    """Handle responsible party column selection changes."""
    # Update individual reports warning visibility
    if self.individual_reports_checkbox.isChecked() and index == 0:  # "None" selected
        self.individual_reports_warning.setVisible(True)
    else:
        self.individual_reports_warning.setVisible(False)
    
    # ... rest of existing code ...
```

## 5. Update CancellableValidationWorker

In `cancellable_validation_worker.py`, update the constructor and run method:

```python
def __init__(self, 
             # ... existing parameters ...
             generate_individual_reports: bool = False):
    super().__init__()
    
    # ... existing initialization ...
    self.generate_individual_reports = generate_individual_reports
    
    # Update default report formats
    self.report_formats = report_formats or ['iag_excel']
```

## 6. Integration with New Reporting Methods

In the validation service or worker, after validation completes:

```python
# Generate reports if requested
if 'iag_excel' in self.report_formats:
    # Generate the IAG Summary Excel report
    excel_path = generate_iag_summary_excel(
        validation_results=results,
        output_path=os.path.join(self.output_dir, f"{self.analytic_id}_report.xlsx")
    )
    output_files.append(excel_path)
    
    # Generate individual leader reports if requested
    if self.generate_individual_reports and self.responsible_party_column:
        individual_files = split_report_by_leader(
            excel_path=excel_path,
            output_dir=self.output_dir,
            responsible_party_column=self.responsible_party_column
        )
        output_files.extend(individual_files)
```

## Summary of Changes

1. **Removed**: HTML report checkbox (not needed)
2. **Updated**: "Generate Excel Report" to use new IAG reporting
3. **Renamed**: "Generate Audit Leader-Specific Workbooks" → "Generate Individual Leader Reports"
4. **Changed**: Both checkboxes are visible by default and checked by default
5. **Connected**: New reporting methods `generate_iag_summary_excel()` and `split_report_by_leader()`
6. **Simplified**: Report format handling to focus on Excel/JSON only

The new flow:
- User selects validation options
- Both report checkboxes are visible and checked by default
- When validation runs, it generates JSON results
- If Excel is checked, it generates the IAG Summary Report
- If Individual Reports is also checked (and a responsible party column is selected), it splits the report
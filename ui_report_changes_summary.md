# UI Report Generation Changes Summary

## Changes Made to main_application.py:

### 1. Updated Checkboxes (lines 419-440)
- **Kept**: "Generate Excel Report" checkbox
  - Added tooltip explaining it generates IAG Summary Report
  - Remains checked by default
  
- **Removed**: "Generate HTML Report" checkbox entirely

- **Replaced**: "Generate Audit Leader-Specific Workbooks" → "Generate Individual Leader Reports"
  - Changed default from unchecked to **checked** 
  - Updated tooltip to explain it splits the master report
  - Variable renamed: `leader_packs_checkbox` → `individual_reports_checkbox`

### 2. Updated Warning Label (lines 443-451)
- Renamed: `leader_packs_warning` → `individual_reports_warning`
- Same functionality - shows when individual reports are checked but no responsible party column selected

### 3. Updated Event Handlers
- **_on_report_option_changed()**: 
  - Now disables individual reports if Excel report is unchecked
  - Simplified logic - only checks for Excel report
  
- **_on_leader_packs_changed()** → **_on_individual_reports_changed()**:
  - Renamed method
  - Updated log messages

- **_on_responsible_party_changed()**:
  - Updated to reference `individual_reports_checkbox` instead of `leader_packs_checkbox`

### 4. Updated Validation Start Logic (lines ~3290-3328)
- Changed variable: `generate_leader_packs` → `generate_individual_reports`
- Updated report format from 'excel' to 'iag_excel' to indicate new reporting system
- Removed HTML report format handling
- Updated log messages

## What Still Needs to Be Done:

### 1. Update CancellableValidationWorker
The worker needs to handle the new 'iag_excel' format and call the new reporting methods:
- `generate_iag_summary_excel()`
- `split_report_by_leader()` (if individual reports are requested)

### 2. Import New Reporting Methods
Add imports for the new reporting functions from wherever they're implemented.

### 3. Remove Old Reporting Code
Remove any code that handles the old report generation logic.

## New UI Behavior:
1. Both checkboxes are visible immediately (not hidden until after validation)
2. Both are checked by default
3. If Excel report is unchecked, individual reports automatically unchecks and disables
4. Warning still shows if individual reports are selected without a responsible party column
5. Only generates JSON and IAG Excel reports (no HTML)
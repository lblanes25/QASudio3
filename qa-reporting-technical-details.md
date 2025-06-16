# QA Studio Excel Reporting - Technical Implementation Details

## Data Integration Points

### JSON Validation Results Location
- **Path**: `output/Analytics_Validation_[timestamp]_results.json`
- **Key Fields to Extract**:
  - `grouped_summary` → Audit leader compliance counts
  - `rule_results` → Individual rule compliance details
  - `data_metrics.row_count` → Population size
  - `data_source` → Source file name

### Rule Metadata Location
- **Path**: `data/rules/[rule-id].json`
- **Key Fields**:
  - `metadata.title` → Test name for tab
  - `metadata.severity` → Risk rating (1-3, with 1 being most severe)
  - `description` → Test description
  - `metadata.responsible_party_column` → Leader grouping column
  - `threshold` → Error threshold for the rule

## Phase 1: Enhanced IAG Summary Report Generation (Weeks 1-6)

### Week 1-2: Core Functions with IAG Scoring

**1.1 Add IAGScoringCalculator Class (The ONE new class we need):**
```python
# Add to core/scoring/iag_scoring_calculator.py
class IAGScoringCalculator:
    """Implements IAG scoring methodology exactly as defined"""
    
    def __init__(self):
        self.weights = {'GC': 5, 'PC': 3, 'DNC': 1, 'NA': 0}
        self.thresholds = {'GC': 0.80, 'PC': 0.50, 'DNC': 0.00}
    
    def calculate_weighted_score(self, gc_count, pc_count, dnc_count, total_count):
        """Calculate weighted score using exact IAG formula"""
        if total_count == 0:
            return "N/A"
        
        weighted_sum = (gc_count * self.weights['GC'] + 
                       pc_count * self.weights['PC'] + 
                       dnc_count * self.weights['DNC'])
        max_possible = total_count * self.weights['GC']
        return weighted_sum / max_possible
    
    def assign_rating(self, weighted_score):
        """Assign rating based on IAG thresholds"""
        if weighted_score == "N/A":
            return "N/A"
        elif weighted_score >= self.thresholds['GC']:
            return "GC"
        elif weighted_score < self.thresholds['PC']:
            return "DNC"
        else:
            return "PC"
```

**1.2 Replace simple report with complete IAG Summary in `services/validation_service.py`:**
```python
def generate_excel_report(validation_results_path, output_path):
    """Generate complete IAG Summary Report with all 3 sections"""
    # Read validation results
    with open(validation_results_path, 'r') as f:
        results = json.load(f)
    
    # Create IAG Summary Report
    wb = Workbook()
    ws = wb.active
    ws.title = "IAG Summary Report"
    
    # Get responsible party column from first rule
    first_rule_id = list(results['rule_results'].keys())[0]
    rule_path = f"data/rules/{first_rule_id}.json"
    with open(rule_path, 'r') as f:
        rule_meta = json.load(f)
    responsible_party_column = rule_meta['metadata'].get('responsible_party_column', 'AuditLeader')
    
    # Section 1: IAG Overall Results (rows 3-10)
    current_row = generate_section1_iag_overall(ws, results['rule_results'], start_row=3)
    
    # Section 2: Audit Leader Results (2 rows below Section 1)
    current_row = generate_section2_leader_results(ws, results, 
                                                   responsible_party_column, 
                                                   start_row=current_row+2)
    
    # Section 3: Detailed Analytics (2 rows below Section 2)
    generate_section3_detailed_analytics(ws, results, 
                                       responsible_party_column, 
                                       start_row=current_row+2)
    
    # Generate individual test tabs
    for rule_id, rule_result in results['rule_results'].items():
        create_test_tab(wb, rule_id, rule_result, results)
    
    wb.save(output_path)
```

**1.3 Section 1 - IAG Overall Results:**
```python
def generate_section1_iag_overall(ws, rule_results, start_row=3):
    """Generate Section 1: IAG Overall Results and Rating"""
    # Calculate totals across ALL leaders and rules
    total_gc = sum(r.get('gc_count', 0) for r in rule_results.values())
    total_pc = sum(r.get('pc_count', 0) for r in rule_results.values())
    total_dnc = sum(r.get('dnc_count', 0) for r in rule_results.values())
    total_tests = total_gc + total_pc + total_dnc
    
    calculator = IAGScoringCalculator()
    weighted_score = calculator.calculate_weighted_score(total_gc, total_pc, total_dnc, total_tests)
    rating = calculator.assign_rating(weighted_score)
    
    # Write header
    ws[f'A{start_row}'] = "IAG Overall Results and Rating"
    
    # Write metrics
    ws[f'A{start_row+1}'] = "Total Score:"
    ws[f'B{start_row+1}'] = (total_gc * 5) + (total_pc * 3) + (total_dnc * 1)
    
    ws[f'A{start_row+2}'] = "GC Score:"
    ws[f'B{start_row+2}'] = total_gc * 5
    
    ws[f'A{start_row+3}'] = "PC Score:"
    ws[f'B{start_row+3}'] = total_pc * 3
    
    ws[f'A{start_row+4}'] = "DNC Score:"
    ws[f'B{start_row+4}'] = total_dnc * 1
    
    ws[f'A{start_row+5}'] = "Total Count of Applicable Tests Across Audit Leaders:"
    ws[f'B{start_row+5}'] = total_tests
    
    ws[f'A{start_row+6}'] = "Weighted Score Across Audit Leaders:"
    ws[f'B{start_row+6}'] = f"{weighted_score*100:.1f}%" if weighted_score != "N/A" else "N/A"
    
    ws[f'A{start_row+7}'] = "Weighted Rating Across Audit Leaders:"
    ws[f'B{start_row+7}'] = rating
    
    # Override fields (blank for manual entry)
    ws[f'D{start_row+7}'] = "Override Rating:"
    ws[f'E{start_row+7}'] = ""  # Blank for manual entry
    ws[f'F{start_row+7}'] = "Rationale:"
    ws[f'G{start_row+7}'] = ""  # Blank for manual entry
    
    return start_row + 8
```

**1.4 Section 2 - Audit Leader Results:**
```python
def generate_section2_leader_results(ws, results, responsible_party_column, start_row):
    """Generate Section 2: Audit Leader Overall Results and Ratings"""
    # Header
    ws[f'A{start_row}'] = "Audit Leader Overall Results and Ratings"
    
    # Column headers
    headers = ["Audit Leader Name", "Total Tests", "GC Count", "PC Count", "DNC Count", 
               "Weighted Score", "Weighted Average Rating", "Volume of Sampled Entities",
               "Overridden AL Rating", "Rating Override Rationale"]
    
    for i, header in enumerate(headers):
        ws.cell(row=start_row+1, column=i+1, value=header)
    
    # Get leader summary data
    calculator = IAGScoringCalculator()
    row = start_row + 2
    
    for leader, stats in results.get('grouped_summary', {}).items():
        ws[f'A{row}'] = leader
        ws[f'B{row}'] = stats['total_rules']
        ws[f'C{row}'] = stats.get('GC', 0)
        ws[f'D{row}'] = stats.get('PC', 0)
        ws[f'E{row}'] = stats.get('DNC', 0)
        
        # Calculate weighted score
        score = calculator.calculate_weighted_score(
            stats.get('GC', 0), stats.get('PC', 0), stats.get('DNC', 0), stats['total_rules']
        )
        ws[f'F{row}'] = f"{score*100:.1f}%" if score != "N/A" else "N/A"
        ws[f'G{row}'] = calculator.assign_rating(score)
        
        # Volume (from data metrics if available)
        ws[f'H{row}'] = results.get('data_metrics', {}).get('row_count', 0)
        
        # Override fields (blank)
        ws[f'I{row}'] = ""  # Overridden AL Rating
        ws[f'J{row}'] = ""  # Rating Override Rationale
        
        row += 1
    
    return row
```

**1.5 Section 3 - Detailed Analytics (Fixed with per-leader per-rule data):**
```python
def generate_section3_detailed_analytics(ws, results, responsible_party_column, start_row):
    """Generate Section 3: Detailed Analytics Section with per-leader per-rule results"""
    # Header
    ws[f'A{start_row}'] = "Audit Leader Average Test Results"
    
    # Get rule metadata and load actual rule results
    rule_info = {}
    for rule_id in results['rule_results']:
        rule_path = f"data/rules/{rule_id}.json"
        with open(rule_path, 'r') as f:
            rule_meta = json.load(f)
            rule_info[rule_id] = {
                'title': rule_meta['metadata']['title'],
                'threshold': rule_meta.get('threshold', 0.0),
                'severity': rule_meta['metadata'].get('severity', 'medium'),
                'risk_level': rule_meta['metadata'].get('risk_level', 3),
                'analytic_id': rule_meta['metadata'].get('analytic_id', rule_id)
            }
    
    # Column headers
    col = 1
    ws.cell(row=start_row+1, column=col, value="Audit Leader")
    col += 1
    
    # Rule columns with metadata
    for rule_id, info in rule_info.items():
        ws.cell(row=start_row+1, column=col, value=info['title'])
        ws.cell(row=start_row+2, column=col, value=f"Threshold: {info['threshold']*100:.0f}%")
        ws.cell(row=start_row+3, column=col, value=f"Risk Level: {info['risk_level']}")
        col += 1
    
    # Summary columns
    for header in ["Samples Tested", "GC Count", "PC Count", "DNC Count", "NA Count",
                   "Total Applicable", "Average Score", "Average Rating"]:
        ws.cell(row=start_row+1, column=col, value=header)
        col += 1
    
    # Data rows - get actual per-leader per-rule results
    calculator = IAGScoringCalculator()
    row = start_row + 4
    
    for leader, stats in results.get('grouped_summary', {}).items():
        ws[f'A{row}'] = leader
        
        # Get per-rule results for this leader
        col = 2
        for rule_id in rule_info:
            # Extract actual result from rule's party_results
            if 'party_results' in results['rule_results'][rule_id]:
                party_results = results['rule_results'][rule_id]['party_results']
                if leader in party_results:
                    status = party_results[leader].get('status', 'NA')
                else:
                    status = 'NA'  # Rule doesn't apply to this leader
            else:
                status = 'NA'  # No party results available
                
            ws.cell(row=row, column=col, value=status)
            # Apply color based on status
            apply_rating_color(ws.cell(row=row, column=col))
            col += 1
        
        # Summary data - use entity_count for samples tested
        ws.cell(row=row, column=col, value=stats.get('entity_count', 0))
        ws.cell(row=row, column=col+1, value=stats.get('GC', 0))
        ws.cell(row=row, column=col+2, value=stats.get('PC', 0))
        ws.cell(row=row, column=col+3, value=stats.get('DNC', 0))
        ws.cell(row=row, column=col+4, value=stats.get('NA', 0))
        
        # Total applicable (excluding NA)
        total_applicable = stats['total_rules'] - stats.get('NA', 0)
        ws.cell(row=row, column=col+5, value=total_applicable)
        
        # Average score using IAG calculator (excluding NA)
        score = calculator.calculate_weighted_score(
            stats.get('GC', 0), stats.get('PC', 0), stats.get('DNC', 0), total_applicable
        )
        ws.cell(row=row, column=col+6, value=f"{score*100:.1f}%" if score != "N/A" else "N/A")
        ws.cell(row=row, column=col+7, value=calculator.assign_rating(score))
        apply_rating_color(ws.cell(row=row, column=col+7))
        
        row += 1
```

**1.6 Column Width Formatting:**
```python
def apply_column_widths(ws):
    """Apply appropriate column widths for better readability"""
    # Set column widths based on content
    ws.column_dimensions['A'].width = 30  # Audit Leader names
    
    # For test columns, use medium width
    for col in range(2, ws.max_column - 7):  # Test columns
        ws.column_dimensions[get_column_letter(col)].width = 20
    
    # Summary columns can be narrower
    for col in range(ws.max_column - 6, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(col)].width = 12
```

### Week 3-4: Test Tab Implementation

**3.1 Enhanced Individual Test Tab Generator with Summary and Detail Sections:**
```python
def create_test_tab(wb, rule_id, rule_result, full_results):
    """Create test tab with both leader summary and detailed item results"""
    # Load rule metadata
    rule_path = f"data/rules/{rule_id}.json"
    with open(rule_path, 'r') as f:
        rule_meta = json.load(f)
    
    ws = wb.create_sheet(title=rule_meta['metadata']['title'][:31])
    
    # SECTION 1: Test Header (rows 1-5)
    ws['A1'] = "Test Name:"
    ws['B1'] = rule_meta['metadata']['title']
    ws['A2'] = "Description:"
    ws['B2'] = rule_meta['description']
    ws['A3'] = "Risk Rating:"
    ws['B3'] = rule_meta['metadata']['severity'].upper()
    ws['A4'] = "Population:"
    ws['B4'] = full_results['data_metrics']['row_count']
    ws['A5'] = "Error Threshold:"
    ws['B5'] = f"{rule_meta.get('threshold', 0.0) * 100:.0f}%"
    
    # Apply header formatting
    for row in range(1, 6):
        ws[f'A{row}'].font = Font(bold=True)
    
    # SECTION 2: Leader Summary (starting row 7)
    ws['A7'] = "Audit Leader Summary"
    ws['A7'].font = Font(bold=True, size=12)
    
    # Leader summary column headers
    headers = ["Audit Leader", "Items Tested", "GC", "PC", "DNC", "NA", 
               "Compliance Rate", "Status"]
    for col, header in enumerate(headers, 1):
        ws.cell(row=8, column=col, value=header)
        ws.cell(row=8, column=col).font = Font(bold=True)
        ws.cell(row=8, column=col).border = Border(bottom=Side(style='thin'))
    
    # Process leader results from party_results if available
    current_row = 9
    if 'party_results' in rule_result:
        for leader, leader_result in sorted(rule_result['party_results'].items()):
            ws[f'A{current_row}'] = leader
            ws[f'B{current_row}'] = leader_result.get('item_count', 0)
            ws[f'C{current_row}'] = leader_result.get('gc_count', 0)
            ws[f'D{current_row}'] = leader_result.get('pc_count', 0)
            ws[f'E{current_row}'] = leader_result.get('dnc_count', 0)
            ws[f'F{current_row}'] = leader_result.get('na_count', 0)
            
            # Calculate compliance rate
            total_applicable = (leader_result.get('gc_count', 0) + 
                              leader_result.get('pc_count', 0) + 
                              leader_result.get('dnc_count', 0))
            if total_applicable > 0:
                compliance_rate = leader_result.get('gc_count', 0) / total_applicable
                ws[f'G{current_row}'] = compliance_rate
                ws[f'G{current_row}'].number_format = '0.0%'
            else:
                ws[f'G{current_row}'] = "N/A"
            
            ws[f'H{current_row}'] = leader_result.get('status', 'NA')
            apply_rating_color(ws[f'H{current_row}'])
            
            current_row += 1
    
    # SECTION 3: Detailed Results (starting ~row 15)
    detail_start_row = current_row + 3
    ws[f'A{detail_start_row}'] = "Detailed Test Results (100% Population Coverage)"
    ws[f'A{detail_start_row}'].font = Font(bold=True, size=12)
    
    # Parse formula to determine which fields to display
    formula_fields = extract_fields_from_formula(rule_meta['formula'])
    
    # Detail section headers
    detail_headers = ["Item ID", "Audit Leader"] + formula_fields + \
                    ["Status", "Failure Reason", "Internal Notes", "Audit Leader Response"]
    
    header_row = detail_start_row + 1
    for col, header in enumerate(detail_headers, 1):
        ws.cell(row=header_row, column=col, value=header)
        ws.cell(row=header_row, column=col).font = Font(bold=True)
        ws.cell(row=header_row, column=col).border = Border(bottom=Side(style='thin'))
    
    # Get detailed results from validation data
    # Note: This requires storing item-level results during validation
    detail_row = header_row + 1
    
    # Load the actual test data and results
    if 'result_df' in rule_result:  # If we have detailed results
        result_df = rule_result['result_df']
        result_column = rule_result.get('result_column', f'Result_{rule_meta["name"]}')
        
        # Sort by status: DNC first, then PC, then GC
        status_order = {'DNC': 0, 'PC': 1, 'GC': 2, 'NA': 3}
        result_df['sort_order'] = result_df[result_column].map(status_order)
        result_df = result_df.sort_values('sort_order')
        
        # Write each row
        for idx, row in result_df.iterrows():
            ws.cell(row=detail_row, column=1, value=row.get('AuditEntityID', idx))
            ws.cell(row=detail_row, column=2, value=row.get('AuditLeader', ''))
            
            # Write formula field values
            col_offset = 3
            for field in formula_fields:
                ws.cell(row=detail_row, column=col_offset, value=row.get(field, ''))
                col_offset += 1
            
            # Status
            status = row[result_column]
            ws.cell(row=detail_row, column=col_offset, value=status)
            apply_rating_color(ws.cell(row=detail_row, column=col_offset))
            
            # Failure reason (populate for DNC/PC items)
            if status in ['DNC', 'PC']:
                ws.cell(row=detail_row, column=col_offset+1, 
                       value=rule_meta.get('metadata', {}).get('error_message', ''))
            
            # Leave Internal Notes and Audit Leader Response blank
            # These are columns col_offset+2 and col_offset+3
            
            detail_row += 1
    
    # Apply column widths
    ws.column_dimensions['A'].width = 20
    ws.column_dimensions['B'].width = 25
    for col in range(3, len(detail_headers) + 1):
        ws.column_dimensions[get_column_letter(col)].width = 15

def extract_fields_from_formula(formula):
    """Extract field names from Excel formula (e.g., [FieldName])"""
    import re
    # Find all bracketed field names in the formula
    fields = re.findall(r'\[([^\]]+)\]', formula)
    return list(set(fields))  # Remove duplicates
```

**3.2 Implementation Notes for Test Tabs:**

1. **Data Requirements:**
   - Store `result_df` in rule evaluation results during validation
   - Include item-level pass/fail status and responsible party assignment
   - Preserve all data fields used in rule formulas

2. **Leader-Specific Filtering:**
   ```python
   def filter_test_tab_for_leader(ws, leader_name):
       """Filter detail section to show only specific leader's items"""
       # Implementation would hide/remove rows not matching the leader
   ```

3. **Dynamic Field Display:**
   - Parse rule formula to extract referenced fields
   - Only show columns for fields actually used in the validation
   - Maintains relevance and reduces clutter

4. **Status Sorting:**
   - Failures (DNC) appear at top for easy review
   - Partial compliance (PC) items next
   - Successful items (GC) at bottom
   - Helps auditors focus on issues first

### Week 5-6: Color Coding & Formatting

**5.1 Enhanced Color Application with NA handling:**
```python
def apply_rating_color(cell):
    """Apply IAG-specific colors to rating cells"""
    if cell.value == 'GC':
        cell.fill = PatternFill("solid", start_color="90EE90")  # Light green
    elif cell.value == 'PC':
        cell.fill = PatternFill("solid", start_color="FFFF99")  # Light yellow
    elif cell.value == 'DNC':
        cell.fill = PatternFill("solid", start_color="FF6B6B")  # Light red
    elif cell.value == 'NA' or cell.value == 'N/A':
        cell.fill = PatternFill("solid", start_color="D3D3D3")  # Gray
        cell.font = Font(italic=True)  # Italicize NA values for distinction

def apply_iag_formatting(wb):
    """Apply formatting to IAG Summary Report sections"""
    ws = wb["IAG Summary Report"]
    
    # Bold headers for each section
    ws['A3'].font = Font(bold=True)  # Section 1 header
    ws['A12'].font = Font(bold=True) # Section 2 header (example row)
    ws['A20'].font = Font(bold=True) # Section 3 header (example row)
    
    # Apply colors to rating cells in Section 2
    for row in range(14, ws.max_row + 1):
        if ws[f'G{row}'].value in ['GC', 'PC', 'DNC', 'NA']:
            apply_rating_color(ws[f'G{row}'])
```

## Phase 2: Leader File Splitting (Weeks 7-9)

### Week 7-8: Split Logic

**7.1 Add to validation_service.py:**
```python
def split_report_by_leader(master_file_path, output_dir):
    """Split master Excel into individual leader files"""
    wb = load_workbook(master_file_path)
    
    # Get unique leaders from IAG Summary
    summary_ws = wb['IAG Summary']
    leaders = []
    for row in range(2, summary_ws.max_row + 1):
        leader = summary_ws[f'A{row}'].value
        if leader:
            leaders.append(leader)
    
    # Create individual files
    for leader in leaders:
        leader_wb = Workbook()
        
        # Copy IAG Summary with only this leader's row
        copy_iag_summary_for_leader(wb, leader_wb, leader)
        
        # Copy test tabs with only this leader's data
        for sheet_name in wb.sheetnames[1:]:  # Skip IAG Summary
            copy_test_tab_for_leader(wb[sheet_name], leader_wb, leader)
        
        # Save
        filename = f"QA_Results_{leader.replace(' ', '_')}_{datetime.now():%Y%m%d}.xlsx"
        leader_wb.save(os.path.join(output_dir, filename))
```

### Week 9: File Management

**9.1 Simple Directory Structure:**
```python
def organize_report_files(validation_results_path):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create directories
    os.makedirs(f"output/reports/{timestamp}/Master", exist_ok=True)
    os.makedirs(f"output/reports/{timestamp}/Leaders", exist_ok=True)
    
    # Generate master report
    master_path = f"output/reports/{timestamp}/Master/QA_Results_Master_{timestamp}.xlsx"
    generate_excel_report(validation_results_path, master_path)
    
    # Split by leader
    split_report_by_leader(master_path, f"output/reports/{timestamp}/Leaders")
```

## Phase 3: Trend Analysis with IAG Scores (Weeks 10-12)

### Week 10-11: Historical Data Reading with IAG Scoring

**11.1 Enhanced Trend Calculation with IAG Scores:**
```python
def calculate_iag_trends(current_results_path, historical_results_paths):
    """Calculate period-over-period trends using IAG scoring"""
    trends = {}
    calculator = IAGScoringCalculator()
    
    # Read current results
    with open(current_results_path, 'r') as f:
        current = json.load(f)
    
    # Read historical results
    historical = []
    for path in sorted(historical_results_paths)[-3:]:  # Last 3 periods
        with open(path, 'r') as f:
            historical.append(json.load(f))
    
    # Calculate leader trends with IAG scores
    for leader in current['grouped_summary']:
        stats = current['grouped_summary'][leader]
        
        # Current IAG score
        current_score = calculator.calculate_weighted_score(
            stats.get('GC', 0), stats.get('PC', 0), stats.get('DNC', 0), stats['total_rules']
        )
        current_rating = calculator.assign_rating(current_score)
        
        trends[leader] = {
            'current_score': current_score,
            'current_rating': current_rating,
            'historical_scores': [],
            'historical_ratings': [],
            'trend_direction': 'stable'
        }
        
        # Get historical IAG scores
        for hist in historical:
            if leader in hist['grouped_summary']:
                hist_stats = hist['grouped_summary'][leader]
                hist_score = calculator.calculate_weighted_score(
                    hist_stats.get('GC', 0), hist_stats.get('PC', 0), 
                    hist_stats.get('DNC', 0), hist_stats['total_rules']
                )
                trends[leader]['historical_scores'].append(hist_score)
                trends[leader]['historical_ratings'].append(calculator.assign_rating(hist_score))
        
        # Trend direction based on IAG scores
        if len(trends[leader]['historical_scores']) > 0 and current_score != "N/A":
            last_score = trends[leader]['historical_scores'][-1]
            if last_score != "N/A":
                diff = current_score - last_score
                trends[leader]['trend_direction'] = 'up' if diff > 0.05 else 'down' if diff < -0.05 else 'stable'
    
    return trends
```

### Week 12: Add Trend Tab with IAG Scores

**12.1 Enhanced Trend Tab with IAG Scores:**
```python
def add_iag_trend_tab(wb, trends):
    """Add trend analysis tab with IAG scores and ratings"""
    ws = wb.create_sheet(title="IAG Trend Analysis")
    
    # Headers
    headers = ["Audit Leader", "Current IAG Score", "Current Rating", 
               "Previous Score", "Previous Rating", "Score Change", "Trend"]
    for i, header in enumerate(headers):
        ws.cell(row=1, column=i+1, value=header)
    
    # Data
    row = 2
    for leader, data in trends.items():
        ws[f'A{row}'] = leader
        
        # Current period
        if data['current_score'] != "N/A":
            ws[f'B{row}'] = f"{data['current_score']*100:.1f}%"
        else:
            ws[f'B{row}'] = "N/A"
        ws[f'C{row}'] = data['current_rating']
        
        # Previous period
        if data['historical_scores']:
            prev_score = data['historical_scores'][-1]
            if prev_score != "N/A":
                ws[f'D{row}'] = f"{prev_score*100:.1f}%"
                ws[f'F{row}'] = f"{(data['current_score'] - prev_score)*100:+.1f}%"
            else:
                ws[f'D{row}'] = "N/A"
                ws[f'F{row}'] = "N/A"
            ws[f'E{row}'] = data['historical_ratings'][-1]
        
        ws[f'G{row}'] = data['trend_direction']
        
        # Apply rating colors
        apply_rating_color(ws[f'C{row}'])
        if data['historical_ratings']:
            apply_rating_color(ws[f'E{row}'])
        
        # Trend formatting
        if data['trend_direction'] == 'up':
            ws[f'G{row}'].font = Font(color="00AA00")  # Green
            ws[f'G{row}'].value = "↑ Improving"
        elif data['trend_direction'] == 'down':
            ws[f'G{row}'].font = Font(color="AA0000")  # Red
            ws[f'G{row}'].value = "↓ Declining"
        else:
            ws[f'G{row}'].value = "→ Stable"
        
        row += 1
```

## Phase 4: Testing Approach (Weeks 13-16)

### Week 13-14: Simple Test Cases

**14.1 Basic Test Function:**
```python
def test_report_generation():
    """Test with real validation data"""
    # Use most recent validation results
    latest_results = sorted(glob.glob("output/*_results.json"))[-1]
    
    # Generate report
    output_path = "test_report.xlsx"
    generate_excel_report(latest_results, output_path)
    
    # Basic checks
    wb = load_workbook(output_path)
    assert "IAG Summary" in wb.sheetnames
    assert len(wb.sheetnames) > 1  # Has test tabs
    
    # Check data populated
    summary = wb["IAG Summary"]
    assert summary['A2'].value is not None  # Has leader data
    
    print(f"Test passed - generated {len(wb.sheetnames)} tabs")
```

### Week 15-16: Integration Points

**16.1 Add to Main Application UI:**
```python
# In ui/analytics_runner/main_application.py, add button:
self.generate_report_btn = QPushButton("Generate Excel Report")
self.generate_report_btn.clicked.connect(self.generate_excel_report)

def generate_excel_report(self):
    if self.last_validation_results:
        output_path = f"output/QA_Report_{datetime.now():%Y%m%d_%H%M%S}.xlsx"
        generate_excel_report(self.last_validation_results, output_path)
        QMessageBox.information(self, "Success", f"Report saved to {output_path}")
```

## Data Volume Considerations

Based on validation results:
- Typical population: 30-100 rows
- Number of rules: 5-10 per run
- Number of audit leaders: 3-5
- File sizes: < 1MB per report

No streaming or optimization needed for these volumes.

## Key Implementation Notes

1. **ONE new class** - IAGScoringCalculator for exact IAG formula implementation
2. **Use existing JSON** - Don't create new storage
3. **Direct OpenPyXL calls** - No abstraction layers
4. **IAG-specific colors** - GC=Green, PC=Yellow, DNC=Red, NA=Gray
5. **Simple file I/O** - No distribution pipeline
6. **Minimal error handling** - Just try/except around file operations

## Required OpenPyXL Imports
```python
from openpyxl import Workbook, load_workbook
from openpyxl.styles import PatternFill, Font, Alignment
from openpyxl.utils import get_column_letter
```

## Summary of IAG Integration Changes

### What Changed from Original Plan
1. **Enhanced IAG Summary Report** - Replaced simple summary with 3-section IAG report
2. **IAG Scoring Calculator** - Added ONE class to implement exact scoring formula
3. **Weighted Scores** - All calculations now use IAG methodology (GC=5, PC=3, DNC=1, NA=0)
4. **Rating Thresholds** - GC≥80%, PC=50-79%, DNC<50%
5. **Trend Analysis** - Now uses IAG scores instead of simple compliance rates
6. **NA Status Support** - Added "Not Applicable" status for rules that don't apply to certain leaders
7. **Entity Volume Tracking** - Added unique entity counts per audit leader
8. **Enhanced Metadata** - Added risk_level, error_threshold, and out_of_scope fields to rules

### What Stayed the Same
1. **File Structure** - Still uses existing JSON validation results
2. **Implementation Approach** - Still simple functions, not complex architectures
3. **Leader Splitting** - Works exactly as originally planned
4. **Testing Approach** - Same simple test with real data
5. **UI Integration** - Still just one button to generate reports

### Critical IAG Formula Implementation
```python
# The exact IAG weighted score formula
weighted_score = ((gc_count * 5) + (pc_count * 3) + (dnc_count * 1)) / (total_count * 5)

# Rating assignment
if weighted_score >= 0.80:
    rating = "GC"
elif weighted_score < 0.50:
    rating = "DNC"
else:
    rating = "PC"
```

This ensures compliance with internal audit requirements while keeping the implementation minimal and focused.

### Handling NA (Not Applicable) Rules

**When rules don't apply to certain leaders:**
1. **Rule Applicability** - Use `applicability_formula` field in rule metadata to define when a rule applies
2. **Compliance Calculation** - NA items are excluded from compliance rate calculations
3. **IAG Scoring** - NA has weight of 0 and doesn't count toward total applicable tests
4. **Reporting** - NA status shown in gray with italic text to distinguish from compliance statuses
5. **Entity Counts** - Each leader shows their specific entity count, not total population

**Example NA scenarios:**
- A rule only applies to certain departments
- A rule only applies when specific conditions are met
- A leader has no entities matching the rule criteria

**JSON structure for NA tracking:**
```json
"grouped_summary": {
    "Leader Name": {
        "total_rules": 7,
        "GC": 4,
        "PC": 1,
        "DNC": 1,
        "NA": 1,
        "compliance_rate": 0.6667,  // 4/(7-1) = 4/6
        "entity_count": 150
    }
}
```
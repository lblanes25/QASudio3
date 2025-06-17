# Project Plan: Secondary Source File Integration (Final Version)

## Executive Summary
Enable the validation system to perform lookups against secondary data sources through a smart, zero-configuration LOOKUP function that automatically discovers and uses any files loaded in the session.

## Core Concept
**Zero Configuration Lookups**: Any file loaded in the application becomes automatically available for LOOKUP operations. No setup, no configuration files, no mapping - just load and use.

## Use Cases

1. **Employee Level Validation**: Load HR file, verify reviewer is senior to submitter
2. **Department Validation**: Load department data, ensure cross-department approvals
3. **Vendor Status Checks**: Load vendor list, validate active vendors only
4. **Dynamic Authority Limits**: Load authority matrix, check approval limits

## Technical Architecture

### Smart Lookup System

```python
# Core concept: Any loaded file is searchable
# User loads files in any order:
# - audit_data.xlsx
# - hr_master.xlsx  
# - vendors.csv

# LOOKUP automatically finds the right data:
formula = "LOOKUP([ReviewerID], 'EmployeeID', 'Level')"  # Searches all files
formula = "LOOKUP([VendorID], 'Status')"                 # Smart column matching
formula = "LOOKUP([ReviewerID], 'hr_master', 'Level')"   # Optional hint
```

## Rule Persistence & Portability

### How LOOKUP Rules Are Saved
Rules containing LOOKUP functions are saved exactly like any other formula - as plain text strings. The LOOKUP function is just another Excel-like function in the formula. No special handling is required.

```json
{
  "id": "reviewer-level-check",
  "name": "Reviewer Level Validation",
  "condition": "LOOKUP([ReviewerID], 'Level') > LOOKUP([SubmitterID], 'Level')",
  "message": "Reviewer must be at least one level above submitter",
  "severity": "high"
}
```

**Key Points:**
- LOOKUP is stored as part of the formula string, just like SUM() or IF()
- No file paths or data are embedded in the rule
- Missing lookup files are handled gracefully at runtime
- Rules remain portable between users and systems
- If lookup data is not available, the lookup returns None and the comparison fails appropriately

## Implementation Phases

## Phase 1: Smart LOOKUP Function (Week 1)

### Goals
Implement intelligent LOOKUP function that works with zero configuration.

### Tasks

#### 1. Create SmartLookupManager with Lazy Loading Support

```python
class SmartLookupManager:
    def __init__(self):
        self.loaded_files = {}      # filepath -> DataFrame
        self.file_metadata = {}     # filepath -> metadata (columns, rows, size)
        self.column_index = {}      # column -> [filepaths]
        self.file_aliases = {}      # friendly name -> filepath
        self.lookup_cache = {}      # cache for performance
        self.lazy_threshold_mb = 50 # Files > 50MB use lazy loading
    
    def add_file(self, filepath: str, df: pd.DataFrame = None, 
                 alias: str = None, lazy: bool = None):
        """Register file for lookups with optional lazy loading"""
        file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
        
        # Auto-determine lazy loading based on file size
        if lazy is None:
            lazy = file_size_mb > self.lazy_threshold_mb
        
        if lazy or df is None:
            # Lazy loading - just store metadata
            self.file_metadata[filepath] = {
                'columns': self._peek_columns(filepath),
                'row_count': self._count_rows(filepath),
                'size_mb': file_size_mb,
                'lazy': True
            }
            logger.info(f"Registered {alias or Path(filepath).stem} for lazy loading "
                       f"({file_size_mb:.1f}MB, {self.file_metadata[filepath]['row_count']:,} rows)")
        else:
            # Full loading
            self.loaded_files[filepath] = df
            self.file_metadata[filepath] = {
                'columns': list(df.columns),
                'row_count': len(df),
                'size_mb': file_size_mb,
                'lazy': False
            }
        
        # Create friendly alias
        if alias:
            self.file_aliases[alias] = filepath
        else:
            alias = Path(filepath).stem
            self.file_aliases[alias] = filepath
        
        # Index columns for fast discovery
        for col in self.file_metadata[filepath]['columns']:
            if col not in self.column_index:
                self.column_index[col] = []
            self.column_index[col].append(filepath)
        
        # Create indices for loaded data
        if not lazy and df is not None:
            self._create_lookup_indices(filepath, df)
    
    def _peek_columns(self, filepath: str) -> List[str]:
        """Get column names without loading full file"""
        ext = Path(filepath).suffix.lower()
        if ext in ['.csv', '.tsv']:
            # Read just first line
            with open(filepath, 'r', encoding='utf-8') as f:
                header = f.readline().strip()
                return header.split(',' if ext == '.csv' else '\t')
        elif ext in ['.xlsx', '.xls']:
            # Use openpyxl to read just headers
            import openpyxl
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            ws = wb.active
            columns = []
            for cell in ws[1]:
                if cell.value:
                    columns.append(str(cell.value))
            wb.close()
            return columns
        return []
    
    def _count_rows(self, filepath: str) -> int:
        """Count rows without loading full file"""
        ext = Path(filepath).suffix.lower()
        if ext in ['.csv', '.tsv']:
            with open(filepath, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f) - 1  # Subtract header
        elif ext in ['.xlsx', '.xls']:
            import openpyxl
            wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
            count = wb.active.max_row - 1  # Subtract header
            wb.close()
            return count
        return 0
    
    def _ensure_loaded(self, filepath: str) -> pd.DataFrame:
        """Load file data if it was lazy-loaded"""
        if filepath not in self.loaded_files:
            if filepath in self.file_metadata and self.file_metadata[filepath].get('lazy'):
                logger.info(f"Loading {Path(filepath).name} for first lookup...")
                # Import here to avoid circular imports
                from data_integration.io.importer import DataImporter
                importer = DataImporter()
                df = importer.load_file(filepath)
                self.loaded_files[filepath] = df
                self._create_lookup_indices(filepath, df)
                self.file_metadata[filepath]['lazy'] = False
                return df
        return self.loaded_files.get(filepath)
    
    def smart_lookup(self, lookup_value: Any, 
                    search_column: str = None,
                    return_column: str = None,
                    source_hint: str = None) -> Any:
        """
        Intelligent lookup with multiple resolution strategies
        """
        # Strategy 1: If source hint provided, try that first
        if source_hint:
            result = self._try_lookup_in_source(
                lookup_value, search_column, return_column, source_hint
            )
            if result is not None:
                return result
        
        # Strategy 2: Find file with both columns
        if search_column and return_column:
            for filepath in self._find_files_with_columns(search_column, return_column):
                df = self._ensure_loaded(filepath)  # Load if needed
                if df is not None:
                    result = self._perform_lookup(
                        df, lookup_value, search_column, return_column, filepath
                    )
                    if result is not None:
                        return result
        
        # Strategy 3: Smart single-column lookup
        if not search_column and return_column:
            # Find lookup_value in any unique column, return return_column
            return self._smart_value_lookup(lookup_value, return_column)
        
        return None
    
    def _perform_lookup(self, df: pd.DataFrame, lookup_value: Any, 
                       search_col: str, return_col: str, filepath: str) -> Any:
        """
        Perform actual lookup with clear missing value handling.
        Returns None if not found - this will make comparisons fail appropriately.
        """
        try:
            # Check if we have an index for this column
            if filepath in self.value_indices and search_col in self.value_indices[filepath]:
                index = self.value_indices[filepath][search_col]
                if lookup_value in index:
                    return index[lookup_value].get(return_col)
            else:
                # Fallback to DataFrame search
                matches = df[df[search_col] == lookup_value]
                if not matches.empty:
                    return matches.iloc[0][return_col]
            
            # Not found - log for debugging but don't crash
            logger.debug(f"Lookup not found: {lookup_value} in {search_col} "
                        f"(file: {Path(filepath).name})")
            return None
            
        except Exception as e:
            logger.warning(f"Lookup error in {Path(filepath).name}: {e}")
            return None
    
    def _find_files_with_columns(self, *columns) -> List[str]:
        """Find files that have all specified columns"""
        if not columns:
            return []
        
        # Start with files that have the first column
        candidates = set(self.column_index.get(columns[0], []))
        
        # Intersect with files that have other columns
        for col in columns[1:]:
            candidates &= set(self.column_index.get(col, []))
        
        return list(candidates)
```

#### 2. Extend ExcelFormulaProcessor

**Quick Implementation Note:**
The SmartLookupManager integrates with ExcelFormulaProcessor at two key points:

1. **Initialization** - Accept lookup_manager in constructor:
```python
def __init__(self, template_path=None, visible=False, track_errors=True):
    # ... existing code ...
    self.lookup_manager = None  # Will be injected by ValidationPipeline
```

2. **Formula Processing** - Handle LOOKUP in `_parse_formula`:
```python
def _parse_formula(self, formula: str, row_data: pd.Series) -> str:
    """Parse formula and replace column references and LOOKUP calls"""
    parsed_formula = formula
    
    # Handle LOOKUP function calls FIRST
    if 'LOOKUP(' in parsed_formula:
        parsed_formula = self._parse_lookup_calls(parsed_formula, row_data)
    
    # Then handle column references as before
    # ... existing column replacement code ...
    return parsed_formula
```

The LOOKUP parsing happens before column replacement to ensure proper evaluation order.

#### 3. Implement LOOKUP Syntax Variants

```python
# All of these work:
"LOOKUP([ReviewerID], 'EmployeeID', 'Level')"     # Find in any file
"LOOKUP([ReviewerID], 'Level')"                   # Smart column match
"LOOKUP([ReviewerID], 'hr_master', 'Level')"      # File hint
"LOOKUP([ReviewerID], 'hr_master.xlsx', 'Level')" # Full path
```

#### 4. Integration with Data Loading

```python
# In DataSourcePanel._on_file_loaded():
def _on_file_loaded(self, filepath: str, df: pd.DataFrame):
    # Existing code...
    
    # NEW: Register with lookup manager
    lookup_manager = self.get_lookup_manager()
    lookup_manager.add_file(filepath, df)
    
    # Notify user
    columns = len(df.columns)
    rows = len(df)
    self.log_message(
        f"File loaded: {Path(filepath).name} "
        f"({rows:,} rows, {columns} columns) - "
        f"available for LOOKUP operations"
    )
```

### Testing Requirements

#### Unit Tests

- [ ] **Test SmartLookupManager initialization and basic operations**
  - Test file: `tests/unit/lookup/test_smart_lookup_manager.py`
  - Coverage target: 95%
  - Test singleton pattern implementation
  - Test file registration with various file types (CSV, Excel)
  - Test alias creation and resolution

- [ ] **Test lazy loading functionality**
  - Test file: `tests/unit/lookup/test_lazy_loading.py`
  - Verify metadata-only storage for files >50MB
  - Test _peek_columns for CSV and Excel files
  - Test _count_rows accuracy
  - Verify on-demand loading triggers correctly

- [ ] **Test column indexing and discovery**
  - Test file: `tests/unit/lookup/test_column_indexing.py`
  - Test column index building
  - Test _find_files_with_columns with various scenarios
  - Test duplicate column handling

- [ ] **Test LOOKUP parsing in ExcelFormulaProcessor**
  - Test file: `tests/unit/lookup/test_lookup_parsing.py`
  - Coverage target: 90%
  - Test all LOOKUP syntax variants
  - Test integration with existing formula parsing

#### Integration Tests

- [ ] **Test LOOKUP function in complete validation flow**
  - Test file: `tests/integration/test_lookup_validation.py`
  - Test with actual rule evaluation
  - Test with multiple loaded files
  - Test fallback to None for missing values

- [ ] **Test file loading and registration**
  - Test file: `tests/integration/test_lookup_file_loading.py`
  - Test DataSourcePanel integration
  - Test concurrent file loading
  - Test file updates and re-registration

#### Performance Tests

- [ ] **Verify lookup performance requirements**
  - Test file: `tests/performance/test_lookup_performance.py`
  - Target: <10ms for lookups in datasets <10k rows
  - Test with various data sizes (100, 1k, 10k, 100k rows)
  - Test index creation overhead
  - Test cache effectiveness

- [ ] **Test memory usage with lazy loading**
  - Verify memory stays under 100MB with metadata for 10 large files
  - Test memory cleanup after file unloading

#### Edge Case Tests

- [ ] **Test boundary conditions**
  - Test file: `tests/unit/lookup/test_lookup_edge_cases.py`
  - Empty files (0 rows)
  - Files with no headers
  - Files with 100+ columns
  - Non-existent columns in LOOKUP
  - Circular lookup references
  - Unicode and special characters in column names

#### Test Data Requirements

- **Sample files in** `tests/data/lookup/`:
  - `small_hr_data.csv` (100 rows, known employee data)
  - `large_hr_data.xlsx` (100k rows for performance testing)
  - `empty_file.csv` (headers only)
  - `unicode_columns.xlsx` (special characters test)
  - `mixed_types.csv` (numeric/text in same column)

### Deliverables

- Zero-configuration LOOKUP function
- Automatic file discovery
- Multiple syntax options for flexibility
- Lazy loading support for large files
- Clear missing value handling strategy

## Phase 2: Seamless UI Integration (Week 2)

### Goals
Enhance UI to show lookup availability without adding complexity.

### Tasks

#### 1. Enhanced Data Source Panel with Informative Status

```python
# Enhanced lookup status in data panel
self.lookup_status = ClickableLabel("📁 No lookup files loaded")
self.lookup_status.clicked.connect(self._show_lookup_details)

def update_lookup_status(self):
    manager = self.lookup_manager
    file_count = len(manager.file_metadata)
    total_columns = len(manager.column_index)
    
    if file_count == 0:
        self.lookup_status.setText("📁 No lookup files loaded")
    else:
        # Make it informative and actionable
        status_text = f"📁 {file_count} files available | {total_columns} columns searchable | Click to see"
        self.lookup_status.setText(status_text)
        self.lookup_status.setToolTip(
            f"Files loaded for LOOKUP:\n" +
            "\n".join([f"• {info['alias']} ({info['row_count']:,} rows, {len(info['columns'])} cols)"
                      for filepath, info in manager.file_metadata.items()])
        )

def _show_lookup_details(self):
    """Show detailed lookup information when clicked"""
    dialog = LookupDetailsDialog(self.lookup_manager, self)
    dialog.exec()
```

#### 2. File Loading Enhancement

- Multi-file selection in file dialog
- Drag & drop multiple files
- Show which columns are available for lookup
- Quick preview of lookup data

#### 3. Real-time Rule Validation Feedback with Specific Column Discovery

```python
class FormulaValidator(QObject):
    """Provides real-time validation feedback for LOOKUP formulas"""
    
    validationResult = Signal(dict)
    
    def validate_lookup_formula(self, formula: str, lookup_manager: SmartLookupManager):
        """Validate LOOKUP formula and provide inline feedback"""
        import re
        pattern = r'LOOKUP\(([^,]+)(?:,\s*[\'"]([^"\']+)[\'"])?(?:,\s*[\'"]([^"\']+)[\'"])?\)'
        
        feedback = []
        for match in re.finditer(pattern, formula):
            lookup_value_expr = match.group(1)
            search_col = match.group(2)
            return_col = match.group(3) if match.group(3) else match.group(2)
            
            if return_col:
                # Check if column exists
                files_with_col = lookup_manager.column_index.get(return_col, [])
                if files_with_col:
                    # Found the column
                    file_info = lookup_manager.file_metadata[files_with_col[0]]
                    feedback.append({
                        'column': return_col,
                        'status': 'found',
                        'message': f"✓ '{return_col}' found in {Path(files_with_col[0]).stem} ({file_info['row_count']:,} rows)",
                        'file': files_with_col[0]
                    })
                else:
                    # Column not found
                    feedback.append({
                        'column': return_col,
                        'status': 'missing',
                        'message': f"✗ '{return_col}' not found in any loaded file",
                        'suggestion': self.get_missing_columns_message(return_col, lookup_manager)
                    })
        
        self.validationResult.emit({'formula': formula, 'feedback': feedback})
    
    def get_missing_columns_message(self, column: str, manager: SmartLookupManager) -> str:
        """Generate specific message about what columns are needed"""
        # Check similar columns
        from difflib import get_close_matches
        all_columns = list(manager.column_index.keys())
        similar = get_close_matches(column, all_columns, n=3, cutoff=0.6)
        
        if similar:
            # We have similar columns loaded
            files_info = []
            for col in similar:
                files = manager.column_index[col]
                for f in files[:2]:  # Show max 2 files per column
                    files_info.append(f"'{col}' in {Path(f).stem}")
            return f"Did you mean: {', '.join(files_info)}?"
        else:
            # Need to load a file with this column
            # Check recent files that might have it
            suggestions = []
            recent_files = self.get_recent_files()  # From session manager
            
            for filepath in recent_files[:5]:  # Check last 5 recent files
                if os.path.exists(filepath):
                    columns = manager._peek_columns(filepath)
                    if column in columns:
                        suggestions.append(f"Load {Path(filepath).name} (has '{column}')")
                    else:
                        # Check for partial matches
                        matches = get_close_matches(column, columns, n=1, cutoff=0.6)
                        if matches:
                            suggestions.append(f"Load {Path(filepath).name} (has '{matches[0]}')")
            
            if suggestions:
                return f"Suggestions: {'; '.join(suggestions[:2])}"
            else:
                return f"Load a file containing '{column}' column"

# Integration with formula editor
def on_formula_changed(self, formula: str):
    """Called when formula text changes"""
    if 'LOOKUP(' in formula:
        self.formula_validator.validate_lookup_formula(formula, self.lookup_manager)
```

#### 4. Smart File Suggestions

```python
class LookupFileSuggester:
    def suggest_files_for_formula(self, formula: str, 
                                 recent_files: List[str]) -> List[str]:
        """Suggest files that might help with formula"""
        needed_columns = self.extract_needed_columns(formula)
        suggestions = []
        
        for filepath in recent_files:
            # Quick header check without loading full file
            columns = self.peek_file_columns(filepath)
            match_score = len(needed_columns & set(columns))
            if match_score > 0:
                suggestions.append((filepath, match_score))
        
        # Return sorted by relevance
        return [f for f, _ in sorted(suggestions, 
                                    key=lambda x: x[1], 
                                    reverse=True)]
```

### Testing Requirements

#### Unit Tests

- [ ] **Test lookup status UI components**
  - Test file: `tests/unit/ui/test_lookup_status_widget.py`
  - Test status label updates
  - Test clickable behavior
  - Test tooltip generation

- [ ] **Test FormulaValidator**
  - Test file: `tests/unit/ui/test_formula_validator.py`
  - Coverage target: 90%
  - Test LOOKUP pattern recognition
  - Test feedback message generation
  - Test column suggestion logic

- [ ] **Test file suggestion system**
  - Test file: `tests/unit/ui/test_file_suggester.py`
  - Test relevance scoring
  - Test recent file analysis
  - Test column matching algorithms

#### Integration Tests

- [ ] **Test real-time validation feedback**
  - Test file: `tests/integration/test_lookup_ui_feedback.py`
  - Test formula entry with immediate feedback
  - Test status updates on file loading
  - Test interaction between components

- [ ] **Test multi-file operations**
  - Test file: `tests/integration/test_multi_file_loading.py`
  - Test drag-and-drop of multiple files
  - Test file dialog multi-selection
  - Test status updates with multiple files

#### UI Tests

- [ ] **Test user interactions**
  - Test file: `tests/ui/test_lookup_interactions.py`
  - Test clicking on status label
  - Test hovering for tooltips
  - Test responsive updates

- [ ] **Test error message clarity**
  - Verify error messages are specific and actionable
  - Test with various missing column scenarios
  - Test suggestion accuracy

#### Performance Tests

- [ ] **Test UI responsiveness**
  - Target: Status updates complete in <100ms
  - Test with rapid file loading/unloading
  - Test formula validation doesn't block UI

#### Edge Case Tests

- [ ] **Test UI edge cases**
  - Very long file names
  - Files with 100+ columns in tooltip
  - Rapid formula changes
  - Network drives or slow file systems

### Deliverables

- Natural integration with existing workflow
- Visual feedback on lookup availability with inline validation
- Smart suggestions without being intrusive
- Enhanced lookup status indicator
- Specific column discovery messaging

## Phase 3: Rule Builder Intelligence (Week 3)

### Goals
Make creating lookup rules effortless through smart assistance.

### Tasks

#### 1. LOOKUP Function Assistant

```python
class LookupAssistant(QDialog):
    """Simple dialog for building LOOKUP calls"""
    
    def __init__(self, loaded_files: Dict[str, pd.DataFrame]):
        # Dropdown: "What value are you looking up?"
        # - Column from primary data
        # - Custom value
        
        # Dropdown: "What do you want to find?"
        # - Shows all unique columns across loaded files
        
        # Smart preview showing example results
```

#### 2. Auto-Complete in Formula Editor

- Detect when user types "LOOKUP("
- Show available columns from all files
- Preview lookup results in real-time
- Complete column names from loaded files

#### 3. Common Patterns Library

```python
# Smart templates that adapt to loaded files
def generate_templates(self, loaded_files: Dict) -> List[Template]:
    templates = []
    
    # If we detect an HR-like file (has Level, Department, etc.)
    if self.has_hr_columns(loaded_files):
        templates.append({
            'name': 'Reviewer Level Check',
            'formula': 'LOOKUP([ReviewerID], "Level") > LOOKUP([SubmitterID], "Level")',
            'description': 'Ensure reviewer is senior to submitter'
        })
    
    # If we detect a vendor file
    if self.has_vendor_columns(loaded_files):
        templates.append({
            'name': 'Active Vendor Check',
            'formula': 'LOOKUP([VendorID], "Status") = "Active"',
            'description': 'Verify vendor is active'
        })
    
    return templates
```

#### 4. Visual Formula Builder

- Drag & drop column names
- Visual representation of lookups
- Test lookup with sample values
- See which file will provide data

### Testing Requirements

#### Unit Tests

- [ ] **Test LookupAssistant dialog**
  - Test file: `tests/unit/ui/test_lookup_assistant.py`
  - Test dropdown population
  - Test formula generation
  - Test preview functionality

- [ ] **Test auto-complete system**
  - Test file: `tests/unit/ui/test_lookup_autocomplete.py`
  - Test trigger detection ("LOOKUP(")
  - Test suggestion list generation
  - Test column name completion

- [ ] **Test template generation**
  - Test file: `tests/unit/ui/test_template_generation.py`
  - Test HR file detection logic
  - Test vendor file detection
  - Test template customization

#### Integration Tests

- [ ] **Test complete LOOKUP creation flow**
  - Test file: `tests/integration/test_lookup_rule_creation.py`
  - Test from dialog to formula
  - Test template application
  - Test preview with real data

- [ ] **Test formula builder interactions**
  - Test file: `tests/integration/test_visual_formula_builder.py`
  - Test drag-and-drop
  - Test visual updates
  - Test generated formula validity

#### UI Tests

- [ ] **Test assistant usability**
  - Test dialog flow
  - Test keyboard navigation
  - Test mouse interactions
  - Verify tooltips and help text

- [ ] **Test auto-complete behavior**
  - Test popup positioning
  - Test selection with keyboard/mouse
  - Test dismissal behavior

#### Performance Tests

- [ ] **Test template generation speed**
  - Target: <50ms for template generation
  - Test with various file combinations
  - Test with large column lists

#### Edge Case Tests

- [ ] **Test builder edge cases**
  - Columns with same names in different files
  - Very long column names
  - Special characters in column names
  - Empty or single-column files

### Deliverables

- Intuitive LOOKUP creation
- Context-aware templates
- Real-time validation and preview

## Phase 4: Production Features (Week 4-5)

### Goals
Add robustness and performance for production use.

### Tasks

#### 1. Threshold-Based Performance Optimization

```python
class OptimizedLookupManager(SmartLookupManager):
    def __init__(self):
        super().__init__()
        self.batch_threshold = 1000  # Switch strategy above this
        self.performance_metrics = {
            'lookup_count': 0,
            'cache_hits': 0,
            'total_time': 0,
            'strategy_usage': {'individual': 0, 'batch': 0}
        }
    
    def evaluate_rule(self, rule: ValidationRule, data_df: pd.DataFrame,
                     processor: ExcelFormulaProcessor) -> RuleEvaluationResult:
        """Evaluate rule with optimized lookup strategy"""
        row_count = len(data_df)
        
        # Detect if rule contains LOOKUP functions
        if 'LOOKUP(' in rule.condition:
            if row_count < self.batch_threshold:
                # Use individual lookups for small datasets
                return self._evaluate_with_individual_lookups(rule, data_df, processor)
            else:
                # Use batch/merge strategy for large datasets
                return self._evaluate_with_batch_lookups(rule, data_df, processor)
        else:
            # No lookups, use standard evaluation
            return super().evaluate_rule(rule, data_df, processor)
    
    def _evaluate_with_batch_lookups(self, rule: ValidationRule, 
                                    data_df: pd.DataFrame,
                                    processor: ExcelFormulaProcessor) -> RuleEvaluationResult:
        """Optimized evaluation using DataFrame merges"""
        # Extract all LOOKUP calls from the rule
        lookups = self._extract_lookups(rule.condition)
        
        # Pre-fetch all lookup data using merges
        enriched_df = data_df.copy()
        for lookup in lookups:
            # Perform batch lookup
            lookup_results = self.batch_lookup(
                enriched_df[lookup.lookup_column],
                lookup.search_column,
                lookup.return_column,
                lookup.source_hint
            )
            # Add results as temporary column
            temp_col = f"_lookup_{lookup.return_column}"
            enriched_df[temp_col] = lookup_results
            
        # Now evaluate with pre-fetched data
        # ... evaluation logic ...
        
        self.performance_metrics['strategy_usage']['batch'] += 1
        return result
    
    def _create_lookup_indices(self, filepath: str, df: pd.DataFrame):
        """Create optimized indices for common lookup patterns"""
        # Identify likely key columns (unique or mostly unique)
        for col in df.columns:
            if df[col].nunique() / len(df) > 0.9:  # 90% unique
                # Create hash index for O(1) lookups
                self.indices[filepath][col] = df.set_index(col)
    
    def batch_lookup(self, lookup_values: pd.Series, 
                    search_column: str, 
                    return_column: str) -> pd.Series:
        """Vectorized lookups for performance"""
        # Use merge instead of individual lookups for large datasets
        # Implementation here...
        pass
```

#### 2. Ambiguity Resolution

- Handle multiple files with same columns
- Smart disambiguation based on context
- User preferences for column priority
- Clear feedback when ambiguous

```python
def resolve_ambiguous_lookup(self, search_col: str, 
                            return_col: str) -> str:
    """When multiple files have the columns"""
    candidates = self.find_files_with_columns(search_col, return_col)
    
    if len(candidates) == 1:
        return candidates[0]
    
    # Smart resolution strategies:
    # 1. Prefer files with both as indexed columns
    # 2. Prefer files loaded more recently
    # 3. Prefer files with "master" or "reference" in name
    # 4. Ask user if still ambiguous
```

#### 3. Enhanced Data Handling

```python
class RobustLookupManager(OptimizedLookupManager):
    """Enhanced lookup manager with robust data handling"""
    
    def __init__(self):
        super().__init__()
        self.case_sensitive = False  # Default to case-insensitive
        self.type_coercion = True    # Auto-coerce types
    
    def _normalize_column_name(self, col: str) -> str:
        """Normalize column name for case-insensitive matching"""
        return col.lower() if not self.case_sensitive else col
    
    def add_file(self, filepath: str, df: pd.DataFrame = None, 
                 alias: str = None, lazy: bool = None):
        """Register file with column normalization"""
        # Store original column names
        if filepath not in self.file_metadata:
            self.file_metadata[filepath] = {}
        
        if df is not None:
            # Store original column name mapping
            self.file_metadata[filepath]['original_columns'] = {
                self._normalize_column_name(col): col 
                for col in df.columns
            }
            
            # Rename columns for internal use (preserving originals)
            df_normalized = df.copy()
            df_normalized.columns = [self._normalize_column_name(col) for col in df.columns]
            
            # Call parent method with normalized DataFrame
            super().add_file(filepath, df_normalized, alias, lazy)
        else:
            super().add_file(filepath, df, alias, lazy)
    
    def _coerce_lookup_value(self, value: Any, target_series: pd.Series) -> Any:
        """Intelligently coerce lookup value to match target column type"""
        if not self.type_coercion:
            return value
            
        target_dtype = target_series.dtype
        
        try:
            if pd.api.types.is_numeric_dtype(target_dtype):
                # Try to convert to numeric
                return pd.to_numeric(value, errors='raise')
            elif pd.api.types.is_string_dtype(target_dtype):
                # Convert to string
                return str(value)
            elif pd.api.types.is_datetime64_dtype(target_dtype):
                # Try to parse as datetime
                return pd.to_datetime(value)
        except:
            # If coercion fails, return original value
            pass
            
        return value
    
    def _perform_lookup(self, df: pd.DataFrame, lookup_value: Any,
                       search_col: str, return_col: str, filepath: str) -> Any:
        """Enhanced lookup with type coercion and case handling"""
        # Normalize column names
        search_col_norm = self._normalize_column_name(search_col)
        return_col_norm = self._normalize_column_name(return_col)
        
        # Coerce lookup value if needed
        if search_col_norm in df.columns:
            lookup_value = self._coerce_lookup_value(lookup_value, df[search_col_norm])
        
        # Perform lookup with error handling
        try:
            result = super()._perform_lookup(df, lookup_value, 
                                           search_col_norm, return_col_norm, filepath)
            
            # If found, return with original case from return column
            if result is not None and filepath in self.file_metadata:
                original_cols = self.file_metadata[filepath].get('original_columns', {})
                # Result already has the correct value, just log for debugging
                logger.debug(f"Lookup found: {lookup_value} -> {result}")
                
            return result
        except Exception as e:
            logger.warning(f"Lookup error: {e}")
            return None
```

#### 4. Missing Value Handling

- LOOKUP_DEFAULT with fallback values
- LOOKUP_EXISTS for validation
- Configurable NA handling
- Detailed logging of failed lookups

#### 5. Session Management (Enhanced for Clarity)

```python
# Session Integration - lookup_files are saved for CONVENIENCE ONLY
# They are NOT required - files can be loaded fresh each session
session_data = {
    'primary_source': 'audit_data.xlsx',
    'lookup_files': [
        {
            'path': 'hr_master.xlsx',
            'alias': 'hr_master',
            'last_modified': '2024-01-15T10:30:00',
            'purpose': 'auto-detected',  # Not assumed, just detected columns
            'columns_used': ['Level', 'Department', 'ManagerID']  # Track what was actually used
        },
        {
            'path': 'vendors.csv',
            'alias': 'vendors', 
            'last_modified': '2024-01-14T15:45:00',
            'purpose': 'auto-detected',
            'columns_used': ['Status', 'VendorID']
        }
    ],
    'lookup_stats': {
        'total_lookups': 15234,
        'cache_hits': 14500,
        'missing_values': 234
    }
}

def restore_lookup_files(self, session_data: Dict):
    """
    Optionally restore lookup files from session.
    This is a CONVENIENCE feature - not required for rules to work.
    """
    lookup_files = session_data.get('lookup_files', [])
    
    for file_info in lookup_files:
        filepath = file_info['path']
        if os.path.exists(filepath):
            # Check if file has been modified
            current_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
            saved_mtime = datetime.fromisoformat(file_info['last_modified'])
            
            if current_mtime <= saved_mtime:
                # File unchanged, can use lazy loading
                self.lookup_manager.add_file(
                    filepath,
                    alias=file_info.get('alias'),
                    lazy=True  # Don't load data until needed
                )
                logger.info(f"Restored lookup file reference: {filepath}")
            else:
                logger.info(f"Lookup file modified, will reload when needed: {filepath}")
```

#### 6. Performance Benchmarking

```python
class PerformanceBenchmark:
    """Benchmark lookup performance and provide optimization recommendations"""
    
    def benchmark_lookup_strategy(self, data_df: pd.DataFrame, 
                                 lookup_config: Dict) -> Dict[str, Any]:
        """Compare individual vs batch lookup performance"""
        import time
        
        results = {}
        
        # Test individual lookups
        start = time.time()
        individual_results = self._run_individual_lookups(data_df, lookup_config)
        results['individual_time'] = time.time() - start
        
        # Test batch lookups
        start = time.time()
        batch_results = self._run_batch_lookups(data_df, lookup_config)
        results['batch_time'] = time.time() - start
        
        # Calculate recommendation
        if len(data_df) < 1000:
            results['recommendation'] = 'individual'
        elif results['batch_time'] < results['individual_time'] * 0.5:
            results['recommendation'] = 'batch'
        else:
            results['recommendation'] = 'adaptive'
            
        return results
```

### Testing Requirements

#### Unit Tests

- [ ] **Test performance optimization logic**
  - Test file: `tests/unit/lookup/test_optimization.py`
  - Test threshold detection
  - Test strategy selection
  - Test batch lookup implementation

- [ ] **Test type coercion**
  - Test file: `tests/unit/lookup/test_type_coercion.py`
  - Coverage target: 95%
  - Test numeric/string conversions
  - Test datetime parsing
  - Test coercion failures

- [ ] **Test case-insensitive matching**
  - Test file: `tests/unit/lookup/test_case_sensitivity.py`
  - Test column normalization
  - Test original case preservation
  - Test mixed-case scenarios

- [ ] **Test ambiguity resolution**
  - Test file: `tests/unit/lookup/test_ambiguity.py`
  - Test disambiguation strategies
  - Test user dialog triggering
  - Test preference application

#### Integration Tests

- [ ] **Test session save/restore**
  - Test file: `tests/integration/test_lookup_session.py`
  - Test lookup file persistence
  - Test modification detection
  - Test lazy restore functionality

- [ ] **Test production workflows**
  - Test file: `tests/integration/test_lookup_production.py`
  - Test with 10+ lookup files
  - Test mixed file types
  - Test performance under load

#### Performance Tests

- [ ] **Test optimization effectiveness**
  - Test file: `tests/performance/test_lookup_optimization.py`
  - Compare individual vs batch performance
  - Test with datasets: 100, 1k, 10k, 100k, 1M rows
  - Verify threshold switching
  - Target: <10ms for <1k rows, <100ms for 10k rows

- [ ] **Test memory management**
  - Test with multiple 100MB+ files
  - Verify lazy loading effectiveness
  - Test memory cleanup
  - Target: <500MB with 5 large files loaded

- [ ] **Test cache performance**
  - Measure cache hit rates
  - Test cache size limits
  - Verify performance improvement
  - Target: >90% cache hit rate for repeated lookups

#### Edge Case Tests

- [ ] **Test data type edge cases**
  - Mixed numeric/text in lookup columns
  - NULL/NaN values
  - Date formats
  - Leading/trailing spaces

- [ ] **Test scale limits**
  - 100+ column files
  - 1M+ row lookups
  - 50+ loaded files
  - Deeply nested LOOKUP formulas

#### Test Automation

- **CI/CD Integration**:
  - All unit tests run on every commit
  - Integration tests run on PR creation
  - Performance tests run nightly
  - Edge case tests run weekly

- **Manual Testing Requirements**:
  - UI interaction tests with actual user workflows
  - Performance testing on production-like data
  - Accessibility testing for dialogs

### Deliverables

- Production-ready performance with threshold-based optimization
- Robust error handling with type coercion
- Clear ambiguity resolution
- Session persistence (as convenience feature)
- Performance metrics and benchmarking

## Phase 5: Excel Report Enhancement for LOOKUP Data (Week 5)

### Goals

Ensure Excel reports include complete information about secondary source lookups used during validation.

### Tasks

#### 1. Extend RuleEvaluationResult to Capture Lookup Data

```python
class RuleEvaluationResult:
    """Enhanced to capture lookup operations during rule evaluation."""
    
    def __init__(self, rule_id: str, rule_name: str):
        # Existing fields...
        self.lookup_operations = []  # List of LookupOperation objects
        
class LookupOperation:
    """Represents a single lookup operation during validation."""
    
    def __init__(self):
        self.lookup_value = None      # The value being looked up
        self.search_column = None     # Column searched in
        self.return_column = None     # Column value returned from
        self.source_file = None       # File that provided the result
        self.source_alias = None      # Friendly name of the file
        self.result_value = None      # The value returned (or None)
        self.success = False          # Whether lookup succeeded
        self.execution_time_ms = 0    # Time taken for lookup
        self.row_index = None         # Which row in validation data
        self.rule_name = None         # Rule that triggered this lookup
        self.validation_row_data = {} # Key data from the row being validated
```

#### 2. Modify SmartLookupManager to Track Operations

```python
class SmartLookupManager:
    def __init__(self):
        # Existing initialization...
        self.operation_tracking_enabled = False
        self.tracked_operations = []  # Store LookupOperation objects
        
    def enable_operation_tracking(self):
        """Enable tracking of lookup operations for reporting."""
        self.operation_tracking_enabled = True
        self.tracked_operations = []
    
    def get_tracked_operations(self) -> List[LookupOperation]:
        """Get all tracked operations and clear the list."""
        operations = self.tracked_operations.copy()
        self.tracked_operations = []
        return operations
    
    def _perform_lookup(self, df: pd.DataFrame, lookup_value: Any, 
                       search_col: str, return_col: str, filepath: str) -> Any:
        """Enhanced to track lookup operations when enabled."""
        start_time = time.time() if self.operation_tracking_enabled else None
        
        # Existing lookup logic...
        result = # ... existing implementation
        
        # Track the operation if enabled
        if self.operation_tracking_enabled:
            operation = LookupOperation()
            operation.lookup_value = lookup_value
            operation.search_column = search_col
            operation.return_column = return_col
            operation.source_file = filepath
            operation.source_alias = self.file_aliases.get(filepath, Path(filepath).stem)
            operation.result_value = result
            operation.success = result is not None
            operation.execution_time_ms = (time.time() - start_time) * 1000
            
            self.tracked_operations.append(operation)
        
        return result
```

#### 3. Integration with RuleEvaluator

```python
# In RuleEvaluator.evaluate_rule method
def evaluate_rule(self, rule: ValidationRule, data_df: pd.DataFrame, 
                 responsible_party_column: str = None) -> RuleEvaluationResult:
    """Enhanced to capture lookup operations."""
    # Enable lookup tracking for this evaluation
    if self.excel_processor and self.excel_processor.lookup_manager:
        self.excel_processor.lookup_manager.enable_operation_tracking()
    
    # Existing evaluation logic...
    result = self._evaluate_with_processor(rule, data_df)
    
    # Capture lookup operations
    if self.excel_processor and self.excel_processor.lookup_manager:
        lookup_operations = self.excel_processor.lookup_manager.get_tracked_operations()
        result.lookup_operations = lookup_operations
        
        # Group operations by row for easier reporting
        result.lookup_operations_by_row = defaultdict(list)
        for op in lookup_operations:
            result.lookup_operations_by_row[op.row_index].append(op)
    
    return result
```

#### 4. Enhance Report Generation

```python
class ExcelReportGenerator:
    """Enhanced to include lookup data in reports."""
    
    def generate_report(self, validation_results: ValidationResults, 
                       lookup_manager: SmartLookupManager) -> str:
        """Generate Excel report with lookup information."""
        
        # Create workbook with existing sheets
        wb = self._create_base_report(validation_results)
        
        # Add new sheet for lookup data sources
        self._add_lookup_summary_sheet(wb, lookup_manager)
        
        # Enhance rule results with lookup columns
        self._enhance_rule_results_with_lookups(wb, validation_results)
        
        # Save and return path
        return self._save_report(wb)
    
    def _enhance_rule_results_with_lookups(self, wb: Workbook, 
                                          validation_results: ValidationResults):
        """Add lookup information columns to rule results."""
        for rule_result in validation_results.rule_results:
            if rule_result.lookup_operations:
                # Add columns for lookup data
                ws = wb[rule_result.rule_name]
                
                # Add headers
                ws.cell(1, ws.max_column + 1, "Lookup Value")
                ws.cell(1, ws.max_column + 1, "Lookup Source")
                ws.cell(1, ws.max_column + 1, "Lookup Result")
                ws.cell(1, ws.max_column + 1, "Lookup Status")
                
                # Add data for each row
                for row_idx, operations in enumerate(rule_result.lookup_operations_by_row):
                    for op in operations:
                        row = row_idx + 2  # Excel 1-based + header
                        ws.cell(row, ws.max_column - 3, op.lookup_value)
                        ws.cell(row, ws.max_column - 2, op.source_alias)
                        ws.cell(row, ws.max_column - 1, op.result_value)
                        ws.cell(row, ws.max_column, "Success" if op.success else "Failed")
                        
                        # Highlight failed lookups
                        if not op.success:
                            for col in range(ws.max_column - 3, ws.max_column + 1):
                                ws.cell(row, col).fill = PatternFill(
                                    start_color="FFCCCC", 
                                    end_color="FFCCCC", 
                                    fill_type="solid"
                                )
```

#### 4. Create Lookup Summary Sheet

```python
def _add_lookup_summary_sheet(self, wb: Workbook, lookup_manager: SmartLookupManager):
    """Add a summary sheet with lookup data source information."""
    ws = wb.create_sheet("Lookup Data Sources")
    
    # Section 1: Loaded Files Summary
    ws.cell(1, 1, "Secondary Data Sources Used").font = Font(bold=True, size=14)
    
    row = 3
    headers = ["File Name", "Full Path", "Rows", "Columns", "Size (MB)", 
               "Last Modified", "Columns Used", "Lookup Count"]
    for col, header in enumerate(headers, 1):
        ws.cell(row, col, header).font = Font(bold=True)
    
    # Add file information
    stats = lookup_manager.get_statistics()
    for filepath, metadata in lookup_manager.file_metadata.items():
        row += 1
        ws.cell(row, 1, Path(filepath).name)
        ws.cell(row, 2, filepath)
        ws.cell(row, 3, metadata['row_count'])
        ws.cell(row, 4, len(metadata['columns']))
        ws.cell(row, 5, f"{metadata['size_mb']:.1f}")
        ws.cell(row, 6, datetime.fromtimestamp(os.path.getmtime(filepath)).strftime('%Y-%m-%d %H:%M'))
        
        # Get columns actually used
        used_columns = self._get_used_columns_for_file(filepath, lookup_manager.tracked_operations)
        ws.cell(row, 7, ", ".join(used_columns))
        
        # Count lookups for this file
        lookup_count = sum(1 for op in lookup_manager.tracked_operations 
                          if op.source_file == filepath)
        ws.cell(row, 8, lookup_count)
    
    # Section 2: Lookup Performance Statistics
    row += 3
    ws.cell(row, 1, "Lookup Performance Summary").font = Font(bold=True, size=14)
    
    row += 2
    ws.cell(row, 1, "Total Lookups:").font = Font(bold=True)
    ws.cell(row, 2, len(lookup_manager.tracked_operations))
    
    row += 1
    ws.cell(row, 1, "Successful Lookups:").font = Font(bold=True)
    successful = sum(1 for op in lookup_manager.tracked_operations if op.success)
    ws.cell(row, 2, f"{successful} ({successful/len(lookup_manager.tracked_operations)*100:.1f}%)")
    
    row += 1
    ws.cell(row, 1, "Failed Lookups:").font = Font(bold=True)
    failed = len(lookup_manager.tracked_operations) - successful
    ws.cell(row, 2, f"{failed} ({failed/len(lookup_manager.tracked_operations)*100:.1f}%)")
    
    row += 1
    ws.cell(row, 1, "Average Lookup Time:").font = Font(bold=True)
    avg_time = sum(op.execution_time_ms for op in lookup_manager.tracked_operations) / len(lookup_manager.tracked_operations)
    ws.cell(row, 2, f"{avg_time:.2f} ms")
    
    row += 1
    ws.cell(row, 1, "Cache Hit Rate:").font = Font(bold=True)
    ws.cell(row, 2, stats.get('cache_hit_rate', 'N/A'))
    
    # Auto-adjust column widths
    for column in ws.columns:
        max_length = 0
        for cell in column:
            if cell.value:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[column[0].column_letter].width = min(max_length + 2, 50)

def _get_used_columns_for_file(self, filepath: str, operations: List[LookupOperation]) -> List[str]:
    """Get list of columns actually used from a file during validation."""
    used_columns = set()
    for op in operations:
        if op.source_file == filepath:
            if op.search_column:
                used_columns.add(op.search_column)
            if op.return_column != op.search_column:
                used_columns.add(op.return_column)
    return sorted(list(used_columns))

def _calculate_lookup_statistics(self, operations: List[LookupOperation]) -> Dict[str, Any]:
    """Calculate aggregate statistics from lookup operations."""
    if not operations:
        return {'total': 0, 'successful': 0, 'failed': 0, 'avg_time_ms': 0}
    
    successful = sum(1 for op in operations if op.success)
    failed = len(operations) - successful
    avg_time = sum(op.execution_time_ms for op in operations) / len(operations)
    
    # Group by source file
    by_file = defaultdict(int)
    for op in operations:
        by_file[op.source_alias] += 1
    
    return {
        'total': len(operations),
        'successful': successful,
        'failed': failed,
        'success_rate': successful / len(operations),
        'avg_time_ms': avg_time,
        'by_file': dict(by_file),
        'unique_values': len(set(op.lookup_value for op in operations))
    }

def _add_failed_lookups_section(self, ws: Worksheet, row_start: int, 
                                failed_operations: List[LookupOperation]) -> int:
    """Add detailed section for failed lookups that need investigation."""
    if not failed_operations:
        return row_start
    
    ws.cell(row_start, 1, "Failed Lookups Requiring Attention").font = Font(
        bold=True, size=12, color="FF0000"
    )
    
    row = row_start + 2
    headers = ["Rule", "Row #", "Lookup Value", "Search Column", 
               "Expected in File", "Suggestion"]
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row, col, header)
        cell.font = Font(bold=True)
        cell.fill = PatternFill(start_color="FFE6E6", end_color="FFE6E6", fill_type="solid")
    
    row += 1
    for op in failed_operations:
        ws.cell(row, 1, op.rule_name)
        ws.cell(row, 2, op.row_index + 1)  # Convert to 1-based
        ws.cell(row, 3, str(op.lookup_value))
        ws.cell(row, 4, op.search_column)
        ws.cell(row, 5, op.source_alias or "Any file")
        ws.cell(row, 6, self._suggest_fix_for_failed_lookup(op))
        row += 1
    
    return row

def _suggest_fix_for_failed_lookup(self, op: LookupOperation) -> str:
    """Generate helpful suggestion for fixing failed lookup."""
    if not op.source_alias:
        return f"Load file containing '{op.search_column}' column"
    elif op.lookup_value and isinstance(op.lookup_value, str):
        # Check for common issues
        if op.lookup_value.strip() != op.lookup_value:
            return "Check for extra spaces in lookup value"
        elif any(char in op.lookup_value for char in ['\n', '\r', '\t']):
            return "Remove special characters from lookup value"
        else:
            return f"Verify '{op.lookup_value}' exists in {op.source_alias}"
    else:
        return f"Check data type compatibility with {op.source_alias}"
```

### Testing Requirements

#### Unit Tests

- [ ] **Test lookup operation recording**
  - Test file: `tests/unit/lookup/test_lookup_tracking.py`
  - Verify LookupOperation objects are created correctly
  - Test enable/disable tracking functionality
  - Verify tracked operations are cleared after retrieval

- [ ] **Test report enhancement with lookup data**
  - Test file: `tests/unit/reporting/test_lookup_report_enhancement.py`
  - Test addition of lookup columns to rule results
  - Test failed lookup highlighting
  - Verify lookup attribution is correct

- [ ] **Test lookup summary sheet generation**
  - Test file: `tests/unit/reporting/test_lookup_summary_sheet.py`
  - Test file metadata inclusion
  - Test performance statistics calculation
  - Test column usage tracking

#### Integration Tests

- [ ] **Test complete validation flow with lookup tracking**
  - Test file: `tests/integration/test_validation_with_lookup_tracking.py`
  - Run validation with multiple LOOKUP rules
  - Verify all lookups are tracked
  - Test tracking across multiple files

- [ ] **Test Excel report generation with embedded lookup data**
  - Test file: `tests/integration/test_report_with_lookup_data.py`
  - Generate complete report with lookup data
  - Verify all sheets are created correctly
  - Test with large datasets

- [ ] **Verify audit trail completeness**
  - Test file: `tests/integration/test_lookup_audit_trail.py`
  - Ensure no lookup operations are missed
  - Verify timestamps are accurate
  - Test with concurrent validations

#### Performance Tests

- [ ] **Test report generation performance with lookup data**
  - Test file: `tests/performance/test_lookup_report_performance.py`
  - Test with 10k+ lookup operations
  - Verify report generation stays under 5 seconds
  - Test memory usage during report generation
  - Measure impact of failed lookup analysis

#### Edge Case Tests

- [ ] **Test report edge cases**
  - Test file: `tests/edge_cases/test_lookup_report_edge_cases.py`
  - Very long lookup values (>255 chars)
  - Special characters in lookup results
  - Circular lookup references in reports
  - Missing source files during report generation
  - Unicode characters in lookup values
  - Null/None values in lookup operations
  - Empty lookup results dataset

### Deliverables

- Rule results include lookup source attribution
- Dedicated lookup summary sheet in reports
- Failed lookup highlighting for investigation
- Complete audit trail of secondary data usage

## Workflow Examples

### Example 1: First-Time User
1. User loads audit_data.xlsx
2. Creates rule: "Amount <= 50000" ✓ Works
3. Needs manager approval: Tries "LOOKUP([ManagerID], 'Level')"
4. System shows inline: "✗ 'Level' not found. Load hr_master.xlsx (has 'Level')"
5. User loads hr_master.xlsx
6. System updates: "✓ 'Level' found in hr_master (2,341 rows)"
7. Formula automatically works! ✓

### Example 2: Power User
1. Drag & drop 5 files at once:
   - audit_data.xlsx
   - employees.xlsx
   - departments.csv
   - vendors.xlsx
   - authority_matrix.csv

2. Status shows: "📁 5 files available | 89 columns searchable | Click to see"

3. Write complex rule:
   "LOOKUP([ReviewerID], 'Level') >= LOOKUP([SubmitterID], 'Level') + 1 
    AND LOOKUP([VendorID], 'vendors', 'Status') = 'Active'
    AND [Amount] <= LOOKUP([Department] & [Level], 'authority_matrix', 'Limit')"

4. Real-time feedback shows each column's location
5. Everything just works! ✓

### Example 3: Ambiguous Columns

1. Two files have 'Status' column
2. Formula: "LOOKUP([ID], 'Status') = 'Active'"
3. System shows smart prompt:
   "Multiple files have 'Status' column:
    • employees.xlsx (Status: Active/Inactive/Terminated)
    • vendors.xlsx (Status: Active/Inactive/Blocked)
    Which one do you mean?"
4. User clicks choice, formula updates to:
   "LOOKUP([ID], 'vendors', 'Status') = 'Active'"

## Success Metrics

### Immediate (Phase 1)
- ✓ LOOKUP works with zero configuration
- ✓ Any loaded file is instantly available
- ✓ Performance <10ms per lookup
- ✓ Lazy loading for files >50MB

### Short-term (Phase 2-3)
- ✓ Users create lookup rules without documentation
- ✓ File loading feels natural and integrated
- ✓ Column discovery is automatic
- ✓ Real-time validation feedback

### Long-term (Phase 4)
- ✓ Handle 10+ lookup files seamlessly
- ✓ 1M+ row lookups stay responsive
- ✓ Ambiguity resolution feels intelligent
- ✓ Automatic performance optimization

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Column name conflicts | Smart disambiguation, optional hints, case-insensitive matching |
| Large file performance | Lazy loading, intelligent indexing, threshold-based strategies |
| User confusion | Progressive disclosure, smart defaults, inline validation |
| Missing values | Clear feedback, LOOKUP_DEFAULT option, graceful None handling |
| Type mismatches | Automatic type coercion with fallback |

## Key Benefits

1. **True Zero Configuration**: Just load files and use them
2. **Intuitive**: Works like users expect
3. **Flexible**: Handles any file combination
4. **Smart**: System figures out the details
5. **Progressive**: Simple cases are simple, complex cases are possible
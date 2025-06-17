# Migration Guide: ValidationPipeline Refactoring

This guide helps you migrate from the old ValidationPipeline to the refactored architecture.

## Overview of Changes

The monolithic `ValidationPipeline` class has been split into several focused components:

1. **ValidationPipeline** (validation_service_refactored.py) - Simplified orchestrator
2. **ReportGenerator** (report_generator.py) - Excel report generation
3. **EnhancedDataValidator** (data_validator.py) - Data validation and statistics
4. **RuleConfigurationLoader** (rule_loader.py) - YAML rule loading
5. **Configuration Classes** (validation_config.py) - Config objects
6. **Constants** (validation_constants.py) - All magic values

## Migration Steps

### 1. Update Imports

**Old:**
```python
from services.validation_service import ValidationPipeline
```

**New:**
```python
from services.validation_service_refactored import ValidationPipeline
from services.validation_config import ValidationConfig, ReportConfig, ValidationRequest
```

### 2. Update Initialization

**Old:**
```python
pipeline = ValidationPipeline(
    rule_manager=rule_manager,
    output_dir="./output",
    max_workers=4,
    rule_config_paths=["data/rules"]
)
```

**New:**
```python
config = ValidationConfig(
    output_dir="./output",
    max_workers=4,
    rule_config_paths=["data/rules"]
)
pipeline = ValidationPipeline(config)
```

### 3. Update validate_data_source Calls

**Old (with many parameters):**
```python
results = pipeline.validate_data_source(
    data_source="data.xlsx",
    rule_ids=["RULE1", "RULE2"],
    analytic_id="TEST",
    responsible_party_column="Leader",
    output_formats=["json", "excel"],
    min_severity="high",
    use_parallel=True,
    analytic_title="Test Report"
)
```

**New (with request object):**
```python
request = ValidationRequest(
    data_source="data.xlsx",
    validation_config=ValidationConfig(
        rule_ids=["RULE1", "RULE2"],
        responsible_party_column="Leader",
        min_severity="high",
        use_parallel=True
    ),
    report_config=ReportConfig(
        analytic_id="TEST",
        analytic_title="Test Report",
        output_formats=["json", "excel"]
    )
)
results = pipeline.validate_data_source(request)
```

### 4. Access Results

**Old:**
```python
# Results were a dictionary
compliance_rate = results['summary']['compliance_rate']
output_files = results.get('output_files', [])
```

**New:**
```python
# Results are a ValidationResult object
compliance_rate = results.compliance_rate
output_files = results.output_files
# Or convert to dict
results_dict = results.to_dict()
```

### 5. Report Generation

**Old:**
```python
# Was part of ValidationPipeline
pipeline.generate_excel_report(json_path, excel_path)
pipeline.split_report_by_leader(master_path, output_dir)
```

**New:**
```python
# Still available on pipeline (delegates to ReportGenerator)
pipeline.generate_excel_report(json_path, excel_path)
pipeline.split_report_by_leader(master_path, output_dir)

# Or use ReportGenerator directly
from services.report_generator import ReportGenerator
generator = ReportGenerator(rule_manager)
generator.generate_excel_report(json_path, excel_path)
```

### 6. Rule Configuration

**Old:**
```python
# Internal method
pipeline._load_rule_configurations()
```

**New:**
```python
# Public API
summary = pipeline.reload_rule_configurations()
config_summary = pipeline.get_rule_configuration_summary()

# Or use RuleConfigurationLoader directly
from services.rule_loader import RuleConfigurationLoader
loader = RuleConfigurationLoader(rule_manager)
loader.load_from_directory("data/rules")
```

### 7. Constants

**Old:**
```python
# Hardcoded values
entity_column = "AuditEntityID"
max_workers = 4
```

**New:**
```python
from services.validation_constants import (
    DEFAULT_ENTITY_ID_COLUMN,
    MAX_PARALLEL_WORKERS,
    IAG_RATING_THRESHOLDS
)
entity_column = DEFAULT_ENTITY_ID_COLUMN
max_workers = MAX_PARALLEL_WORKERS
```

## Deprecated Methods

The following methods have been removed:
- `generate_leader_packs()` - Use `split_report_by_leader()`
- `generate_iag_summary_report()` - Use `generate_excel_report()`
- `generate_comprehensive_iag_report()` - Use `generate_excel_report()`

## Benefits of Refactoring

1. **Cleaner API** - Request/Response objects instead of many parameters
2. **Better Testing** - Each component can be tested independently
3. **Reusability** - Components can be used separately
4. **Maintainability** - Smaller, focused classes
5. **Configuration** - All config in one place
6. **Type Safety** - Better type hints with dataclasses

## Example: Complete Migration

**Old Code:**
```python
from services.validation_service import ValidationPipeline

# Initialize
pipeline = ValidationPipeline(
    output_dir="./output",
    max_workers=4,
    rule_config_paths=["data/rules"]
)

# Validate
results = pipeline.validate_data_source(
    data_source="test_data.xlsx",
    rule_ids=None,  # Use all rules
    responsible_party_column="AuditLeader",
    output_formats=["json", "excel"],
    use_parallel=True
)

# Check results
if results['status'] == 'SUCCESS':
    print(f"Compliance: {results['summary']['compliance_rate']:.1f}%")
    print(f"Files: {results['output_files']}")
```

**New Code:**
```python
from services.validation_service_refactored import ValidationPipeline
from services.validation_config import ValidationConfig, ReportConfig, ValidationRequest

# Initialize
config = ValidationConfig(
    output_dir="./output",
    max_workers=4,
    rule_config_paths=["data/rules"],
    use_parallel=True
)
pipeline = ValidationPipeline(config)

# Create request
request = ValidationRequest(
    data_source="test_data.xlsx",
    validation_config=ValidationConfig(
        responsible_party_column="AuditLeader",
        use_all_rules=True,
        use_parallel=True
    ),
    report_config=ReportConfig(
        output_formats=["json", "excel"]
    )
)

# Validate
results = pipeline.validate_data_source(request)

# Check results
if results.status == 'SUCCESS':
    print(f"Compliance: {results.compliance_rate:.1f}%")
    print(f"Files: {results.output_files}")
```

## Backward Compatibility

To maintain backward compatibility during transition:

1. Keep the old `validation_service.py` file temporarily
2. Add deprecation warnings to old methods
3. Create a wrapper that converts old-style calls to new API
4. Gradually migrate code to use new API
5. Remove old code after full migration

## Need Help?

- Check the docstrings in each new module
- Review the test files for usage examples
- Look at the constants file for available options
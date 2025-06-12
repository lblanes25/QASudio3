# Date Detection and Conversion Guide

## Overview

The QA Analytics Framework now includes automatic date detection and conversion capabilities in the data loading pipeline. This feature solves the common problem of date columns being loaded as text, which prevents Excel formulas from performing date operations correctly.

## Features

### Automatic Date Detection
- Analyzes text columns to identify those containing date values
- Supports multiple date formats simultaneously
- Uses intelligent sampling for performance on large datasets
- Considers column names as hints for date detection

### Supported Date Formats
The system automatically recognizes these common formats:
- US formats: `01/15/2024`, `01-15-2024`
- ISO formats: `2024-01-15`, `2024/01/15`
- European formats: `15/01/2024`, `15.01.2024`
- Long formats: `January 15, 2024`, `Jan 15, 2024`
- With time: `2024-01-15 10:30:45`, `01/15/2024 10:30 AM`

### Robust Conversion
- Handles mixed data gracefully (valid dates + invalid text)
- Preserves null values
- Provides detailed conversion reports
- Logs all conversion activities

## Usage

### Basic Usage (Automatic Detection)
By default, date detection is enabled when loading files:

```python
from data_integration.io import DataImporter

# Automatically detect and convert date columns
df = DataImporter.load_file('data.csv')
```

### Disable Date Detection
If you want to load data without date conversion:

```python
df = DataImporter.load_file('data.csv', detect_dates=False)
```

### Specify Date Columns
To convert specific columns only:

```python
df = DataImporter.load_file(
    'data.csv',
    date_columns=['Start_Date', 'End_Date']
)
```

### Custom Date Formats
Add custom formats for non-standard dates:

```python
df = DataImporter.load_file(
    'data.csv',
    date_formats=['%Y|%m|%d', '%d*%m*%Y']  # Custom separators
)
```

### Advanced Usage with DateDetector

For more control, use the DateDetector class directly:

```python
from data_integration.io import DateDetector

# Create detector with custom settings
detector = DateDetector(
    sample_size=200,           # Sample more rows for detection
    detection_threshold=0.9,   # Require 90% valid dates
    additional_formats=['%Y.%j']  # Year + day of year
)

# Get detection report
report = detector.get_date_columns_report(df)
print(f"Detected date columns: {report['detected_date_columns']}")

# Convert with detailed report
converted_df, conversion_report = detector.convert_date_columns(df)
```

## Integration with Excel Formula Processing

The detected dates are automatically prepared for Excel when using validation rules:

```python
# Original data has dates as text
data = pd.DataFrame({
    'Order_Date': ['01/15/2024', '02/20/2024'],
    'Ship_Date': ['01/20/2024', '02/25/2024']
})

# Load with date detection
df = DataImporter.load_file('orders.csv')

# Now Excel formulas work correctly
rule = ValidationRule(
    formula='=[Ship_Date]>[Order_Date]',  # Date comparison works!
    name='Ship After Order'
)
```

## Configuration Options

### DataImporter.load_file() Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `detect_dates` | bool | True | Enable automatic date detection |
| `date_columns` | List[str] | None | Specific columns to convert |
| `date_formats` | List[str] | None | Additional date formats to try |

### DateDetector Configuration

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sample_size` | int | 100 | Rows to sample for detection |
| `detection_threshold` | float | 0.8 | Minimum valid date ratio |
| `additional_formats` | List[str] | None | Custom date formats |

## Performance Considerations

1. **Sampling**: Only samples 100 rows by default for detection
2. **Caching**: Detected formats are cached per column
3. **Parallel Processing**: Compatible with parallel validation
4. **Large Datasets**: Minimal overhead even for millions of rows

## Troubleshooting

### Common Issues

1. **Dates not detected**: Check if threshold is too high
   ```python
   detector = DateDetector(detection_threshold=0.6)  # Lower threshold
   ```

2. **Wrong format detected**: Specify the format explicitly
   ```python
   df = DataImporter.load_file(
       'data.csv',
       date_columns=['DateCol'],
       date_formats=['%d/%m/%Y']  # Force European format
   )
   ```

3. **Mixed formats in same column**: Use pandas intelligent parser
   ```python
   # The detector will fall back to pandas.to_datetime() 
   # which can handle mixed formats
   ```

### Logging

Enable detailed logging to troubleshoot:

```python
import logging

# Set logging level
logging.getLogger('data_integration.io.date_detector').setLevel(logging.DEBUG)
logging.getLogger('data_integration.io.importer').setLevel(logging.DEBUG)
```

## Best Practices

1. **Column Naming**: Use descriptive names containing "date", "time", etc.
2. **Consistent Formats**: Keep date formats consistent within columns
3. **Validation**: Review the conversion report for important datasets
4. **Testing**: Test with sample data before processing large files
5. **Documentation**: Document expected date formats in your data sources

## Example: Complete Workflow

```python
from data_integration.io import DataImporter, DateDetector
import logging

# Enable logging
logging.basicConfig(level=logging.INFO)

# Load data with automatic date detection
df = DataImporter.load_file('sales_data.csv')

# Verify conversions
detector = DateDetector()
report = detector.get_date_columns_report(df)

print("Date Detection Report:")
print(f"- Existing datetime columns: {report['existing_datetime_columns']}")
print(f"- Newly detected: {report['detected_date_columns']}")

for col, details in report['detection_details'].items():
    print(f"\n{col}:")
    print(f"  Format: {details['detected_format']}")
    print(f"  Confidence: {details['confidence']:.1%}")

# Now use with validation rules that include date operations
from services.validation_service import ValidationPipeline

pipeline = ValidationPipeline()
results = pipeline.validate_data_source(
    df,
    rule_ids=['date_validation_rules']
)
```

## API Reference

See the inline documentation in:
- `data_integration/io/date_detector.py` - Core detection logic
- `data_integration/io/importer.py` - Integration with file loading
- `tests/test_date_detection.py` - Usage examples
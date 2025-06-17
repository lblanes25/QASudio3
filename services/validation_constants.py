# services/validation_constants.py

"""Constants used throughout the validation service module."""

# Severity levels for rules
SEVERITY_LEVELS = ['critical', 'high', 'medium', 'low', 'info']

# Compliance status values
COMPLIANCE_STATUSES = ['GC', 'PC', 'DNC', 'NA']

# IAG scoring weights
IAG_SCORING_WEIGHTS = {
    'GC': 5,
    'PC': 3,
    'DNC': 1,
    'NA': 0
}

# Performance settings
MAX_PARALLEL_WORKERS = 4
DEFAULT_BATCH_SIZE = 1000

# Column names
DEFAULT_ENTITY_ID_COLUMN = 'AuditEntityID'
DEFAULT_RESPONSIBLE_PARTY_COLUMN = 'ResponsibleParty'

# Search limits
MAX_SUMMARY_SEARCH_ROWS = 30

# Output formats
SUPPORTED_OUTPUT_FORMATS = ['json', 'excel', 'csv', 'html']
DEFAULT_OUTPUT_FORMAT = 'json'

# Directory paths
DEFAULT_OUTPUT_DIR = './output'
DEFAULT_ARCHIVE_DIR = './archive'
DEFAULT_RULES_DIR = 'data/rules'
DEFAULT_TEMPLATES_DIR = 'templates'

# File naming patterns
RESULTS_FILE_PATTERN = '{analytic_id}_{timestamp}_results.{format}'
REPORT_FILE_PATTERN = '{analytic_id}_{timestamp}_report.xlsx'
LEADER_REPORT_PATTERN = 'QA_Results_{leader}_{timestamp}.xlsx'

# Excel report settings
EXCEL_MAX_COL_WIDTH = 50
EXCEL_MIN_COL_WIDTH = 10
EXCEL_DEFAULT_COL_WIDTH = 15
EXCEL_HEADER_ROW_HEIGHT = 30
EXCEL_DATA_ROW_HEIGHT = 15

# Excel styles
HEADER_FONT_SIZE = 12
HEADER_FONT_BOLD = True
HEADER_FILL_COLOR = 'D3D3D3'
HEADER_ALIGNMENT = 'center'

# IAG report sections
IAG_SECTIONS = {
    'OVERALL_SUMMARY': 'Section 1: IAG Overall Summary',
    'LEADER_RESULTS': 'Section 2: IAG Leader Results',
    'DETAILED_ANALYTICS': 'Section 3: Detailed Analytics'
}

# Rating thresholds
IAG_RATING_THRESHOLDS = {
    'Excellent': 90,
    'Satisfactory': 70,
    'Needs Improvement': 50,
    'Unsatisfactory': 0
}

# Rating colors (RGB)
IAG_RATING_COLORS = {
    'Excellent': '00FF00',       # Green
    'Satisfactory': 'FFFF00',    # Yellow
    'Needs Improvement': 'FFA500', # Orange
    'Unsatisfactory': 'FF0000'    # Red
}

# Compliance colors (RGB)
COMPLIANCE_COLORS = {
    'GC': '00FF00',   # Green
    'PC': 'FFFF00',   # Yellow
    'DNC': 'FF0000',  # Red
    'NA': 'C0C0C0'    # Gray
}

# Report tab names
REPORT_TABS = {
    'SUMMARY': 'IAG Summary',
    'GUIDE': 'Guide',
    'TEST_PREFIX': 'Test '
}

# Guide tab content headers
GUIDE_HEADERS = {
    'COMPLIANCE': 'Compliance Status Definitions',
    'IAG_SCORING': 'IAG Scoring Methodology',
    'NAVIGATION': 'Report Navigation Guide'
}

# Validation messages
VALIDATION_MESSAGES = {
    'NO_DATA': 'No data found to validate',
    'NO_RULES': 'No validation rules found',
    'INVALID_SCHEMA': 'Data schema validation failed',
    'RULE_ERROR': 'Error evaluating rule: {rule_id}',
    'EXPORT_ERROR': 'Error exporting results to {format}'
}

# Logging formats
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Thread safety
THREAD_LOCAL_STORAGE_KEY = 'excel_app'

# COM initialization comment
COM_INIT_COMMENT = "COM initialization required for Excel automation in threads"

# YAML validation comment
YAML_VALIDATION_COMMENT = "YAML schema validation ensures rules have required fields"
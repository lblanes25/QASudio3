import sys
import os

# Add the project root directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pandas as pd
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SampleReportGenerator")

# Try to import and initialize pythoncom for Excel automation
try:
    import pythoncom

    pythoncom.CoInitialize()
    logger.info("COM initialized")
except ImportError:
    logger.warning("pythoncom not available - Excel formulas may not work")
except Exception as e:
    logger.warning(f"Error initializing COM: {str(e)}")

# Import our components
from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
from core.rule_engine.rule_evaluator import RuleEvaluator
from reporting.generation.report_generator import ReportGenerator

try:
    # Create a directory for output
    output_dir = Path("./sample_reports")
    output_dir.mkdir(exist_ok=True)
    logger.info(f"Output directory: {output_dir.absolute()}")


    # Create a sample DataFrame for testing
    def create_test_data():
        data = {
            'EmployeeID': ['E001', 'E002', 'E003', 'E004', 'E005'],
            'Name': ['John Smith', 'Jane Doe', 'Bob Johnson', 'Alice Brown', 'David Lee'],
            'Department': ['IT', 'HR', 'Finance', 'IT', 'HR'],
            'Manager': ['M001', 'M002', 'M002', 'M001', 'M002'],
            'Salary': [75000, 65000, 85000, 72000, 68000],
            'HireDate': ['2020-01-15', '2019-05-20', '2021-02-10', '2018-11-30', '2022-03-01'],
            'ReviewStatus': ['Completed', 'Completed', 'Pending', 'Completed', None],
            'PerformanceScore': [4.2, 3.8, None, 4.5, 3.2]
        }
        return pd.DataFrame(data)


    # Create sample data
    test_df = create_test_data()
    logger.info(f"Created test data with {len(test_df)} rows")

    # Create rule manager and add test rules
    rule_manager = ValidationRuleManager()

    # Add sample rules
    rule1 = ValidationRule(
        name="Salary_NotNull",
        formula="=NOT(ISBLANK([Salary]))",
        description="Salary values must not be null",
        threshold=1.0,
        severity="high",
        category="data_quality"
    )
    rule_id1 = rule_manager.add_rule(rule1)
    logger.info(f"Added rule 1: {rule_id1}")

    rule2 = ValidationRule(
        name="ReviewStatus_NotNull",
        formula="=NOT(ISBLANK([ReviewStatus]))",
        description="Review status must not be null",
        threshold=1.0,
        severity="medium",
        category="completeness"
    )
    rule_id2 = rule_manager.add_rule(rule2)
    logger.info(f"Added rule 2: {rule_id2}")

    rule3 = ValidationRule(
        name="PerformanceScore_Range",
        formula="=OR(ISBLANK([PerformanceScore]), AND([PerformanceScore]>=1, [PerformanceScore]<=5))",
        description="Performance scores must be between 1 and 5 if present",
        threshold=1.0,
        severity="medium",
        category="data_quality"
    )
    rule_id3 = rule_manager.add_rule(rule3)
    logger.info(f"Added rule 3: {rule_id3}")

    # List rules to verify they're in the manager
    rules = rule_manager.list_rules()
    logger.info(f"Rule manager contains {len(rules)} rules")
    for rule in rules:
        logger.info(f"Rule in manager: {rule.rule_id} - {rule.name}")

    # Create rule evaluator
    evaluator = RuleEvaluator(rule_manager=rule_manager)
    logger.info("Created rule evaluator")

    # Evaluate rules directly
    responsible_party_column = "Department"
    rule_results = {}
    logger.info("Evaluating rules directly...")

    try:
        # Evaluate rule 1
        logger.info(f"Evaluating rule 1 ({rule_id1})...")
        result1 = evaluator.evaluate_rule(rule1, test_df, responsible_party_column)
        rule_results[rule_id1] = result1
        logger.info(f"Rule 1 result: {result1.compliance_status}")

        # Evaluate rule 2
        logger.info(f"Evaluating rule 2 ({rule_id2})...")
        result2 = evaluator.evaluate_rule(rule2, test_df, responsible_party_column)
        rule_results[rule_id2] = result2
        logger.info(f"Rule 2 result: {result2.compliance_status}")

        # Evaluate rule 3
        logger.info(f"Evaluating rule 3 ({rule_id3})...")
        result3 = evaluator.evaluate_rule(rule3, test_df, responsible_party_column)
        rule_results[rule_id3] = result3
        logger.info(f"Rule 3 result: {result3.compliance_status}")
    except Exception as e:
        logger.error(f"Error evaluating rules: {str(e)}", exc_info=True)

    # Create results dictionary
    results = {
        'status': 'FULLY_COMPLIANT',
        'analytic_id': 'sample_report',
        'rule_results': {
            rule_id1: result1.summary,
            rule_id2: result2.summary,
            rule_id3: result3.summary
        },
        'summary': {
            'total_rules': 3,
            'compliance_counts': {
                'GC': 3,
                'PC': 0,
                'DNC': 0
            }
        }
    }

    # Create and use report generator directly
    logger.info("Generating reports...")
    report_generator = ReportGenerator()

    # Generate Excel report
    excel_path = output_dir / "sample_report_detailed.xlsx"
    try:
        logger.info(f"Generating Excel report at {excel_path}...")
        report_generator.generate_excel(
            results=results,
            rule_results=rule_results,
            output_path=str(excel_path),
            group_by=responsible_party_column
        )
        logger.info("Excel report generated successfully")
        print(f"Excel report generated: {excel_path}")
    except Exception as e:
        logger.error(f"Error generating Excel report: {str(e)}", exc_info=True)

    # Generate HTML report
    html_path = output_dir / "sample_report.html"
    try:
        logger.info(f"Generating HTML report at {html_path}...")
        report_generator.generate_html(
            results=results,
            rule_results=rule_results,
            output_path=str(html_path)
        )
        logger.info("HTML report generated successfully")
        print(f"HTML report generated: {html_path}")
    except Exception as e:
        logger.error(f"Error generating HTML report: {str(e)}", exc_info=True)

except Exception as e:
    logger.error(f"Error generating sample report: {str(e)}", exc_info=True)
finally:
    # Clean up COM
    try:
        pythoncom.CoUninitialize()
        logger.info("COM uninitialized")
    except:
        pass
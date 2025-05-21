import unittest
import tempfile
import os
import pandas as pd
from pathlib import Path
import yaml
import xlsxwriter
from unittest.mock import patch, MagicMock

# Import the module to test
from reporting.generation.report_generator import ReportGenerator


class TestReportGenerator(unittest.TestCase):
    """Tests for the ReportGenerator class."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a temporary directory for test outputs
        self.temp_dir = tempfile.TemporaryDirectory()

        # Create a basic ReportGenerator instance
        self.report_generator = ReportGenerator()

        # Sample data for testing
        self.sample_results = {
            'valid': False,
            'status': 'PARTIALLY_COMPLIANT',
            'analytic_id': 'test_analytic',
            'timestamp': '2023-01-01T00:00:00',
            'data_source': 'test_data.csv',
            'execution_time': 1.23,
            'summary': {
                'total_rules': 3,
                'compliance_counts': {
                    'GC': 1,
                    'PC': 1,
                    'DNC': 1
                },
                'compliance_rate': 0.33,
                'rule_stats': {
                    'by_category': {
                        'data_quality': {
                            'count': 3,
                            'GC': 1,
                            'PC': 1,
                            'DNC': 1
                        }
                    },
                    'by_severity': {
                        'medium': {
                            'count': 3,
                            'GC': 1,
                            'PC': 1,
                            'DNC': 1
                        }
                    }
                }
            },
            'rule_results': {}
        }

        # We'll add more test setup as needed

    def tearDown(self):
        """Clean up test fixtures."""
        self.temp_dir.cleanup()

    def test_init_default(self):
        """Test initialization with default config."""
        generator = ReportGenerator()
        self.assertIsNotNone(generator.config)
        self.assertIn('test_weights', generator.config)
        self.assertIn('score_mapping', generator.config)
        self.assertIn('rating_labels', generator.config)

    def test_load_config(self):
        """Test loading configuration from YAML file."""
        # Create a test config file
        config_path = os.path.join(self.temp_dir.name, 'test_config.yaml')
        test_config = {
            'report_config': {
                'test_weights': {
                    'test_rule_1': 0.5,
                    'test_rule_2': 0.5
                },
                'score_mapping': {
                    '0.9-1.0': 5,
                    '0.0-0.89': 1
                }
            }
        }

        with open(config_path, 'w') as f:
            yaml.dump(test_config, f)

        # Create generator with this config
        generator = ReportGenerator(config_path)

        # Verify config was loaded
        self.assertEqual(generator.config['test_weights']['test_rule_1'], 0.5)
        self.assertEqual(generator.config['score_mapping']['0.9-1.0'], 5)

    def test_analyze_formula_components(self):
        """Test formula component analysis."""
        # Test a simple formula
        simple_formula = "=[Column1] > 5"
        components = self.report_generator._analyze_formula_components(simple_formula)

        self.assertEqual(components['complexity'], 'simple')
        self.assertEqual(components['referenced_columns'], ['Column1'])
        self.assertTrue('>' in components['comparisons'])

        # Test a complex formula
        complex_formula = "=AND([Column1] > 5, OR([Column2] = 'Yes', [Column3] < 10))"
        components = self.report_generator._analyze_formula_components(complex_formula)

        self.assertEqual(components['complexity'], 'complex')
        self.assertIn('Column1', components['referenced_columns'])
        self.assertIn('Column2', components['referenced_columns'])
        self.assertIn('Column3', components['referenced_columns'])
        self.assertIn('AND', components['logical_operators'])
        self.assertIn('OR', components['logical_operators'])

    def test_calculate_score(self):
        """Test score calculation from compliance rates."""
        # Test different compliance rates against score mapping
        self.assertEqual(self.report_generator._calculate_score(0.95), 5.0)  # Top range
        self.assertEqual(self.report_generator._calculate_score(0.85), 4.0)  # Middle range
        self.assertEqual(self.report_generator._calculate_score(0.30), 1.0)  # Bottom range

    def test_extract_column_references(self):
        """Test extraction of column references from formulas."""
        formula = "=IF([Column1] > 10, [Column2], [Column3])"
        refs = self.report_generator._extract_column_references(formula)

        self.assertEqual(len(refs), 3)
        self.assertIn('Column1', refs)
        self.assertIn('Column2', refs)
        self.assertIn('Column3', refs)

    def test_safe_sheet_name(self):
        """Test creation of safe Excel sheet names."""
        # Test a name with invalid chars
        unsafe_name = "Test: Sheet [With] Invalid/Chars?"
        safe_name = self.report_generator._safe_sheet_name(unsafe_name)

        self.assertNotIn(':', safe_name)
        self.assertNotIn('[', safe_name)
        self.assertNotIn(']', safe_name)
        self.assertNotIn('/', safe_name)
        self.assertNotIn('?', safe_name)

        # Test a name that's too long (over 31 chars)
        long_name = "ThisIsAReallyReallyReallyLongSheetNameThatExceedsExcelLimit"
        safe_name = self.report_generator._safe_sheet_name(long_name)

        self.assertLessEqual(len(safe_name), 31)
        self.assertTrue(safe_name.endswith('...'))

    def test_calculate_weighted_score(self):
        """Test calculation of weighted scores."""
        # Create mock rule results
        rule_results = {
            'rule1': MagicMock(
                compliance_metrics={'gc_count': 90, 'total_count': 100},
                party_results={'Party1': {'metrics': {'gc_count': 45, 'total_count': 50}}}
            ),
            'rule2': MagicMock(
                compliance_metrics={'gc_count': 70, 'total_count': 100},
                party_results={'Party1': {'metrics': {'gc_count': 35, 'total_count': 50}}}
            )
        }

        # Configure test weights
        self.report_generator.config['test_weights'] = {
            'rule1': 0.6,
            'rule2': 0.4
        }

        # Test overall score
        overall_score = self.report_generator.calculate_weighted_score(
            self.sample_results, rule_results
        )

        # Expected: (5.0 * 0.6 + 3.0 * 0.4) = 4.2, rounded to 4.0
        self.assertEqual(overall_score, 4.0)

        # Test party-specific score
        party_score = self.report_generator.calculate_weighted_score(
            self.sample_results, rule_results, 'Party1'
        )

        # Should be the same in this case
        self.assertEqual(party_score, 4.0)

    def test_generate_html(self):
        """Test HTML report generation."""
        # Create mock rule and result objects
        rule = MagicMock(
            rule_id='test_rule',
            name='Test Rule',
            description='A test rule',
            formula='=[Column1] > 0'
        )

        result = MagicMock(
            rule=rule,
            compliance_status='PC',
            compliance_metrics={'total_count': 100, 'gc_count': 80, 'pc_count': 10, 'dnc_count': 10},
            result_column='Result'
        )

        # Create a DataFrame for failure items
        failure_df = pd.DataFrame({
            'ID': [1, 2],
            'Column1': [-1, -2],
            'Result': [False, False]
        })

        # Set up the get_failing_items method to return our DataFrame
        result.get_failing_items.return_value = failure_df

        # Set up rule results
        rule_results = {'test_rule': result}

        # Generate the HTML report
        output_path = os.path.join(self.temp_dir.name, 'test_report.html')
        result_path = self.report_generator.generate_html(
            self.sample_results, rule_results, output_path
        )

        # Verify the file was created
        self.assertTrue(os.path.exists(result_path))

        # Read the content and verify some expected elements
        with open(result_path, 'r') as f:
            content = f.read()

        self.assertIn('Test Rule', content)
        self.assertIn('A test rule', content)
        self.assertIn('Failures: 2', content)

    @patch('xlsxwriter.Workbook')
    def test_create_summary_sheet(self, mock_workbook_class):
        """Test creation of summary sheet in Excel report."""
        # Set up the mock workbook and worksheet
        mock_workbook = MagicMock()
        mock_workbook_class.return_value = mock_workbook

        mock_worksheet = MagicMock()
        mock_workbook.add_worksheet.return_value = mock_worksheet

        # Set up formats
        formats = {
            'title': MagicMock(),
            'header': MagicMock(),
            'subheader': MagicMock(),
            'normal': MagicMock(),
            'number': MagicMock(),
            'percentage': MagicMock(),
            'gc': MagicMock(),
            'pc': MagicMock(),
            'dnc': MagicMock()
        }

        # Call the method
        self.report_generator.create_summary_sheet(mock_workbook, self.sample_results, formats)

        # Verify worksheet was created
        mock_workbook.add_worksheet.assert_called_once_with('Summary')

        # Verify content was written
        # We'll just check a few key calls
        mock_worksheet.merge_range.assert_any_call(
            'A1:G1', 'QA Analytics Framework - Validation Summary', formats['title']
        )

        # Verify status was written with correct format
        calls = mock_worksheet.write.call_args_list
        status_written = False
        for call in calls:
            args = call[0]
            if len(args) >= 3 and args[2] == 'PARTIALLY_COMPLIANT' and args[3] == formats['pc']:
                status_written = True
                break

        self.assertTrue(status_written, "Status wasn't written with correct format")

    def test_organize_display_columns(self):
        """Test organization of display columns for reports."""
        # Create a test DataFrame
        df = pd.DataFrame({
            'ID': [1, 2],
            'Name': ['Test1', 'Test2'],
            'Value': [10, 20],
            'Date': pd.to_datetime(['2023-01-01', '2023-01-02']),
            'Result': [False, True],
            'Calc_Reason': ['Value too low', 'Pass'],
            'Extra': ['x', 'y']
        })

        # Test organization with formula columns
        formula_columns = ['Value', 'Date']
        result_column = 'Result'
        error_column = None

        organized = self.report_generator._organize_display_columns(
            df, formula_columns, result_column, error_column
        )

        # Check that order is sensible:
        # 1. Key columns first
        self.assertEqual(organized[0], 'ID')
        self.assertEqual(organized[1], 'Name')

        # 2. Formula columns next
        self.assertIn('Value', organized[2:4])
        self.assertIn('Date', organized[2:4])

        # 3. Calculation columns
        self.assertEqual(organized[4], 'Calc_Reason')

        # 4. Result column
        self.assertEqual(organized[5], 'Result')

        # 5. Remaining columns
        self.assertEqual(organized[6], 'Extra')

    @unittest.skipIf(not xlsxwriter, "xlsxwriter not installed")
    def test_report_generation_integration(self):
        """Integration test for report generation with a small dataset."""
        # Create a very simple rule and result
        rule = MagicMock(
            rule_id='test_rule',
            name='Test Rule',
            description='A test rule',
            formula='=[Amount] > 0',
            category='data_quality',
            severity='medium'
        )

        # Create a DataFrame for the result
        df = pd.DataFrame({
            'ID': [1, 2, 3],
            'Amount': [-10, 20, 30],
            'Result_Test Rule': [False, True, True]
        })

        result = MagicMock(
            rule=rule,
            compliance_status='PC',
            compliance_metrics={
                'total_count': 3,
                'gc_count': 2,
                'pc_count': 0,
                'dnc_count': 1,
                'error_count': 0
            },
            result_column='Result_Test Rule',
            result_df=df,
            summary={
                'rule_id': 'test_rule',
                'rule_name': 'Test Rule',
                'compliance_status': 'PC',
                'compliance_rate': 0.67,
                'total_items': 3,
                'gc_count': 2,
                'pc_count': 0,
                'dnc_count': 1,
                'error_count': 0
            }
        )

        # Set up the get_failing_items method
        failing_df = df[df['Result_Test Rule'] == False].copy()
        result.get_failing_items.return_value = failing_df

        # Create rule results dictionary
        rule_results = {'test_rule': result}

        # Update sample results
        results = self.sample_results.copy()
        results['rule_results']['test_rule'] = result.summary

        # Generate Excel report
        excel_path = os.path.join(self.temp_dir.name, 'test_report.xlsx')

        # This will create an actual Excel file
        mock_formats = {
            'title': MagicMock(),
            'header': MagicMock(),
            'subheader': MagicMock(),
            'normal': MagicMock(),
            'number': MagicMock(),
            'percentage': MagicMock(),
            'gc': MagicMock(),
            'pc': MagicMock(),
            'dnc': MagicMock()
        }
        with patch.object(ReportGenerator, '_create_excel_formats', return_value=mock_formats):
            output_path = self.report_generator.generate_excel(
                results, rule_results, excel_path
            )

        # Verify file exists
        self.assertTrue(os.path.exists(output_path))

        # Generate HTML report
        html_path = os.path.join(self.temp_dir.name, 'test_report.html')
        html_output = self.report_generator.generate_html(
            results, rule_results, html_path
        )

        # Verify file exists
        self.assertTrue(os.path.exists(html_output))
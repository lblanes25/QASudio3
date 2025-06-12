"""
Unit tests for IAGScoringCalculator class.

Tests the exact IAG scoring methodology with verified examples from the Excel specification.
"""

import unittest
from unittest.mock import Mock
from core.scoring.iag_scoring_calculator import IAGScoringCalculator, IAGScoringResult


class TestIAGScoringCalculator(unittest.TestCase):
    """Test IAG scoring calculations against known examples"""
    
    def setUp(self):
        """Initialize calculator for each test"""
        self.calculator = IAGScoringCalculator()
    
    def test_initialization(self):
        """Test proper initialization of rating weights and thresholds"""
        self.assertEqual(self.calculator.rating_weights['GC'], 5)
        self.assertEqual(self.calculator.rating_weights['PC'], 3)
        self.assertEqual(self.calculator.rating_weights['DNC'], 1)
        self.assertEqual(self.calculator.rating_weights['N/A'], 0)
        
        self.assertEqual(self.calculator.rating_thresholds['GC'], 0.80)
        self.assertEqual(self.calculator.rating_thresholds['PC'], 0.50)
        self.assertEqual(self.calculator.rating_thresholds['DNC'], 0.00)
    
    def test_calculate_iag_weighted_score_all_gc(self):
        """Test Case 1: All GC (from Excel row 31) - should be 100%"""
        score = self.calculator.calculate_iag_weighted_score(
            gc_count=1, pc_count=0, dnc_count=0, total_count=1
        )
        self.assertEqual(score, 1.0)  # 100%
    
    def test_calculate_iag_weighted_score_all_dnc(self):
        """Test Case 2: All DNC (from Excel row 32) - should be 20%"""
        score = self.calculator.calculate_iag_weighted_score(
            gc_count=0, pc_count=0, dnc_count=1, total_count=1
        )
        self.assertEqual(score, 0.2)  # 20%
    
    def test_calculate_iag_weighted_score_mixed(self):
        """Test Case 3: Mixed results (2 GC, 1 PC, 1 DNC) - should be 70%"""
        score = self.calculator.calculate_iag_weighted_score(
            gc_count=2, pc_count=1, dnc_count=1, total_count=4
        )
        # ((2*5) + (1*3) + (1*1)) / (4*5) = 14/20 = 0.7
        self.assertEqual(score, 0.7)  # 70%
    
    def test_calculate_iag_weighted_score_no_applicable(self):
        """Test with no applicable tests - should return N/A"""
        score = self.calculator.calculate_iag_weighted_score(
            gc_count=0, pc_count=0, dnc_count=0, total_count=0
        )
        self.assertEqual(score, "N/A")
    
    def test_assign_iag_rating_gc(self):
        """Test rating assignment for GC (>= 80%)"""
        self.assertEqual(self.calculator.assign_iag_rating(0.80), "GC")  # Exactly 80%
        self.assertEqual(self.calculator.assign_iag_rating(0.85), "GC")  # Above 80%
        self.assertEqual(self.calculator.assign_iag_rating(1.0), "GC")   # 100%
    
    def test_assign_iag_rating_pc(self):
        """Test rating assignment for PC (50% - 79%)"""
        self.assertEqual(self.calculator.assign_iag_rating(0.50), "PC")  # Exactly 50%
        self.assertEqual(self.calculator.assign_iag_rating(0.70), "PC")  # 70%
        self.assertEqual(self.calculator.assign_iag_rating(0.79), "PC")  # Just below 80%
    
    def test_assign_iag_rating_dnc(self):
        """Test rating assignment for DNC (< 50%)"""
        self.assertEqual(self.calculator.assign_iag_rating(0.0), "DNC")   # 0%
        self.assertEqual(self.calculator.assign_iag_rating(0.20), "DNC")  # 20%
        self.assertEqual(self.calculator.assign_iag_rating(0.49), "DNC")  # Just below 50%
    
    def test_assign_iag_rating_na(self):
        """Test rating assignment for N/A score"""
        self.assertEqual(self.calculator.assign_iag_rating("N/A"), "N/A")
    
    def test_calculate_leader_score_all_gc(self):
        """Test leader score calculation with all GC results"""
        rule_results = [
            {'compliance_status': 'GC'},
            {'compliance_status': 'GC'},
            {'compliance_status': 'GC'}
        ]
        
        result = self.calculator.calculate_leader_score(rule_results)
        
        self.assertEqual(result.gc_count, 3)
        self.assertEqual(result.pc_count, 0)
        self.assertEqual(result.dnc_count, 0)
        self.assertEqual(result.na_count, 0)
        self.assertEqual(result.total_applicable, 3)
        self.assertEqual(result.weighted_score, 1.0)  # 100%
        self.assertEqual(result.rating, "GC")
    
    def test_calculate_leader_score_mixed_with_na(self):
        """Test leader score calculation with mixed results including N/A"""
        rule_results = [
            {'compliance_status': 'GC'},
            {'compliance_status': 'PC'},
            {'compliance_status': 'DNC'},
            {'compliance_status': 'N/A'},
            {'compliance_status': 'GC'}
        ]
        
        result = self.calculator.calculate_leader_score(rule_results)
        
        self.assertEqual(result.gc_count, 2)
        self.assertEqual(result.pc_count, 1)
        self.assertEqual(result.dnc_count, 1)
        self.assertEqual(result.na_count, 1)
        self.assertEqual(result.total_applicable, 4)  # Excludes N/A
        self.assertEqual(result.total_count, 5)       # Includes N/A
        self.assertEqual(result.weighted_score, 0.7)  # 70%
        self.assertEqual(result.rating, "PC")
    
    def test_calculate_leader_score_empty_results(self):
        """Test leader score calculation with no results"""
        result = self.calculator.calculate_leader_score([])
        
        self.assertEqual(result.gc_count, 0)
        self.assertEqual(result.pc_count, 0)
        self.assertEqual(result.dnc_count, 0)
        self.assertEqual(result.na_count, 0)
        self.assertEqual(result.total_applicable, 0)
        self.assertEqual(result.weighted_score, "N/A")
        self.assertEqual(result.rating, "N/A")
    
    def test_calculate_overall_iag_score(self):
        """Test overall IAG score calculation across multiple leaders"""
        all_rule_results = {
            'Leader A': [
                {'compliance_status': 'GC'},
                {'compliance_status': 'GC'},
                {'compliance_status': 'PC'}
            ],
            'Leader B': [
                {'compliance_status': 'PC'},
                {'compliance_status': 'DNC'},
                {'compliance_status': 'DNC'}
            ],
            'Leader C': [
                {'compliance_status': 'GC'},
                {'compliance_status': 'N/A'},
                {'compliance_status': 'PC'}
            ]
        }
        
        scores = self.calculator.calculate_overall_iag_score(
            all_rule_results, 'Audit Leader'
        )
        
        # Check individual leader scores
        self.assertIn('Leader A', scores)
        self.assertIn('Leader B', scores)
        self.assertIn('Leader C', scores)
        self.assertIn('overall', scores)
        
        # Check overall calculation
        overall = scores['overall']
        self.assertEqual(overall.gc_count, 3)    # 2 + 0 + 1
        self.assertEqual(overall.pc_count, 2)    # 1 + 1 + 1
        self.assertEqual(overall.dnc_count, 2)   # 0 + 2 + 0
        self.assertEqual(overall.na_count, 1)    # 0 + 0 + 1
        self.assertEqual(overall.total_applicable, 7)  # Excludes N/A
        
        # Verify weighted score: ((3*5) + (2*3) + (2*1)) / (7*5) = 23/35 ≈ 0.657
        self.assertAlmostEqual(overall.weighted_score, 23/35, places=4)
        self.assertEqual(overall.rating, "PC")  # Between 50% and 80%
    
    def test_format_percentage(self):
        """Test percentage formatting"""
        self.assertEqual(self.calculator.format_percentage(0.756), "75.6%")
        self.assertEqual(self.calculator.format_percentage(0.756, 2), "75.60%")
        self.assertEqual(self.calculator.format_percentage(1.0), "100.0%")
        self.assertEqual(self.calculator.format_percentage(0.0), "0.0%")
        self.assertEqual(self.calculator.format_percentage("N/A"), "N/A")
    
    def test_edge_cases(self):
        """Test edge cases and boundary conditions"""
        # Test with missing compliance_status
        rule_results = [
            {'some_other_key': 'value'},
            {'compliance_status': 'GC'}
        ]
        result = self.calculator.calculate_leader_score(rule_results)
        self.assertEqual(result.gc_count, 1)
        self.assertEqual(result.na_count, 1)  # Missing status treated as N/A
        
        # Test with unknown compliance status
        rule_results = [
            {'compliance_status': 'UNKNOWN'},
            {'compliance_status': 'GC'}
        ]
        result = self.calculator.calculate_leader_score(rule_results)
        self.assertEqual(result.gc_count, 1)
        self.assertEqual(result.na_count, 1)  # Unknown status treated as N/A
    
    def test_iag_scoring_result_dataclass(self):
        """Test IAGScoringResult dataclass properties"""
        result = IAGScoringResult(
            gc_count=5,
            pc_count=3,
            dnc_count=2,
            na_count=1,
            total_applicable=10,
            weighted_score=0.75,
            rating="PC"
        )
        
        # Test total_count property
        self.assertEqual(result.total_count, 11)  # 10 applicable + 1 N/A


if __name__ == '__main__':
    unittest.main()
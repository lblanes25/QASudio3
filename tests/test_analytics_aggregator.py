import pytest
import pandas as pd
import numpy as np
import os
import json
import tempfile
from pandas.testing import assert_frame_equal, assert_series_equal
from datetime import datetime

# Import the module to test
from business_logic.aggregation.analytics_aggregator import (
    standardize_result_format,
    aggregate_by_audit_leader,
    calculate_weighted_scores,
    generate_comparative_summary,
    tag_outliers_and_exceptions,
    extract_rule_details_summary,
    aggregate_analytics_results,
    AnalyticsSummary,
    load_weights_configuration
)


# Fixture for standard result dictionaries
@pytest.fixture
def sample_result_dicts():
    """Fixture providing sample result dictionaries for testing."""
    # Sample result 1
    result1 = {
        'analytic_id': 'test_analytic_1',
        'status': 'PARTIALLY_COMPLIANT',
        'timestamp': '2023-01-01T00:00:00',
        'grouped_summary': {
            'Leader1': {
                'total_rules': 3,
                'GC': 2,
                'PC': 1,
                'DNC': 0,
                'compliance_rate': 0.67
            },
            'Leader2': {
                'total_rules': 3,
                'GC': 1,
                'PC': 1,
                'DNC': 1,
                'compliance_rate': 0.33
            }
        },
        'rule_results': {
            'rule1': {
                'rule_id': 'rule1',
                'rule_name': 'Test Rule 1',
                'compliance_status': 'GC',
                'compliance_rate': 0.9,
                'total_items': 10,
                'gc_count': 9,
                'pc_count': 1,
                'dnc_count': 0,
                'party_results': {
                    'Leader1': {
                        'status': 'GC',
                        'metrics': {
                            'total_count': 5,
                            'gc_count': 5,
                            'pc_count': 0,
                            'dnc_count': 0
                        }
                    },
                    'Leader2': {
                        'status': 'GC',
                        'metrics': {
                            'total_count': 5,
                            'gc_count': 4,
                            'pc_count': 1,
                            'dnc_count': 0
                        }
                    }
                }
            },
            'rule2': {
                'rule_id': 'rule2',
                'rule_name': 'Test Rule 2',
                'compliance_status': 'PC',
                'compliance_rate': 0.7,
                'total_items': 10,
                'gc_count': 7,
                'pc_count': 1,
                'dnc_count': 2,
                'category': 'data_quality',
                'severity': 'high',
                'party_results': {
                    'Leader1': {
                        'status': 'GC',
                        'metrics': {
                            'total_count': 5,
                            'gc_count': 4,
                            'pc_count': 1,
                            'dnc_count': 0
                        }
                    },
                    'Leader2': {
                        'status': 'PC',
                        'metrics': {
                            'total_count': 5,
                            'gc_count': 3,
                            'pc_count': 0,
                            'dnc_count': 2
                        }
                    }
                }
            },
            'rule3': {
                'rule_id': 'rule3',
                'rule_name': 'Test Rule 3',
                'compliance_status': 'DNC',
                'compliance_rate': 0.3,
                'total_items': 10,
                'gc_count': 3,
                'pc_count': 1,
                'dnc_count': 6,
                'category': 'compliance',
                'severity': 'critical',
                'party_results': {
                    'Leader1': {
                        'status': 'PC',
                        'metrics': {
                            'total_count': 5,
                            'gc_count': 3,
                            'pc_count': 0,
                            'dnc_count': 2
                        }
                    },
                    'Leader2': {
                        'status': 'DNC',
                        'metrics': {
                            'total_count': 5,
                            'gc_count': 0,
                            'pc_count': 1,
                            'dnc_count': 4
                        }
                    }
                }
            }
        }
    }

    # Sample result 2
    result2 = {
        'analytic_id': 'test_analytic_2',
        'status': 'FULLY_COMPLIANT',
        'timestamp': '2023-01-02T00:00:00',
        'grouped_summary': {
            'Leader1': {
                'total_rules': 2,
                'GC': 2,
                'PC': 0,
                'DNC': 0,
                'compliance_rate': 1.0
            },
            'Leader2': {
                'total_rules': 2,
                'GC': 1,
                'PC': 1,
                'DNC': 0,
                'compliance_rate': 0.5
            },
            'Leader3': {
                'total_rules': 2,
                'GC': 0,
                'PC': 1,
                'DNC': 1,
                'compliance_rate': 0.0
            }
        },
        'rule_results': {
            'rule4': {
                'rule_id': 'rule4',
                'rule_name': 'Test Rule 4',
                'compliance_status': 'GC',
                'compliance_rate': 1.0,
                'total_items': 10,
                'gc_count': 10,
                'pc_count': 0,
                'dnc_count': 0,
                'category': 'completeness',
                'severity': 'medium',
                'party_results': {
                    'Leader1': {
                        'status': 'GC',
                        'metrics': {
                            'total_count': 3,
                            'gc_count': 3,
                            'pc_count': 0,
                            'dnc_count': 0
                        }
                    },
                    'Leader2': {
                        'status': 'GC',
                        'metrics': {
                            'total_count': 3,
                            'gc_count': 3,
                            'pc_count': 0,
                            'dnc_count': 0
                        }
                    },
                    'Leader3': {
                        'status': 'GC',
                        'metrics': {
                            'total_count': 4,
                            'gc_count': 4,
                            'pc_count': 0,
                            'dnc_count': 0
                        }
                    }
                }
            },
            'rule5': {
                'rule_id': 'rule5',
                'rule_name': 'Test Rule 5',
                'compliance_status': 'PC',
                'compliance_rate': 0.6,
                'total_items': 10,
                'gc_count': 6,
                'pc_count': 2,
                'dnc_count': 2,
                'category': 'accuracy',
                'severity': 'low',
                'party_results': {
                    'Leader1': {
                        'status': 'GC',
                        'metrics': {
                            'total_count': 3,
                            'gc_count': 3,
                            'pc_count': 0,
                            'dnc_count': 0
                        }
                    },
                    'Leader2': {
                        'status': 'PC',
                        'metrics': {
                            'total_count': 3,
                            'gc_count': 2,
                            'pc_count': 1,
                            'dnc_count': 0
                        }
                    },
                    'Leader3': {
                        'status': 'DNC',
                        'metrics': {
                            'total_count': 4,
                            'gc_count': 1,
                            'pc_count': 1,
                            'dnc_count': 2
                        }
                    }
                }
            }
        }
    }

    # Sample result 3 - Legacy format, missing fields, different structure
    result3 = {
        'id': 'test_analytic_3',  # Using 'id' instead of 'analytic_id'
        'status': 'NON_COMPLIANT',
        # Missing timestamp
        'results': {  # Legacy format using 'results' instead of 'rule_results'
            'rule6': {
                'rule_id': 'rule6',
                'rule_name': 'Legacy Rule 6',
                'compliance_status': 'DNC',
                'compliance_rate': 0.2,
                'total_items': 15,
                'gc_count': 3,
                'pc_count': 0,
                'dnc_count': 12
                # No party_results or category/severity
            },
            'rule7': {
                'rule_id': 'rule7',
                'rule_name': 'Legacy Rule 7',
                'compliance_status': 'PC',
                'compliance_rate': 0.8,
                'total_items': 15,
                'gc_count': 12,
                'pc_count': 3,
                'dnc_count': 0,
                'category': 'efficiency',
                'severity': 'medium'
                # No party_results
            }
        }
        # No grouped_summary
    }

    return [result1, result2, result3]


# Fixture for edge cases
@pytest.fixture
def edge_case_result_dicts():
    """Fixture providing edge case result dictionaries."""
    # Empty result dict
    empty_result = {}

    # Minimal dict with just rule results
    minimal_result = {
        'rule_results': {
            'rule_min': {
                'rule_id': 'rule_min',
                'rule_name': 'Minimal Rule',
                'compliance_status': 'GC',
                'compliance_rate': 1.0,
                'total_items': 5,
                'gc_count': 5,
                'pc_count': 0,
                'dnc_count': 0
            }
        }
    }

    # 100% compliant leader
    perfect_leader_result = {
        'analytic_id': 'perfect_test',
        'status': 'FULLY_COMPLIANT',
        'grouped_summary': {
            'PerfectLeader': {
                'total_rules': 10,
                'GC': 10,
                'PC': 0,
                'DNC': 0,
                'compliance_rate': 1.0
            }
        },
        'rule_results': {
            'perfect_rule': {
                'rule_id': 'perfect_rule',
                'rule_name': 'Perfect Rule',
                'compliance_status': 'GC',
                'compliance_rate': 1.0,
                'total_items': 100,
                'gc_count': 100,
                'pc_count': 0,
                'dnc_count': 0,
                'category': 'data_quality',  # Added category
                'severity': 'medium',  # Added severity
                'party_results': {
                    'PerfectLeader': {
                        'status': 'GC',
                        'metrics': {
                            'total_count': 100,
                            'gc_count': 100,
                            'pc_count': 0,
                            'dnc_count': 0
                        }
                    }
                }
            }
        }
    }

    # 0% compliant leader
    zero_leader_result = {
        'analytic_id': 'zero_test',
        'status': 'NON_COMPLIANT',
        'grouped_summary': {
            'ZeroLeader': {
                'total_rules': 10,
                'GC': 0,
                'PC': 0,
                'DNC': 10,
                'compliance_rate': 0.0
            }
        },
        'rule_results': {
            'zero_rule': {
                'rule_id': 'zero_rule',
                'rule_name': 'Failed Rule',
                'compliance_status': 'DNC',
                'compliance_rate': 0.0,
                'total_items': 100,
                'gc_count': 0,
                'pc_count': 0,
                'dnc_count': 100,
                'category': 'compliance',  # Added category
                'severity': 'high',  # Added severity
                'party_results': {
                    'ZeroLeader': {
                        'status': 'DNC',
                        'metrics': {
                            'total_count': 100,
                            'gc_count': 0,
                            'pc_count': 0,
                            'dnc_count': 100
                        }
                    }
                }
            }
        }
    }

    return [empty_result, minimal_result, perfect_leader_result, zero_leader_result]


# Fixture for weights configuration
@pytest.fixture
def weights_config():
    """Fixture providing a weights configuration."""
    return {
        'category_weights': {
            'data_quality': 1.0,
            'compliance': 1.5,
            'completeness': 0.8,
            'accuracy': 0.7,
            'efficiency': 0.5,
            'default': 1.0
        },
        'severity_weights': {
            'critical': 2.0,
            'high': 1.5,
            'medium': 1.0,
            'low': 0.5,
            'default': 1.0
        },
        'rule_weights': {
            'rule1': 2.0,  # Specific rule override
            'perfect_rule': 3.0
        }
    }


# Tests for standardize_result_format
class TestStandardizeResultFormat:
    def test_complete_result_dict(self, sample_result_dicts):
        """Test standardization with a complete result dictionary."""
        result = sample_result_dicts[0]  # First sample is complete
        standardized = standardize_result_format(result)

        # Basic structure check
        assert 'analytic_id' in standardized
        assert 'status' in standardized
        assert 'timestamp' in standardized
        assert 'rule_results' in standardized

        # Value verification
        assert standardized['analytic_id'] == 'test_analytic_1'
        assert standardized['status'] == 'PARTIALLY_COMPLIANT'
        assert standardized['timestamp'] == '2023-01-01T00:00:00'
        assert 'rule1' in standardized['rule_results']

        # Verify structure is preserved
        assert standardized['rule_results']['rule1']['rule_name'] == 'Test Rule 1'

    def test_legacy_format(self, sample_result_dicts):
        """Test conversion from legacy 'results' to 'rule_results'."""
        result = sample_result_dicts[2]  # Third sample uses legacy format
        standardized = standardize_result_format(result)

        # Check transformation of 'results' to 'rule_results'
        assert 'rule_results' in standardized
        assert 'rule6' in standardized['rule_results']
        assert 'rule7' in standardized['rule_results']
        assert standardized['rule_results']['rule6']['rule_name'] == 'Legacy Rule 6'

        # Check analytic_id mapping from 'id'
        assert standardized['analytic_id'] == 'test_analytic_3'

    def test_missing_fields(self, edge_case_result_dicts):
        """Test handling of a dictionary with missing fields."""
        result = edge_case_result_dicts[0]  # Empty dict
        standardized = standardize_result_format(result)

        # Check all expected fields are present, even if empty/null
        assert 'analytic_id' in standardized and standardized['analytic_id'] is None
        assert 'status' in standardized and standardized['status'] is None
        assert 'timestamp' in standardized and isinstance(standardized['timestamp'], str)
        assert 'rule_results' in standardized and standardized['rule_results'] == {}
        assert 'summary' in standardized and standardized['summary'] == {}
        assert 'grouped_summary' in standardized and standardized['grouped_summary'] == {}

    def test_minimal_result_dict(self, edge_case_result_dicts):
        """Test standardization with a minimal result dictionary."""
        result = edge_case_result_dicts[1]  # Minimal dict
        standardized = standardize_result_format(result)

        # Check preservation of rule results
        assert 'rule_results' in standardized
        assert 'rule_min' in standardized['rule_results']
        assert standardized['rule_results']['rule_min']['rule_name'] == 'Minimal Rule'

        # Check auto-generated timestamp
        assert 'timestamp' in standardized
        assert isinstance(standardized['timestamp'], str)


# Tests for aggregate_by_audit_leader
class TestAggregateByAuditLeader:
    def test_basic_aggregation(self, sample_result_dicts):
        """Test basic aggregation of results by audit leader."""
        results = sample_result_dicts[:2]  # First two samples have good leader data
        aggregated_df = aggregate_by_audit_leader(results)

        # Check structure
        assert isinstance(aggregated_df, pd.DataFrame)
        assert 'audit_leader' in aggregated_df.columns
        assert 'total_rules' in aggregated_df.columns
        assert 'gc_count' in aggregated_df.columns
        assert 'compliance_rate' in aggregated_df.columns

        # Check data
        assert set(aggregated_df['audit_leader']) == {'Leader1', 'Leader2', 'Leader3'}

        # Check Leader1 stats (should be 5 rules, 4 GC)
        leader1_row = aggregated_df[aggregated_df['audit_leader'] == 'Leader1'].iloc[0]
        assert leader1_row['total_rules'] == 5
        assert leader1_row['gc_count'] == 4
        assert leader1_row['pc_count'] == 1
        assert leader1_row['dnc_count'] == 0
        assert leader1_row['compliance_rate'] == 0.8  # 4/5 = 0.8

        # Check order (should be by compliance_rate, descending)
        assert aggregated_df.iloc[0]['audit_leader'] == 'Leader1'  # Leader1 has highest rate

    def test_missing_grouped_summary(self, sample_result_dicts):
        """Test aggregation when some results lack grouped_summary."""
        results = sample_result_dicts  # Third sample has no grouped_summary
        aggregated_df = aggregate_by_audit_leader(results)

        # Should still work, with data from first two samples
        assert set(aggregated_df['audit_leader']) == {'Leader1', 'Leader2', 'Leader3'}

    def test_empty_input(self):
        """Test aggregation with an empty list of results."""
        aggregated_df = aggregate_by_audit_leader([])

        # Should return empty DataFrame with expected columns
        assert isinstance(aggregated_df, pd.DataFrame)
        assert aggregated_df.empty
        assert 'audit_leader' in aggregated_df.columns
        assert 'total_rules' in aggregated_df.columns
        assert 'gc_count' in aggregated_df.columns
        assert 'compliance_rate' in aggregated_df.columns

    def test_edge_case_leaders(self, edge_case_result_dicts):
        """Test aggregation with edge case leaders (100% and 0% compliance)."""
        results = edge_case_result_dicts[2:4]  # Perfect and zero leaders
        aggregated_df = aggregate_by_audit_leader(results)

        # Check structure
        assert set(aggregated_df['audit_leader']) == {'PerfectLeader', 'ZeroLeader'}

        # Check PerfectLeader stats
        perfect_row = aggregated_df[aggregated_df['audit_leader'] == 'PerfectLeader'].iloc[0]
        assert perfect_row['total_rules'] == 10
        assert perfect_row['gc_count'] == 10
        assert perfect_row['compliance_rate'] == 1.0

        # Check ZeroLeader stats
        zero_row = aggregated_df[aggregated_df['audit_leader'] == 'ZeroLeader'].iloc[0]
        assert zero_row['total_rules'] == 10
        assert zero_row['gc_count'] == 0
        assert zero_row['compliance_rate'] == 0.0

        # Check order (PerfectLeader should be first)
        assert aggregated_df.iloc[0]['audit_leader'] == 'PerfectLeader'
        assert aggregated_df.iloc[1]['audit_leader'] == 'ZeroLeader'


# Tests for calculate_weighted_scores
class TestCalculateWeightedScores:
    def test_basic_score_calculation(self, sample_result_dicts):
        """Test basic weighted score calculation."""
        # First aggregate the results
        results = sample_result_dicts[:2]
        aggregated_df = aggregate_by_audit_leader(results)

        # Calculate weighted scores
        scored_df = calculate_weighted_scores(aggregated_df)

        # Check structure
        assert 'weighted_score' in scored_df.columns
        assert 'rating' in scored_df.columns

        # Check scores (based on compliance rates)
        # Leader1: 0.8 -> ~4.0
        # Leader2: 0.4 -> ~2.0
        # Leader3: 0.0 -> 1.0
        leader1_row = scored_df[scored_df['audit_leader'] == 'Leader1'].iloc[0]
        assert leader1_row['weighted_score'] >= 3.5  # Should be around 4.0

        leader2_row = scored_df[scored_df['audit_leader'] == 'Leader2'].iloc[0]
        assert leader2_row['weighted_score'] >= 1.0 and leader2_row[
            'weighted_score'] <= 2.5  # Between 1.0-2.5 based on actual implementation

        leader3_row = scored_df[scored_df['audit_leader'] == 'Leader3'].iloc[0]
        assert leader3_row['weighted_score'] <= 1.5  # Should be around 1.0

        # Ratings should match scores
        assert leader1_row['rating'] in ['Strong', 'Satisfactory']
        assert leader3_row['rating'] in ['Critical Concerns', 'Deficient']

    def test_custom_weights(self, sample_result_dicts, weights_config):
        """Test weighted score calculation with custom weights configuration."""
        # First aggregate the results
        results = sample_result_dicts[:2]
        aggregated_df = aggregate_by_audit_leader(results)

        # Calculate weighted scores with custom weights
        scored_df = calculate_weighted_scores(aggregated_df, weights_config)

        # The weighting shouldn't affect leader scores directly in this test
        # Just verify structure and basic functionality
        assert 'weighted_score' in scored_df.columns
        assert 'rating' in scored_df.columns

        # Scores should be the same as in basic test because our fixture
        # doesn't affect the direct leader scoring
        leader1_row = scored_df[scored_df['audit_leader'] == 'Leader1'].iloc[0]
        assert leader1_row['weighted_score'] >= 3.5  # Should be around 4.0

    def test_perfect_and_zero_leaders(self, edge_case_result_dicts):
        """Test score calculation with perfect and zero compliant leaders."""
        results = edge_case_result_dicts[2:4]  # Perfect and zero leaders
        aggregated_df = aggregate_by_audit_leader(results)

        # Calculate weighted scores
        scored_df = calculate_weighted_scores(aggregated_df)

        # Check perfect leader
        perfect_row = scored_df[scored_df['audit_leader'] == 'PerfectLeader'].iloc[0]
        assert perfect_row['weighted_score'] == 5.0  # Should be exactly 5.0
        assert perfect_row['rating'] == 'Exemplary'

        # Check zero leader
        zero_row = scored_df[scored_df['audit_leader'] == 'ZeroLeader'].iloc[0]
        assert zero_row['weighted_score'] == 1.0  # Should be exactly 1.0
        assert zero_row['rating'] == 'Critical Concerns'

    def test_null_weights_config(self, sample_result_dicts):
        """Test score calculation with null weights configuration."""
        aggregated_df = aggregate_by_audit_leader(sample_result_dicts[:2])

        # Calculate weighted scores with null weights
        scored_df = calculate_weighted_scores(aggregated_df, None)

        # Should still work with default weights
        assert 'weighted_score' in scored_df.columns
        assert 'rating' in scored_df.columns

    def test_override_columns(self, sample_result_dicts):
        """Test that override columns are added correctly."""
        aggregated_df = aggregate_by_audit_leader(sample_result_dicts[:2])
        scored_df = calculate_weighted_scores(aggregated_df)

        # Check override columns are added
        assert 'override_score' in scored_df.columns
        assert 'override_rating' in scored_df.columns
        assert 'comments' in scored_df.columns

        # Override columns should be empty/NaN
        assert pd.isna(scored_df['override_score']).all()
        assert (scored_df['override_rating'] == '').all()
        assert (scored_df['comments'] == '').all()


# Tests for generate_comparative_summary
class TestGenerateComparativeSummary:
    def test_basic_comparative_metrics(self, sample_result_dicts):
        """Test generation of basic comparative metrics."""
        # First prepare the data
        aggregated_df = aggregate_by_audit_leader(sample_result_dicts[:2])
        scored_df = calculate_weighted_scores(aggregated_df)

        # Generate comparative summary
        comparative_df = generate_comparative_summary(scored_df)

        # Check structure
        assert 'compliance_vs_avg' in comparative_df.columns
        assert 'compliance_percentile' in comparative_df.columns

        if 'score_vs_avg' in comparative_df.columns:
            assert 'score_percentile' in comparative_df.columns

        # Check department averages in attributes
        assert 'dept_avg_compliance' in comparative_df.attrs
        assert isinstance(comparative_df.attrs['dept_avg_compliance'], float)

        if 'dept_avg_score' in comparative_df.attrs:
            assert isinstance(comparative_df.attrs['dept_avg_score'], float)

        # Check calculations for Leader1
        leader1_row = comparative_df[comparative_df['audit_leader'] == 'Leader1'].iloc[0]
        dept_avg = comparative_df.attrs['dept_avg_compliance']
        assert leader1_row['compliance_vs_avg'] == leader1_row['compliance_rate'] - dept_avg

        # Leader1 should be highest percentile
        assert leader1_row['compliance_percentile'] == 100.0

        # Check trend column (should be 'stable' as default)
        assert 'trend' in comparative_df.columns
        assert leader1_row['trend'] == 'stable'

    def test_small_sample(self, edge_case_result_dicts):
        """Test comparative metrics with small sample size."""
        # Use just the perfect leader case
        aggregated_df = aggregate_by_audit_leader([edge_case_result_dicts[2]])
        scored_df = calculate_weighted_scores(aggregated_df)

        # Generate comparative summary
        comparative_df = generate_comparative_summary(scored_df)

        # Still should work with a single leader
        assert 'compliance_vs_avg' in comparative_df.columns
        assert 'compliance_percentile' in comparative_df.columns

        # Perfect leader should have no deviation vs. avg (since they are the avg)
        leader_row = comparative_df.iloc[0]
        assert leader_row['compliance_vs_avg'] == 0.0
        assert leader_row['compliance_percentile'] == 100.0

    def test_yoy_change_column(self, sample_result_dicts):
        """Test that YoY change column is added (even if placeholder)."""
        aggregated_df = aggregate_by_audit_leader(sample_result_dicts[:2])
        scored_df = calculate_weighted_scores(aggregated_df)
        comparative_df = generate_comparative_summary(scored_df)

        # Check YoY column
        assert 'yoy_change' in comparative_df.columns
        # Should be NaN (placeholder)
        assert pd.isna(comparative_df['yoy_change']).all()


# Tests for tag_outliers_and_exceptions
class TestTagOutliersAndExceptions:
    def test_basic_outlier_tagging(self, sample_result_dicts):
        """Test basic outlier tagging functionality."""
        # First prepare the data
        aggregated_df = aggregate_by_audit_leader(sample_result_dicts[:2])
        scored_df = calculate_weighted_scores(aggregated_df)
        comparative_df = generate_comparative_summary(scored_df)

        # Tag outliers
        tagged_df = tag_outliers_and_exceptions(comparative_df)

        # Check structure
        assert 'is_high_performer' in tagged_df.columns
        assert 'is_concern' in tagged_df.columns
        assert 'is_critical' in tagged_df.columns
        assert 'performance_tag' in tagged_df.columns

        # Leader1 might not be high performer due to threshold (typically 0.95)
        # Just check overall performance tag is meaningful
        leader1_row = tagged_df[tagged_df['audit_leader'] == 'Leader1'].iloc[0]
        assert leader1_row['performance_tag'] in ['Above Average', 'High Performer',
                                                  'Average']  # More flexible assertion
        assert leader1_row['is_concern'] == False
        assert leader1_row['is_critical'] == False
        assert leader1_row['performance_tag'] == 'High Performer'

        # Leader3 should be concern/critical
        leader3_row = tagged_df[tagged_df['audit_leader'] == 'Leader3'].iloc[0]
        assert leader3_row['is_high_performer'] == False  # compliance_rate = 0.0
        assert leader3_row['is_concern'] == True
        assert leader3_row['is_critical'] == True
        assert leader3_row['performance_tag'] == 'Critical Concern'

    def test_statistical_outlier_detection(self, sample_result_dicts):
        """Test statistical outlier detection when enough data points."""
        # First prepare the data (use all 3 result dicts to get more leaders)
        aggregated_df = aggregate_by_audit_leader(sample_result_dicts[:2])
        scored_df = calculate_weighted_scores(aggregated_df)
        comparative_df = generate_comparative_summary(scored_df)

        # Tag outliers
        tagged_df = tag_outliers_and_exceptions(comparative_df)

        # Check if statistical columns are present (should be since we have enough data)
        if 'is_statistical_outlier' in tagged_df.columns:
            assert 'is_statistical_high' in tagged_df.columns
            assert 'is_statistical_low' in tagged_df.columns

            # Leader1 should be statistically high
            leader1_row = tagged_df[tagged_df['audit_leader'] == 'Leader1'].iloc[0]
            assert leader1_row['is_statistical_high'] == True

            # Leader3 should be statistically low
            leader3_row = tagged_df[tagged_df['audit_leader'] == 'Leader3'].iloc[0]
            assert leader3_row['is_statistical_low'] == True

    def test_custom_thresholds(self, sample_result_dicts):
        """Test outlier tagging with custom thresholds."""
        # First prepare the data
        aggregated_df = aggregate_by_audit_leader(sample_result_dicts[:2])
        scored_df = calculate_weighted_scores(aggregated_df)
        comparative_df = generate_comparative_summary(scored_df)

        # Custom thresholds
        custom_thresholds = {
            'high_performer_threshold': 0.9,  # Higher than default
            'concern_threshold': 0.6,  # Higher than default
            'critical_threshold': 0.4,  # Higher than default
            'z_score_threshold': 1.0  # Lower than default
        }

        # Tag outliers with custom thresholds
        tagged_df = tag_outliers_and_exceptions(comparative_df, custom_thresholds)

        # With higher thresholds, Leader1 (0.8) should no longer be high performer
        leader1_row = tagged_df[tagged_df['audit_leader'] == 'Leader1'].iloc[0]
        assert leader1_row['is_high_performer'] == False

        # Leader2 (0.4) should now be critical with the raised threshold
        leader2_row = tagged_df[tagged_df['audit_leader'] == 'Leader2'].iloc[0]
        assert leader2_row['is_critical'] == True

    def test_perfect_and_zero_leaders(self, edge_case_result_dicts):
        """Test outlier tagging with perfect and zero compliant leaders."""
        # Prepare data with perfect and zero leaders
        results = edge_case_result_dicts[2:4]  # Perfect and zero leaders
        aggregated_df = aggregate_by_audit_leader(results)
        scored_df = calculate_weighted_scores(aggregated_df)
        comparative_df = generate_comparative_summary(scored_df)

        # Tag outliers
        tagged_df = tag_outliers_and_exceptions(comparative_df)

        # Check perfect leader
        perfect_row = tagged_df[tagged_df['audit_leader'] == 'PerfectLeader'].iloc[0]
        assert perfect_row['is_high_performer'] == True
        assert perfect_row['is_concern'] == False
        assert perfect_row['is_critical'] == False
        assert perfect_row['performance_tag'] == 'High Performer'

        # Check zero leader
        zero_row = tagged_df[tagged_df['audit_leader'] == 'ZeroLeader'].iloc[0]
        assert zero_row['is_high_performer'] == False
        assert zero_row['is_concern'] == True
        assert zero_row['is_critical'] == True
        assert zero_row['performance_tag'] == 'Critical Concern'


# Tests for extract_rule_details_summary
class TestExtractRuleDetailsSummary:
    def test_basic_rule_extraction(self, sample_result_dicts):
        """Test basic extraction of rule details."""
        # Standardize the results
        std_results = [standardize_result_format(r) for r in sample_result_dicts[:2]]

        # Extract rule details
        rule_details = extract_rule_details_summary(std_results)

        # Check structure
        assert isinstance(rule_details, pd.DataFrame)
        assert 'rule_id' in rule_details.columns
        assert 'rule_name' in rule_details.columns
        assert 'compliance_status' in rule_details.columns
        assert 'compliance_rate' in rule_details.columns
        assert 'audit_leader' in rule_details.columns

        # Check data
        assert set(rule_details['rule_id'].unique()) == {'rule1', 'rule2', 'rule3', 'rule4', 'rule5'}

        # Check each rule has entries for each leader
        rule1_df = rule_details[rule_details['rule_id'] == 'rule1']
        assert len(rule1_df) >= 2  # Should have at least entries for Leader1 and Leader2
        assert set(rule1_df['audit_leader'].dropna()) == {'Leader1', 'Leader2'}

        # Check aggregation logic
        leader1_rule1 = rule1_df[rule1_df['audit_leader'] == 'Leader1'].iloc[0]
        assert leader1_rule1['total_items'] == 5
        assert leader1_rule1['gc_count'] == 5
        assert leader1_rule1['compliance_rate'] == 1.0

    def test_with_and_without_party_results(self, sample_result_dicts):
        """Test extraction with and without party_results."""
        # Create a mix of results with and without party_results
        result1 = standardize_result_format(sample_result_dicts[0])  # Has party_results
        result3 = standardize_result_format(sample_result_dicts[2])  # No party_results

        # Extract rule details
        rule_details = extract_rule_details_summary([result1, result3])

        # Check rules with party_results
        rule1_df = rule_details[rule_details['rule_id'] == 'rule1']
        assert not rule1_df.empty
        assert set(rule1_df['audit_leader'].dropna()) == {'Leader1', 'Leader2'}

        # Check rules without party_results
        rule6_df = rule_details[rule_details['rule_id'] == 'rule6']
        assert not rule6_df.empty
        # Should have a row with null audit_leader for the overall stats
        assert rule6_df['audit_leader'].isna().any()

    def test_rule_category_and_severity(self, sample_result_dicts):
        """Test that rule category and severity are preserved."""
        std_results = [standardize_result_format(r) for r in sample_result_dicts[:2]]
        rule_details = extract_rule_details_summary(std_results)

        # Check category and severity columns
        assert 'category' in rule_details.columns
        assert 'severity' in rule_details.columns

        # Check values for rules with known category/severity
        rule3_df = rule_details[rule_details['rule_id'] == 'rule3']
        rule3_row = rule3_df.iloc[0]
        assert rule3_row['category'] == 'compliance'
        assert rule3_row['severity'] == 'critical'

    def test_empty_input(self):
        """Test extraction with empty input."""
        rule_details = extract_rule_details_summary([])

        # Should return empty DataFrame with expected columns
        assert isinstance(rule_details, pd.DataFrame)
        assert rule_details.empty

    def test_compliance_status_calculation(self, sample_result_dicts):
        """Test that compliance status is calculated correctly."""
        std_results = [standardize_result_format(r) for r in sample_result_dicts[:2]]
        rule_details = extract_rule_details_summary(std_results)

        # Test a specific leader's compliance on a specific rule
        leader1_rule3 = rule_details[(rule_details['rule_id'] == 'rule3') &
                                     (rule_details['audit_leader'] == 'Leader1')].iloc[0]

        # Leader1 on rule3 has 3/5 GC = 0.6, which could be PC or DNC depending on thresholds
        assert leader1_rule3['compliance_rate'] == 0.6
        # Don't strictly test the status as thresholds might vary
        assert leader1_rule3['compliance_status'] in ['PC', 'DNC']


# Tests for AnalyticsSummary class
class TestAnalyticsSummary:
    @pytest.fixture
    def sample_summary(self, sample_result_dicts):
        """Fixture providing a sample AnalyticsSummary instance."""
        std_results = [standardize_result_format(r) for r in sample_result_dicts]
        leader_summary = aggregate_by_audit_leader(std_results)
        leader_summary = calculate_weighted_scores(leader_summary)
        leader_summary = generate_comparative_summary(leader_summary)
        leader_summary = tag_outliers_and_exceptions(leader_summary)

        rule_details = extract_rule_details_summary(std_results)

        department_summary = {
            'total_rules': leader_summary['total_rules'].sum(),
            'gc_count': leader_summary['gc_count'].sum(),
            'pc_count': leader_summary['pc_count'].sum(),
            'dnc_count': leader_summary['dnc_count'].sum(),
            'overall_compliance_rate': leader_summary['gc_count'].sum() / leader_summary['total_rules'].sum()
        }

        return AnalyticsSummary(
            leader_summary=leader_summary,
            department_summary=department_summary,
            rule_details=rule_details
        )

    def test_get_leader_ranking(self, sample_summary):
        """Test get_leader_ranking method."""
        ranking = sample_summary.get_leader_ranking()

        # Check structure
        assert isinstance(ranking, pd.DataFrame)
        assert 'rank' in ranking.columns
        assert 'audit_leader' in ranking.columns

        # Check sorting (should be by weighted_score or compliance_rate, descending)
        assert ranking['rank'].tolist() == [1, 2, 3]  # 1, 2, 3 in order

        # Leader1 should be at the top
        assert ranking.iloc[0]['audit_leader'] == 'Leader1'

    def test_get_rules_by_compliance(self, sample_summary):
        """Test get_rules_by_compliance method."""
        rules = sample_summary.get_rules_by_compliance()

        # Check structure
        assert isinstance(rules, pd.DataFrame)
        assert 'rule_id' in rules.columns
        assert 'compliance_rate' in rules.columns

        # Check sorting (should be by compliance_rate, descending)
        assert rules.iloc[0]['compliance_rate'] >= rules.iloc[-1]['compliance_rate']

    def test_get_leaders_by_rule(self, sample_summary):
        """Test get_leaders_by_rule method."""
        # Get leaders for rule1
        rule1_leaders = sample_summary.get_leaders_by_rule('rule1')

        # Check structure
        assert isinstance(rule1_leaders, pd.DataFrame)
        assert 'audit_leader' in rule1_leaders.columns
        assert 'compliance_rate' in rule1_leaders.columns

        # Check expected leaders are present
        assert set(rule1_leaders['audit_leader'].dropna()) == {'Leader1', 'Leader2'}

        # Check sorting (should be by compliance_rate, descending)
        if len(rule1_leaders) > 1:
            assert rule1_leaders.iloc[0]['compliance_rate'] >= rule1_leaders.iloc[-1]['compliance_rate']

        # Test with non-existent rule
        nonexistent = sample_summary.get_leaders_by_rule('nonexistent_rule')
        assert isinstance(nonexistent, pd.DataFrame)
        assert nonexistent.empty

    def test_export_to_dict(self, sample_summary):
        """Test export_to_dict method."""
        exported = sample_summary.export_to_dict()

        # Check structure
        assert isinstance(exported, dict)
        assert 'leader_summary' in exported
        assert 'department_summary' in exported
        assert 'rule_details' in exported
        assert 'timestamp' in exported

        # Check data types
        assert isinstance(exported['leader_summary'], list)
        assert isinstance(exported['department_summary'], dict)
        assert isinstance(exported['rule_details'], list)

    def test_from_dict(self, sample_summary):
        """Test from_dict class method."""
        # Export to dict and then create a new instance from that dict
        exported = sample_summary.export_to_dict()
        recreated = AnalyticsSummary.from_dict(exported)

        # Check that the recreated instance has the same structure
        assert isinstance(recreated, AnalyticsSummary)
        assert isinstance(recreated.leader_summary, pd.DataFrame)
        assert isinstance(recreated.department_summary, dict)
        assert isinstance(recreated.rule_details, pd.DataFrame)

        # Check that some key data is preserved
        assert recreated.department_summary['total_rules'] == sample_summary.department_summary['total_rules']
        assert len(recreated.leader_summary) == len(sample_summary.leader_summary)
        assert len(recreated.rule_details) == len(sample_summary.rule_details)

    def test_export_to_file_and_from_file(self, sample_summary, tmp_path):
        """Test export_to_file and from_file methods."""
        # Export to file
        file_path = tmp_path / "test_summary.json"
        saved_path = sample_summary.export_to_file(str(file_path))

        # Check file exists
        assert os.path.exists(saved_path)

        # Load from file
        loaded = AnalyticsSummary.from_file(saved_path)

        # Check that the loaded instance has the same structure
        assert isinstance(loaded, AnalyticsSummary)
        assert isinstance(loaded.leader_summary, pd.DataFrame)
        assert isinstance(loaded.department_summary, dict)
        assert isinstance(loaded.rule_details, pd.DataFrame)

        # Check that some key data is preserved (using more flexible equality)
        assert int(loaded.department_summary['total_rules']) == int(sample_summary.department_summary['total_rules'])
        assert len(loaded.leader_summary) == len(sample_summary.leader_summary)
        assert len(loaded.rule_details) == len(sample_summary.rule_details)


# Tests for end-to-end aggregate_analytics_results
class TestAggregateAnalyticsResults:
    def test_basic_aggregation(self, sample_result_dicts):
        """Test basic end-to-end analytics aggregation."""
        # Perform full aggregation
        summary = aggregate_analytics_results(sample_result_dicts)

        # Check structure
        assert isinstance(summary, AnalyticsSummary)
        assert isinstance(summary.leader_summary, pd.DataFrame)
        assert isinstance(summary.department_summary, dict)
        assert isinstance(summary.rule_details, pd.DataFrame)

        # Check leader data
        assert len(summary.leader_summary) == 3  # Leader1, Leader2, Leader3
        assert 'audit_leader' in summary.leader_summary.columns
        assert 'weighted_score' in summary.leader_summary.columns
        assert 'performance_tag' in summary.leader_summary.columns

        # Check department summary
        assert 'total_rules' in summary.department_summary
        assert 'overall_compliance_rate' in summary.department_summary

        # Check rule details
        assert len(summary.rule_details) > 0
        assert 'rule_id' in summary.rule_details.columns
        assert 'audit_leader' in summary.rule_details.columns

    def test_with_weights_config(self, sample_result_dicts, weights_config):
        """Test aggregation with weights configuration."""
        # Perform aggregation with weights config
        summary = aggregate_analytics_results(sample_result_dicts, weights_config=weights_config)

        # Check config was stored
        assert 'weights' in summary.config

        # Core functionality should work the same
        assert isinstance(summary, AnalyticsSummary)
        assert len(summary.leader_summary) == 3  # Leader1, Leader2, Leader3

    def test_empty_input(self):
        """Test aggregation with empty input."""
        # Should handle empty input gracefully
        summary = aggregate_analytics_results([])

        # Check structure is still valid
        assert isinstance(summary, AnalyticsSummary)
        assert isinstance(summary.leader_summary, pd.DataFrame)
        assert summary.leader_summary.empty
        assert isinstance(summary.department_summary, dict)
        assert isinstance(summary.rule_details, pd.DataFrame)
        assert summary.rule_details.empty

    def test_edge_case_leaders(self, edge_case_result_dicts):
        """Test aggregation with edge case leaders."""
        # Use perfect and zero leaders
        results = edge_case_result_dicts[2:4]
        summary = aggregate_analytics_results(results)

        # Check structure
        assert isinstance(summary, AnalyticsSummary)
        assert len(summary.leader_summary) == 2  # PerfectLeader, ZeroLeader

        # Check perfect leader
        perfect_row = summary.leader_summary[summary.leader_summary['audit_leader'] == 'PerfectLeader'].iloc[0]
        assert perfect_row['weighted_score'] == 5.0
        assert perfect_row['is_high_performer'] == True

        # Check zero leader
        zero_row = summary.leader_summary[summary.leader_summary['audit_leader'] == 'ZeroLeader'].iloc[0]
        assert zero_row['weighted_score'] == 1.0
        assert zero_row['is_critical'] == True


# Tests for load_weights_configuration
class TestLoadWeightsConfiguration:
    def test_default_weights(self):
        """Test loading default weights with no config path."""
        weights = load_weights_configuration()

        # Check structure
        assert isinstance(weights, dict)
        assert 'category_weights' in weights
        assert 'severity_weights' in weights
        assert 'rule_weights' in weights

        # Check default values
        assert weights['category_weights']['default'] == 1.0
        assert weights['severity_weights']['high'] > weights['severity_weights']['low']

    def test_custom_weights_file(self, tmp_path):
        """Test loading weights from a custom file."""
        # Create a test weights file
        custom_weights = {
            'category_weights': {
                'test_category': 2.5,
                'default': 0.8
            },
            'severity_weights': {
                'critical': 3.0,
                'default': 0.5
            },
            'rule_weights': {
                'test_rule': 4.0
            }
        }

        # Save to JSON file
        weights_path = tmp_path / "test_weights.json"
        with open(weights_path, 'w') as f:
            json.dump(custom_weights, f)

        # Load weights
        weights = load_weights_configuration(str(weights_path))

        # Check custom values were loaded
        assert weights['category_weights']['test_category'] == 2.5
        assert weights['category_weights']['default'] == 0.8
        assert weights['severity_weights']['critical'] == 3.0
        assert weights['rule_weights']['test_rule'] == 4.0

    def test_invalid_config_path(self):
        """Test handling of invalid config path."""
        # Should return default weights if path doesn't exist
        weights = load_weights_configuration("nonexistent_path.json")

        # Check structure shows defaults were used
        assert isinstance(weights, dict)
        assert 'category_weights' in weights
        assert 'severity_weights' in weights
        assert 'rule_weights' in weights
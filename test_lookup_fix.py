#!/usr/bin/env python3
"""
Test script to verify LOOKUP function is working in validation rules
"""

import os
import sys
import json
import logging
import pandas as pd
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import required modules
from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
from core.rule_engine.rule_evaluator import RuleEvaluator
from core.lookup.smart_lookup_manager import SmartLookupManager
from services.validation_service import ValidationPipeline
from services.progress_tracking_pipeline import ProgressTrackingPipeline


def create_test_data():
    """Create test data files"""
    # Primary data file
    primary_data = pd.DataFrame({
        'AuditEntityID': ['A001', 'A002', 'A003', 'A004', 'A005'],
        'AuditLeader': ['John Smith', 'Jane Doe', 'Bob Johnson', 'Alice Brown', 'Charlie Wilson'],
        'Status': ['Complete', 'In Progress', 'Complete', 'Pending', 'Complete']
    })
    
    # Secondary data file (HR data)
    hr_data = pd.DataFrame({
        'Employee_Name': ['John Smith', 'Jane Doe', 'Bob Johnson', 'Alice Brown', 'Charlie Wilson'],
        'Title': ['Audit Manager', 'Senior Auditor', 'Audit Manager', 'Junior Auditor', 'Audit Manager']
    })
    
    # Save files
    os.makedirs('test_data', exist_ok=True)
    primary_data.to_excel('test_data/primary_data.xlsx', index=False)
    hr_data.to_excel('test_data/hr_data.xlsx', index=False)
    
    return primary_data, hr_data


def test_lookup_function():
    """Test LOOKUP function in validation rules"""
    logger.info("Starting LOOKUP function test...")
    
    # Create test data
    primary_data, hr_data = create_test_data()
    logger.info("Test data created")
    
    # Create lookup manager
    lookup_manager = SmartLookupManager()
    lookup_manager.add_file('test_data/hr_data.xlsx', alias='hr_data')
    logger.info("Lookup manager initialized with HR data")
    
    # Create a test rule with LOOKUP
    rule_manager = ValidationRuleManager()
    test_rule = ValidationRule(
        rule_id="test_lookup_001",
        name="Test LOOKUP Rule",
        formula="=LOOKUP([AuditLeader], 'Employee_Name', 'Title') = 'Audit Manager'",
        description="Test rule to check if AuditLeader is an Audit Manager",
        threshold=0.8,
        severity="High"
    )
    rule_manager.add_rule(test_rule)
    logger.info(f"Created test rule: {test_rule.formula}")
    
    # Create evaluator with lookup manager
    evaluator = RuleEvaluator(rule_manager=rule_manager)
    
    # Test 1: Direct evaluation
    logger.info("\n=== Test 1: Direct Rule Evaluation ===")
    try:
        result = evaluator.evaluate_rule(test_rule, primary_data, lookup_manager=lookup_manager)
        logger.info(f"Evaluation completed successfully")
        logger.info(f"Compliance status: {result.compliance_status}")
        logger.info(f"Metrics: {result.compliance_metrics}")
        
        # Check results
        result_column = result.result_column
        if result_column in result.result_df.columns:
            logger.info(f"Results per row:")
            for idx, row in result.result_df.iterrows():
                leader = row['AuditLeader']
                is_manager = row[result_column]
                logger.info(f"  {leader}: {is_manager}")
        
        # Check lookup operations
        if result.lookup_operations:
            logger.info(f"\nLookup operations performed: {len(result.lookup_operations)}")
            for op in result.lookup_operations[:3]:  # Show first 3
                logger.info(f"  Looked up '{op['lookup_value']}' -> '{op['result']}'")
    except Exception as e:
        logger.error(f"Direct evaluation failed: {str(e)}")
        raise
    
    # Test 2: Via ValidationPipeline
    logger.info("\n=== Test 2: Via ValidationPipeline ===")
    try:
        pipeline = ValidationPipeline(
            rule_manager=rule_manager,
            evaluator=evaluator,
            lookup_manager=lookup_manager,
            output_dir='test_output'
        )
        
        results = pipeline.validate_data_source(
            data_source='test_data/primary_data.xlsx',
            rule_ids=[test_rule.rule_id],
            output_formats=['json']
        )
        
        logger.info(f"Pipeline validation status: {results.get('status')}")
        logger.info(f"Rules applied: {results.get('rules_applied')}")
        
        # Check rule results
        rule_results = results.get('rule_results', {})
        if test_rule.rule_id in rule_results:
            rule_result = rule_results[test_rule.rule_id]
            logger.info(f"Rule compliance: {rule_result['compliance_status']}")
            logger.info(f"Rule metrics: {rule_result['compliance_metrics']}")
    except Exception as e:
        logger.error(f"Pipeline validation failed: {str(e)}")
        raise
    
    # Test 3: Via ProgressTrackingPipeline
    logger.info("\n=== Test 3: Via ProgressTrackingPipeline ===")
    try:
        progress_pipeline = ProgressTrackingPipeline(pipeline)
        
        def progress_callback(progress, status):
            logger.info(f"Progress: {progress}% - {status}")
        
        results = progress_pipeline.validate_data_source_with_progress(
            data_source_path='test_data/primary_data.xlsx',
            source_type='excel',
            rule_ids=[test_rule.rule_id],
            progress_callback=progress_callback
        )
        
        logger.info(f"Progress pipeline validation status: {results.get('status')}")
        
        # Check rule results
        rule_results = results.get('rule_results', {})
        if test_rule.rule_id in rule_results:
            rule_result = rule_results[test_rule.rule_id]
            logger.info(f"Rule compliance: {rule_result['compliance_status']}")
            logger.info(f"Rule metrics: {rule_result['compliance_metrics']}")
            
            # Check if lookup operations were tracked
            if 'lookup_operations' in rule_result:
                logger.info(f"Lookup operations tracked: {len(rule_result['lookup_operations'])}")
    except Exception as e:
        logger.error(f"Progress pipeline validation failed: {str(e)}")
        raise
    
    logger.info("\n=== LOOKUP Function Test Complete ===")
    
    # Cleanup
    import shutil
    if os.path.exists('test_data'):
        shutil.rmtree('test_data')
    if os.path.exists('test_output'):
        shutil.rmtree('test_output')


if __name__ == "__main__":
    test_lookup_function()
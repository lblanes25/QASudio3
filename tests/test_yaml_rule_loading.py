def test_yaml_rule_loading():
    """Test loading rules from YAML files"""
    import tempfile
    import yaml
    import os
    from pathlib import Path
    from services.validation_service import ValidationPipeline
    from core.rule_engine.rule_manager import ValidationRuleManager

    # Create a temporary YAML file with test rules
    test_rules = {
        'rules': [
            {
                'name': 'Test_NotNull',
                'formula': '=NOT(ISBLANK([TestColumn]))',
                'description': 'Test column must not be null',
                'threshold': 1.0,
                'severity': 'high',
                'category': 'data_quality',
                'tags': ['required', 'test']
            },
            {
                'name': 'Test_ValidValue',
                'formula': '=OR([Status]="Active", [Status]="Inactive")',
                'description': 'Status must be Active or Inactive',
                'threshold': 0.95,
                'severity': 'medium',
                'category': 'validity',
                'tags': ['status']
            }
        ]
    }

    # Create a fresh rule manager instance to avoid interference from existing rules
    rule_manager = ValidationRuleManager()

    with tempfile.NamedTemporaryFile(suffix='.yaml', mode='w', delete=False) as temp_file:
        yaml.dump(test_rules, temp_file)

    try:
        # Create ValidationPipeline with the test YAML file and our clean rule manager
        pipeline = ValidationPipeline(
            rule_manager=rule_manager,
            rule_config_paths=[temp_file.name]
        )

        # Get the file stem for rule ID verification
        file_stem = Path(temp_file.name).stem

        # Verify specific rules were loaded (rather than counting total rules)
        rule1_id = f"{file_stem}_Test_NotNull"
        rule2_id = f"{file_stem}_Test_ValidValue"

        rule1 = pipeline.rule_manager.get_rule(rule1_id)
        rule2 = pipeline.rule_manager.get_rule(rule2_id)

        assert rule1 is not None, f"Rule with ID {rule1_id} not found"
        assert rule2 is not None, f"Rule with ID {rule2_id} not found"

        # Verify rule properties
        assert rule1.name == "Test_NotNull"
        assert rule1.formula == "=NOT(ISBLANK([TestColumn]))"
        assert rule1.threshold == 1.0
        assert rule1.severity == "high"
        assert "required" in rule1.tags

        assert rule2.name == "Test_ValidValue"
        assert rule2.formula == '=OR([Status]="Active", [Status]="Inactive")'
        assert rule2.threshold == 0.95
        assert rule2.severity == "medium"
        assert "status" in rule2.tags

        # Test reloading - verify our two rules are kept
        reload_results = pipeline.reload_rule_configurations()
        assert rule1_id in reload_results['kept_rules'], f"Rule {rule1_id} should be kept on reload"
        assert rule2_id in reload_results['kept_rules'], f"Rule {rule2_id} should be kept on reload"

        print("YAML rule loading test passed!")

    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_file.name)
        except:
            pass


def test_yaml_rule_compatibility_with_existing_rules():
    """Test that YAML-loaded rules work alongside existing rules"""
    import tempfile
    import yaml
    import os
    from pathlib import Path
    from services.validation_service import ValidationPipeline
    import pandas as pd

    # Create a ValidationPipeline with default rule manager to get existing rules
    initial_pipeline = ValidationPipeline()
    existing_rules = initial_pipeline.rule_manager.list_rules()
    print(f"Found {len(existing_rules)} existing rules")

    # Sample some existing rules to verify later
    sample_existing_rules = existing_rules[:3] if len(existing_rules) > 3 else existing_rules

    # Create a temporary YAML file with test rules
    test_rules = {
        'rules': [
            {
                'name': 'Test_NotNull',
                'formula': '=NOT(ISBLANK([TestColumn]))',
                'description': 'Test column must not be null',
                'threshold': 1.0,
                'severity': 'high',
                'category': 'data_quality',
                'tags': ['required', 'test']
            },
            {
                'name': 'Test_ValidValue',
                'formula': '=OR([Status]="Active", [Status]="Inactive")',
                'description': 'Status must be Active or Inactive',
                'threshold': 0.95,
                'severity': 'medium',
                'category': 'validity',
                'tags': ['status']
            }
        ]
    }

    with tempfile.NamedTemporaryFile(suffix='.yaml', mode='w', delete=False) as temp_file:
        yaml.dump(test_rules, temp_file)

    try:
        # Create a new pipeline with the YAML config, using the default rule manager
        # This should keep existing rules and add our new ones
        pipeline = ValidationPipeline(rule_config_paths=[temp_file.name])

        # Get all rules after adding YAML rules
        all_rules = pipeline.rule_manager.list_rules()
        print(f"After loading YAML: {len(all_rules)} total rules")

        # Verify existing rules are still present
        for rule in sample_existing_rules:
            assert pipeline.rule_manager.get_rule(rule.rule_id) is not None, f"Existing rule {rule.rule_id} was lost"

        # Verify our new rules were added
        file_stem = Path(temp_file.name).stem
        yaml_rule1 = pipeline.rule_manager.get_rule(f"{file_stem}_Test_NotNull")
        yaml_rule2 = pipeline.rule_manager.get_rule(f"{file_stem}_Test_ValidValue")

        assert yaml_rule1 is not None, "YAML rule 1 not found"
        assert yaml_rule2 is not None, "YAML rule 2 not found"

        # Create a test DataFrame for rule evaluation
        test_data = {
            'TestColumn': ['Value', None, 'Value'],
            'Status': ['Active', 'Inactive', 'Unknown']
        }
        test_df = pd.DataFrame(test_data)

        # Evaluate a sample existing rule if available
        if sample_existing_rules:
            sample_rule = sample_existing_rules[0]
            try:
                # Skip evaluation if the rule doesn't match our test DataFrame columns
                required_columns = sample_rule.get_required_columns()
                if all(col in test_df.columns for col in required_columns):
                    result = pipeline.evaluator.evaluate_rule(sample_rule, test_df)
                    print(f"Successfully evaluated existing rule: {sample_rule.name}")
            except Exception as e:
                print(f"Could not evaluate existing rule: {str(e)}")

        # Evaluate our YAML rules
        rule1_result = pipeline.evaluator.evaluate_rule(yaml_rule1, test_df)
        assert rule1_result.result_column == f"Result_{yaml_rule1.name}"
        assert rule1_result.compliance_status in ["GC", "PC", "DNC"]

        rule2_result = pipeline.evaluator.evaluate_rule(yaml_rule2, test_df)
        assert rule2_result.result_column == f"Result_{yaml_rule2.name}"
        assert rule2_result.compliance_status in ["GC", "PC", "DNC"]

        print("YAML rules are compatible with existing rules!")

    finally:
        # Clean up the temporary file
        try:
            os.unlink(temp_file.name)
        except:
            pass
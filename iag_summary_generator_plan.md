
# IAG Summary Report Generator (Unformatted Version)

## Purpose

Generate a raw (unstyled) Excel report that summarizes Internal Audit Group (IAG) and Audit Leader (AL) compliance results. This version avoids all Excel formatting and focuses on structured data export only.

## Function Signature

```python
def generate_iag_summary_excel(self, results, rule_results, output_path, 
                               responsible_party_column, analytics_metadata=None, 
                               manual_overrides=None, review_year_name=None):
    """
    Generate IAG and AL Results Summary (unstyled raw Excel version)

    Args:
        results: Overall validation pipeline output
        rule_results: Dict of RuleEvaluationResult objects
        output_path: Target Excel file path
        responsible_party_column: Column to group audit leaders
        analytics_metadata: Optional dict with risk levels or custom thresholds
        manual_overrides: Optional dict of manual rating overrides
        review_year_name: Optional string for report title/header

    Returns:
        Path to saved Excel file
    """
```

## Implementation Steps

| Step | Purpose |
|------|---------|
| 1 | Initialize `IAGScoringCalculator` (pass `analytics_metadata` if needed) |
| 2 | Group rule results by audit leader using `responsible_party_column` |
| 3 | For each leader, calculate IAG weighted score and rating (use per-rule overrides if present) |
| 4 | Aggregate all rule results across leaders for the overall IAG score |
| 5 | Build Excel sheet using `openpyxl` or `pandas.ExcelWriter` with 3 sections:<br> • Section 1: Overall IAG Summary<br> • Section 2: Audit Leader Ratings<br> • Section 3: Rule-by-Rule Details |
| 6 | Skip all formatting — no styles, merges, borders, column widths, etc. |
| 7 | Save the file to `output_path` and return the path |

## Flexible Thresholds per Rule

Enhance `IAGScoringCalculator` to support rule-specific thresholds if provided in `analytics_metadata`:

```python
def get_thresholds_for_rule(self, rule_id: str) -> Dict[str, float]:
    return self.custom_thresholds.get(rule_id, self.default_thresholds)
```

Where `custom_thresholds` is initialized from `analytics_metadata` like this:

```python
{
  "RULE_123": {"GC": 0.85, "PC": 0.60, "DNC": 0.00},
  "RULE_456": {"GC": 0.90, "PC": 0.70, "DNC": 0.00}
}
```

## Recommended Implementation Order

1. **Implement `IAGScoringCalculator`**
    - Base logic and thresholds
    - Add support for per-rule threshold overrides

2. **Create `generate_iag_summary_excel()`**
    - Use `openpyxl` or `pandas.ExcelWriter`
    - Structure output sections without formatting

3. **Add wrapper method `generate_iag_summary_report()`**
    - For CLI/GUI triggering
    - Auto-generate filename if not specified

4. **Add unit tests**
    - Rule combinations, override logic, N/A handling

5. **(Optional) Add HTML export**
    - For future dashboarding or preview use

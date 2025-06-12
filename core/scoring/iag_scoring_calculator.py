"""
IAG (Internal Audit Group) Scoring Calculator

Implements the exact IAG scoring methodology as defined in the Excel template:
- GC (Generally Conforms) = 5 points
- PC (Partially Conforms) = 3 points  
- DNC (Does Not Conform) = 1 point
- N/A (Not Applicable) = 0 points

Rating thresholds:
- GC: >= 80%
- PC: 50% - 79%
- DNC: < 50%

Formula: ((GC*5) + (PC*3) + (DNC*1)) / (Total*5)
"""

from typing import Dict, List, Tuple, Union, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class IAGScoringResult:
    """Container for IAG scoring results"""
    gc_count: int
    pc_count: int
    dnc_count: int
    na_count: int
    total_applicable: int
    weighted_score: Union[float, str]  # Float percentage or "N/A"
    rating: str  # "GC", "PC", "DNC", or "N/A"
    
    @property
    def total_count(self) -> int:
        """Total count including N/A"""
        return self.total_applicable + self.na_count


class IAGScoringCalculator:
    """
    Implements IAG (Internal Audit Group) scoring methodology exactly as defined in Excel.
    
    This calculator follows the verified formulas and thresholds from the IAG template.
    """
    
    def __init__(self):
        """Initialize with IAG rating configuration"""
        self.rating_weights = {
            'GC': 5,    # Generally Conforms = 5 points
            'PC': 3,    # Partially Conforms = 3 points  
            'DNC': 1,   # Does Not Conform = 1 point
            'N/A': 0    # Not Applicable = 0 points
        }
        
        self.rating_thresholds = {
            'GC': 0.80,   # 80% threshold for Generally Conforms
            'PC': 0.50,   # 50% threshold for Partially Conforms (50-79%)
            'DNC': 0.00   # Below 50% = Does Not Conform
        }
        
    def calculate_iag_weighted_score(self, gc_count: int, pc_count: int, 
                                   dnc_count: int, total_count: int) -> Union[float, str]:
        """
        Calculate weighted score using exact IAG methodology.
        
        Excel Formula: ((GC*5) + (PC*3) + (DNC*1)) / (Total*5)
        
        Args:
            gc_count: Number of Generally Conforms results
            pc_count: Number of Partially Conforms results
            dnc_count: Number of Does Not Conform results
            total_count: Total applicable tests (excluding N/A)
            
        Returns:
            Float between 0.0 and 1.0 representing percentage, or "N/A" if no applicable tests
        """
        if total_count == 0:
            return "N/A"
        
        # Calculate weighted sum using IAG point values
        weighted_sum = (
            gc_count * self.rating_weights['GC'] + 
            pc_count * self.rating_weights['PC'] + 
            dnc_count * self.rating_weights['DNC']
        )
        
        # Maximum possible score if all rules were GC
        max_possible_score = total_count * self.rating_weights['GC']
        
        # Return percentage as decimal
        return weighted_sum / max_possible_score
    
    def assign_iag_rating(self, weighted_score: Union[float, str]) -> str:
        """
        Assign rating based on IAG thresholds.
        
        Excel Formula: IFS(score="N/A", "N/A", score>=80%, "GC", score<50%, "DNC", TRUE, "PC")
        
        Args:
            weighted_score: The calculated weighted score (0.0-1.0) or "N/A"
            
        Returns:
            Rating string: "GC", "PC", "DNC", or "N/A"
        """
        if weighted_score == "N/A":
            return "N/A"
        elif weighted_score >= self.rating_thresholds['GC']:  # 80% or higher
            return "GC"
        elif weighted_score < self.rating_thresholds['PC']:   # Below 50%
            return "DNC"
        else:                                                  # Between 50% and 79%
            return "PC"
    
    def calculate_leader_score(self, rule_results: List[Dict]) -> IAGScoringResult:
        """
        Calculate weighted score and rating for a single audit leader.
        
        Args:
            rule_results: List of rule evaluation results for this leader
                         Each dict should have 'compliance_status' key
        
        Returns:
            IAGScoringResult with counts, score, and rating
        """
        # Count results by status
        gc_count = pc_count = dnc_count = na_count = 0
        
        for result in rule_results:
            status = result.get('compliance_status', 'N/A')
            if status == 'GC':
                gc_count += 1
            elif status == 'PC':
                pc_count += 1
            elif status == 'DNC':
                dnc_count += 1
            else:  # N/A or other
                na_count += 1
        
        # Calculate total applicable (excluding N/A)
        total_applicable = gc_count + pc_count + dnc_count
        
        # Calculate weighted score
        weighted_score = self.calculate_iag_weighted_score(
            gc_count, pc_count, dnc_count, total_applicable
        )
        
        # Assign rating
        rating = self.assign_iag_rating(weighted_score)
        
        return IAGScoringResult(
            gc_count=gc_count,
            pc_count=pc_count,
            dnc_count=dnc_count,
            na_count=na_count,
            total_applicable=total_applicable,
            weighted_score=weighted_score,
            rating=rating
        )
    
    def calculate_overall_iag_score(self, all_rule_results: Dict[str, List[Dict]], 
                                  responsible_party_column: str) -> Dict[str, IAGScoringResult]:
        """
        Calculate overall IAG score across all audit leaders.
        
        Args:
            all_rule_results: Dictionary mapping leader names to their rule results
            responsible_party_column: Column name used for grouping (for logging)
            
        Returns:
            Dictionary with 'overall' key containing aggregate IAGScoringResult,
            plus individual leader scores
        """
        leader_scores = {}
        
        # Calculate scores for each leader
        total_gc = total_pc = total_dnc = total_na = 0
        
        for leader_name, leader_results in all_rule_results.items():
            leader_score = self.calculate_leader_score(leader_results)
            leader_scores[leader_name] = leader_score
            
            # Accumulate totals
            total_gc += leader_score.gc_count
            total_pc += leader_score.pc_count
            total_dnc += leader_score.dnc_count
            total_na += leader_score.na_count
        
        # Calculate overall IAG score
        total_applicable = total_gc + total_pc + total_dnc
        overall_weighted_score = self.calculate_iag_weighted_score(
            total_gc, total_pc, total_dnc, total_applicable
        )
        overall_rating = self.assign_iag_rating(overall_weighted_score)
        
        # Add overall score to results
        leader_scores['overall'] = IAGScoringResult(
            gc_count=total_gc,
            pc_count=total_pc,
            dnc_count=total_dnc,
            na_count=total_na,
            total_applicable=total_applicable,
            weighted_score=overall_weighted_score,
            rating=overall_rating
        )
        
        logger.info(f"Calculated IAG scores for {len(all_rule_results)} leaders "
                   f"grouped by {responsible_party_column}")
        
        return leader_scores
    
    def get_detailed_metrics_by_leader(self, rule_results: Dict[str, Dict], 
                                     responsible_party_column: str) -> Dict[str, Dict]:
        """
        Generate Section 3 detailed analytics per leader.
        
        Args:
            rule_results: Dictionary of rule results by rule_id
            responsible_party_column: Column for audit leader grouping
            
        Returns:
            Dictionary with detailed metrics per leader and rule
        """
        # Group results by leader
        leader_metrics = {}
        
        # This would typically process the raw rule evaluation results
        # and group them by the responsible party column
        # For now, returning a structure placeholder
        
        logger.info(f"Generating detailed metrics grouped by {responsible_party_column}")
        
        return leader_metrics
    
    def format_percentage(self, score: Union[float, str], decimal_places: int = 1) -> str:
        """
        Format score as percentage string.
        
        Args:
            score: Decimal score (0.0-1.0) or "N/A"
            decimal_places: Number of decimal places to show
            
        Returns:
            Formatted percentage string (e.g., "75.0%") or "N/A"
        """
        if score == "N/A":
            return "N/A"
        
        percentage = score * 100
        return f"{percentage:.{decimal_places}f}%"
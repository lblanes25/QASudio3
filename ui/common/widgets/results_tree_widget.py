"""
Interactive Results Tree Widget - Hierarchical display of validation results
Provides drill-down capabilities into rule details and failing items
"""

import logging
import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import pandas as pd

from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QVBoxLayout, QHBoxLayout,
    QWidget, QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QProgressBar, QMenu, QFileDialog,
    QMessageBox, QFrame, QTabWidget, QStackedWidget
)
from PySide6.QtCore import Qt, Signal, QRunnable, QThreadPool, QObject, QTimer
from PySide6.QtGui import QIcon, QFont, QColor, QBrush
from PySide6.QtWidgets import QApplication

from ui.common.stylesheet import AnalyticsRunnerStylesheet

logger = logging.getLogger(__name__)


class FailingItemsLoaderSignals(QObject):
    """Signals for async failing items loader"""
    dataLoaded = Signal(pd.DataFrame)
    error = Signal(str)
    progress = Signal(int)


class FailingItemsLoader(QRunnable):
    """Worker to load failing items asynchronously"""
    
    def __init__(self, rule_result, max_rows=1000):
        super().__init__()
        self.rule_result = rule_result
        self.max_rows = max_rows
        self.signals = FailingItemsLoaderSignals()
        
    def run(self):
        """Load failing items data"""
        try:
            # Get failing items
            failing_items = self.rule_result.get_failing_items()
            
            # Limit rows for performance
            if len(failing_items) > self.max_rows:
                failing_items = failing_items.head(self.max_rows)
                
            self.signals.dataLoaded.emit(failing_items)
            
        except Exception as e:
            logger.error(f"Error loading failing items: {str(e)}")
            self.signals.error.emit(str(e))


class ResultsTreeWidget(QWidget):
    """
    Interactive tree widget for exploring validation results.
    
    Features:
    - Hierarchical display of rules and their results
    - Lazy loading of failing items
    - Responsible party breakdown
    - Export capabilities
    - Filterable/sortable tables
    """
    
    # Signals
    ruleSelected = Signal(str)  # Rule ID
    exportRequested = Signal(str, pd.DataFrame)  # Rule ID, failing items
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.results_data = None
        self.rule_results = {}
        self.threadpool = QThreadPool()
        self.failing_items_cache = {}  # Cache loaded data
        
        self.init_ui()
        
    def init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Create splitter for tree and details
        self.splitter = QSplitter(Qt.Horizontal)
        
        # Left panel - Results tree
        self.tree_widget = QTreeWidget()
        self.tree_widget.setHeaderLabels(["Item", "Status", "Count", "Details"])
        self.tree_widget.setAlternatingRowColors(True)
        self.tree_widget.itemClicked.connect(self._on_item_clicked)
        self.tree_widget.itemExpanded.connect(self._on_item_expanded)
        self.tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree_widget.customContextMenuRequested.connect(self._show_context_menu)
        
        # Style the tree
        self.tree_widget.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
            }}
            QTreeWidget::item {{
                padding: 4px;
                border-bottom: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR}20;
            }}
            QTreeWidget::item:selected {{
                background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR}20;
                color: {AnalyticsRunnerStylesheet.DARK_TEXT};
            }}
            QTreeWidget::item:hover {{
                background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
            }}
        """)
        
        # Right panel - Details view
        self.details_widget = QTabWidget()
        self.details_widget.setVisible(False)
        
        # Summary tab
        self.summary_widget = QWidget()
        summary_layout = QVBoxLayout(self.summary_widget)
        
        self.rule_info_label = QLabel("Select a rule to view details")
        self.rule_info_label.setWordWrap(True)
        self.rule_info_label.setStyleSheet(f"""
            padding: 12px;
            background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
            border-radius: 4px;
            color: {AnalyticsRunnerStylesheet.DARK_TEXT};
        """)
        summary_layout.addWidget(self.rule_info_label)
        
        # Rule metadata frame
        self.metadata_frame = QFrame()
        self.metadata_frame.setFrameStyle(QFrame.StyledPanel)
        self.metadata_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.SURFACE_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 8px;
            }}
        """)
        metadata_layout = QVBoxLayout(self.metadata_frame)
        
        self.metadata_labels = {}
        for field in ["Name", "Description", "Formula", "Threshold", "Category", "Severity"]:
            label = QLabel(f"<b>{field}:</b> -")
            label.setWordWrap(True)
            metadata_layout.addWidget(label)
            self.metadata_labels[field.lower()] = label
            
        summary_layout.addWidget(self.metadata_frame)
        summary_layout.addStretch()
        
        self.details_widget.addTab(self.summary_widget, "Rule Details")
        
        # Failing items tab
        self.failing_items_widget = QWidget()
        failing_layout = QVBoxLayout(self.failing_items_widget)
        
        # Loading indicator
        self.loading_bar = QProgressBar()
        self.loading_bar.setRange(0, 0)  # Indeterminate
        self.loading_bar.setVisible(False)
        failing_layout.addWidget(self.loading_bar)
        
        # Export button
        export_layout = QHBoxLayout()
        self.items_count_label = QLabel("0 failing items")
        export_layout.addWidget(self.items_count_label)
        export_layout.addStretch()
        
        self.export_button = QPushButton("Export to CSV")
        self.export_button.clicked.connect(self._export_failing_items)
        self.export_button.setEnabled(False)
        export_layout.addWidget(self.export_button)
        
        failing_layout.addLayout(export_layout)
        
        # Failing items table
        self.failing_items_table = QTableWidget()
        self.failing_items_table.setSortingEnabled(True)
        self.failing_items_table.setAlternatingRowColors(True)
        self.failing_items_table.horizontalHeader().setStretchLastSection(True)
        self.failing_items_table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
                gridline-color: {AnalyticsRunnerStylesheet.BORDER_COLOR};
            }}
            QTableWidget::item {{
                padding: 4px;
            }}
            QTableWidget::item:selected {{
                background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR}20;
            }}
        """)
        failing_layout.addWidget(self.failing_items_table)
        
        self.details_widget.addTab(self.failing_items_widget, "Failing Items")
        
        # Responsible party tab
        self.party_widget = QWidget()
        party_layout = QVBoxLayout(self.party_widget)
        
        self.party_tree = QTreeWidget()
        self.party_tree.setHeaderLabels(["Responsible Party", "Status", "Items", "Compliance %"])
        self.party_tree.setAlternatingRowColors(True)
        party_layout.addWidget(self.party_tree)
        
        self.details_widget.addTab(self.party_widget, "By Responsible Party")
        
        # Add to splitter
        self.splitter.addWidget(self.tree_widget)
        self.splitter.addWidget(self.details_widget)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 2)
        
        layout.addWidget(self.splitter)
        
    def load_results(self, results: Dict[str, Any]):
        """Load validation results into the tree"""
        self.results_data = results
        self.rule_results = results.get('rule_results', {})
        
        # Clear existing items
        self.tree_widget.clear()
        self.failing_items_cache.clear()
        
        # Create root items
        timestamp = results.get('timestamp', 'N/A')
        status = results.get('status', 'UNKNOWN')
        
        # Summary root
        summary_root = QTreeWidgetItem(self.tree_widget)
        summary_root.setText(0, "Summary")
        summary_root.setText(1, status)
        summary_root.setText(2, timestamp)
        summary_root.setExpanded(True)
        
        # Set summary styling
        font = QFont()
        font.setBold(True)
        summary_root.setFont(0, font)
        
        # Add summary items
        summary_data = results.get('summary', {})
        if summary_data:
            self._add_summary_items(summary_root, summary_data)
            
        # Rules root
        if self.rule_results:
            rules_root = QTreeWidgetItem(self.tree_widget)
            rules_root.setText(0, "Validation Rules")
            rules_root.setText(1, "")
            rules_root.setText(2, f"{len(self.rule_results)} rules")
            rules_root.setExpanded(True)
            rules_root.setFont(0, font)
            
            # Add rule items
            self._add_rule_items(rules_root)
            
        # Reports root
        output_files = results.get('output_files', [])
        if output_files:
            reports_root = QTreeWidgetItem(self.tree_widget)
            reports_root.setText(0, "Generated Reports")
            reports_root.setText(1, "")
            reports_root.setText(2, f"{len(output_files)} files")
            reports_root.setFont(0, font)
            
            for file_path in output_files:
                file_item = QTreeWidgetItem(reports_root)
                file_item.setText(0, os.path.basename(str(file_path)))
                file_item.setText(3, str(file_path))
                
        # Resize columns
        for i in range(4):
            self.tree_widget.resizeColumnToContents(i)
            
    def _add_summary_items(self, parent: QTreeWidgetItem, summary: Dict[str, Any]):
        """Add summary items to tree"""
        # Compliance counts
        compliance_counts = summary.get('compliance_counts', {})
        for status, count in compliance_counts.items():
            item = QTreeWidgetItem(parent)
            item.setText(0, f"{status} Rules")
            item.setText(1, status)
            item.setText(2, str(count))
            
            # Color code by status
            if status == "GC":
                color = QColor(AnalyticsRunnerStylesheet.SUCCESS_COLOR)
            elif status == "PC":
                color = QColor(AnalyticsRunnerStylesheet.WARNING_COLOR)
            elif status == "DNC":
                color = QColor(AnalyticsRunnerStylesheet.ERROR_COLOR)
            else:
                color = QColor(AnalyticsRunnerStylesheet.LIGHT_TEXT)
                
            item.setForeground(1, QBrush(color))
            
        # Overall compliance
        compliance_rate = summary.get('compliance_rate', 0)
        comp_item = QTreeWidgetItem(parent)
        comp_item.setText(0, "Overall Compliance")
        comp_item.setText(1, f"{compliance_rate:.1%}")
        
    def _add_rule_items(self, parent: QTreeWidgetItem):
        """Add rule items to tree"""
        # Sort rules by name
        def get_rule_name(item):
            rule_id, result = item
            if hasattr(result, 'rule'):
                return result.rule.name
            elif isinstance(result, dict):
                return result.get('rule_name', rule_id)
            else:
                return rule_id
                
        sorted_rules = sorted(self.rule_results.items(), key=get_rule_name)
        
        for rule_id, result in sorted_rules:
            try:
                # Create rule item
                rule_item = QTreeWidgetItem(parent)
                rule_item.setData(0, Qt.UserRole, rule_id)  # Store rule ID
                
                # Extract rule info - handle both object and dict formats
                if hasattr(result, 'rule'):
                    # RuleEvaluationResult object
                    rule_name = result.rule.name
                    rule_status = result.compliance_status
                    summary = result.summary
                elif isinstance(result, dict):
                    # Dictionary from validation service
                    rule_name = result.get('rule_name', rule_id)
                    rule_status = result.get('compliance_status', 'UNKNOWN')
                    summary = result
                else:
                    rule_name = rule_id
                    rule_status = "UNKNOWN"
                    summary = {}
                    
                # Get counts from summary
                total = summary.get('total_items', 0)
                passed = summary.get('gc_count', 0)
                failed = summary.get('dnc_count', 0) + summary.get('pc_count', 0)
                    
                # Set item text
                rule_item.setText(0, rule_name)
                rule_item.setText(1, rule_status)
                rule_item.setText(2, f"{passed}/{total}")
                rule_item.setText(3, f"{failed} failures")
                
                # Color code
                if rule_status == "GC":
                    color = QColor(AnalyticsRunnerStylesheet.SUCCESS_COLOR)
                elif rule_status == "PC":
                    color = QColor(AnalyticsRunnerStylesheet.WARNING_COLOR)
                elif rule_status == "DNC":
                    color = QColor(AnalyticsRunnerStylesheet.ERROR_COLOR)
                else:
                    color = QColor(AnalyticsRunnerStylesheet.LIGHT_TEXT)
                    
                rule_item.setForeground(1, QBrush(color))
                
                # Add placeholder child for lazy loading
                if failed > 0:
                    placeholder = QTreeWidgetItem(rule_item)
                    placeholder.setText(0, "Click to load details...")
                    placeholder.setForeground(0, QBrush(QColor(AnalyticsRunnerStylesheet.LIGHT_TEXT)))
                    
            except Exception as e:
                logger.error(f"Error adding rule item {rule_id}: {str(e)}")
                
    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle item click"""
        # Check if it's a rule item
        rule_id = item.data(0, Qt.UserRole)
        if rule_id and rule_id in self.rule_results:
            self._show_rule_details(rule_id)
            
    def _on_item_expanded(self, item: QTreeWidgetItem):
        """Handle item expansion for lazy loading"""
        rule_id = item.data(0, Qt.UserRole)
        if rule_id and rule_id in self.rule_results:
            # Check if we need to load data
            if item.childCount() == 1 and item.child(0).text(0) == "Click to load details...":
                self._load_rule_details(item, rule_id)
                
    def _show_rule_details(self, rule_id: str):
        """Show detailed information for a rule"""
        self.details_widget.setVisible(True)
        self.ruleSelected.emit(rule_id)
        
        result = self.rule_results.get(rule_id)
        if not result:
            return
            
        # Update rule info
        if hasattr(result, 'rule'):
            rule = result.rule
            self.rule_info_label.setText(f"<h3>{rule.name}</h3>")
            
            # Update metadata
            self.metadata_labels['name'].setText(f"<b>Name:</b> {rule.name}")
            self.metadata_labels['description'].setText(f"<b>Description:</b> {rule.description or 'N/A'}")
            self.metadata_labels['formula'].setText(f"<b>Formula:</b> <code>{rule.formula}</code>")
            self.metadata_labels['threshold'].setText(f"<b>Threshold:</b> {rule.threshold:.1%}")
            self.metadata_labels['category'].setText(f"<b>Category:</b> {rule.category or 'N/A'}")
            self.metadata_labels['severity'].setText(f"<b>Severity:</b> {rule.severity or 'N/A'}")
        elif isinstance(result, dict):
            # Handle dictionary format
            rule_name = result.get('rule_name', rule_id)
            self.rule_info_label.setText(f"<h3>{rule_name}</h3>")
            
            # Update metadata with available data
            self.metadata_labels['name'].setText(f"<b>Name:</b> {rule_name}")
            self.metadata_labels['description'].setText(f"<b>Description:</b> N/A")
            self.metadata_labels['formula'].setText(f"<b>Formula:</b> N/A")
            self.metadata_labels['threshold'].setText(f"<b>Threshold:</b> N/A")
            self.metadata_labels['category'].setText(f"<b>Category:</b> N/A")
            self.metadata_labels['severity'].setText(f"<b>Severity:</b> N/A")
            
        # Load failing items if not cached
        if rule_id not in self.failing_items_cache:
            self._load_failing_items_async(rule_id)
            
        # Load responsible party breakdown
        self._load_party_breakdown(rule_id)
        
    def _load_failing_items_async(self, rule_id: str):
        """Load failing items asynchronously"""
        result = self.rule_results.get(rule_id)
        if not result:
            return
            
        # Only load failing items for RuleEvaluationResult objects
        if hasattr(result, 'get_failing_items'):
            # Show loading indicator
            self.loading_bar.setVisible(True)
            self.failing_items_table.setEnabled(False)
            self.export_button.setEnabled(False)
            
            # Create and start loader
            loader = FailingItemsLoader(result)
            loader.signals.dataLoaded.connect(
                lambda df: self._on_failing_items_loaded(rule_id, df)
            )
            loader.signals.error.connect(self._on_loading_error)
            
            self.threadpool.start(loader)
        else:
            # For dictionary results, show a message
            self.loading_bar.setVisible(False)
            self.items_count_label.setText("Detailed failure data not available")
            self.export_button.setEnabled(False)
            self.failing_items_table.setRowCount(0)
            self.failing_items_table.setColumnCount(1)
            self.failing_items_table.setHorizontalHeaderLabels(["Message"])
            item = QTableWidgetItem("Detailed failure data is not available for this validation result.")
            self.failing_items_table.setItem(0, 0, item)
        
    def _on_failing_items_loaded(self, rule_id: str, df: pd.DataFrame):
        """Handle loaded failing items"""
        # Cache the data
        self.failing_items_cache[rule_id] = df
        
        # Hide loading indicator
        self.loading_bar.setVisible(False)
        self.failing_items_table.setEnabled(True)
        
        # Update count
        self.items_count_label.setText(f"{len(df)} failing items")
        self.export_button.setEnabled(len(df) > 0)
        
        # Populate table
        self.failing_items_table.setRowCount(len(df))
        self.failing_items_table.setColumnCount(len(df.columns))
        self.failing_items_table.setHorizontalHeaderLabels(df.columns.tolist())
        
        for row in range(len(df)):
            for col in range(len(df.columns)):
                value = df.iloc[row, col]
                item = QTableWidgetItem(str(value))
                self.failing_items_table.setItem(row, col, item)
                
        # Resize columns
        self.failing_items_table.resizeColumnsToContents()
        
    def _on_loading_error(self, error: str):
        """Handle loading error"""
        self.loading_bar.setVisible(False)
        self.failing_items_table.setEnabled(True)
        QMessageBox.warning(self, "Loading Error", f"Failed to load failing items:\n{error}")
        
    def _load_party_breakdown(self, rule_id: str):
        """Load responsible party breakdown"""
        self.party_tree.clear()
        
        result = self.rule_results.get(rule_id)
        if not result:
            return
            
        # Check if we have party results (only for RuleEvaluationResult objects)
        if hasattr(result, 'party_results'):
            party_results = result.party_results
            if not party_results:
                no_data = QTreeWidgetItem(self.party_tree)
                no_data.setText(0, "No responsible party data available")
                return
        else:
            # For dictionary results, show a message
            no_data = QTreeWidgetItem(self.party_tree)
            no_data.setText(0, "Party breakdown not available for this validation result")
            return
            
        # Add party items
        for party, party_data in sorted(party_results.items()):
            party_item = QTreeWidgetItem(self.party_tree)
            party_item.setText(0, party)
            party_item.setText(1, party_data.get('compliance_status', 'UNKNOWN'))
            party_item.setText(2, str(party_data.get('total_count', 0)))
            
            compliance_rate = party_data.get('compliance_rate', 0)
            party_item.setText(3, f"{compliance_rate:.1%}")
            
            # Color code
            status = party_data.get('compliance_status', '')
            if status == "GC":
                color = QColor(AnalyticsRunnerStylesheet.SUCCESS_COLOR)
            elif status == "PC":
                color = QColor(AnalyticsRunnerStylesheet.WARNING_COLOR)
            elif status == "DNC":
                color = QColor(AnalyticsRunnerStylesheet.ERROR_COLOR)
            else:
                color = QColor(AnalyticsRunnerStylesheet.LIGHT_TEXT)
                
            party_item.setForeground(1, QBrush(color))
            
        # Resize columns
        for i in range(4):
            self.party_tree.resizeColumnToContents(i)
            
    def _show_context_menu(self, position):
        """Show context menu for tree items"""
        item = self.tree_widget.itemAt(position)
        if not item:
            return
            
        rule_id = item.data(0, Qt.UserRole)
        if not rule_id:
            return
            
        menu = QMenu(self)
        
        # Export action
        export_action = menu.addAction("Export Failing Items")
        export_action.triggered.connect(lambda: self._export_rule_data(rule_id))
        
        # Copy action
        copy_action = menu.addAction("Copy Rule Details")
        copy_action.triggered.connect(lambda: self._copy_rule_details(rule_id))
        
        menu.exec_(self.tree_widget.mapToGlobal(position))
        
    def _export_failing_items(self):
        """Export current failing items to CSV"""
        # Get current rule
        current_tab = self.details_widget.currentIndex()
        if current_tab != 1:  # Not on failing items tab
            return
            
        # Find selected rule
        selected = self.tree_widget.selectedItems()
        if not selected:
            return
            
        rule_id = selected[0].data(0, Qt.UserRole)
        if rule_id and rule_id in self.failing_items_cache:
            self._export_rule_data(rule_id)
            
    def _export_rule_data(self, rule_id: str):
        """Export failing items for a specific rule"""
        df = self.failing_items_cache.get(rule_id)
        if df is None:
            # Load synchronously for export
            result = self.rule_results.get(rule_id)
            if result and hasattr(result, 'get_failing_items'):
                df = result.get_failing_items()
                
        if df is not None and not df.empty:
            # Get file path
            result = self.rule_results[rule_id]
            if hasattr(result, 'rule'):
                rule_name = result.rule.name
            elif isinstance(result, dict):
                rule_name = result.get('rule_name', rule_id)
            else:
                rule_name = rule_id
            safe_name = "".join(c for c in rule_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            
            file_path, _ = QFileDialog.getSaveFileName(
                self,
                "Export Failing Items",
                f"{safe_name}_failures_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                "CSV Files (*.csv);;Excel Files (*.xlsx)"
            )
            
            if file_path:
                try:
                    if file_path.endswith('.xlsx'):
                        # Use xlsxwriter engine to avoid formula corruption
                        df.to_excel(file_path, index=False, engine='xlsxwriter')
                    else:
                        df.to_csv(file_path, index=False)
                        
                    QMessageBox.information(self, "Export Complete", f"Exported {len(df)} failing items to:\n{file_path}")
                    self.exportRequested.emit(rule_id, df)
                    
                except Exception as e:
                    QMessageBox.critical(self, "Export Error", f"Failed to export data:\n{str(e)}")
                    
    def _copy_rule_details(self, rule_id: str):
        """Copy rule details to clipboard"""
        result = self.rule_results.get(rule_id)
        if not result:
            return
            
        # Build text
        lines = []
        if hasattr(result, 'rule'):
            rule = result.rule
            lines.append(f"Rule: {rule.name}")
            lines.append(f"Status: {result.compliance_status}")
            lines.append(f"Description: {rule.description or 'N/A'}")
            lines.append(f"Formula: {rule.formula}")
            summary = result.summary
        elif isinstance(result, dict):
            lines.append(f"Rule: {result.get('rule_name', rule_id)}")
            lines.append(f"Status: {result.get('compliance_status', 'UNKNOWN')}")
            lines.append(f"Description: N/A")
            lines.append(f"Formula: N/A")
            summary = result
        else:
            return
            
        if summary:
            lines.append(f"Total Items: {summary.get('total_items', 0)}")
            lines.append(f"Passed: {summary.get('gc_count', 0)}")
            lines.append(f"Failed: {summary.get('dnc_count', 0) + summary.get('pc_count', 0)}")
            
        # Copy to clipboard
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(lines))
        
    def _load_rule_details(self, parent_item: QTreeWidgetItem, rule_id: str):
        """Load detailed breakdown for a rule"""
        # Remove placeholder
        parent_item.takeChild(0)
        
        result = self.rule_results.get(rule_id)
        if not result:
            return
            
        # Add breakdown items
        if hasattr(result, 'summary'):
            summary = result.summary
            
            # Counts breakdown
            counts_item = QTreeWidgetItem(parent_item)
            counts_item.setText(0, "Item Counts")
            counts_item.setFont(0, QFont("", -1, QFont.Bold))
            
            for metric, value in [
                ("Total Processed", summary.get('total_items', 0)),
                ("Passed (GC)", summary.get('gc_count', 0)),
                ("Partially Compliant (PC)", summary.get('pc_count', 0)),
                ("Failed (DNC)", summary.get('dnc_count', 0)),
                ("Errors", summary.get('error_count', 0))
            ]:
                metric_item = QTreeWidgetItem(counts_item)
                metric_item.setText(0, metric)
                metric_item.setText(2, str(value))
                
        # Add party summary if available
        if hasattr(result, 'party_results') and result.party_results:
            party_item = QTreeWidgetItem(parent_item)
            party_item.setText(0, "By Responsible Party")
            party_item.setText(2, f"{len(result.party_results)} parties")
            party_item.setFont(0, QFont("", -1, QFont.Bold))
            
            for party, data in sorted(result.party_results.items())[:10]:  # Limit to 10
                p_item = QTreeWidgetItem(party_item)
                p_item.setText(0, party)
                p_item.setText(1, data.get('compliance_status', 'UNKNOWN'))
                p_item.setText(2, f"{data.get('compliance_rate', 0):.1%}")


# Import os for file operations
import os
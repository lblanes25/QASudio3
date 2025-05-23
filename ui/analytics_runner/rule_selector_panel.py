"""
Rule Selector Panel for Analytics Runner with Integrated Rule Editor
Enhanced version of the existing rule_selector_panel.py with real rule editing capabilities
"""

import logging
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QLineEdit, QPushButton, QLabel, QCheckBox, QComboBox, QFrame,
    QSplitter, QTextEdit, QGroupBox, QScrollArea, QMessageBox, QTabWidget
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont, QIcon

# Import backend components
from core.rule_engine.rule_manager import ValidationRule, ValidationRuleManager
from core.rule_engine.rule_parser import ValidationRuleParser
from services.validation_service import ValidationPipeline
from ui.common.stylesheet import AnalyticsRunnerStylesheet
from ui.common.session_manager import SessionManager

# Import the rule editor panel
from rule_editor_panel import RuleEditorPanel

logger = logging.getLogger(__name__)


class RuleSelectorPanel(QWidget):
    """
    Unified rule selection and management interface with integrated editor.

    Features:
    - Browse and filter existing rules by category/tags
    - Select multiple rules with checkboxes
    - View rule metadata and details
    - EDIT RULES with real backend integration
    - CREATE NEW RULES with JSON persistence
    - TEST RULES against current data
    - Session persistence for selections

    Signals:
    - rulesSelectionChanged: Emitted when rule selection changes
    - ruleDoubleClicked: Emitted when user wants to edit a rule
    """

    rulesSelectionChanged = Signal(list)  # List of selected rule IDs
    ruleDoubleClicked = Signal(str)       # Rule ID for editing

    def __init__(self, session_manager: Optional[SessionManager] = None, parent=None):
        super().__init__(parent)

        # Initialize backend connections
        self.session_manager = session_manager or SessionManager()
        self.rule_manager = ValidationRuleManager()
        self.validation_pipeline = None  # Will initialize when needed

        # Internal state
        self.all_rules: List[ValidationRule] = []
        self.filtered_rules: List[ValidationRule] = []
        self.selected_rule_ids: Set[str] = set()

        # Search and filter state
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self._perform_search)

        # Initialize UI
        self.init_ui()

        # Load rules and restore session
        self.load_rules()
        self.restore_session_state()

        logger.info("RuleSelectorPanel initialized with integrated editor")

    def init_ui(self):
        """Initialize the user interface components with integrated editor."""
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        # Header section
        self.create_header_section(main_layout)

        # Filter and search controls
        self.create_filter_section(main_layout)

        # Main content area - horizontal splitter for rules tree + editor
        self.create_main_content_section(main_layout)

        # Action buttons
        self.create_action_section(main_layout)

    def create_header_section(self, parent_layout):
        """Create the header with title and summary stats."""
        header_layout = QHBoxLayout()

        # Title
        title_label = QLabel("Rule Management")
        title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['title'])
        title_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR}; font-weight: bold;")
        header_layout.addWidget(title_label)

        # Stats label (updated dynamically)
        self.stats_label = QLabel("Loading rules...")
        self.stats_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.stats_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};")
        header_layout.addStretch()
        header_layout.addWidget(self.stats_label)

        parent_layout.addLayout(header_layout)

    def create_filter_section(self, parent_layout):
        """Create search and filter controls - REMOVED preset buttons"""
        filter_widget = QWidget()
        filter_layout = QVBoxLayout(filter_widget)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.setSpacing(12)

        # Search row
        search_layout = QHBoxLayout()
        search_layout.setSpacing(8)

        # Search box
        search_label = QLabel("Search:")
        search_layout.addWidget(search_label)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter rules by name, description, or tags...")
        self.search_edit.setMinimumHeight(32)
        self.search_edit.textChanged.connect(self._on_search_changed)
        search_layout.addWidget(self.search_edit)

        # Clear search button
        clear_search_btn = QPushButton("Clear")
        clear_search_btn.setProperty("buttonStyle", "secondary")
        clear_search_btn.setMinimumHeight(32)
        clear_search_btn.setMinimumWidth(80)
        clear_search_btn.setToolTip("Clear search and show all rules")
        clear_search_btn.clicked.connect(self.clear_search)
        search_layout.addWidget(clear_search_btn)

        filter_layout.addLayout(search_layout)

        # Filter row
        filter_row_layout = QHBoxLayout()
        filter_row_layout.setSpacing(12)

        # Category filter
        filter_row_layout.addWidget(QLabel("Category:"))
        self.category_filter = QComboBox()
        self.category_filter.addItem("All Categories")
        self.category_filter.setMinimumHeight(32)
        self.category_filter.setToolTip("Filter rules by category")
        self.category_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_row_layout.addWidget(self.category_filter)

        # Severity filter
        filter_row_layout.addWidget(QLabel("Severity:"))
        self.severity_filter = QComboBox()
        self.severity_filter.addItem("All Severities")
        self.severity_filter.setMinimumHeight(32)
        self.severity_filter.setToolTip("Filter rules by severity level")
        self.severity_filter.currentTextChanged.connect(self._on_filter_changed)
        filter_row_layout.addWidget(self.severity_filter)

        # Add stretch to push everything to the left
        filter_row_layout.addStretch()

        # REMOVED: Data Quality and High Priority preset buttons

        filter_layout.addLayout(filter_row_layout)

        parent_layout.addWidget(filter_widget)

    def create_main_content_section(self, parent_layout):
        """Create the main content area with rule tree and integrated editor."""
        # Horizontal splitter for rules tree and editor
        self.content_splitter = QSplitter(Qt.Horizontal)

        # Left panel: Rules tree
        self.create_rules_tree_panel()
        self.content_splitter.addWidget(self.rules_tree_panel)

        # Right panel: Integrated Rule Editor
        self.rule_editor = RuleEditorPanel(self.rule_manager, self)

        # Connect editor signals
        self.rule_editor.ruleUpdated.connect(self._on_rule_updated)
        self.rule_editor.ruleCreated.connect(self._on_rule_created)

        self.content_splitter.addWidget(self.rule_editor)

        # Set initial splitter proportions (50% tree, 50% editor)
        self.content_splitter.setSizes([500, 500])

        parent_layout.addWidget(self.content_splitter)

    def create_rules_tree_panel(self):
        """Create the rules tree panel."""
        self.rules_tree_panel = QWidget()
        tree_layout = QVBoxLayout(self.rules_tree_panel)
        tree_layout.setContentsMargins(0, 0, 0, 0)
        tree_layout.setSpacing(8)

        # Panel header
        tree_header = QLabel("Available Rules")
        tree_header.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        tree_header.setStyleSheet(AnalyticsRunnerStylesheet.get_header_stylesheet())
        tree_layout.addWidget(tree_header)

        # Selection controls
        selection_layout = QHBoxLayout()

        self.select_all_btn = QPushButton("Select All")
        self.select_all_btn.setProperty("buttonStyle", "secondary")
        self.select_all_btn.clicked.connect(self.select_all_visible)
        selection_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("Deselect All")
        self.deselect_all_btn.setProperty("buttonStyle", "secondary")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        selection_layout.addWidget(self.deselect_all_btn)

        # Selected count
        self.selection_count_label = QLabel("0 rules selected")
        self.selection_count_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};")
        selection_layout.addStretch()
        selection_layout.addWidget(self.selection_count_label)

        tree_layout.addLayout(selection_layout)

        # Rules tree
        self.rules_tree = QTreeWidget()
        self.rules_tree.setHeaderLabels(["Rule", "Severity", "Category"])
        self.rules_tree.setAlternatingRowColors(True)
        self.rules_tree.setRootIsDecorated(True)
        self.rules_tree.itemChanged.connect(self._on_item_changed)
        self.rules_tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.rules_tree.currentItemChanged.connect(self._on_current_item_changed)

        # Apply table styling
        self.rules_tree.setStyleSheet(AnalyticsRunnerStylesheet.get_table_stylesheet())

        tree_layout.addWidget(self.rules_tree)

    def create_action_section(self, parent_layout):
        """Create action buttons at the bottom - ENHANCED with clear labels"""
        action_layout = QHBoxLayout()

        # SINGLE New rule button with clear purpose
        self.new_rule_btn = QPushButton("Create New Rule")
        self.new_rule_btn.setToolTip("Create a brand new validation rule")
        self.new_rule_btn.clicked.connect(self.create_new_rule)
        action_layout.addWidget(self.new_rule_btn)

        # Refresh rules button
        refresh_btn = QPushButton("Refresh List")
        refresh_btn.setProperty("buttonStyle", "secondary")
        refresh_btn.setToolTip("Reload rules from storage")
        refresh_btn.clicked.connect(self.load_rules)
        action_layout.addWidget(refresh_btn)

        # Delete rule button
        self.delete_rule_btn = QPushButton("Delete Selected")
        self.delete_rule_btn.setProperty("buttonStyle", "secondary")
        self.delete_rule_btn.setToolTip("Delete the currently highlighted rule")
        self.delete_rule_btn.clicked.connect(self.delete_selected_rule)
        self.delete_rule_btn.setEnabled(False)
        action_layout.addWidget(self.delete_rule_btn)

        action_layout.addStretch()

        # Save selection preset - FIXED with clear disabled state
        save_preset_btn = QPushButton("Save as Preset")
        save_preset_btn.setProperty("buttonStyle", "secondary")
        save_preset_btn.setToolTip("Feature coming soon - save current selection as reusable preset")
        save_preset_btn.clicked.connect(self.save_selection_preset)
        save_preset_btn.setEnabled(False)  # Clearly disabled
        action_layout.addWidget(save_preset_btn)

        parent_layout.addLayout(action_layout)

    def load_rules(self):
        """Load rules from the rule manager and populate the tree - ENHANCED WITH ERROR HANDLING"""
        try:
            # Store current selection before reload
            previously_selected = self.selected_rule_ids.copy()

            self.all_rules = self.rule_manager.list_rules()
            logger.info(f"Loaded {len(self.all_rules)} rules from rule manager")

            # Update filter options
            self.update_filter_options()

            # Update tree
            self.update_rules_tree()

            # Update stats
            self.update_stats_display()

            # Restore selection
            self.selected_rule_ids = previously_selected

            # Update selection count
            self.update_selection_count()

            # Emit selection change to notify other components
            if self.selected_rule_ids:
                self.rulesSelectionChanged.emit(list(self.selected_rule_ids))

        except Exception as e:
            logger.error(f"Error loading rules: {e}")
            QMessageBox.warning(self, "Error Loading Rules", f"Failed to load rules: {str(e)}")

    def update_filter_options(self):
        """Update the filter dropdown options based on loaded rules."""
        # Get unique categories and severities
        categories = set()
        severities = set()

        for rule in self.all_rules:
            if hasattr(rule, 'category') and rule.category:
                categories.add(rule.category)
            if hasattr(rule, 'severity') and rule.severity:
                severities.add(rule.severity)

        # Update category filter
        current_category = self.category_filter.currentText()
        self.category_filter.blockSignals(True)
        self.category_filter.clear()
        self.category_filter.addItem("All Categories")
        for category in sorted(categories):
            self.category_filter.addItem(category.title().replace('_', ' '))

        # Restore selection if possible
        index = self.category_filter.findText(current_category)
        if index >= 0:
            self.category_filter.setCurrentIndex(index)
        self.category_filter.blockSignals(False)

        # Update severity filter
        current_severity = self.severity_filter.currentText()
        self.severity_filter.blockSignals(True)
        self.severity_filter.clear()
        self.severity_filter.addItem("All Severities")

        # Add severities in priority order
        severity_order = ["critical", "high", "medium", "low", "info"]
        for severity in severity_order:
            if severity in severities:
                self.severity_filter.addItem(severity.title())

        # Restore selection if possible
        index = self.severity_filter.findText(current_severity)
        if index >= 0:
            self.severity_filter.setCurrentIndex(index)
        self.severity_filter.blockSignals(False)

    def update_rules_tree(self):
        """Update the rules tree with filtered results - CORRECT PySide6 syntax"""
        # Apply current filters
        self.apply_filters()

        # Store current selection to preserve it
        selected_rule_ids = self.selected_rule_ids.copy()

        # Clear tree
        self.rules_tree.clear()

        # Group rules by category
        grouped_rules = defaultdict(list)
        for rule in self.filtered_rules:
            category = getattr(rule, 'category', 'Uncategorized')
            grouped_rules[category].append(rule)

        # Create tree items
        for category, rules in sorted(grouped_rules.items()):
            category_item = QTreeWidgetItem(self.rules_tree)
            category_item.setText(0, category.title().replace('_', ' '))
            category_item.setText(1, f"({len(rules)} rules)")

            # CORRECT: Use the proper Qt.ItemFlag enumeration
            category_item.setFlags(
                category_item.flags() |
                Qt.ItemFlag.ItemIsAutoTristate |
                Qt.ItemFlag.ItemIsUserCheckable
            )
            category_item.setCheckState(0, Qt.CheckState.Unchecked)

            # Set category styling
            font = category_item.font(0)
            font.setBold(True)
            category_item.setFont(0, font)

            # Add rule items
            for rule in sorted(rules, key=lambda r: r.name):
                rule_item = QTreeWidgetItem(category_item)
                rule_item.setText(0, rule.name)
                rule_item.setText(1, getattr(rule, 'severity', 'medium').title())
                rule_item.setText(2, getattr(rule, 'category', 'uncategorized').title().replace('_', ' '))

                # CORRECT: Use Qt.ItemFlag.ItemIsUserCheckable
                rule_item.setFlags(rule_item.flags() | Qt.ItemFlag.ItemIsUserCheckable)

                # RESTORE SELECTION: Set check state based on previous selection
                if rule.rule_id in selected_rule_ids:
                    rule_item.setCheckState(0, Qt.CheckState.Checked)
                else:
                    rule_item.setCheckState(0, Qt.CheckState.Unchecked)

                # Store rule ID for reference
                rule_item.setData(0, Qt.UserRole, rule.rule_id)

                # Add tooltip with rule description
                if rule.description:
                    rule_item.setToolTip(0, f"{rule.name}\n\n{rule.description}")

        # Expand all categories by default
        self.rules_tree.expandAll()

        # Resize columns to content
        for i in range(3):
            self.rules_tree.resizeColumnToContents(i)

    def apply_filters(self):
        """Apply current search and filter criteria to rules."""
        search_text = self.search_edit.text().lower().strip()
        category_filter = self.category_filter.currentText()
        severity_filter = self.severity_filter.currentText()

        self.filtered_rules = []

        for rule in self.all_rules:
            # Apply search filter
            if search_text:
                searchable_text = f"{rule.name} {rule.description} {' '.join(getattr(rule, 'tags', []))}"
                if search_text not in searchable_text.lower():
                    continue

            # Apply category filter
            if category_filter != "All Categories":
                rule_category = getattr(rule, 'category', 'uncategorized').title().replace('_', ' ')
                if rule_category != category_filter:
                    continue

            # Apply severity filter
            if severity_filter != "All Severities":
                rule_severity = getattr(rule, 'severity', 'medium').title()
                if rule_severity != severity_filter:
                    continue

            self.filtered_rules.append(rule)

    def update_stats_display(self):
        """Update the statistics display in the header - ENHANCED"""
        total_rules = len(self.all_rules)
        filtered_rules = len(self.filtered_rules)
        selected_rules = len(self.selected_rule_ids)

        if total_rules == 0:
            self.stats_label.setText("No rules available - click 'Create New Rule' to get started")
            self.stats_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; font-style: italic;")
        elif filtered_rules == total_rules:
            self.stats_label.setText(f"{total_rules} rules • {selected_rules} selected for validation")
            self.stats_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.TEXT_COLOR};")
        else:
            self.stats_label.setText(f"Showing {filtered_rules} of {total_rules} rules • {selected_rules} selected")
            self.stats_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.TEXT_COLOR};")

    def update_selection_count(self):
        """Update the selection count display."""
        count = len(self.selected_rule_ids)
        self.selection_count_label.setText(f"{count} rule{'s' if count != 1 else ''} selected")
        self.update_stats_display()

    # Event handlers
    def _on_search_changed(self):
        """Handle search text changes with debouncing."""
        self.search_timer.stop()
        self.search_timer.start(300)  # 300ms delay

    def _perform_search(self):
        """Perform the actual search/filter operation."""
        self.update_rules_tree()
        self.update_stats_display()

    def _on_filter_changed(self):
        """Handle filter dropdown changes."""
        self.update_rules_tree()
        self.update_stats_display()

    def _on_item_changed(self, item: QTreeWidgetItem, column: int):
        """Handle item check state changes - CORRECT CheckState references"""
        if column != 0:  # Only handle check state changes in first column
            return

        rule_id = item.data(0, Qt.UserRole)
        if rule_id:  # This is a rule item (has rule_id)
            if item.checkState(0) == Qt.CheckState.Checked:
                self.selected_rule_ids.add(rule_id)
            else:
                self.selected_rule_ids.discard(rule_id)

            self.update_selection_count()
            self.rulesSelectionChanged.emit(list(self.selected_rule_ids))
            self.save_session_state()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle item double-click to load rule in editor - ENHANCED with feedback"""
        rule_id = item.data(0, Qt.UserRole)
        if rule_id:
            # Show which rule is being loaded
            rule = self.rule_manager.get_rule(rule_id)
            if rule:
                self._show_filter_feedback(f"Loading '{rule.name}' in editor...")
            self.load_rule_in_editor(rule_id)

    def _on_current_item_changed(self, current: QTreeWidgetItem, previous: QTreeWidgetItem):
        """Handle current item selection change."""
        if not current:
            self.delete_rule_btn.setEnabled(False)
            return

        rule_id = current.data(0, Qt.UserRole)
        if rule_id:
            # Enable delete button for rule items
            self.delete_rule_btn.setEnabled(True)
        else:
            # Category item selected
            self.delete_rule_btn.setEnabled(False)

    def _on_rule_updated(self, rule_id: str):
        """Handle rule update from editor - ENHANCED with immediate feedback"""
        logger.info(f"Rule updated: {rule_id}")

        # Show immediate feedback
        self._show_filter_feedback(f"Rule updated: {rule_id}")

        # Reload rules to reflect changes
        self.load_rules()

        # Ensure the updated rule stays selected if it was selected before
        if rule_id in self.selected_rule_ids:
            # The selection will be restored by load_rules() -> update_rules_tree()
            pass

    def _on_rule_created(self, rule_id: str):
        """Handle rule creation from editor - ENHANCED with better UX"""
        logger.info(f"Rule created: {rule_id}")

        # Get the rule to show its name
        rule = self.rule_manager.get_rule(rule_id)
        rule_name = rule.name if rule else rule_id

        # Show immediate feedback
        self._show_filter_feedback(f"✓ Created: {rule_name}")

        # Reload rules to show new rule
        self.load_rules()

        # AUTO-SELECT the newly created rule
        self.selected_rule_ids.add(rule_id)
        self.update_selection_count()
        self.rulesSelectionChanged.emit(list(self.selected_rule_ids))

        # Update the tree to show selection
        self.update_rules_tree()

        # EXPAND to show the new rule and scroll to it
        self._scroll_to_rule(rule_id)

    def _scroll_to_rule(self, rule_id: str):
        """Scroll to and highlight a specific rule in the tree - NEW METHOD"""
        try:
            # Find the rule item in the tree
            def find_rule_item(parent_item, target_rule_id):
                for i in range(parent_item.childCount()):
                    child = parent_item.child(i)
                    if child.data(0, Qt.UserRole) == target_rule_id:
                        return child
                return None

            # Search through all category items
            root = self.rules_tree.invisibleRootItem()
            for i in range(root.childCount()):
                category_item = root.child(i)
                rule_item = find_rule_item(category_item, rule_id)
                if rule_item:
                    # Expand the category
                    category_item.setExpanded(True)
                    # Select and scroll to the rule
                    self.rules_tree.setCurrentItem(rule_item)
                    self.rules_tree.scrollToItem(rule_item)
                    logger.debug(f"Scrolled to rule: {rule_id}")
                    break

        except Exception as e:
            logger.warning(f"Could not scroll to rule {rule_id}: {e}")

    def _show_filter_feedback(self, message: str, is_warning: bool = False):
        """Show temporary feedback about filter actions - NEW METHOD"""
        # Update stats label temporarily with feedback
        original_text = self.stats_label.text()
        original_style = self.stats_label.styleSheet()

        if is_warning:
            self.stats_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.WARNING_COLOR}; font-style: italic;")
        else:
            self.stats_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR}; font-style: italic;")

        self.stats_label.setText(message)

        # Restore original text after 3 seconds
        QTimer.singleShot(3000, lambda: [
            self.stats_label.setText(original_text),
            self.stats_label.setStyleSheet(original_style)
        ])

    # Public methods
    def clear_search(self):
        """Clear the search box and refresh results."""
        self.search_edit.clear()
        self.update_rules_tree()
        self.update_stats_display()

    def select_all_visible(self):
        """Select all currently visible (filtered) rules."""
        for rule in self.filtered_rules:
            self.selected_rule_ids.add(rule.rule_id)

        self.update_rules_tree()
        self.update_selection_count()
        self.rulesSelectionChanged.emit(list(self.selected_rule_ids))
        self.save_session_state()

    def deselect_all(self):
        """Deselect all rules."""
        self.selected_rule_ids.clear()
        self.update_rules_tree()
        self.update_selection_count()
        self.rulesSelectionChanged.emit(list(self.selected_rule_ids))
        self.save_session_state()

    def apply_preset_filter(self, preset_type: str):
        """Apply a predefined filter preset - ENHANCED with user feedback"""
        if preset_type == "data_quality":
            # Set category filter to data quality
            original_filter = self.category_filter.currentText()

            # Try exact match first
            index = self.category_filter.findText("Data Quality")
            if index >= 0:
                self.category_filter.setCurrentIndex(index)
                self._show_filter_feedback("Filtered to Data Quality rules")
                return

            # Try case variations
            for i in range(self.category_filter.count()):
                text = self.category_filter.itemText(i).lower()
                if "data" in text and "quality" in text:
                    self.category_filter.setCurrentIndex(i)
                    self._show_filter_feedback(f"Filtered to {self.category_filter.itemText(i)} rules")
                    return

            # If no data quality category found
            self._show_filter_feedback("No Data Quality rules found", is_warning=True)

        elif preset_type == "high_severity":
            original_filter = self.severity_filter.currentText()

            # Try High first, then Critical
            for severity in ["High", "Critical"]:
                index = self.severity_filter.findText(severity)
                if index >= 0:
                    self.severity_filter.setCurrentIndex(index)
                    self._show_filter_feedback(f"Filtered to {severity} severity rules")
                    return

            # If neither found
            self._show_filter_feedback("No High/Critical severity rules found", is_warning=True)

    def get_selected_rule_ids(self) -> List[str]:
        """Get the list of currently selected rule IDs."""
        return list(self.selected_rule_ids)

    def set_selected_rule_ids(self, rule_ids: List[str]):
        """Set the selected rule IDs programmatically."""
        self.selected_rule_ids = set(rule_ids)
        self.update_rules_tree()
        self.update_selection_count()
        self.rulesSelectionChanged.emit(list(self.selected_rule_ids))

    def create_new_rule(self):
        """Create a new rule using the integrated editor - FIXED: No double dialog"""
        # DON'T check for unsaved changes here - let the editor handle it
        # The editor's create_new_rule method will handle the discard dialog

        # Show immediate feedback
        self._show_filter_feedback("Creating new rule...")

        # Create new rule in editor - this will handle the unsaved changes check
        self.rule_editor.create_new_rule()

        # Clear any search/filters to ensure new rule will be visible
        self.clear_search()

    def load_rule_in_editor(self, rule_id: str):
        """Load a rule into the integrated editor."""
        # Check if editor has unsaved changes
        if self.rule_editor.has_changes():
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "The editor has unsaved changes. Do you want to discard them?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # Load rule in editor
        success = self.rule_editor.load_rule(rule_id)
        if success:
            logger.info(f"Loaded rule {rule_id} in editor")

    def delete_selected_rule(self):
        """Delete the currently selected rule."""
        current_item = self.rules_tree.currentItem()
        if not current_item:
            return

        rule_id = current_item.data(0, Qt.UserRole)
        if not rule_id:
            return

        # Get rule for confirmation
        rule = self.rule_manager.get_rule(rule_id)
        if not rule:
            QMessageBox.warning(self, "Rule Not Found", "The selected rule could not be found.")
            return

        # Confirm deletion
        reply = QMessageBox.question(
            self,
            "Delete Rule",
            f"Are you sure you want to delete the rule '{rule.name}'?\n\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                # Delete from rule manager
                success = self.rule_manager.delete_rule(rule_id)

                if success:
                    # Remove from selected rules
                    self.selected_rule_ids.discard(rule_id)

                    # Clear editor if it's showing the deleted rule
                    if self.rule_editor.get_current_rule_id() == rule_id:
                        self.rule_editor.reset_editor()

                    # Reload rules list
                    self.load_rules()
                    self.update_selection_count()
                    self.rulesSelectionChanged.emit(list(self.selected_rule_ids))

                    logger.info(f"Deleted rule: {rule.name} ({rule_id})")
                else:
                    QMessageBox.warning(self, "Delete Failed", "Failed to delete the rule.")

            except Exception as e:
                error_msg = f"Error deleting rule: {str(e)}"
                logger.error(error_msg)
                QMessageBox.critical(self, "Delete Error", error_msg)

    def save_selection_preset(self):
        """Save current selection as a preset - ENHANCED with clear messaging"""
        # Show informative dialog instead of silent failure
        QMessageBox.information(
            self,
            "Feature Not Available",
            "Saving selection presets is planned for a future release.\n\n"
            "For now, you can use the filter buttons to quickly select common rule types."
        )

    def set_available_columns(self, columns: List[str]):
        """Set available columns for the rule editor."""
        self.rule_editor.set_available_columns(columns)

    def set_current_data_preview(self, data_df):
        """Set current data preview for rule testing."""
        self.rule_editor.set_current_data_preview(data_df)

    # Session management
    def save_session_state(self):
        """Save current state to session manager."""
        state = {
            'selected_rule_ids': list(self.selected_rule_ids),
            'search_text': self.search_edit.text(),
            'category_filter': self.category_filter.currentText(),
            'severity_filter': self.severity_filter.currentText(),
            'splitter_state': self.content_splitter.saveState().data(),
        }

        self.session_manager.set('rule_selector_state', state, auto_save=True)

    def restore_session_state(self):
        """Restore state from session manager."""
        state = self.session_manager.get('rule_selector_state', {})

        # Restore selected rules
        if 'selected_rule_ids' in state:
            self.selected_rule_ids = set(state['selected_rule_ids'])

        # Restore search text
        if 'search_text' in state:
            self.search_edit.setText(state['search_text'])

        # Restore filters (after filter options are populated)
        if 'category_filter' in state:
            QTimer.singleShot(100, lambda: self._restore_filter_selection('category_filter', state['category_filter']))

        if 'severity_filter' in state:
            QTimer.singleShot(100, lambda: self._restore_filter_selection('severity_filter', state['severity_filter']))

        # Restore splitter state
        if 'splitter_state' in state:
            try:
                from PySide6.QtCore import QByteArray
                splitter_data = QByteArray(state['splitter_state'])
                self.content_splitter.restoreState(splitter_data)
            except Exception as e:
                logger.warning(f"Could not restore splitter state: {e}")

    def _restore_filter_selection(self, filter_name: str, value: str):
        """Helper to restore filter selection after options are populated."""
        filter_widget = getattr(self, filter_name, None)
        if filter_widget:
            index = filter_widget.findText(value)
            if index >= 0:
                filter_widget.setCurrentIndex(index)

    def cleanup(self):
        """Clean up resources when the panel is destroyed."""
        self.save_session_state()
        self.search_timer.stop()
        logger.info("RuleSelectorPanel cleaned up")
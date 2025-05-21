from PySide6.QtWidgets import (QMainWindow, QTabWidget, QVBoxLayout,
                             QWidget, QMessageBox, QSplitter, QLabel)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from rule_model import RuleModel
from simple_rule_editor import SimpleRuleEditor
from advanced_rule_editor import AdvancedRuleEditor
from rule_preview_panel import RulePreviewPanel
from rule_test_panel import RuleTestPanel
from data_loader_panel import DataLoaderPanel

from core.rule_engine.rule_manager import ValidationRuleManager


class RuleBuilderMainWindow(QMainWindow):
    """Main window for the Rule Builder application."""

    def __init__(self, rule_manager_path=None):
        super().__init__()

        # Initialize ValidationRuleManager with optional path
        self.rule_manager = ValidationRuleManager(rule_manager_path)

        # Initialize rule model with our rule manager
        self.rule_model = RuleModel(self.rule_manager)

        # Set up UI
        self.setWindowTitle("Audit QA Rule Builder")
        self.resize(1200, 800)

        # Create main layout
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # Create tab widget for main sections
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs)

        # Initialize UI components
        self.setup_rule_builder_tab()
        self.setup_advanced_editor_tab()
        self.setup_preview_tab()
        self.setup_test_tab()

        # Connect signals
        self.connect_signals()

        # Set up menu and toolbar
        self.setup_menu()

        # Status bar for messages
        self.statusBar().showMessage("Ready")

        # Load rules for selection
        self.load_rule_list()

    def setup_rule_builder_tab(self):
        """Set up the simple rule builder tab."""
        rule_builder_widget = QWidget()
        layout = QVBoxLayout(rule_builder_widget)

        # Create splitter for rule editor and data preview
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Add simple rule editor to left side
        self.simple_editor = SimpleRuleEditor(self.rule_model)
        splitter.addWidget(self.simple_editor)

        # Add data loader/preview to right side
        self.data_loader = DataLoaderPanel()
        splitter.addWidget(self.data_loader)

        # Set initial splitter sizes (60% editor, 40% data preview)
        splitter.setSizes([600, 400])

        self.tabs.addTab(rule_builder_widget, "Rule Builder")

    def setup_advanced_editor_tab(self):
        """Set up the advanced rule editor tab."""
        advanced_editor_widget = QWidget()
        layout = QVBoxLayout(advanced_editor_widget)

        # Create splitter for advanced editor and logic tree
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        # Add advanced rule editor to left side
        self.advanced_editor = AdvancedRuleEditor(self.rule_model)
        splitter.addWidget(self.advanced_editor)

        # Add rule preview panel to right side
        self.rule_preview = RulePreviewPanel(self.rule_model)
        splitter.addWidget(self.rule_preview)

        # Set initial splitter sizes
        splitter.setSizes([600, 400])

        self.tabs.addTab(advanced_editor_widget, "Advanced Editor")

    def setup_preview_tab(self):
        """Set up the rule preview tab."""
        preview_widget = QWidget()
        layout = QVBoxLayout(preview_widget)

        # Add YAML preview
        title = QLabel("Rule Configuration Preview")
        title.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(title)

        self.yaml_preview = RulePreviewPanel(self.rule_model)
        layout.addWidget(self.yaml_preview)

        self.tabs.addTab(preview_widget, "Preview")

    def setup_test_tab(self):
        """Set up the rule testing tab."""
        test_widget = QWidget()
        layout = QVBoxLayout(test_widget)

        # Add rule test panel
        self.test_panel = RuleTestPanel(self.rule_model, self.data_loader)
        layout.addWidget(self.test_panel)

        self.tabs.addTab(test_widget, "Test Results")

    def connect_signals(self):
        """Connect signals between components."""
        # Connect rule model changes to update previews
        self.rule_model.rule_changed.connect(self.rule_preview.update_preview)
        self.rule_model.rule_changed.connect(self.yaml_preview.update_preview)

        # Connect data loader to test panel and simple editor
        self.data_loader.data_loaded.connect(self.test_panel.set_data)
        self.data_loader.data_loaded.connect(self.update_available_columns)

        # Connect tab changes
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Connect editors to switch between simple and advanced modes
        self.simple_editor.switch_to_advanced.connect(lambda: self.tabs.setCurrentIndex(1))
        self.advanced_editor.switch_to_simple.connect(lambda: self.tabs.setCurrentIndex(0))

    def update_available_columns(self, df):
        """Update column suggestions in the simple editor when data is loaded."""
        if hasattr(self, 'simple_editor'):
            columns = list(df.columns)
            self.simple_editor.set_available_columns(columns)

    def setup_menu(self):
        """Set up the application menu."""
        # File menu
        file_menu = self.menuBar().addMenu("&File")

        # New rule action
        new_action = file_menu.addAction("&New Rule")
        new_action.setShortcut("Ctrl+N")
        new_action.triggered.connect(self.new_rule)

        # Open rule action
        open_action = file_menu.addAction("&Open Rule...")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.open_rule)

        # Save rule action
        save_action = file_menu.addAction("&Save Rule")
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_rule)

        # Save As action
        save_as_action = file_menu.addAction("Save Rule &As...")
        save_as_action.setShortcut("Ctrl+Shift+S")
        save_as_action.triggered.connect(self.save_rule_as)

        file_menu.addSeparator()

        # Reload rules action
        reload_action = file_menu.addAction("&Reload Rules")
        reload_action.setShortcut("F5")
        reload_action.triggered.connect(self.load_rule_list)

        file_menu.addSeparator()

        # Exit action
        exit_action = file_menu.addAction("E&xit")
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)

        # Edit menu
        edit_menu = self.menuBar().addMenu("&Edit")

        # Validate rule action
        validate_action = edit_menu.addAction("&Validate Rule")
        validate_action.setShortcut("F7")
        validate_action.triggered.connect(self.validate_rule)

        # Tools menu
        tools_menu = self.menuBar().addMenu("&Tools")

        # Test with sample data action
        test_action = tools_menu.addAction("&Test Rule with Data")
        test_action.setShortcut("F9")
        test_action.triggered.connect(lambda: self.tabs.setCurrentIndex(3))  # Switch to test tab

        # Export rule configuration action
        export_action = tools_menu.addAction("&Export Rule Configuration")
        export_action.triggered.connect(self.export_rule_configuration)

        # Help menu
        help_menu = self.menuBar().addMenu("&Help")

        # About action
        about_action = help_menu.addAction("&About")
        about_action.triggered.connect(self.show_about)

    def on_tab_changed(self, index):
        """Handle tab changes to update content."""
        if index == 2:  # Preview tab
            self.yaml_preview.update_preview()
        elif index == 3:  # Test tab
            self.test_panel.refresh_test_results()

    def new_rule(self):
        """Create a new rule."""
        self.rule_model.reset_rule()
        self.simple_editor.reset_form()
        self.advanced_editor.reset_editor()
        self.statusBar().showMessage("Created new rule")

    def open_rule(self):
        """Open an existing rule from the rule manager."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QLabel

        # Create a dialog to select a rule
        dialog = QDialog(self)
        dialog.setWindowTitle("Select Rule")
        dialog.setMinimumWidth(400)
        dialog.setMinimumHeight(300)

        layout = QVBoxLayout(dialog)

        # Add label
        layout.addWidget(QLabel("Select a rule to open:"))

        # Add list widget
        list_widget = QListWidget()
        layout.addWidget(list_widget)

        # Add rules to list
        rules = self.rule_manager.list_rules()
        for rule in rules:
            list_widget.addItem(f"{rule.name} ({rule.rule_id})")
            # Store rule_id as item data
            list_widget.item(list_widget.count() - 1).setData(Qt.UserRole, rule.rule_id)

        # Add buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)

        open_btn = QPushButton("Open")
        open_btn.setDefault(True)
        open_btn.clicked.connect(dialog.accept)

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(open_btn)

        layout.addLayout(button_layout)

        # Show dialog
        if dialog.exec() == QDialog.Accepted:
            selected_items = list_widget.selectedItems()
            if selected_items:
                rule_id = selected_items[0].data(Qt.UserRole)
                self.load_rule(rule_id)

    def load_rule(self, rule_id):
        """Load a rule by ID."""
        # Load the rule from rule manager
        rule = self.rule_manager.get_rule(rule_id)
        if rule:
            # Set the rule in the model
            self.rule_model.set_rule(rule)

            # Update UI components
            self.simple_editor.update_from_model()
            self.advanced_editor.update_from_model()

            self.statusBar().showMessage(f"Opened rule: {rule.name}")

            # Switch to Rule Builder tab
            self.tabs.setCurrentIndex(0)
        else:
            QMessageBox.warning(self, "Error", f"Rule with ID {rule_id} not found.")

    def save_rule(self):
        """Save the current rule."""
        # Check if rule_id is set (existing rule)
        if self.rule_model.rule_id:
            success, error = self.rule_model.save_rule()
            if success:
                self.statusBar().showMessage(f"Rule '{self.rule_model.name}' updated successfully")
            else:
                QMessageBox.warning(self, "Error", f"Failed to save rule: {error}")
        else:
            # No rule_id, do a Save As
            self.save_rule_as()

    def save_rule_as(self):
        """Save the current rule with a new ID."""
        from PySide6.QtWidgets import QInputDialog, QLineEdit

        # Check if rule is valid
        is_valid, error = self.rule_model.validate()
        if not is_valid:
            QMessageBox.warning(self, "Error", f"Rule is not valid: {error}")
            return

        # Get rule name if not set
        if not self.rule_model.name:
            name, ok = QInputDialog.getText(
                self, "Rule Name", "Enter a name for the rule:",
                QLineEdit.Normal, ""
            )
            if ok and name:
                self.rule_model.name = name
            else:
                return

        # Generate new rule ID if needed
        if not self.rule_model.rule_id:
            import uuid
            self.rule_model.current_rule.rule_id = str(uuid.uuid4())

        # Save rule
        success, error = self.rule_model.save_rule()
        if success:
            self.statusBar().showMessage(f"Rule '{self.rule_model.name}' saved successfully")
            # Reload rule list to show the new rule
            self.load_rule_list()
        else:
            QMessageBox.warning(self, "Error", f"Failed to save rule: {error}")

    def validate_rule(self):
        """Validate the current rule."""
        is_valid, error = self.rule_model.validate()
        if is_valid:
            QMessageBox.information(self, "Validation", "Rule is valid.")
        else:
            QMessageBox.warning(self, "Validation", f"Rule is invalid: {error}")

    def export_rule_configuration(self):
        """Export the current rule to a YAML file."""
        from PySide6.QtWidgets import QFileDialog

        # Check if rule is valid
        is_valid, error = self.rule_model.validate()
        if not is_valid:
            QMessageBox.warning(self, "Error", f"Rule is not valid: {error}")
            return

        # Get export file path
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Rule", "",
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )

        if file_path:
            try:
                # Export rule as YAML
                with open(file_path, 'w') as f:
                    f.write(self.rule_model.to_yaml())

                self.statusBar().showMessage(f"Rule exported to {file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Error exporting rule: {str(e)}")

    def load_rule_list(self):
        """Reload the list of rules from the rule manager."""
        try:
            rules = self.rule_manager.list_rules()
            self.statusBar().showMessage(f"Loaded {len(rules)} rules")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error loading rules: {str(e)}")

    def show_about(self):
        """Show about dialog."""
        about_text = (
            "Rule Builder for Audit QA Framework\n\n"
            "A tool for creating, editing, and testing validation rules\n"
            "using the QA Analytics Framework."
        )
        QMessageBox.about(self, "About Rule Builder", about_text)
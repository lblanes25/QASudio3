from PySide6.QtWidgets import (QMainWindow, QTabWidget, QVBoxLayout,
                               QWidget, QMessageBox, QSplitter, QLabel, QScrollArea)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from rule_model import RuleModel
from ui.rule_builder.editors.simple_rule_editor import SimpleRuleEditor
from ui.rule_builder.editors.advanced_rule_editor import AdvancedRuleEditor
from ui.rule_builder.panels.rule_preview_panel import RulePreviewPanel
from ui.rule_builder.panels.rule_test_panel import RuleTestPanel
from ui.rule_builder.panels.data_loader_panel import DataLoaderPanel

from core.rule_engine.rule_manager import ValidationRuleManager
from stylesheet import Stylesheet


class RuleBuilderMainWindow(QMainWindow):
    """Main window for the Rule Builder application."""

    def __init__(self, rule_manager_path=None):
        super().__init__()

        # Initialize ValidationRuleManager with optional path
        self.rule_manager = ValidationRuleManager(rule_manager_path)

        # Initialize rule model with our rule manager
        self.rule_model = RuleModel(self.rule_manager)

        # Set up UI with improved layout and resizing
        self.setWindowTitle("Audit Rule Builder")

        # FIX: Enable window resizing and set reasonable defaults
        self.resize(1400, 900)  # Larger initial size
        self.setMinimumSize(1000, 700)  # Reasonable minimum
        # Remove maximum size constraints to allow full screen

        # Apply global stylesheet
        self.setStyleSheet(Stylesheet.get_global_stylesheet())

        # Set application font
        self.setFont(Stylesheet.get_regular_font())

        # Create main layout with reduced nesting
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(Stylesheet.FORM_SPACING, Stylesheet.FORM_SPACING,
                                            Stylesheet.FORM_SPACING, Stylesheet.FORM_SPACING)
        self.main_layout.setSpacing(Stylesheet.STANDARD_SPACING)

        # Create header
        self.setup_header()

        # FIX: Simplified layout without nested scroll areas
        # Create main content splitter (vertical)
        self.main_splitter = QSplitter(Qt.Vertical)

        # Top section: Editor area
        self.editor_container = QWidget()
        editor_layout = QVBoxLayout(self.editor_container)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(0)

        # Create stack widget for simple/advanced toggle
        from PySide6.QtWidgets import QStackedWidget
        self.stack = QStackedWidget()

        # Create editors
        self.simple_editor = SimpleRuleEditor(self.rule_model)
        self.advanced_editor = AdvancedRuleEditor(self.rule_model)

        self.stack.addWidget(self.simple_editor)
        self.stack.addWidget(self.advanced_editor)

        editor_layout.addWidget(self.stack)
        self.main_splitter.addWidget(self.editor_container)

        # Middle section: Data loader (collapsible)
        self.data_loader = DataLoaderPanel()
        self.data_loader.setVisible(False)
        self.main_splitter.addWidget(self.data_loader)

        # Bottom section: Test results (collapsible)
        self.test_panel = RuleTestPanel(self.rule_model, self.data_loader)
        self.test_panel.setVisible(False)
        self.main_splitter.addWidget(self.test_panel)

        # Set splitter sizes - give most space to editor
        self.main_splitter.setSizes([600, 150, 150])
        self.main_splitter.setCollapsible(0, False)  # Editor can't be collapsed
        self.main_splitter.setCollapsible(1, True)  # Data loader can be collapsed
        self.main_splitter.setCollapsible(2, True)  # Test panel can be collapsed

        self.main_layout.addWidget(self.main_splitter)

        # Connect signals
        self.connect_signals()

        # Footer
        self.setup_footer()

        # Status bar
        self.statusBar().showMessage("Ready")

        # Start with simple editor
        self.stack.setCurrentIndex(0)

        # Load rules
        self.load_rule_list()

    def setup_header(self):
        """Create header with title and mode toggle."""
        from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QButtonGroup

        header_layout = QHBoxLayout()
        header_layout.setSpacing(Stylesheet.SECTION_SPACING)

        # Title
        title = QLabel("Audit Rule Builder")
        title.setFont(Stylesheet.get_title_font())
        title.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(title, 1)

        # Mode toggle buttons
        toggle_layout = QHBoxLayout()
        toggle_layout.setSpacing(0)

        self.simple_button = QPushButton("Simple")
        self.simple_button.setCheckable(True)
        self.simple_button.setChecked(True)
        self.simple_button.setMinimumWidth(80)
        self.simple_button.setMinimumHeight(Stylesheet.BUTTON_HEIGHT)

        self.advanced_button = QPushButton("Advanced")
        self.advanced_button.setCheckable(True)
        self.advanced_button.setMinimumWidth(80)
        self.advanced_button.setMinimumHeight(Stylesheet.BUTTON_HEIGHT)

        # Apply toggle styling
        toggle_style = Stylesheet.get_toggle_button_style()
        self.simple_button.setStyleSheet(toggle_style)
        self.advanced_button.setStyleSheet(toggle_style)

        toggle_layout.addWidget(self.simple_button)
        toggle_layout.addWidget(self.advanced_button)

        # Button group for mutual exclusion
        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.simple_button, 0)
        self.mode_group.addButton(self.advanced_button, 1)
        self.mode_group.buttonToggled.connect(self.toggle_editor_mode)

        header_layout.addLayout(toggle_layout)

        self.main_layout.addLayout(header_layout)
        self.main_layout.addSpacing(Stylesheet.STANDARD_SPACING)

    def setup_footer(self):
        """Create footer with action buttons."""
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QFrame

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        self.main_layout.addWidget(separator)

        # Footer layout
        footer_layout = QHBoxLayout()
        footer_layout.setSpacing(Stylesheet.STANDARD_SPACING)

        # Save button
        save_button = QPushButton("Save Rule")
        save_button.setMinimumHeight(Stylesheet.HEADER_HEIGHT)
        save_button.setFont(Stylesheet.get_regular_font())
        save_button.clicked.connect(self.save_rule)
        footer_layout.addWidget(save_button)

        # Data toggle button
        self.show_data_button = QPushButton("Show Test Data")
        self.show_data_button.setMinimumHeight(Stylesheet.HEADER_HEIGHT)
        self.show_data_button.setCheckable(True)
        self.show_data_button.clicked.connect(self.toggle_data_loader)
        footer_layout.addWidget(self.show_data_button)

        # Test button
        test_button = QPushButton("Test Rule")
        test_button.setMinimumHeight(Stylesheet.HEADER_HEIGHT)
        test_button.clicked.connect(self.run_test)
        footer_layout.addWidget(test_button)

        self.main_layout.addLayout(footer_layout)

    def toggle_editor_mode(self, button, checked):
        """Toggle between simple and advanced editor modes."""
        if checked:
            if button == self.simple_button:
                self.stack.setCurrentIndex(0)
            else:
                self.stack.setCurrentIndex(1)

    def toggle_data_loader(self, checked):
        """Toggle the data loader panel visibility."""
        self.data_loader.setVisible(checked)

        # Update button text
        if checked:
            self.show_data_button.setText("Hide Test Data")
        else:
            self.show_data_button.setText("Show Test Data")

        # Adjust splitter sizes when showing/hiding
        if checked:
            self.main_splitter.setSizes([500, 200, 200])
        else:
            self.main_splitter.setSizes([700, 0, 100])

    def run_test(self):
        """Run the rule test and show results."""
        # Show test panel if hidden
        if not self.test_panel.isVisible():
            self.test_panel.setVisible(True)
            # Adjust splitter sizes
            self.main_splitter.setSizes([400, 200, 300])

        # Run the test
        self.test_panel.run_test()

    def connect_signals(self):
        """Connect signals between components."""
        # Data loader to test panel and column updates
        self.data_loader.data_loaded.connect(self.test_panel.set_data)
        self.data_loader.data_loaded.connect(self.update_available_columns)

        # Editor switching
        self.simple_editor.switch_to_advanced.connect(lambda: self.stack.setCurrentIndex(1))
        self.advanced_editor.switch_to_simple.connect(lambda: self.stack.setCurrentIndex(0))

    def update_available_columns(self, df):
        """Update column suggestions when data is loaded."""
        if hasattr(self, 'simple_editor'):
            columns = list(df.columns)
            self.simple_editor.set_available_columns(columns)

    def new_rule(self):
        """Create a new rule."""
        self.rule_model.reset_rule()
        self.simple_editor.reset_form()
        self.advanced_editor.reset_editor()
        self.statusBar().showMessage("Created new rule")

    def open_rule(self):
        """Open an existing rule."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QPushButton, QHBoxLayout, QLabel

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Rule")
        dialog.setMinimumWidth(400)
        dialog.setMinimumHeight(300)

        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Select a rule to open:"))

        list_widget = QListWidget()
        layout.addWidget(list_widget)

        # Add rules to list
        rules = self.rule_manager.list_rules()
        for rule in rules:
            list_widget.addItem(f"{rule.name} ({rule.rule_id})")
            list_widget.item(list_widget.count() - 1).setData(Qt.UserRole, rule.rule_id)

        # Buttons
        button_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        open_btn = QPushButton("Open")
        open_btn.setDefault(True)
        open_btn.clicked.connect(dialog.accept)
        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(open_btn)
        layout.addLayout(button_layout)

        if dialog.exec() == QDialog.Accepted:
            selected_items = list_widget.selectedItems()
            if selected_items:
                rule_id = selected_items[0].data(Qt.UserRole)
                self.load_rule(rule_id)

    def load_rule(self, rule_id):
        """Load a rule by ID."""
        rule = self.rule_manager.get_rule(rule_id)
        if rule:
            self.rule_model.set_rule(rule)
            self.simple_editor.update_from_model()
            self.advanced_editor.update_from_model()
            self.statusBar().showMessage(f"Opened rule: {rule.name}")
            # Switch to Simple Editor
            self.stack.setCurrentIndex(0)
            self.simple_button.setChecked(True)
        else:
            QMessageBox.warning(self, "Error", f"Rule with ID {rule_id} not found.")

    def save_rule(self):
        """Save the current rule."""
        if self.rule_model.rule_id:
            success, error = self.rule_model.save_rule()
            if success:
                self.statusBar().showMessage(f"Rule '{self.rule_model.name}' updated successfully")
            else:
                QMessageBox.warning(self, "Error", f"Failed to save rule: {error}")
        else:
            self.save_rule_as()

    def save_rule_as(self):
        """Save rule with new ID."""
        from PySide6.QtWidgets import QInputDialog, QLineEdit

        is_valid, error = self.rule_model.validate()
        if not is_valid:
            QMessageBox.warning(self, "Error", f"Rule is not valid: {error}")
            return

        if not self.rule_model.name:
            name, ok = QInputDialog.getText(
                self, "Rule Name", "Enter a name for the rule:",
                QLineEdit.Normal, ""
            )
            if ok and name:
                self.rule_model.name = name
            else:
                return

        if not self.rule_model.rule_id:
            import uuid
            self.rule_model.current_rule.rule_id = str(uuid.uuid4())

        success, error = self.rule_model.save_rule()
        if success:
            self.statusBar().showMessage(f"Rule '{self.rule_model.name}' saved successfully")
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

    def load_rule_list(self):
        """Reload the list of rules."""
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
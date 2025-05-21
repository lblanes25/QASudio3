from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal
import yaml


class AdvancedRuleEditor(QWidget):
    """Advanced rule editor with YAML editing and formula builder."""

    # Signal to switch to simple editor
    switch_to_simple = Signal()

    def __init__(self, rule_model):
        super().__init__()
        self.rule_model = rule_model

        # Set up UI
        self.init_ui()

        # Connect signals
        self.connect_signals()

        # Initial update from model
        self.update_from_model()

    def init_ui(self):
        """Initialize the UI components."""
        from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel,
                                       QPlainTextEdit, QPushButton, QGroupBox,
                                       QCheckBox, QSplitter, QTabWidget)
        from PySide6.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat
        from PySide6.QtCore import QRegularExpression

        # Main layout
        main_layout = QVBoxLayout(self)

        # Create formula editor group
        formula_group = QGroupBox("Excel Formula")
        formula_layout = QVBoxLayout()
        formula_group.setLayout(formula_layout)

        # Formula input with monospace font
        self.formula_edit = QPlainTextEdit()
        font = QFont("Consolas", 10)
        self.formula_edit.setFont(font)
        self.formula_edit.setMinimumHeight(80)
        formula_layout.addWidget(self.formula_edit)

        # Formula helper buttons
        helper_layout = QHBoxLayout()
        for op in ["AND", "OR", "NOT", "ISBLANK", "IF"]:
            btn = QPushButton(op)
            btn.clicked.connect(lambda checked, op=op: self.insert_formula_text(f"{op}()"))
            helper_layout.addWidget(btn)

        formula_layout.addLayout(helper_layout)

        main_layout.addWidget(formula_group)

        # YAML Editor group using tabs to switch between views
        editor_tabs = QTabWidget()

        # YAML Tab
        yaml_widget = QWidget()
        yaml_layout = QVBoxLayout(yaml_widget)

        yaml_label = QLabel("Edit rule as YAML:")
        yaml_layout.addWidget(yaml_label)

        self.yaml_edit = QPlainTextEdit()
        self.yaml_edit.setFont(font)
        self.yaml_edit.setMinimumHeight(300)
        yaml_layout.addWidget(self.yaml_edit)

        editor_tabs.addTab(yaml_widget, "YAML")

        # JSON Tab
        json_widget = QWidget()
        json_layout = QVBoxLayout(json_widget)

        json_label = QLabel("Edit rule as JSON:")
        json_layout.addWidget(json_label)

        self.json_edit = QPlainTextEdit()
        self.json_edit.setFont(font)
        self.json_edit.setMinimumHeight(300)
        json_layout.addWidget(self.json_edit)

        editor_tabs.addTab(json_widget, "JSON")

        main_layout.addWidget(editor_tabs)

        # Buttons
        button_layout = QHBoxLayout()

        self.validate_btn = QPushButton("Validate")
        self.validate_btn.clicked.connect(self.validate_rule)
        button_layout.addWidget(self.validate_btn)

        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.clicked.connect(self.apply_changes)
        button_layout.addWidget(self.apply_btn)

        # Switch to simple editor button
        switch_btn = QPushButton("Switch to Simple Editor")
        switch_btn.clicked.connect(self.switch_to_simple.emit)
        button_layout.addWidget(switch_btn)

        main_layout.addLayout(button_layout)

        # Add syntax highlighting (simplified version)
        class YamlHighlighter(QSyntaxHighlighter):
            def __init__(self, document):
                super().__init__(document)

                # Keyword format
                keyword_format = QTextCharFormat()
                keyword_format.setForeground(QColor("#0000FF"))
                keyword_format.setFontWeight(QFont.Bold)

                # String format
                string_format = QTextCharFormat()
                string_format.setForeground(QColor("#008000"))

                # Number format
                number_format = QTextCharFormat()
                number_format.setForeground(QColor("#FF0000"))

                # Comment format
                comment_format = QTextCharFormat()
                comment_format.setForeground(QColor("#808080"))
                comment_format.setFontItalic(True)

                # Rules
                self.highlighting_rules = [
                    # Keywords
                    (QRegularExpression(r'^\s*\w+:'), keyword_format),
                    # Strings
                    (QRegularExpression(r'"[^"]*"'), string_format),
                    (QRegularExpression(r"'[^']*'"), string_format),
                    # Numbers
                    (QRegularExpression(r'\b\d+\.?\d*\b'), number_format),
                    # Comments
                    (QRegularExpression(r'#.*$'), comment_format),
                ]

            def highlightBlock(self, text):
                for pattern, format in self.highlighting_rules:
                    matches = pattern.globalMatch(text)
                    while matches.hasNext():
                        match = matches.next()
                        self.setFormat(match.capturedStart(), match.capturedLength(), format)

        # Apply highlighters
        self.yaml_highlighter = YamlHighlighter(self.yaml_edit.document())
        self.json_highlighter = YamlHighlighter(self.json_edit.document())

    def connect_signals(self):
        """Connect signals for UI updates."""
        # Connect model changes to update editor
        self.rule_model.rule_changed.connect(self.update_from_model)

        # Connect formula editor to update model when edited
        self.formula_edit.textChanged.connect(self.update_formula)

    def insert_formula_text(self, text):
        """Insert text at cursor position in formula editor."""
        cursor = self.formula_edit.textCursor()
        cursor.insertText(text)
        # Move cursor inside parentheses if present
        if "(" in text and ")" in text:
            pos = cursor.position()
            cursor.setPosition(pos - 1)  # Position before closing parenthesis
            self.formula_edit.setTextCursor(cursor)

    def update_formula(self):
        """Update the formula in the model when edited."""
        formula = self.formula_edit.toPlainText().strip()
        self.rule_model.formula = formula

    def update_from_model(self):
        """Update editor content from rule model."""
        # Block signals
        self.formula_edit.blockSignals(True)
        self.yaml_edit.blockSignals(True)
        self.json_edit.blockSignals(True)

        # Update formula
        self.formula_edit.setPlainText(self.rule_model.formula)

        # Update YAML
        yaml_text = self.rule_model.to_yaml()
        self.yaml_edit.setPlainText(yaml_text)

        # Update JSON
        json_text = self.rule_model.to_json()
        self.json_edit.setPlainText(json_text)

        # Unblock signals
        self.formula_edit.blockSignals(False)
        self.yaml_edit.blockSignals(False)
        self.json_edit.blockSignals(False)

    def validate_rule(self):
        """Validate the current rule."""
        from PySide6.QtWidgets import QMessageBox

        try:
            # Get current formula
            formula = self.formula_edit.toPlainText().strip()

            # Validate formula syntax using ValidationRuleParser
            is_valid = self.rule_model.is_valid_formula(formula)

            if not is_valid:
                QMessageBox.warning(self, "Validation", "Invalid formula syntax")
                return

            # Parse YAML to validate syntax and structure
            yaml_text = self.yaml_edit.toPlainText()
            try:
                rule_dict = yaml.safe_load(yaml_text)
            except yaml.YAMLError as e:
                QMessageBox.warning(self, "Validation", f"Invalid YAML syntax: {str(e)}")
                return

            # Check required fields
            if not isinstance(rule_dict, dict) or 'rules' not in rule_dict:
                QMessageBox.warning(self, "Validation", "Invalid YAML: Missing 'rules' key")
                return

            if not rule_dict['rules'] or not isinstance(rule_dict['rules'], list):
                QMessageBox.warning(self, "Validation", "Invalid YAML: 'rules' must be a non-empty list")
                return

            rule = rule_dict['rules'][0]

            # Check required fields
            if 'name' not in rule:
                QMessageBox.warning(self, "Validation", "Missing required field: 'name'")
                return

            if 'formula' not in rule:
                QMessageBox.warning(self, "Validation", "Missing required field: 'formula'")
                return

            # Validate formula syntax (using ValidationRuleParser)
            formula = rule['formula']
            if not self.rule_model.is_valid_formula(formula):
                QMessageBox.warning(self, "Validation", "Invalid formula syntax in YAML")
                return

            # All checks passed
            QMessageBox.information(self, "Validation", "Rule configuration is valid")

        except Exception as e:
            QMessageBox.warning(self, "Validation", f"Validation error: {str(e)}")

    def apply_changes(self):
        """Apply changes from editor to rule model."""
        from PySide6.QtWidgets import QMessageBox

        try:
            # Parse YAML to get rule data
            yaml_text = self.yaml_edit.toPlainText()
            rule_dict = yaml.safe_load(yaml_text)

            if not isinstance(rule_dict, dict) or 'rules' not in rule_dict:
                QMessageBox.warning(self, "Error", "Invalid YAML: Missing 'rules' key")
                return

            if not rule_dict['rules'] or not isinstance(rule_dict['rules'], list):
                QMessageBox.warning(self, "Error", "Invalid YAML: 'rules' must be a non-empty list")
                return

            # Update model with first rule in list
            rule = rule_dict['rules'][0]
            self.rule_model.update_from_dict(rule)

            QMessageBox.information(self, "Success", "Changes applied successfully")

        except yaml.YAMLError as e:
            QMessageBox.warning(self, "Error", f"Invalid YAML syntax: {str(e)}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error applying changes: {str(e)}")

    def reset_editor(self):
        """Reset the editor to match a new empty rule."""
        self.update_from_model()
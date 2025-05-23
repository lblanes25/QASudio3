from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QTextOption
import yaml
from stylesheet import Stylesheet


class AdvancedRuleEditor(QWidget):
    """Advanced rule editor with YAML editing and formula builder."""

    # Signal to switch to simple editor
    switch_to_simple = Signal()

    def __init__(self, rule_model):
        super().__init__()
        self.rule_model = rule_model
        self._updating_from_model = False  # Add flag to prevent signal recursion

        # Set up UI
        self.init_ui()

        # Connect signals
        self.connect_signals()

        # Initial update from model
        self.update_from_model()

    def init_ui(self):
        """Initialize the UI components with minimalist design."""
        from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel,
                                       QPlainTextEdit, QPushButton,
                                       QFrame, QWidget)
        from PySide6.QtGui import QFont, QColor, QSyntaxHighlighter, QTextCharFormat, QPalette
        from PySide6.QtCore import QRegularExpression

        # Set default font using stylesheet
        self.setFont(Stylesheet.get_regular_font())

        # Monospace font for code
        mono_font = Stylesheet.get_mono_font()

        # Label font with medium weight
        label_font = Stylesheet.get_header_font()

        # Main layout with optimized spacing
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(Stylesheet.FORM_SPACING)
        main_layout.setContentsMargins(Stylesheet.STANDARD_SPACING, Stylesheet.STANDARD_SPACING,
                                       Stylesheet.STANDARD_SPACING, Stylesheet.STANDARD_SPACING)

        # -- Formula Editor Section --
        formula_label = QLabel("Excel Formula")
        formula_label.setFont(label_font)
        main_layout.addWidget(formula_label)

        # Formula input with monospace font and RTL prevention
        self.formula_edit = QPlainTextEdit()
        self.formula_edit.setFont(mono_font)
        self.formula_edit.setMinimumHeight(200)
        self.formula_edit.setMaximumHeight(300)
        self.formula_edit.setPlaceholderText("Enter Excel formula here")

        # Prevent RTL text direction issues
        self.formula_edit.setLayoutDirection(Qt.LeftToRight)
        option = QTextOption()
        option.setTextDirection(Qt.LeftToRight)
        option.setAlignment(Qt.AlignLeft)
        self.formula_edit.document().setDefaultTextOption(option)

        # Force initial cursor and block formatting
        cursor = self.formula_edit.textCursor()
        block_format = cursor.blockFormat()
        block_format.setLayoutDirection(Qt.LeftToRight)
        block_format.setAlignment(Qt.AlignLeft)
        cursor.setBlockFormat(block_format)

        char_format = cursor.charFormat()
        char_format.setLayoutDirection(Qt.LeftToRight)
        cursor.setCharFormat(char_format)

        self.formula_edit.setTextCursor(cursor)

        main_layout.addWidget(self.formula_edit)

        # Formula helper buttons - full width, stacked
        helper_label = QLabel("Insert Functions")
        helper_label.setFont(label_font)
        main_layout.addWidget(helper_label)

        helper_layout = QHBoxLayout()
        helper_layout.setSpacing(Stylesheet.STANDARD_SPACING)

        functions = ["AND", "OR", "NOT", "ISBLANK", "IF"]
        for op in functions:
            btn = QPushButton(op)
            btn.setMinimumHeight(Stylesheet.BUTTON_HEIGHT)
            btn.clicked.connect(lambda checked, op=op: self.insert_formula_text(f"{op}()"))
            helper_layout.addWidget(btn)

        main_layout.addLayout(helper_layout)

        # Validation status (hidden initially)
        self.validation_label = QLabel()
        self.validation_label.setVisible(False)
        main_layout.addWidget(self.validation_label)

        # Validate button (full width)
        validate_btn = QPushButton("Validate Formula")
        validate_btn.setMinimumHeight(Stylesheet.BUTTON_HEIGHT)
        validate_btn.clicked.connect(self.validate_rule)
        main_layout.addWidget(validate_btn)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)

        # -- YAML Section --
        yaml_label = QLabel("YAML Configuration (Optional)")
        yaml_label.setFont(label_font)
        main_layout.addWidget(yaml_label)

        # YAML editor with RTL prevention
        self.yaml_edit = QPlainTextEdit()
        self.yaml_edit.setFont(mono_font)
        self.yaml_edit.setMinimumHeight(200)
        self.yaml_edit.setMaximumHeight(300)

        # Prevent RTL text direction issues
        self.yaml_edit.setLayoutDirection(Qt.LeftToRight)
        yaml_option = QTextOption()
        yaml_option.setTextDirection(Qt.LeftToRight)
        yaml_option.setAlignment(Qt.AlignLeft)
        self.yaml_edit.document().setDefaultTextOption(yaml_option)

        # Force initial cursor and block formatting for YAML
        yaml_cursor = self.yaml_edit.textCursor()
        yaml_block_format = yaml_cursor.blockFormat()
        yaml_block_format.setLayoutDirection(Qt.LeftToRight)
        yaml_block_format.setAlignment(Qt.AlignLeft)
        yaml_cursor.setBlockFormat(yaml_block_format)

        yaml_char_format = yaml_cursor.charFormat()
        yaml_char_format.setLayoutDirection(Qt.LeftToRight)
        yaml_cursor.setCharFormat(yaml_char_format)

        self.yaml_edit.setTextCursor(yaml_cursor)

        main_layout.addWidget(self.yaml_edit)

        # Apply changes button (full width)
        self.apply_btn = QPushButton("Apply Configuration")
        self.apply_btn.setMinimumHeight(Stylesheet.BUTTON_HEIGHT)
        self.apply_btn.clicked.connect(self.apply_changes)
        main_layout.addWidget(self.apply_btn)

        # Spacer at the bottom
        main_layout.addStretch(1)

        # Create hidden JSON editor for compatibility with existing code
        self.json_edit = QPlainTextEdit()
        self.json_edit.setVisible(False)

        # Prevent RTL text direction issues in JSON editor too
        self.json_edit.setLayoutDirection(Qt.LeftToRight)
        json_option = QTextOption()
        json_option.setTextDirection(Qt.LeftToRight)
        json_option.setAlignment(Qt.AlignLeft)
        self.json_edit.document().setDefaultTextOption(json_option)

        # Store validate button reference for compatibility
        self.validate_btn = validate_btn

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

        # Store the JSON editor for compatibility with existing code, but don't display it
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
        """Update the formula in the model when edited - preserve all spaces during typing."""
        # FIX: Prevent signal recursion
        if self._updating_from_model:
            return

        # FIX: DON'T strip during live typing - preserve all spaces including trailing ones
        # Users should be able to type spaces naturally without cursor jumping
        formula = self.formula_edit.toPlainText()
        self.rule_model.formula = formula

    def update_from_model(self):
        """Update editor content from rule model."""
        self._updating_from_model = True

        try:
            # FIX: Only update formula if it's actually different
            current_formula = self.formula_edit.toPlainText()
            if current_formula != self.rule_model.formula:
                self.formula_edit.setPlainText(self.rule_model.formula)

            # FIX: Only update YAML if it's actually different
            yaml_text = self.rule_model.to_yaml()
            current_yaml = self.yaml_edit.toPlainText()
            if current_yaml != yaml_text:
                self.yaml_edit.setPlainText(yaml_text)

            # FIX: Only update JSON if it's actually different
            json_text = self.rule_model.to_json()
            current_json = self.json_edit.toPlainText()
            if current_json != json_text:
                self.json_edit.setPlainText(json_text)

        finally:
            self._updating_from_model = False

    def validate_rule(self):
        """Validate the current rule with inline feedback - strip only here for validation."""
        from PySide6.QtGui import QColor

        try:
            # Get current formula - strip only for validation, not during live editing
            formula = self.formula_edit.toPlainText().strip()

            # Show validation label
            self.validation_label.setVisible(True)

            # Validate formula syntax using ValidationRuleParser
            is_valid = self.rule_model.is_valid_formula(formula)

            if not is_valid:
                self.validation_label.setText("✗ Invalid formula syntax")
                self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")  # Error red
                self.formula_edit.setStyleSheet("border: 1px solid #E53935;")
                return

            # If YAML section has content, validate it too
            yaml_text = self.yaml_edit.toPlainText().strip()
            if yaml_text:
                try:
                    rule_dict = yaml.safe_load(yaml_text)

                    # Check required fields
                    if not isinstance(rule_dict, dict) or 'rules' not in rule_dict:
                        self.validation_label.setText("✗ Invalid YAML: Missing 'rules' key")
                        self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")
                        self.yaml_edit.setStyleSheet("border: 1px solid #E53935;")
                        return

                    if not rule_dict['rules'] or not isinstance(rule_dict['rules'], list):
                        self.validation_label.setText("✗ Invalid YAML: 'rules' must be a non-empty list")
                        self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")
                        self.yaml_edit.setStyleSheet("border: 1px solid #E53935;")
                        return

                    rule = rule_dict['rules'][0]

                    # Check required fields
                    if 'name' not in rule:
                        self.validation_label.setText("✗ Missing required field: 'name'")
                        self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")
                        self.yaml_edit.setStyleSheet("border: 1px solid #E53935;")
                        return

                    if 'formula' not in rule:
                        self.validation_label.setText("✗ Missing required field: 'formula'")
                        self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")
                        self.yaml_edit.setStyleSheet("border: 1px solid #E53935;")
                        return

                    # Validate formula syntax (using ValidationRuleParser)
                    yaml_formula = rule['formula'].strip()  # Strip here for validation
                    if not self.rule_model.is_valid_formula(yaml_formula):
                        self.validation_label.setText("✗ Invalid formula syntax in YAML")
                        self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")
                        self.yaml_edit.setStyleSheet("border: 1px solid #E53935;")
                        return

                except yaml.YAMLError as e:
                    self.validation_label.setText(f"✗ Invalid YAML syntax: {str(e)}")
                    self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")
                    self.yaml_edit.setStyleSheet("border: 1px solid #E53935;")
                    return

            # All checks passed
            self.validation_label.setText("✓ Rule configuration is valid")
            self.validation_label.setStyleSheet("color: #43A047; font-size: 16px;")  # Success green
            self.formula_edit.setStyleSheet("border: 1px solid #43A047;")
            if yaml_text:
                self.yaml_edit.setStyleSheet("border: 1px solid #43A047;")

        except Exception as e:
            self.validation_label.setText(f"✗ Validation error: {str(e)}")
            self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")
            self.formula_edit.setStyleSheet("border: 1px solid #E53935;")

    def apply_changes(self):
        """Apply changes from editor to rule model - strip only here when finalizing."""
        try:
            # First apply the formula directly - strip only when applying/saving
            formula = self.formula_edit.toPlainText().strip()
            if formula:
                self.rule_model.formula = formula

            # Then check if there's YAML to apply
            yaml_text = self.yaml_edit.toPlainText().strip()
            if yaml_text:
                try:
                    rule_dict = yaml.safe_load(yaml_text)

                    if not isinstance(rule_dict, dict) or 'rules' not in rule_dict:
                        self.validation_label.setText("✗ Invalid YAML: Missing 'rules' key")
                        self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")
                        self.validation_label.setVisible(True)
                        self.yaml_edit.setStyleSheet("border: 1px solid #E53935;")
                        return

                    if not rule_dict['rules'] or not isinstance(rule_dict['rules'], list):
                        self.validation_label.setText("✗ Invalid YAML: 'rules' must be a non-empty list")
                        self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")
                        self.validation_label.setVisible(True)
                        self.yaml_edit.setStyleSheet("border: 1px solid #E53935;")
                        return

                    # Update model with first rule in list
                    rule = rule_dict['rules'][0]
                    self.rule_model.update_from_dict(rule)

                except yaml.YAMLError as e:
                    self.validation_label.setText(f"✗ Invalid YAML syntax: {str(e)}")
                    self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")
                    self.validation_label.setVisible(True)
                    self.yaml_edit.setStyleSheet("border: 1px solid #E53935;")
                    return

            # Success feedback
            self.validation_label.setText("✓ Changes applied successfully")
            self.validation_label.setStyleSheet("color: #43A047; font-size: 16px;")  # Success green
            self.validation_label.setVisible(True)

            # Reset any error styling
            self.formula_edit.setStyleSheet("")
            self.yaml_edit.setStyleSheet("")

        except Exception as e:
            self.validation_label.setText(f"✗ Error applying changes: {str(e)}")
            self.validation_label.setStyleSheet("color: #E53935; font-size: 16px;")
            self.validation_label.setVisible(True)

    def reset_editor(self):
        """Reset the editor to match a new empty rule."""
        self.update_from_model()
from PySide6.QtWidgets import (QComboBox, QLineEdit, QWidget, QMessageBox)
from PySide6.QtCore import Signal, Qt
from PySide6.QtGui import QKeyEvent

import re

from core.rule_engine.rule_manager import ValidationRule
from stylesheet import Stylesheet


class SimpleRuleEditor(QWidget):
    """Simple form-based rule editor."""

    # Signal to switch to advanced editor
    switch_to_advanced = Signal()

    def __init__(self, rule_model):
        super().__init__()
        self.rule_model = rule_model
        self._updating_model = False
        self._updating_from_model = False
        self._updating_live_preview = False

        # Set up UI
        self.init_ui()

        # Connect signals
        self.connect_signals()

        # Initial update from model
        self.update_from_model()

    def init_ui(self):
        """Initialize the UI components with a cleaner design."""
        from PySide6.QtWidgets import (QFormLayout, QLineEdit, QTextEdit, QComboBox,
                                       QDoubleSpinBox, QPushButton,
                                       QVBoxLayout, QHBoxLayout, QRadioButton,
                                       QScrollArea, QFrame, QLabel, QSizePolicy)
        from PySide6.QtGui import QFont, QPalette, QColor
        from PySide6.QtCore import Qt

        # Set default font using stylesheet
        self.setFont(Stylesheet.get_regular_font())
        label_font = Stylesheet.get_header_font()

        # Main layout - removed extra nesting and scroll areas
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(Stylesheet.STANDARD_SPACING)
        main_layout.setContentsMargins(Stylesheet.FORM_SPACING, Stylesheet.FORM_SPACING,
                                       Stylesheet.FORM_SPACING, Stylesheet.FORM_SPACING)

        # -- Basic Rule Information --
        info_label = QLabel("Rule Information")
        info_label.setFont(label_font)
        info_label.setStyleSheet(Stylesheet.get_section_header_style())
        main_layout.addWidget(info_label)

        # Clean form layout
        form_layout = QFormLayout()
        form_layout.setSpacing(Stylesheet.STANDARD_SPACING)
        form_layout.setLabelAlignment(Qt.AlignLeft)
        form_layout.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        form_layout.setVerticalSpacing(Stylesheet.STANDARD_SPACING)

        # Rule name
        self.name_edit = QLineEdit()
        self.name_edit.setMinimumHeight(Stylesheet.INPUT_HEIGHT)
        self.name_edit.setPlaceholderText("Enter a descriptive name for this rule")
        form_layout.addRow("Name:", self.name_edit)

        # Description - create with explicit styling to prevent mirroring
        self.description_edit = QTextEdit()
        self.description_edit.setMinimumHeight(80)
        self.description_edit.setMaximumHeight(120)
        self.description_edit.setPlaceholderText("What does this rule verify?")
        self.description_edit.setReadOnly(False)
        self.description_edit.setEnabled(True)
        self.description_edit.setFocusPolicy(Qt.StrongFocus)

        # FIX: Multiple approaches to prevent text mirroring
        self.description_edit.setLayoutDirection(Qt.LeftToRight)

        # Set explicit CSS-style direction
        self.description_edit.setStyleSheet(f"""
            QTextEdit {{
                direction: ltr;
                text-align: left;
                unicode-bidi: normal;
                background-color: {Stylesheet.INPUT_BACKGROUND};
                border: 1px solid {Stylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 8px;
                font-size: {Stylesheet.REGULAR_FONT_SIZE}px;
            }}
        """)

        # Force alignment and direction at document level
        from PySide6.QtGui import QTextOption
        option = QTextOption()
        option.setTextDirection(Qt.LeftToRight)
        option.setAlignment(Qt.AlignLeft)
        self.description_edit.document().setDefaultTextOption(option)



        # Set cursor to start and ensure proper initial state
        cursor = self.description_edit.textCursor()
        cursor.movePosition(cursor.MoveOperation.Start)
        cursor.setBlockFormat(cursor.blockFormat())  # Ensure current format is editable
        block_format = cursor.blockFormat()
        block_format.setLayoutDirection(Qt.LeftToRight)
        cursor.setBlockFormat(block_format)
        self.description_edit.setTextCursor(cursor)

        form_layout.addRow("Description:", self.description_edit)

        # Category - ensure persistence
        self.category_combo = QComboBox()
        self.category_combo.setMinimumHeight(Stylesheet.INPUT_HEIGHT)
        self.category_combo.addItem("")  # Add empty option
        for category in ValidationRule.COMMON_CATEGORIES:
            self.category_combo.addItem(category)
        form_layout.addRow("Category:", self.category_combo)

        # Severity - ensure persistence
        self.severity_combo = QComboBox()
        self.severity_combo.setMinimumHeight(Stylesheet.INPUT_HEIGHT)
        self.severity_combo.addItem("")  # Add empty option
        for severity in ValidationRule.SEVERITY_LEVELS:
            self.severity_combo.addItem(severity)
        form_layout.addRow("Severity:", self.severity_combo)

        # Threshold - make fully editable with better handling
        self.threshold_edit = QLineEdit()
        self.threshold_edit.setMinimumHeight(Stylesheet.INPUT_HEIGHT)
        self.threshold_edit.setPlaceholderText("Enter percentage (e.g., 95.0)")
        self.threshold_edit.setText("100.0")
        self.threshold_edit.setToolTip("Enter a percentage between 0 and 100")
        self.threshold_edit.setReadOnly(False)
        self.threshold_edit.setEnabled(True)
        self.threshold_edit.setFocusPolicy(Qt.StrongFocus)
        form_layout.addRow("Threshold (%):", self.threshold_edit)

        # Tags - create with explicit styling to prevent mirroring
        self.tags_edit = QLineEdit()
        self.tags_edit.setMinimumHeight(Stylesheet.INPUT_HEIGHT)
        self.tags_edit.setPlaceholderText(
            "Enter tags separated by commas (e.g., Audit, Financial Reporting, Compliance)")
        self.tags_edit.setReadOnly(False)
        self.tags_edit.setEnabled(True)
        self.tags_edit.setFocusPolicy(Qt.StrongFocus)

        # FIX: Multiple approaches to prevent text mirroring
        self.tags_edit.setLayoutDirection(Qt.LeftToRight)
        self.tags_edit.setInputMethodHints(Qt.ImhNone)

        # Set explicit CSS-style direction and alignment
        self.tags_edit.setStyleSheet(f"""
            QLineEdit {{
                direction: ltr;
                text-align: left;
                unicode-bidi: normal;
                background-color: {Stylesheet.INPUT_BACKGROUND};
                border: 1px solid {Stylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px 8px;
                font-size: {Stylesheet.REGULAR_FONT_SIZE}px;
                min-height: {Stylesheet.INPUT_HEIGHT - 16}px;
                max-height: {Stylesheet.INPUT_HEIGHT}px;
            }}
        """)

        # Force alignment
        self.tags_edit.setAlignment(Qt.AlignLeft)

        form_layout.addRow("Tags:", self.tags_edit)

        main_layout.addLayout(form_layout)

        # -- Rule Conditions Section --
        conditions_label = QLabel("Rule Conditions")
        conditions_label.setFont(label_font)
        conditions_label.setStyleSheet(Stylesheet.get_section_header_style())
        main_layout.addWidget(conditions_label)

        # Logic operator selection - simplified without extra containers
        logic_layout = QHBoxLayout()
        logic_layout.setSpacing(Stylesheet.STANDARD_SPACING)

        logic_label = QLabel("Combine conditions with:")
        self.and_radio = QRadioButton("AND")
        self.and_radio.setChecked(True)
        self.or_radio = QRadioButton("OR")

        logic_layout.addWidget(logic_label)
        logic_layout.addWidget(self.and_radio)
        logic_layout.addWidget(self.or_radio)
        logic_layout.addStretch(1)

        main_layout.addLayout(logic_layout)

        # Conditions container - no extra frames
        self.conditions_layout = QVBoxLayout()
        self.conditions_layout.setSpacing(Stylesheet.FORM_SPACING)
        self.conditions_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.addLayout(self.conditions_layout)

        # Add condition button
        add_condition_btn = QPushButton("+ Add Condition")
        add_condition_btn.setMinimumHeight(Stylesheet.BUTTON_HEIGHT)
        add_condition_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {Stylesheet.INPUT_BACKGROUND};
                color: {Stylesheet.PRIMARY_COLOR};
                border: 1px dashed {Stylesheet.PRIMARY_COLOR};
                border-radius: 4px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {Stylesheet.PRIMARY_COLOR};
                color: white;
                border: 1px solid {Stylesheet.PRIMARY_COLOR};
            }}
        """)
        add_condition_btn.clicked.connect(self.add_condition_row)
        main_layout.addWidget(add_condition_btn)

        # Add initial condition
        self.add_condition_row()

        # -- Formula Preview Section --
        formula_label = QLabel("Formula Preview")
        formula_label.setFont(label_font)
        main_layout.addWidget(formula_label)

        self.formula_preview = QLineEdit()
        self.formula_preview.setReadOnly(True)
        self.formula_preview.setFont(Stylesheet.get_mono_font())
        self.formula_preview.setMinimumHeight(Stylesheet.HEADER_HEIGHT)
        self.formula_preview.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.formula_preview.setStyleSheet(f"""
            QLineEdit {{
                background-color: {Stylesheet.INPUT_BACKGROUND};
                border: 1px solid {Stylesheet.BORDER_COLOR};
                color: {Stylesheet.TEXT_COLOR};
            }}
        """)
        main_layout.addWidget(self.formula_preview)

        # Validation status (hidden initially)
        self.validation_label = QLabel()
        self.validation_label.setVisible(False)
        main_layout.addWidget(self.validation_label)

        # Validate button
        validate_btn = QPushButton("Validate Formula")
        validate_btn.setMinimumHeight(Stylesheet.BUTTON_HEIGHT)
        validate_btn.clicked.connect(self.validate_formula)
        main_layout.addWidget(validate_btn)

        # Add space at the bottom
        main_layout.addStretch()

    def keyPressEvent(self, event):
        """Handle key press events to enable proper tab navigation."""
        if event.key() == Qt.Key_Tab:
            # Check if we're in a text widget that normally consumes Tab
            current_widget = self.focusWidget()

            if isinstance(current_widget, QTextEdit):
                # For QTextEdit (description field), move to next widget instead of inserting tab
                self.focusNextChild()
                event.accept()
                return
            elif isinstance(current_widget, QLineEdit):
                # For QLineEdit widgets, check if Ctrl is held down
                if event.modifiers() & Qt.ControlModifier:
                    # Ctrl+Tab inserts a tab character (if you want this behavior)
                    super().keyPressEvent(event)
                else:
                    # Regular Tab moves to next field
                    self.focusNextChild()
                    event.accept()
                    return
        elif event.key() == Qt.Key_Backtab:  # Shift+Tab
            # Move to previous field
            current_widget = self.focusWidget()
            if isinstance(current_widget, (QTextEdit, QLineEdit)):
                self.focusPreviousChild()
                event.accept()
                return

        # For all other keys, use default behavior
        super().keyPressEvent(event)

    def add_condition_row(self):
        """Add a new condition row with improved design."""
        from PySide6.QtWidgets import (QHBoxLayout, QComboBox, QLineEdit,
                                       QPushButton, QFrame, QWidget)
        from PySide6.QtCore import Qt

        # Create condition container with minimal styling
        condition_widget = QWidget()
        condition_widget.setStyleSheet(f"""
            QWidget {{
                background-color: {Stylesheet.BACKGROUND_COLOR};
                border: none;
                border-bottom: 1px solid {Stylesheet.BORDER_COLOR};
                padding: {Stylesheet.STANDARD_SPACING}px 0px;
            }}
        """)

        # Horizontal layout for inline design
        condition_layout = QHBoxLayout(condition_widget)
        condition_layout.setSpacing(Stylesheet.STANDARD_SPACING)
        condition_layout.setContentsMargins(0, Stylesheet.STANDARD_SPACING, 0, Stylesheet.STANDARD_SPACING)

        # Column selector with placeholder
        column_combo = QComboBox()
        column_combo.setEditable(True)
        column_combo.setMinimumHeight(Stylesheet.INPUT_HEIGHT)
        column_combo.setMinimumWidth(150)
        column_combo.setPlaceholderText("Select column")
        column_combo.lineEdit().setPlaceholderText("Select column")
        column_combo.setCurrentText("")
        column_combo.setToolTip("Choose a data column to check. Load data first to see available columns.")
        condition_layout.addWidget(column_combo)

        # Operator selector with placeholder
        operator_combo = QComboBox()
        operator_combo.addItem("Choose operator")  # Placeholder item
        operators = ["=", "<>", ">", "<", ">=", "<=", "CONTAINS", "ISBLANK", "ISNOTBLANK"]
        operator_combo.addItems(operators)
        operator_combo.setMinimumHeight(Stylesheet.INPUT_HEIGHT)
        operator_combo.setMinimumWidth(120)
        operator_combo.setCurrentIndex(0)
        operator_combo.setToolTip("Choose how to compare the column value")
        condition_layout.addWidget(operator_combo)

        # Value input with contextual placeholder
        value_edit = QLineEdit()
        value_edit.setPlaceholderText("Enter expected value")
        value_edit.setMinimumHeight(Stylesheet.INPUT_HEIGHT)
        value_edit.setMinimumWidth(120)
        value_edit.setToolTip("Enter the value to compare against")
        condition_layout.addWidget(value_edit)

        # Spacer
        condition_layout.addStretch(1)

        # Remove button
        remove_btn = QPushButton("×")
        remove_btn.setMinimumHeight(Stylesheet.INPUT_HEIGHT)
        remove_btn.setMaximumWidth(Stylesheet.INPUT_HEIGHT)
        remove_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {Stylesheet.ERROR_COLOR};
                border: 1px solid {Stylesheet.BORDER_COLOR};
                border-radius: {Stylesheet.INPUT_HEIGHT // 2}px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {Stylesheet.ERROR_COLOR};
                color: white;
                border: 1px solid {Stylesheet.ERROR_COLOR};
            }}
        """)
        remove_btn.clicked.connect(lambda: self.remove_condition_row(condition_widget))
        condition_layout.addWidget(remove_btn)

        # Add widget to layout
        self.conditions_layout.addWidget(condition_widget)

        # Connect signals
        column_combo.currentTextChanged.connect(self.update_formula)
        operator_combo.currentTextChanged.connect(lambda: self._update_value_visibility(operator_combo, value_edit))
        operator_combo.currentTextChanged.connect(self.update_formula)
        value_edit.textChanged.connect(self.update_formula)

        # Set initial visibility
        self._update_value_visibility(operator_combo, value_edit)

        # Update formula preview
        self.update_formula()

    def _update_value_visibility(self, operator_combo, value_edit):
        """Show/hide value field based on operator selection."""
        operator = operator_combo.currentText().strip()
        needs_value = operator not in ["ISBLANK", "ISNOTBLANK", "Choose operator"]

        if needs_value and operator != "Choose operator":
            value_edit.setVisible(True)
            # Update placeholder based on operator
            if operator == "=":
                value_edit.setPlaceholderText("Exact value to match")
            elif operator == "<>":
                value_edit.setPlaceholderText("Value to exclude")
            elif operator in [">", ">="]:
                value_edit.setPlaceholderText("Minimum number")
            elif operator in ["<", "<="]:
                value_edit.setPlaceholderText("Maximum number")
            elif operator == "CONTAINS":
                value_edit.setPlaceholderText("Text to find")
            else:
                value_edit.setPlaceholderText("Enter expected value")
        else:
            value_edit.setVisible(False)
            value_edit.clear()

    def set_available_columns(self, columns):
        """Set available columns for dropdown selectors."""
        for i in range(self.conditions_layout.count()):
            condition_widget = self.conditions_layout.itemAt(i).widget()
            if condition_widget and hasattr(condition_widget, 'layout'):
                condition_layout = condition_widget.layout()

                # Find the column combo box (first combo box)
                for j in range(condition_layout.count()):
                    widget = condition_layout.itemAt(j).widget()
                    if isinstance(widget, QComboBox) and widget.isEditable():
                        # Save current text
                        current_text = widget.currentText()

                        # Block signals
                        widget.blockSignals(True)

                        # Clear and add new items
                        widget.clear()
                        if columns:
                            widget.addItems(columns)
                            widget.setPlaceholderText("Select column")
                        else:
                            widget.setPlaceholderText("Load data to see columns")

                        # Restore selection if it exists
                        index = widget.findText(current_text)
                        if index >= 0:
                            widget.setCurrentIndex(index)
                        else:
                            widget.setCurrentText("")

                        # Re-enable signals
                        widget.blockSignals(False)
                        break

    def remove_condition_row(self, condition_widget):
        """Remove a condition row."""
        if self.conditions_layout.count() > 1:
            condition_widget.deleteLater()
            self.update_formula()
        else:
            # Clear the last condition instead of removing
            if hasattr(condition_widget, 'layout'):
                layout = condition_widget.layout()
                for i in range(layout.count()):
                    widget = layout.itemAt(i).widget()
                    if isinstance(widget, QComboBox) and widget.isEditable():
                        widget.setCurrentText("")
                    elif isinstance(widget, QLineEdit):
                        widget.clear()
            self.update_formula()

    def update_formula(self):
        """Update the formula preview based on condition inputs."""
        if self._updating_from_model:
            return

        from PySide6.QtWidgets import QComboBox, QLineEdit

        # Collect conditions
        conditions = []
        for i in range(self.conditions_layout.count()):
            condition_widget = self.conditions_layout.itemAt(i).widget()
            if condition_widget is None or not hasattr(condition_widget, 'layout'):
                continue

            condition_layout = condition_widget.layout()

            # Extract widgets
            column_combo = None
            operator_combo = None
            value_edit = None

            combo_count = 0
            for j in range(condition_layout.count()):
                widget = condition_layout.itemAt(j).widget()
                if isinstance(widget, QComboBox):
                    if combo_count == 0:  # First combo is column
                        column_combo = widget
                    elif combo_count == 1:  # Second combo is operator
                        operator_combo = widget
                    combo_count += 1
                elif isinstance(widget, QLineEdit):
                    value_edit = widget

            if not column_combo or not operator_combo:
                continue

            column = column_combo.currentText().strip()
            operator = operator_combo.currentText().strip()
            value = value_edit.text().strip() if value_edit and value_edit.isVisible() else ""

            # Skip invalid conditions
            if not column or operator == "Choose operator":
                continue

            if not value and operator not in ["ISBLANK", "ISNOTBLANK"]:
                continue

            # Format condition based on operator
            if operator == "ISBLANK":
                condition = f"ISBLANK([{column}])"
            elif operator == "ISNOTBLANK":
                condition = f"NOT(ISBLANK([{column}]))"
            elif operator == "CONTAINS":
                condition = f'ISNUMBER(SEARCH("{value}", [{column}]))'
            else:
                # Check if value needs quotes
                try:
                    float(value)
                    condition = f"[{column}]{operator}{value}"
                except ValueError:
                    condition = f'[{column}]{operator}"{value}"'

            conditions.append(condition)

        # Combine conditions
        if conditions:
            logic_op = "AND" if self.and_radio.isChecked() else "OR"
            if len(conditions) == 1:
                formula = f"={conditions[0]}"
            else:
                formula = f"={logic_op}({', '.join(conditions)})"
        else:
            formula = ""

        # Update preview
        if hasattr(self, 'formula_preview'):
            self.formula_preview.setText(formula)

            # Reset validation styling
            if hasattr(self, 'validation_label'):
                self.validation_label.setVisible(False)
                self.formula_preview.setStyleSheet(f"""
                    QLineEdit {{
                        background-color: {Stylesheet.INPUT_BACKGROUND};
                        border: 1px solid {Stylesheet.BORDER_COLOR};
                        color: {Stylesheet.TEXT_COLOR};
                    }}
                """)

        # Update model
        if formula and not self._updating_model:
            self.rule_model.formula = formula

    def validate_formula(self):
        """Validate the current formula."""
        formula = self.formula_preview.text()
        if not formula:
            self.validation_label.setText("Formula is empty. Add at least one condition.")
            self.validation_label.setStyleSheet("color: #FFC107; font-size: 16px;")
            self.validation_label.setVisible(True)
            return

        is_valid = self.rule_model.is_valid_formula(formula)
        self.validation_label.setVisible(True)

        if is_valid:
            self.validation_label.setText("✓ Formula syntax is valid")
            self.validation_label.setStyleSheet("color: #28A745; font-size: 16px;")
            self.formula_preview.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {Stylesheet.INPUT_BACKGROUND};
                    border: 2px solid {Stylesheet.SUCCESS_COLOR};
                    color: {Stylesheet.TEXT_COLOR};
                }}
            """)
        else:
            self.validation_label.setText("✗ Invalid formula syntax")
            self.validation_label.setStyleSheet("color: #DC3545; font-size: 16px;")
            self.formula_preview.setStyleSheet(f"""
                QLineEdit {{
                    background-color: {Stylesheet.INPUT_BACKGROUND};
                    border: 2px solid {Stylesheet.ERROR_COLOR};
                    color: {Stylesheet.TEXT_COLOR};
                }}
            """)

    def connect_signals(self):
        """Connect signals for UI updates - with improved handling."""
        # Connect form fields - use different signals to avoid recursion
        self.name_edit.textChanged.connect(self.update_model)

        # For description, use textChanged signal but check for recursion
        self.description_edit.textChanged.connect(self.on_description_changed)

        # For dropdowns, use currentIndexChanged instead of currentTextChanged
        self.category_combo.currentIndexChanged.connect(self.on_category_changed)
        self.severity_combo.currentIndexChanged.connect(self.on_severity_changed)

        self.threshold_edit.textChanged.connect(self.on_threshold_changed)

        # For tags - use textChanged for real-time updates, editingFinished for cleanup
        self.tags_edit.textChanged.connect(self.on_tags_changed)
        self.tags_edit.editingFinished.connect(self.on_tags_editing_finished)

        # Connect radio buttons
        self.and_radio.toggled.connect(self.update_formula)
        self.or_radio.toggled.connect(self.update_formula)

        # Connect rule model changes
        self.rule_model.rule_changed.connect(self.update_from_model)

    def on_description_changed(self):
        """Handle description changes."""
        if self._updating_from_model:
            return
        self.rule_model.description = self.description_edit.toPlainText()

    def on_category_changed(self, index):
        """Handle category dropdown changes."""
        if self._updating_from_model:
            return

        category = self.category_combo.currentText()
        if category and category != "":
            self.rule_model.category = category

    def on_severity_changed(self, index):
        """Handle severity dropdown changes."""
        if self._updating_from_model:
            return

        severity = self.severity_combo.currentText()
        if severity and severity != "":
            self.rule_model.severity = severity

    def on_tags_changed(self):
        """Handle tags field changes - allow commas and spaces while typing."""
        if self._updating_from_model:
            return

        tag_text = self.tags_edit.text()

        if tag_text:
            # Split by comma and clean up each tag
            tags = [tag.strip() for tag in tag_text.split(',')]
            # Only filter out completely empty tags (after stripping whitespace)
            filtered_tags = [tag for tag in tags if tag]

            # Store the tags in the model, but DON'T update the field
            # This allows the user to continue typing
            self.rule_model.tags = filtered_tags
        else:
            self.rule_model.tags = []

    def on_tags_editing_finished(self):
        """Called when user finishes editing tags (loses focus or presses Enter)."""
        if self._updating_from_model:
            return

        # Now we clean up the display
        tag_text = self.tags_edit.text()
        if tag_text:
            tags = [tag.strip() for tag in tag_text.split(',')]
            filtered_tags = [tag for tag in tags if tag]

            # Update both model and display
            self.rule_model.tags = filtered_tags
            clean_text = ', '.join(filtered_tags)

            # Only update the field if it's actually different
            if self.tags_edit.text() != clean_text:
                self._updating_from_model = True
                self.tags_edit.setText(clean_text)
                self._updating_from_model = False

    def update_model(self):
        """Update the rule model from form values."""
        if self._updating_from_model:
            return

        self._updating_model = True
        try:
            # Only update name from this method now
            self.rule_model.name = self.name_edit.text()
        finally:
            self._updating_model = False

    def on_threshold_changed(self):
        """Handle threshold changes with better input handling."""
        if self._updating_from_model:
            return

        text = self.threshold_edit.text().replace('%', '').strip()
        if text:
            try:
                value = float(text)
                value = max(0.0, min(100.0, value))  # Clamp between 0-100
                # Store as percentage value (0-100), not decimal (0-1)
                self.rule_model.threshold = value / 100.0  # Convert to decimal for storage
            except ValueError:
                pass  # Ignore invalid input

    def update_from_model(self):
        """Update form values from rule model."""
        self._updating_from_model = True

        try:
            # Update form fields without blocking signals - just set flag
            self.name_edit.setText(self.rule_model.name)

            # FIX: Only update description if it's actually different
            current_description = self.description_edit.toPlainText()
            if current_description != self.rule_model.description:
                self.description_edit.setPlainText(self.rule_model.description)

            # Handle category - find exact match
            category_index = self.category_combo.findText(self.rule_model.category)
            if category_index >= 0:
                self.category_combo.setCurrentIndex(category_index)
            else:
                self.category_combo.setCurrentIndex(0)  # Set to empty if not found

            # Handle severity - find exact match
            severity_index = self.severity_combo.findText(self.rule_model.severity)
            if severity_index >= 0:
                self.severity_combo.setCurrentIndex(severity_index)
            else:
                self.severity_combo.setCurrentIndex(0)  # Set to empty if not found

            # Update threshold - only if the displayed value is actually different
            percentage_value = self.rule_model.threshold * 100.0
            current_text = self.threshold_edit.text().replace('%', '').strip()

            # Only update if the values are actually different (avoid circular updates)
            try:
                current_value = float(current_text) if current_text else 0.0
                if abs(current_value - percentage_value) > 0.01:  # Small tolerance for float comparison
                    self.threshold_edit.setText(f"{percentage_value:.1f}")
            except ValueError:
                # If current text is invalid, update it
                self.threshold_edit.setText(f"{percentage_value:.1f}")

            # Update tags - only if not currently being edited
            if not self.tags_edit.hasFocus():
                expected_tags_text = ', '.join(self.rule_model.tags)
                current_tags_text = self.tags_edit.text()
                if current_tags_text != expected_tags_text:
                    self.tags_edit.setText(expected_tags_text)

            # Update formula preview
            if hasattr(self, 'formula_preview'):
                self.formula_preview.setText(self.rule_model.formula)

        finally:
            self._updating_from_model = False

    def reset_form(self):
        """Reset the form to default values."""
        # Clear conditions
        for i in reversed(range(self.conditions_layout.count())):
            widget = self.conditions_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Add a single empty condition
        self.add_condition_row()

        # Reset will happen through model update
        self.update_from_model()
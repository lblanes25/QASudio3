from PySide6.QtWidgets import (QComboBox, QLineEdit, QWidget, QMessageBox)
from PySide6.QtCore import Signal

import re

from core.rule_engine.rule_manager import ValidationRule


class SimpleRuleEditor(QWidget):
    """Simple form-based rule editor."""

    # Signal to switch to advanced editor
    switch_to_advanced = Signal()

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
        from PySide6.QtWidgets import (QFormLayout, QLineEdit, QTextEdit, QComboBox,
                                       QDoubleSpinBox, QPushButton, QGroupBox,
                                       QVBoxLayout, QHBoxLayout, QCheckBox,
                                       QScrollArea, QFrame)

        # Main layout
        main_layout = QVBoxLayout(self)

        # Create scrollable area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        main_layout.addWidget(scroll)

        # Container widget for scroll area
        scroll_content = QWidget()
        scroll.setWidget(scroll_content)
        form_layout = QVBoxLayout(scroll_content)

        # Create form layout for rule properties
        rule_group = QGroupBox("Rule Properties")
        properties_layout = QFormLayout()
        rule_group.setLayout(properties_layout)
        form_layout.addWidget(rule_group)

        # Rule name
        self.name_edit = QLineEdit()
        properties_layout.addRow("Rule Name:", self.name_edit)

        # Rule description
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        properties_layout.addRow("Description:", self.description_edit)

        # Category
        self.category_combo = QComboBox()
        # Use ValidationRule's common categories
        for category in ValidationRule.COMMON_CATEGORIES:
            self.category_combo.addItem(category)
        properties_layout.addRow("Category:", self.category_combo)

        # Severity
        self.severity_combo = QComboBox()
        # Use ValidationRule's severity levels
        for severity in ValidationRule.SEVERITY_LEVELS:
            self.severity_combo.addItem(severity)
        properties_layout.addRow("Severity:", self.severity_combo)

        # Threshold
        self.threshold_spin = QDoubleSpinBox()
        self.threshold_spin.setRange(0.0, 1.0)
        self.threshold_spin.setSingleStep(0.05)
        self.threshold_spin.setValue(1.0)
        properties_layout.addRow("Threshold:", self.threshold_spin)

        # Tags
        self.tags_edit = QLineEdit()
        properties_layout.addRow("Tags (comma separated):", self.tags_edit)

        # Formula preview - CREATE THIS BEFORE ADDING CONDITIONS
        formula_group = QGroupBox("Formula Preview")
        formula_layout = QVBoxLayout()
        formula_group.setLayout(formula_layout)

        self.formula_preview = QLineEdit()
        self.formula_preview.setReadOnly(True)
        formula_layout.addWidget(self.formula_preview)

        # Validate button
        validate_btn = QPushButton("Validate Formula")
        validate_btn.clicked.connect(self.validate_formula)
        formula_layout.addWidget(validate_btn)

        # Add button to switch to advanced editor
        advanced_btn = QPushButton("Switch to Advanced Editor")
        advanced_btn.clicked.connect(self.switch_to_advanced.emit)
        formula_layout.addWidget(advanced_btn)

        # Rule definition group
        rule_def_group = QGroupBox("Rule Definition")
        rule_def_layout = QVBoxLayout()
        rule_def_group.setLayout(rule_def_layout)
        form_layout.addWidget(rule_def_group)

        # Conditions container
        self.conditions_layout = QVBoxLayout()
        rule_def_layout.addLayout(self.conditions_layout)

        # Initial condition - NOW PLACED AFTER formula_preview is created
        self.add_condition_row()

        # Logic type (AND/OR)
        logic_layout = QHBoxLayout()
        self.and_radio = QCheckBox("AND (All conditions must be true)")
        self.and_radio.setChecked(True)
        self.or_radio = QCheckBox("OR (Any condition can be true)")
        logic_layout.addWidget(self.and_radio)
        logic_layout.addWidget(self.or_radio)
        rule_def_layout.addLayout(logic_layout)

        # Connect AND/OR radios
        self.and_radio.stateChanged.connect(lambda state: self.or_radio.setChecked(not state))
        self.or_radio.stateChanged.connect(lambda state: self.and_radio.setChecked(not state))

        # Add condition button
        add_condition_btn = QPushButton("Add Condition")
        add_condition_btn.clicked.connect(self.add_condition_row)
        rule_def_layout.addWidget(add_condition_btn)

        form_layout.addWidget(formula_group)

        # Add space at the bottom
        form_layout.addStretch()

    def add_condition_row(self):
        """Add a new condition row to the form."""
        from PySide6.QtWidgets import (QHBoxLayout, QComboBox, QLineEdit,
                                       QPushButton, QFrame)

        # Create a frame to contain the condition
        condition_frame = QFrame()
        condition_frame.setFrameShape(QFrame.StyledPanel)
        condition_frame.setFrameShadow(QFrame.Raised)
        condition_layout = QHBoxLayout(condition_frame)

        # Column selector
        column_combo = QComboBox()
        column_combo.setEditable(True)
        column_combo.setMinimumWidth(150)
        condition_layout.addWidget(column_combo)

        # Operator selector
        operator_combo = QComboBox()
        operators = ["=", "<>", ">", "<", ">=", "<=", "CONTAINS", "ISBLANK", "ISNOTBLANK"]
        operator_combo.addItems(operators)
        condition_layout.addWidget(operator_combo)

        # Value input
        value_edit = QLineEdit()
        value_edit.setPlaceholderText("Value")
        value_edit.setMinimumWidth(150)
        condition_layout.addWidget(value_edit)

        # Remove button
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(lambda: self.remove_condition_row(condition_frame))
        condition_layout.addWidget(remove_btn)

        # Add the frame to the conditions layout
        self.conditions_layout.addWidget(condition_frame)

        # Connect signals to update formula
        column_combo.currentTextChanged.connect(self.update_formula)
        operator_combo.currentTextChanged.connect(self.update_formula)
        value_edit.textChanged.connect(self.update_formula)

        # Update formula preview
        self.update_formula()

    def set_available_columns(self, columns):
        """Set available columns for dropdown selectors."""
        # Update all column selectors with the available columns
        for i in range(self.conditions_layout.count()):
            condition_frame = self.conditions_layout.itemAt(i).widget()
            if condition_frame:
                condition_layout = condition_frame.layout()

                # Find the column combo box (first combo box in the layout)
                for j in range(condition_layout.count()):
                    widget = condition_layout.itemAt(j).widget()
                    if isinstance(widget, QComboBox):
                        # Save current text
                        current_text = widget.currentText()

                        # Block signals to prevent formula updates during rebuild
                        widget.blockSignals(True)

                        # Clear and add new items
                        widget.clear()
                        widget.addItems(columns)

                        # If previous value exists in new list, select it
                        index = widget.findText(current_text)
                        if index >= 0:
                            widget.setCurrentIndex(index)

                        # Re-enable signals
                        widget.blockSignals(False)

                        # Only update the first combo box (column selector)
                        break

    def remove_condition_row(self, condition_frame):
        """Remove a condition row from the form."""
        # Only remove if there's more than one condition
        if self.conditions_layout.count() > 1:
            condition_frame.deleteLater()
            self.update_formula()

    def update_formula(self):
        """Update the formula preview based on condition inputs."""
        from PySide6.QtWidgets import QHBoxLayout, QComboBox, QLineEdit

        # Collect conditions
        conditions = []
        for i in range(self.conditions_layout.count()):
            condition_frame = self.conditions_layout.itemAt(i).widget()
            if condition_frame is None:
                continue

            condition_layout = condition_frame.layout()

            # Extract widgets
            column_combo = None
            operator_combo = None
            value_edit = None

            for j in range(condition_layout.count()):
                widget = condition_layout.itemAt(j).widget()
                if isinstance(widget, QComboBox):
                    if column_combo is None:
                        column_combo = widget
                    else:
                        operator_combo = widget
                elif isinstance(widget, QLineEdit):
                    value_edit = widget

            if column_combo and operator_combo and value_edit:
                column = column_combo.currentText()
                operator = operator_combo.currentText()
                value = value_edit.text()

                # Skip if column is empty
                if not column:
                    continue

                # Skip if value is empty and operator requires a value
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
                    # Check if value needs quotes (non-numeric)
                    try:
                        float(value)  # Test if value is numeric
                        condition = f"[{column}]{operator}{value}"
                    except ValueError:
                        condition = f'[{column}]{operator}"{value}"'

                conditions.append(condition)

        # Combine conditions with AND or OR
        if conditions:
            logic_op = "AND" if self.and_radio.isChecked() else "OR"

            if len(conditions) == 1:
                formula = f"={conditions[0]}"
            else:
                formula = f"={logic_op}({', '.join(conditions)})"
        else:
            formula = ""

        # Update formula preview
        self.formula_preview.setText(formula)

        # Update model
        if formula:
            self.rule_model.formula = formula

    def validate_formula(self):
        """Validate the current formula."""
        formula = self.formula_preview.text()
        if not formula:
            QMessageBox.warning(self, "Validation", "Formula is empty")
            return

        # Use ValidationRuleParser to validate formula
        is_valid = self.rule_model.is_valid_formula(formula)

        if is_valid:
            QMessageBox.information(self, "Validation", "Formula syntax is valid")
        else:
            QMessageBox.warning(self, "Validation", "Invalid formula syntax")

    def connect_signals(self):
        """Connect signals for UI updates."""
        # Connect form fields to update rule model
        self.name_edit.textChanged.connect(self.update_model)
        self.description_edit.textChanged.connect(self.update_model)
        self.category_combo.currentTextChanged.connect(self.update_model)
        self.severity_combo.currentTextChanged.connect(self.update_model)
        self.threshold_spin.valueChanged.connect(self.update_model)
        self.tags_edit.textChanged.connect(self.update_model)

        # Connect rule model changes to update form
        self.rule_model.rule_changed.connect(self.update_from_model)

    def update_model(self):
        """Update the rule model from form values."""
        # Update fields that don't come from condition rows
        self.rule_model.name = self.name_edit.text()
        self.rule_model.description = self.description_edit.toPlainText()
        self.rule_model.category = self.category_combo.currentText()
        self.rule_model.severity = self.severity_combo.currentText()
        self.rule_model.threshold = self.threshold_spin.value()

        # Parse tags from comma-separated string
        tag_text = self.tags_edit.text()
        if tag_text:
            self.rule_model.tags = [tag.strip() for tag in tag_text.split(',')]
        else:
            self.rule_model.tags = []

        # Formula is updated by update_formula method

    def update_from_model(self):
        """Update form values from rule model."""
        # Block signals to prevent recursion
        self.name_edit.blockSignals(True)
        self.description_edit.blockSignals(True)
        self.category_combo.blockSignals(True)
        self.severity_combo.blockSignals(True)
        self.threshold_spin.blockSignals(True)
        self.tags_edit.blockSignals(True)

        # Update form fields
        self.name_edit.setText(self.rule_model.name)
        self.description_edit.setPlainText(self.rule_model.description)

        # Find and select category
        category_index = self.category_combo.findText(self.rule_model.category)
        if category_index >= 0:
            self.category_combo.setCurrentIndex(category_index)

        # Find and select severity
        severity_index = self.severity_combo.findText(self.rule_model.severity)
        if severity_index >= 0:
            self.severity_combo.setCurrentIndex(severity_index)

        self.threshold_spin.setValue(self.rule_model.threshold)

        # Format tags as comma-separated string
        self.tags_edit.setText(', '.join(self.rule_model.tags))

        # Update formula preview
        self.formula_preview.setText(self.rule_model.formula)

        # Re-enable signals
        self.name_edit.blockSignals(False)
        self.description_edit.blockSignals(False)
        self.category_combo.blockSignals(False)
        self.severity_combo.blockSignals(False)
        self.threshold_spin.blockSignals(False)
        self.tags_edit.blockSignals(False)

    def reset_form(self):
        """Reset the form to default values."""
        # Clear conditions
        for i in reversed(range(self.conditions_layout.count())):
            widget = self.conditions_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Add a single empty condition
        self.add_condition_row()

        # Reset other fields (will happen through model update)
        self.update_from_model()

    def _parse_formula_to_conditions(self, formula):
        """Parse a formula to populate condition fields (reverse of update_formula)."""
        # This is a complex task that would require a proper parser.
        # For now, we'll implement a simplified version that handles
        # common cases but won't work for all formulas.

        # Clear existing conditions
        for i in reversed(range(self.conditions_layout.count())):
            widget = self.conditions_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        if not formula:
            # Add a single empty condition
            self.add_condition_row()
            return

        # Strip leading "=" if present
        if formula.startswith("="):
            formula = formula[1:]

        # Determine if it's an AND/OR formula
        if formula.startswith("AND(") and formula.endswith(")"):
            # AND formula
            self.and_radio.setChecked(True)
            conditions_text = formula[4:-1]  # Strip "AND(" and ")"
        elif formula.startswith("OR(") and formula.endswith(")"):
            # OR formula
            self.or_radio.setChecked(True)
            conditions_text = formula[3:-1]  # Strip "OR(" and ")"
        else:
            # Single condition
            self.and_radio.setChecked(True)
            conditions_text = formula

        # Split conditions by comma, but be careful not to split inside quotes or functions
        # This is a simplified approach and won't handle all cases
        conditions = []
        current_condition = ""
        quote_char = None
        paren_level = 0

        for c in conditions_text:
            if c == '"' or c == "'":
                if quote_char is None:
                    quote_char = c
                elif quote_char == c:
                    quote_char = None
                current_condition += c
            elif c == '(':
                paren_level += 1
                current_condition += c
            elif c == ')':
                paren_level -= 1
                current_condition += c
            elif c == ',' and quote_char is None and paren_level == 0:
                # End of condition
                conditions.append(current_condition)
                current_condition = ""
            else:
                current_condition += c

        # Add the last condition if not empty
        if current_condition:
            conditions.append(current_condition)

        # Process each condition
        for condition in conditions:
            self._add_condition_from_text(condition.strip())

        # If no conditions were added, add an empty one
        if self.conditions_layout.count() == 0:
            self.add_condition_row()

    def _add_condition_from_text(self, condition_text):
        """Add a condition row and populate it from text."""
        # Handle simple comparison operators
        for op in [">=", "<=", "<>", ">", "<", "="]:
            if op in condition_text:
                parts = condition_text.split(op, 1)
                if len(parts) == 2:
                    # Extract column
                    column_match = re.search(r'\[([^\]]+)\]', parts[0])
                    if column_match:
                        column_name = column_match.group(1)

                        # Extract value
                        value = parts[1].strip()
                        # Remove quotes if present
                        if value.startswith('"') and value.endswith('"'):
                            value = value[1:-1]
                        elif value.startswith("'") and value.endswith("'"):
                            value = value[1:-1]

                        # Add condition row
                        self.add_condition_row()

                        # Get the added row
                        row_idx = self.conditions_layout.count() - 1
                        condition_frame = self.conditions_layout.itemAt(row_idx).widget()
                        condition_layout = condition_frame.layout()

                        # Find and set widgets
                        column_combo = None
                        operator_combo = None
                        value_edit = None

                        for j in range(condition_layout.count()):
                            widget = condition_layout.itemAt(j).widget()
                            if isinstance(widget, QComboBox):
                                if column_combo is None:
                                    column_combo = widget
                                else:
                                    operator_combo = widget
                            elif isinstance(widget, QLineEdit):
                                value_edit = widget

                        # Update widgets
                        if column_combo:
                            column_combo.setCurrentText(column_name)
                        if operator_combo:
                            operator_combo.setCurrentText(op)
                        if value_edit:
                            value_edit.setText(value)

                        return

        # Handle ISBLANK
        isblank_match = re.search(r'ISBLANK\(\[([^\]]+)\]\)', condition_text)
        if isblank_match:
            column_name = isblank_match.group(1)

            # Add condition row
            self.add_condition_row()

            # Get the added row
            row_idx = self.conditions_layout.count() - 1
            condition_frame = self.conditions_layout.itemAt(row_idx).widget()
            condition_layout = condition_frame.layout()

            # Find and set widgets
            column_combo = None
            operator_combo = None

            for j in range(condition_layout.count()):
                widget = condition_layout.itemAt(j).widget()
                if isinstance(widget, QComboBox):
                    if column_combo is None:
                        column_combo = widget
                    else:
                        operator_combo = widget

            # Update widgets
            if column_combo:
                column_combo.setCurrentText(column_name)
            if operator_combo:
                operator_combo.setCurrentText("ISBLANK")

            return

        # Handle NOT(ISBLANK(...))
        not_isblank_match = re.search(r'NOT\(ISBLANK\(\[([^\]]+)\]\)\)', condition_text)
        if not_isblank_match:
            column_name = not_isblank_match.group(1)

            # Add condition row
            self.add_condition_row()

            # Get the added row
            row_idx = self.conditions_layout.count() - 1
            condition_frame = self.conditions_layout.itemAt(row_idx).widget()
            condition_layout = condition_frame.layout()

            # Find and set widgets
            column_combo = None
            operator_combo = None

            for j in range(condition_layout.count()):
                widget = condition_layout.itemAt(j).widget()
                if isinstance(widget, QComboBox):
                    if column_combo is None:
                        column_combo = widget
                    else:
                        operator_combo = widget

            # Update widgets
            if column_combo:
                column_combo.setCurrentText(column_name)
            if operator_combo:
                operator_combo.setCurrentText("ISNOTBLANK")

            return

        # Handle CONTAINS via SEARCH
        search_match = re.search(r'ISNUMBER\(SEARCH\("([^"]+)", \[([^\]]+)\]\)\)', condition_text)
        if search_match:
            search_text = search_match.group(1)
            column_name = search_match.group(2)

            # Add condition row
            self.add_condition_row()

            # Get the added row
            row_idx = self.conditions_layout.count() - 1
            condition_frame = self.conditions_layout.itemAt(row_idx).widget()
            condition_layout = condition_frame.layout()

            # Find and set widgets
            column_combo = None
            operator_combo = None
            value_edit = None

            for j in range(condition_layout.count()):
                widget = condition_layout.itemAt(j).widget()
                if isinstance(widget, QComboBox):
                    if column_combo is None:
                        column_combo = widget
                    else:
                        operator_combo = widget
                elif isinstance(widget, QLineEdit):
                    value_edit = widget

            # Update widgets
            if column_combo:
                column_combo.setCurrentText(column_name)
            if operator_combo:
                operator_combo.setCurrentText("CONTAINS")
            if value_edit:
                value_edit.setText(search_text)

            return

        # If we get here, we couldn't parse the condition
        # Add a dummy condition
        self.add_condition_row()
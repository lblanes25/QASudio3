from PySide6.QtWidgets import QWidget



class RulePreviewPanel(QWidget):
    """Panel for previewing rule in different formats."""

    def __init__(self, rule_model):
        super().__init__()
        self.rule_model = rule_model

        # Set up UI
        self.init_ui()

        # Initial update
        self.update_preview()

    def init_ui(self):
        """Initialize the UI components."""
        from PySide6.QtWidgets import QVBoxLayout, QLabel, QPlainTextEdit, QComboBox
        from PySide6.QtGui import QFont

        # Main layout
        main_layout = QVBoxLayout(self)

        # Preview format selector
        format_layout = QVBoxLayout()
        format_label = QLabel("Preview Format:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["YAML", "JSON", "Excel Formula"])
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)
        main_layout.addLayout(format_layout)

        # Preview text
        self.preview_edit = QPlainTextEdit()
        font = QFont("Consolas", 10)
        self.preview_edit.setFont(font)
        self.preview_edit.setReadOnly(True)
        main_layout.addWidget(self.preview_edit)

        # Connect format selector
        self.format_combo.currentTextChanged.connect(self.update_preview)

    def update_preview(self):
        """Update the preview based on selected format."""
        format_type = self.format_combo.currentText()

        if format_type == "YAML":
            # YAML preview
            yaml_text = self.rule_model.to_yaml()
            self.preview_edit.setPlainText(yaml_text)

        elif format_type == "JSON":
            # JSON preview
            json_text = self.rule_model.to_json()
            self.preview_edit.setPlainText(json_text)

        elif format_type == "Excel Formula":
            # Formula preview
            formula = self.rule_model.formula
            self.preview_edit.setPlainText(formula)
from PySide6.QtWidgets import QWidget
from stylesheet import Stylesheet



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
        from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QPlainTextEdit, QComboBox
        from PySide6.QtGui import QFont, QPalette, QColor
        from PySide6.QtCore import Qt

        # Set default font using stylesheet
        self.setFont(Stylesheet.get_regular_font())
        
        # Monospace font for code
        mono_font = Stylesheet.get_mono_font()

        # Main layout with consistent spacing
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(Stylesheet.STANDARD_SPACING)
        main_layout.setContentsMargins(Stylesheet.STANDARD_SPACING, Stylesheet.STANDARD_SPACING,
                                      Stylesheet.STANDARD_SPACING, Stylesheet.STANDARD_SPACING)

        # Header with format selector on the same line
        header_layout = QHBoxLayout()
        header_layout.setSpacing(Stylesheet.STANDARD_SPACING)
        
        preview_header = QLabel("Rule Preview")
        preview_header.setFont(Stylesheet.get_header_font())
        preview_header.setStyleSheet(Stylesheet.get_section_header_style())
        header_layout.addWidget(preview_header)
        
        # Format selector as a compact dropdown
        format_label = QLabel("Format:")
        header_layout.addWidget(format_label)
        
        self.format_combo = QComboBox()
        self.format_combo.addItems(["YAML", "Excel Formula"])  # Remove JSON to simplify
        self.format_combo.setMaximumWidth(120)
        self.format_combo.setMinimumHeight(Stylesheet.INPUT_HEIGHT)
        header_layout.addWidget(self.format_combo)
        
        header_layout.addStretch(1)  # Push everything to the left
        main_layout.addLayout(header_layout)

        # Preview text with styled background
        self.preview_edit = QPlainTextEdit()
        self.preview_edit.setFont(mono_font)
        self.preview_edit.setReadOnly(True)
        
        # Use a light background to indicate read-only
        palette = self.preview_edit.palette()
        palette.setColor(QPalette.Base, QColor(245, 245, 245))
        self.preview_edit.setPalette(palette)
        
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
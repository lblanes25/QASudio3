"""
LOOKUP Assistant Dialog for building LOOKUP formulas.
Part of Phase 3, Task 1 for Secondary Source File Integration.
"""

from pathlib import Path
from typing import List, Dict, Optional, Tuple
import pandas as pd

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QGroupBox, QLineEdit, QRadioButton,
    QButtonGroup, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialogButtonBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from ui.common.stylesheet import AnalyticsRunnerStylesheet
from core.lookup.smart_lookup_manager import SmartLookupManager


class LookupAssistant(QDialog):
    """Simple dialog for building LOOKUP calls."""
    
    # Signal emitted when formula is accepted
    formulaGenerated = Signal(str)
    
    def __init__(self, primary_columns: List[str], 
                 lookup_manager: SmartLookupManager,
                 parent=None):
        """
        Initialize the LOOKUP Assistant.
        
        Args:
            primary_columns: List of column names from primary data
            lookup_manager: SmartLookupManager instance
            parent: Parent widget
        """
        super().__init__(parent)
        self.primary_columns = primary_columns or []
        self.lookup_manager = lookup_manager
        self.generated_formula = ""
        
        self.setWindowTitle("LOOKUP Formula Assistant")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        
        self._setup_ui()
        self._populate_dropdowns()
        self._update_formula()
    
    def _setup_ui(self):
        """Setup the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)
        
        # Title and description
        title = QLabel("LOOKUP Formula Assistant")
        title.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        title.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                font-weight: bold;
                padding-bottom: 8px;
            }}
        """)
        layout.addWidget(title)
        
        description = QLabel(
            "Build a LOOKUP formula by selecting what value to look up and what information to retrieve."
        )
        description.setWordWrap(True)
        layout.addWidget(description)
        
        # Step 1: What value are you looking up?
        step1_group = QGroupBox("Step 1: What value are you looking up?")
        step1_layout = QVBoxLayout(step1_group)
        
        # Radio buttons for column vs custom value
        self.lookup_type_group = QButtonGroup()
        
        self.column_radio = QRadioButton("Column from primary data")
        self.column_radio.setChecked(True)
        self.lookup_type_group.addButton(self.column_radio, 0)
        step1_layout.addWidget(self.column_radio)
        
        # Column dropdown
        column_layout = QHBoxLayout()
        column_layout.addSpacing(20)
        self.column_combo = QComboBox()
        self.column_combo.setMinimumWidth(300)
        column_layout.addWidget(self.column_combo)
        column_layout.addStretch()
        step1_layout.addLayout(column_layout)
        
        self.custom_radio = QRadioButton("Custom value")
        self.lookup_type_group.addButton(self.custom_radio, 1)
        step1_layout.addWidget(self.custom_radio)
        
        # Custom value input
        custom_layout = QHBoxLayout()
        custom_layout.addSpacing(20)
        self.custom_input = QLineEdit()
        self.custom_input.setEnabled(False)
        self.custom_input.setPlaceholderText("Enter a custom value...")
        self.custom_input.setMinimumWidth(300)
        custom_layout.addWidget(self.custom_input)
        custom_layout.addStretch()
        step1_layout.addLayout(custom_layout)
        
        layout.addWidget(step1_group)
        
        # Step 2: What do you want to find?
        step2_group = QGroupBox("Step 2: What information do you want to retrieve?")
        step2_layout = QVBoxLayout(step2_group)
        
        self.return_column_combo = QComboBox()
        self.return_column_combo.setMinimumHeight(25)
        step2_layout.addWidget(self.return_column_combo)
        
        # Note about column availability
        self.availability_label = QLabel()
        self.availability_label.setWordWrap(True)
        self.availability_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.INFO_COLOR};
                font-size: {AnalyticsRunnerStylesheet.SMALL_FONT_SIZE}px;
                padding: 4px;
            }}
        """)
        step2_layout.addWidget(self.availability_label)
        
        layout.addWidget(step2_group)
        
        # Preview area
        preview_group = QGroupBox("Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.preview_table = QTableWidget()
        self.preview_table.setMaximumHeight(150)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.horizontalHeader().setStretchLastSection(True)
        preview_layout.addWidget(self.preview_table)
        
        layout.addWidget(preview_group)
        
        # Generated formula
        formula_group = QGroupBox("Generated Formula")
        formula_layout = QVBoxLayout(formula_group)
        
        self.formula_display = QTextEdit()
        self.formula_display.setMaximumHeight(60)
        self.formula_display.setReadOnly(True)
        self.formula_display.setFont(QFont("Consolas", 11))
        self.formula_display.setStyleSheet(f"""
            QTextEdit {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                padding: 8px;
            }}
        """)
        formula_layout.addWidget(self.formula_display)
        
        layout.addWidget(formula_group)
        
        # Buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._accept_formula)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
        
        # Connect signals
        self.lookup_type_group.buttonClicked.connect(self._on_lookup_type_changed)
        self.column_combo.currentTextChanged.connect(self._update_formula)
        self.custom_input.textChanged.connect(self._update_formula)
        self.return_column_combo.currentTextChanged.connect(self._on_return_column_changed)
    
    def _populate_dropdowns(self):
        """Populate the dropdown controls."""
        # Populate primary data columns
        self.column_combo.clear()
        for col in sorted(self.primary_columns):
            self.column_combo.addItem(col)
        
        # Populate return columns from lookup manager
        self._populate_return_columns()
    
    def _populate_return_columns(self):
        """Populate return column dropdown with grouping by file."""
        self.return_column_combo.clear()
        
        # Group columns by file
        columns_by_file = {}
        for column, filepaths in self.lookup_manager.column_index.items():
            for filepath in filepaths:
                alias = self.lookup_manager.file_aliases.get(filepath, Path(filepath).stem)
                if alias not in columns_by_file:
                    columns_by_file[alias] = []
                columns_by_file[alias].append(column)
        
        # Add columns to combo box
        for file_alias in sorted(columns_by_file.keys()):
            columns = sorted(set(columns_by_file[file_alias]))
            for column in columns:
                # Check if this column exists in multiple files
                file_count = len(self.lookup_manager.column_index.get(column, []))
                if file_count > 1:
                    display_text = f"{column} (from {file_alias})"
                    self.return_column_combo.addItem(display_text, (column, file_alias))
                else:
                    self.return_column_combo.addItem(column, (column, None))
    
    def _on_lookup_type_changed(self, button):
        """Handle lookup type radio button changes."""
        if self.column_radio.isChecked():
            self.column_combo.setEnabled(True)
            self.custom_input.setEnabled(False)
        else:
            self.column_combo.setEnabled(False)
            self.custom_input.setEnabled(True)
        self._update_formula()
    
    def _on_return_column_changed(self):
        """Handle return column selection changes."""
        self._update_formula()
        self._update_preview()
        self._update_availability_label()
    
    def _update_availability_label(self):
        """Update the label showing where the column is available."""
        if self.return_column_combo.currentData():
            column, file_hint = self.return_column_combo.currentData()
            files = self.lookup_manager.column_index.get(column, [])
            
            if len(files) == 1:
                filepath = files[0]
                metadata = self.lookup_manager.file_metadata.get(filepath, {})
                alias = self.lookup_manager.file_aliases.get(filepath, Path(filepath).stem)
                rows = metadata.get('row_count', 0)
                self.availability_label.setText(
                    f"ℹ️ Available in {alias} ({rows:,} rows)"
                )
            elif len(files) > 1:
                aliases = [self.lookup_manager.file_aliases.get(f, Path(f).stem) for f in files[:3]]
                text = f"ℹ️ Available in {len(files)} files: {', '.join(aliases)}"
                if len(files) > 3:
                    text += f" and {len(files) - 3} more"
                self.availability_label.setText(text)
            else:
                self.availability_label.setText("⚠️ Column not found in any loaded file")
    
    def _update_formula(self):
        """Update the generated formula based on current selections."""
        if not self.return_column_combo.currentData():
            self.generated_formula = ""
            self.formula_display.clear()
            return
        
        # Get lookup value
        if self.column_radio.isChecked():
            lookup_value = f"[{self.column_combo.currentText()}]" if self.column_combo.currentText() else ""
        else:
            custom_value = self.custom_input.text()
            if custom_value:
                # Quote string values
                if not custom_value.isdigit():
                    lookup_value = f'"{custom_value}"'
                else:
                    lookup_value = custom_value
            else:
                lookup_value = ""
        
        if not lookup_value:
            self.generated_formula = ""
            self.formula_display.clear()
            return
        
        # Get return column info
        column, file_hint = self.return_column_combo.currentData()
        
        # Build formula
        if file_hint and len(self.lookup_manager.column_index.get(column, [])) > 1:
            # Multiple files have this column, add file hint
            self.generated_formula = f"LOOKUP({lookup_value}, '{file_hint}', '{column}')"
        else:
            # Single file or no ambiguity
            self.generated_formula = f"LOOKUP({lookup_value}, '{column}')"
        
        # Display formula
        self.formula_display.setPlainText(self.generated_formula)
    
    def _update_preview(self):
        """Update the preview table with example lookups."""
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)
        
        if not self.return_column_combo.currentData():
            return
        
        column, file_hint = self.return_column_combo.currentData()
        
        # Find the file containing this column
        files = self.lookup_manager.column_index.get(column, [])
        if not files:
            return
        
        # Use the hinted file if specified, otherwise the first file
        target_file = None
        if file_hint:
            for filepath in files:
                alias = self.lookup_manager.file_aliases.get(filepath, Path(filepath).stem)
                if alias == file_hint:
                    target_file = filepath
                    break
        
        if not target_file:
            target_file = files[0]
        
        # Try to get some sample data
        df = self.lookup_manager.loaded_files.get(target_file)
        if df is None:
            # File is lazy-loaded, just show info
            self.preview_table.setColumnCount(1)
            self.preview_table.setRowCount(1)
            self.preview_table.setHorizontalHeaderLabels(["Info"])
            self.preview_table.setItem(0, 0, QTableWidgetItem(
                "Data not loaded (file is lazy-loaded for performance)"
            ))
            return
        
        # Show sample data
        if column in df.columns:
            # Get unique values (up to 10)
            unique_values = df[column].dropna().unique()[:10]
            
            self.preview_table.setColumnCount(2)
            self.preview_table.setRowCount(len(unique_values))
            self.preview_table.setHorizontalHeaderLabels(["Sample Values", "Type"])
            
            for i, value in enumerate(unique_values):
                self.preview_table.setItem(i, 0, QTableWidgetItem(str(value)))
                self.preview_table.setItem(i, 1, QTableWidgetItem(
                    type(value).__name__
                ))
            
            self.preview_table.horizontalHeader().setStretchLastSection(True)
    
    def _accept_formula(self):
        """Accept the formula and emit signal."""
        if self.generated_formula:
            self.formulaGenerated.emit(self.generated_formula)
            self.accept()
    
    def get_formula(self) -> str:
        """Get the generated formula."""
        return self.generated_formula
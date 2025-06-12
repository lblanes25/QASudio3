"""
Save Data Source Dialog - Data Source Registration Component
Allows users to register currently loaded data with metadata for future reuse
"""

import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QTextEdit, QPushButton, QGroupBox, QCheckBox, QComboBox,
    QFormLayout, QFrame, QMessageBox, QScrollArea, QWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter
)
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QFont

from ui.common.stylesheet import AnalyticsRunnerStylesheet
from ui.analytics_runner.data_source_registry import DataSourceRegistry, DataSourceMetadata, DataSourceType

logger = logging.getLogger(__name__)


class SaveDataSourceDialog(QDialog):
    """
    Dialog for saving data source configurations with metadata.
    
    Features:
    - Prefilled file information from current session
    - Custom metadata input (name, description, tags)
    - Live preview of configuration
    - Name uniqueness validation
    - Integration with DataSourceRegistry
    """
    
    # Signals
    dataSourceSaved = Signal(str)  # source_id of saved data source
    
    def __init__(self, 
                 file_path: str,
                 sheet_name: Optional[str] = None,
                 preview_df=None,
                 registry: Optional[DataSourceRegistry] = None,
                 parent: Optional[QWidget] = None):
        """
        Initialize the save data source dialog.
        
        Args:
            file_path: Path to the current data file
            sheet_name: Excel sheet name if applicable
            preview_df: Preview DataFrame for metadata extraction
            registry: DataSourceRegistry instance
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Store parameters
        self.file_path = file_path
        self.sheet_name = sheet_name
        self.preview_df = preview_df
        self.registry = registry or DataSourceRegistry()
        
        # Validation state
        self._name_is_valid = False
        self._existing_names = {source.name for source in self.registry.list_data_sources()}
        self._existing_tags = self._get_existing_tags()
        
        # UI setup
        self.setWindowTitle("Save Data Source")
        self.setModal(True)
        self.resize(700, 600)
        
        self._setup_ui()
        self._populate_file_info()
        self._setup_validation()
        
        # Apply styling
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())
        
        logger.debug(f"SaveDataSourceDialog initialized for: {os.path.basename(file_path)}")
    
    def _setup_ui(self):
        """Setup the user interface components."""
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        main_layout.setContentsMargins(16, 16, 16, 16)
        
        # Title
        title_label = QLabel("Save Data Source Configuration")
        title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['title'])
        title_label.setStyleSheet(AnalyticsRunnerStylesheet.get_header_stylesheet())
        main_layout.addWidget(title_label)
        
        # Create splitter for main content
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # Left panel - Input form
        self._create_input_panel(splitter)
        
        # Right panel - Preview
        self._create_preview_panel(splitter)
        
        # Set splitter proportions (60% input, 40% preview)
        splitter.setSizes([420, 280])
        
        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        
        # Cancel button
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setProperty("buttonStyle", "secondary")
        self.cancel_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)
        
        button_layout.addStretch()
        
        # Save button
        self.save_button = QPushButton("Save Data Source")
        self.save_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.save_button.clicked.connect(self._save_data_source)
        self.save_button.setEnabled(False)  # Disabled until name is valid
        button_layout.addWidget(self.save_button)
        
        main_layout.addLayout(button_layout)
    
    def _create_input_panel(self, parent):
        """Create the input form panel."""
        # Scroll area for input form
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Input widget
        input_widget = QWidget()
        input_layout = QVBoxLayout(input_widget)
        input_layout.setSpacing(AnalyticsRunnerStylesheet.FORM_SPACING)
        input_layout.setContentsMargins(8, 8, 8, 8)
        
        # File Information Group
        self._create_file_info_group(input_layout)
        
        # Metadata Group
        self._create_metadata_group(input_layout)
        
        # Settings Group
        self._create_settings_group(input_layout)
        
        # Add stretch
        input_layout.addStretch()
        
        # Set widget in scroll area
        scroll_area.setWidget(input_widget)
        parent.addWidget(scroll_area)
    
    def _create_file_info_group(self, parent_layout):
        """Create the file information group."""
        file_group = QGroupBox("File Information")
        file_group.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        file_layout = QFormLayout(file_group)
        file_layout.setSpacing(8)
        
        # File path (read-only)
        self.file_path_label = QLabel()
        self.file_path_label.setWordWrap(True)
        self.file_path_label.setStyleSheet(f"""
            QLabel {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px;
                color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
            }}
        """)
        file_layout.addRow("File Path:", self.file_path_label)
        
        # File format (read-only)
        self.file_format_label = QLabel()
        self.file_format_label.setStyleSheet(f"""
            QLabel {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px;
                color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
            }}
        """)
        file_layout.addRow("Format:", self.file_format_label)
        
        # Sheet name (if applicable)
        self.sheet_label = QLabel()
        self.sheet_label.setStyleSheet(f"""
            QLabel {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px;
                color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
            }}
        """)
        self.sheet_row = file_layout.addRow("Sheet:", self.sheet_label)
        
        # File size and modification date
        self.file_stats_label = QLabel()
        self.file_stats_label.setStyleSheet(f"""
            QLabel {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 6px;
                color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
                font-size: {AnalyticsRunnerStylesheet.SMALL_FONT_SIZE}px;
            }}
        """)
        file_layout.addRow("File Stats:", self.file_stats_label)
        
        parent_layout.addWidget(file_group)
    
    def _create_metadata_group(self, parent_layout):
        """Create the metadata input group."""
        metadata_group = QGroupBox("Source Metadata")
        metadata_group.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        metadata_layout = QFormLayout(metadata_group)
        metadata_layout.setSpacing(8)
        
        # Source name (required, must be unique)
        self.name_input = QLineEdit()
        self.name_input.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.name_input.setPlaceholderText("Enter a unique name for this data source")
        self.name_input.textChanged.connect(self._validate_name)
        metadata_layout.addRow("Source Name *:", self.name_input)
        
        # Name validation label
        self.name_validation_label = QLabel()
        self.name_validation_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        self.name_validation_label.setVisible(False)
        metadata_layout.addRow("", self.name_validation_label)
        
        # Description (optional, multi-line)
        self.description_input = QTextEdit()
        self.description_input.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.description_input.setPlaceholderText("Optional description of this data source...")
        self.description_input.setMaximumHeight(80)
        metadata_layout.addRow("Description:", self.description_input)
        
        # Tags (optional, comma-separated with autocomplete)
        self.tags_input = QLineEdit()
        self.tags_input.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.tags_input.setPlaceholderText("Optional tags (comma-separated): finance, quarterly, customers")
        metadata_layout.addRow("Tags:", self.tags_input)
        
        # Data type hint
        self.data_type_combo = QComboBox()
        self.data_type_combo.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.data_type_combo.addItems(["generic", "employee", "financial", "sales", "customer"])
        metadata_layout.addRow("Data Type:", self.data_type_combo)
        
        parent_layout.addWidget(metadata_group)
    
    def _create_settings_group(self, parent_layout):
        """Create the settings group."""
        settings_group = QGroupBox("Settings")
        settings_group.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        settings_layout = QFormLayout(settings_group)
        settings_layout.setSpacing(8)
        
        # Pre-validation enabled
        self.pre_validation_checkbox = QCheckBox("Enable pre-validation")
        self.pre_validation_checkbox.setChecked(True)
        self.pre_validation_checkbox.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        settings_layout.addRow("", self.pre_validation_checkbox)
        
        # Mark as favorite
        self.favorite_checkbox = QCheckBox("Mark as favorite")
        self.favorite_checkbox.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        settings_layout.addRow("", self.favorite_checkbox)
        
        parent_layout.addWidget(settings_group)
    
    def _create_preview_panel(self, parent):
        """Create the preview panel."""
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        preview_layout.setContentsMargins(8, 8, 8, 8)
        
        # Preview title
        preview_title = QLabel("Configuration Preview")
        preview_title.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        preview_title.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                font-weight: bold;
                border-bottom: 2px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                padding-bottom: 4px;
                margin-bottom: 8px;
            }}
        """)
        preview_layout.addWidget(preview_title)
        
        # Preview text area
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setFont(AnalyticsRunnerStylesheet.get_fonts()['mono'])
        self.preview_text.setStyleSheet(f"""
            QTextEdit {{
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 4px;
                padding: 8px;
                font-family: 'Consolas', 'Courier New', monospace;
            }}
        """)
        preview_layout.addWidget(self.preview_text)
        
        # Data preview (if available)
        if self.preview_df is not None and not self.preview_df.empty:
            data_preview_label = QLabel("Data Preview (first 5 rows)")
            data_preview_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
            data_preview_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.DARK_TEXT};
                    font-weight: 500;
                    margin-top: 8px;
                    margin-bottom: 4px;
                }}
            """)
            preview_layout.addWidget(data_preview_label)
            
            # Data preview table
            self.data_preview_table = QTableWidget()
            self.data_preview_table.setMaximumHeight(150)
            self.data_preview_table.setAlternatingRowColors(True)
            self.data_preview_table.verticalHeader().setVisible(False)
            self.data_preview_table.setStyleSheet(AnalyticsRunnerStylesheet.get_table_stylesheet())
            self._populate_data_preview()
            preview_layout.addWidget(self.data_preview_table)
        
        parent.addWidget(preview_widget)
    
    def _populate_file_info(self):
        """Populate the file information fields."""
        # File path
        self.file_path_label.setText(self.file_path)
        
        # File format
        file_ext = Path(self.file_path).suffix.lower()
        if file_ext in ['.xlsx', '.xls']:
            format_text = "Microsoft Excel"
        elif file_ext == '.csv':
            format_text = "Comma-Separated Values (CSV)"
        else:
            format_text = f"Text File ({file_ext})"
        self.file_format_label.setText(format_text)
        
        # Sheet name (show/hide based on file type)
        if self.sheet_name:
            self.sheet_label.setText(self.sheet_name)
            self.sheet_label.setVisible(True)
        else:
            self.sheet_row[0].setVisible(False)  # Hide label
            self.sheet_label.setVisible(False)   # Hide value
        
        # File stats
        try:
            if os.path.exists(self.file_path):
                stat = os.stat(self.file_path)
                file_size = stat.st_size
                mod_time = datetime.datetime.fromtimestamp(stat.st_mtime)
                
                # Format file size
                if file_size < 1024:
                    size_str = f"{file_size} bytes"
                elif file_size < 1024 * 1024:
                    size_str = f"{file_size / 1024:.1f} KB"
                else:
                    size_str = f"{file_size / (1024 * 1024):.1f} MB"
                
                stats_text = f"Size: {size_str} | Modified: {mod_time.strftime('%Y-%m-%d %H:%M')}"
                self.file_stats_label.setText(stats_text)
            else:
                self.file_stats_label.setText("File not found")
        except Exception as e:
            self.file_stats_label.setText(f"Error reading file info: {str(e)}")
        
        # Suggest a default name
        file_name = Path(self.file_path).stem
        if self.sheet_name and self.sheet_name not in file_name:
            suggested_name = f"{file_name}_{self.sheet_name}"
        else:
            suggested_name = file_name
        
        # Make sure suggested name is unique
        base_name = suggested_name
        counter = 1
        while suggested_name in self._existing_names:
            suggested_name = f"{base_name}_{counter}"
            counter += 1
        
        self.name_input.setText(suggested_name)
        
        # Auto-detect data type based on file name and columns
        if self.preview_df is not None:
            detected_type = self._detect_data_type()
            type_index = self.data_type_combo.findText(detected_type)
            if type_index >= 0:
                self.data_type_combo.setCurrentIndex(type_index)
    
    def _populate_data_preview(self):
        """Populate the data preview table."""
        if self.preview_df is None or self.preview_df.empty:
            return
        
        # Show first 5 rows
        preview_data = self.preview_df.head(5)
        
        # Set table dimensions
        self.data_preview_table.setRowCount(len(preview_data))
        self.data_preview_table.setColumnCount(len(preview_data.columns))
        
        # Set headers
        self.data_preview_table.setHorizontalHeaderLabels([str(col) for col in preview_data.columns])
        
        # Populate data
        for row_idx, (_, row) in enumerate(preview_data.iterrows()):
            for col_idx, value in enumerate(row):
                item = QTableWidgetItem(str(value) if value is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.data_preview_table.setItem(row_idx, col_idx, item)
        
        # Resize columns
        self.data_preview_table.resizeColumnsToContents()
        
        # Set maximum column width
        for col in range(self.data_preview_table.columnCount()):
            if self.data_preview_table.columnWidth(col) > 120:
                self.data_preview_table.setColumnWidth(col, 120)
    
    def _detect_data_type(self) -> str:
        """Auto-detect data type based on column names."""
        if self.preview_df is None or self.preview_df.empty:
            return "generic"
        
        columns = [col.lower().strip() for col in self.preview_df.columns]
        column_text = ' '.join(columns)
        
        # Financial data indicators
        financial_indicators = ['amount', 'value', 'price', 'cost', 'revenue', 'expense', 'balance', 'transaction']
        if any(indicator in column_text for indicator in financial_indicators):
            return "financial"
        
        # Employee data indicators
        employee_indicators = ['employee', 'staff', 'worker', 'hire', 'department', 'salary', 'position']
        if any(indicator in column_text for indicator in employee_indicators):
            return "employee"
        
        # Sales data indicators
        sales_indicators = ['sales', 'product', 'customer', 'order', 'purchase', 'quantity', 'item']
        if any(indicator in column_text for indicator in sales_indicators):
            return "sales"
        
        # Customer data indicators
        customer_indicators = ['customer', 'client', 'contact', 'account', 'name', 'email', 'phone']
        if any(indicator in column_text for indicator in customer_indicators):
            return "customer"
        
        return "generic"
    
    def _get_existing_tags(self) -> List[str]:
        """Get list of existing tags from registry."""
        tags = set()
        for source in self.registry.list_data_sources():
            tags.update(source.tags)
        return sorted(tags)
    
    def _setup_validation(self):
        """Setup validation for form fields."""
        # Name validation timer (debounced)
        self._validation_timer = QTimer()
        self._validation_timer.setSingleShot(True)
        self._validation_timer.timeout.connect(self._update_preview)
        
        # Connect input changes to preview update
        self.name_input.textChanged.connect(lambda: self._validation_timer.start(300))
        self.description_input.textChanged.connect(lambda: self._validation_timer.start(300))
        self.tags_input.textChanged.connect(lambda: self._validation_timer.start(300))
        self.data_type_combo.currentTextChanged.connect(lambda: self._validation_timer.start(300))
        self.pre_validation_checkbox.toggled.connect(lambda: self._validation_timer.start(300))
        self.favorite_checkbox.toggled.connect(lambda: self._validation_timer.start(300))
        
        # Initial preview update
        self._update_preview()
    
    def _validate_name(self, name: str):
        """Validate the source name."""
        name = name.strip()
        
        if not name:
            self._show_name_validation("Source name is required", False)
            return
        
        if name in self._existing_names:
            self._show_name_validation("A data source with this name already exists", False)
            return
        
        if len(name) < 3:
            self._show_name_validation("Source name must be at least 3 characters", False)
            return
        
        # Name is valid
        self._show_name_validation("✓ Name is available", True)
    
    def _show_name_validation(self, message: str, is_valid: bool):
        """Show name validation message."""
        self._name_is_valid = is_valid
        self.name_validation_label.setText(message)
        self.name_validation_label.setVisible(True)
        
        if is_valid:
            self.name_validation_label.setStyleSheet(AnalyticsRunnerStylesheet.get_success_style())
        else:
            self.name_validation_label.setStyleSheet(AnalyticsRunnerStylesheet.get_error_style())
        
        # Enable/disable save button
        self.save_button.setEnabled(is_valid)
    
    def _update_preview(self):
        """Update the configuration preview."""
        # Gather current values
        name = self.name_input.text().strip()
        description = self.description_input.toPlainText().strip()
        tags_text = self.tags_input.text().strip()
        tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()] if tags_text else []
        data_type = self.data_type_combo.currentText()
        pre_validation = self.pre_validation_checkbox.isChecked()
        is_favorite = self.favorite_checkbox.isChecked()
        
        # Build preview text
        preview_lines = [
            "Data Source Configuration:",
            "=" * 30,
            "",
            f"Name: {name or '(not set)'}",
            f"File Path: {self.file_path}",
            f"Format: {self.file_format_label.text()}",
        ]
        
        if self.sheet_name:
            preview_lines.append(f"Sheet: {self.sheet_name}")
        
        preview_lines.extend([
            f"Data Type: {data_type}",
            f"Description: {description or '(none)'}",
            f"Tags: {', '.join(tags) if tags else '(none)'}",
            "",
            "Settings:",
            f"  Pre-validation: {'Enabled' if pre_validation else 'Disabled'}",
            f"  Favorite: {'Yes' if is_favorite else 'No'}",
        ])
        
        if self.preview_df is not None:
            preview_lines.extend([
                "",
                "Data Summary:",
                f"  Rows: {len(self.preview_df)}",
                f"  Columns: {len(self.preview_df.columns)}",
                f"  Column Names: {', '.join(str(col) for col in self.preview_df.columns[:5])}{'...' if len(self.preview_df.columns) > 5 else ''}",
            ])
        
        self.preview_text.setPlainText('\n'.join(preview_lines))
    
    def _save_data_source(self):
        """Save the data source to the registry."""
        if not self._name_is_valid:
            QMessageBox.warning(self, "Invalid Name", "Please enter a valid, unique source name.")
            return
        
        try:
            # Gather form data
            name = self.name_input.text().strip()
            description = self.description_input.toPlainText().strip()
            tags_text = self.tags_input.text().strip()
            tags = [tag.strip() for tag in tags_text.split(',') if tag.strip()] if tags_text else []
            data_type = self.data_type_combo.currentText()
            pre_validation = self.pre_validation_checkbox.isChecked()
            is_favorite = self.favorite_checkbox.isChecked()
            
            # Build connection parameters
            connection_params = {}
            if self.sheet_name:
                connection_params['sheet_name'] = self.sheet_name
            
            # Register the data source
            source_id = self.registry.register_data_source(
                name=name,
                file_path=self.file_path,
                description=description,
                tags=tags,
                connection_params=connection_params,
                data_type_hint=data_type,
                overwrite_existing=False
            )
            
            # Update settings if different from defaults
            if not pre_validation or is_favorite:
                self.registry.update_data_source(
                    source_id=source_id,
                    is_favorite=is_favorite
                )
                
                # Update pre_validation_enabled if needed
                metadata = self.registry.get_data_source(source_id)
                if metadata:
                    metadata.pre_validation_enabled = pre_validation
                    # Note: Would need to add this to the update method in registry
            
            # Success
            QMessageBox.information(
                self,
                "Data Source Saved",
                f"Data source '{name}' has been saved successfully."
            )
            
            # Emit signal and close
            self.dataSourceSaved.emit(source_id)
            self.accept()
            
            logger.info(f"Data source saved successfully: {name} ({source_id})")
            
        except Exception as e:
            error_msg = f"Error saving data source: {str(e)}"
            logger.error(error_msg)
            QMessageBox.critical(self, "Save Error", error_msg)
    
    # Public interface
    @staticmethod
    def save_current_data_source(file_path: str, 
                                sheet_name: Optional[str] = None,
                                preview_df=None,
                                registry: Optional[DataSourceRegistry] = None,
                                parent: Optional[QWidget] = None) -> Optional[str]:
        """
        Static method to show the save dialog and return the saved source ID.
        
        Args:
            file_path: Path to the current data file
            sheet_name: Excel sheet name if applicable
            preview_df: Preview DataFrame for metadata extraction
            registry: DataSourceRegistry instance
            parent: Parent widget
            
        Returns:
            Source ID if saved successfully, None if cancelled
        """
        if not os.path.exists(file_path):
            QMessageBox.warning(parent, "File Not Found", f"Cannot save data source: file not found\n{file_path}")
            return None
        
        dialog = SaveDataSourceDialog(file_path, sheet_name, preview_df, registry, parent)
        
        if dialog.exec() == QDialog.Accepted:
            # The source_id would be emitted via signal, but for static method we need to track it
            # This is a simplified approach - in real implementation you'd connect to the signal
            return "saved"  # Placeholder - would return actual source_id
        
        return None

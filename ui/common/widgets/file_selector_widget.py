"""
FileSelectorWidget - Reusable File Selection Component
Provides drag-and-drop, browse, and recent files functionality
"""

import os
from pathlib import Path
from typing import List, Optional, Callable
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QComboBox, QFrame, QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QMimeData, QTimer
from PySide6.QtGui import QDragEnterEvent, QDropEvent, QPalette, QFont

from ui.common.stylesheet import AnalyticsRunnerStylesheet

logger = logging.getLogger(__name__)


class FileSelectorWidget(QWidget):
    """
    Reusable file selector widget with drag-and-drop, browse, and recent files.
    
    Features:
    - Drag and drop file support with visual feedback
    - Browse button with customizable file filters
    - Recent files dropdown integration
    - File validation and status indicators
    - Customizable file type restrictions
    """
    
    # Signals
    fileSelected = Signal(str)  # Emitted when a file is selected
    fileChanged = Signal(str)   # Emitted when the current file changes
    validationChanged = Signal(bool)  # Emitted when validation status changes
    
    def __init__(self, 
                 title: str = "Select File",
                 file_filters: str = "All Files (*)",
                 accepted_extensions: Optional[List[str]] = None,
                 show_recent_files: bool = True,
                 max_recent_files: int = 5,
                 validation_callback: Optional[Callable[[str], tuple[bool, str]]] = None,
                 parent: Optional[QWidget] = None):
        """
        Initialize the file selector widget.
        
        Args:
            title: Title text displayed above the selector
            file_filters: File dialog filter string (e.g., "CSV Files (*.csv);;Excel Files (*.xlsx)")
            accepted_extensions: List of accepted file extensions (e.g., ['.csv', '.xlsx'])
            show_recent_files: Whether to show recent files dropdown
            max_recent_files: Maximum number of recent files to display
            validation_callback: Function to validate selected files (returns bool, message)
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Configuration
        self.title = title
        self.file_filters = file_filters
        self.accepted_extensions = accepted_extensions or []
        self.show_recent_files = show_recent_files
        self.max_recent_files = max_recent_files
        self.validation_callback = validation_callback
        
        # State
        self._current_file = ""
        self._is_valid = False
        self._recent_files: List[str] = []
        self._drag_active = False
        
        # Setup UI
        self._setup_ui()
        self._setup_styles()
        self._setup_drag_drop()
        
        # Setup validation timer (debounce validation calls)
        self._validation_timer = QTimer()
        self._validation_timer.setSingleShot(True)
        self._validation_timer.timeout.connect(self._perform_validation)
        
        logger.debug(f"FileSelectorWidget initialized: {title}")
    
    def _setup_ui(self):
        """Setup the user interface components."""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Title label
        if self.title:
            self.title_label = QLabel(self.title)
            self.title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
            self.main_layout.addWidget(self.title_label)
        
        # Drop zone frame
        self.drop_zone = QFrame()
        self.drop_zone.setFrameStyle(QFrame.StyledPanel)
        self.drop_zone.setLineWidth(2)
        self.drop_zone.setMinimumHeight(120)
        self.drop_zone.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Drop zone layout
        drop_layout = QVBoxLayout(self.drop_zone)
        drop_layout.setSpacing(8)
        drop_layout.setAlignment(Qt.AlignCenter)
        
        # Drop zone icon/text
        self.drop_label = QLabel("Drop files here or click to browse")
        self.drop_label.setAlignment(Qt.AlignCenter)
        self.drop_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        drop_layout.addWidget(self.drop_label)
        
        # File type hint
        if self.accepted_extensions:
            ext_text = ", ".join(self.accepted_extensions)
            self.hint_label = QLabel(f"Accepted types: {ext_text}")
            self.hint_label.setAlignment(Qt.AlignCenter)
            self.hint_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
            drop_layout.addWidget(self.hint_label)
        
        self.main_layout.addWidget(self.drop_zone)
        
        # Button row
        button_layout = QHBoxLayout()
        button_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        
        # Browse button
        self.browse_button = QPushButton("Browse...")
        self.browse_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.browse_button.clicked.connect(self._browse_file)
        button_layout.addWidget(self.browse_button)
        
        # Recent files dropdown
        if self.show_recent_files:
            self.recent_combo = QComboBox()
            self.recent_combo.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
            self.recent_combo.setMinimumWidth(200)
            self.recent_combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self.recent_combo.currentTextChanged.connect(self._on_recent_file_selected)
            button_layout.addWidget(self.recent_combo)
            
            # Update recent files
            self._update_recent_files_combo()
        
        # Clear button
        self.clear_button = QPushButton("Clear")
        self.clear_button.setProperty("buttonStyle", "secondary")
        self.clear_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.clear_button.clicked.connect(self.clear_selection)
        self.clear_button.setEnabled(False)
        button_layout.addWidget(self.clear_button)
        
        self.main_layout.addLayout(button_layout)
        
        # Status row
        self.status_layout = QHBoxLayout()
        self.status_layout.setSpacing(8)
        
        # Current file label
        self.current_file_label = QLabel("No file selected")
        self.current_file_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.current_file_label.setWordWrap(True)
        self.status_layout.addWidget(self.current_file_label, 1)
        
        # Validation indicator
        self.validation_indicator = QLabel()
        self.validation_indicator.setFixedSize(20, 20)
        self.validation_indicator.setAlignment(Qt.AlignCenter)
        self.validation_indicator.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
        self.status_layout.addWidget(self.validation_indicator)
        
        self.main_layout.addLayout(self.status_layout)
    
    def _setup_styles(self):
        """Apply styles to the widget components."""
        # Title styling
        if hasattr(self, 'title_label'):
            self.title_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                    font-weight: bold;
                    margin-bottom: 4px;
                }}
            """)
        
        # Drop zone styling
        self._update_drop_zone_style(False)
        
        # Hint label styling
        if hasattr(self, 'hint_label'):
            self.hint_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                    font-style: italic;
                }}
            """)
        
        # Status label styling
        self._update_status_display()
    
    def _setup_drag_drop(self):
        """Configure drag and drop functionality."""
        self.setAcceptDrops(True)
        self.drop_zone.mousePressEvent = self._on_drop_zone_click
    
    def _update_drop_zone_style(self, drag_active: bool = False):
        """Update drop zone styling based on drag state."""
        if drag_active:
            # Active drag styling
            self.drop_zone.setStyleSheet(f"""
                QFrame {{
                    background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR}20;
                    border: 2px dashed {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                    border-radius: 8px;
                }}
            """)
            self.drop_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                    font-weight: bold;
                }}
            """)
        else:
            # Normal styling
            self.drop_zone.setStyleSheet(f"""
                QFrame {{
                    background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                    border: 2px dashed {AnalyticsRunnerStylesheet.BORDER_COLOR};
                    border-radius: 8px;
                }}
                QFrame:hover {{
                    border-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                    background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
                }}
            """)
            self.drop_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
                }}
            """)
    
    def _update_status_display(self):
        """Update the status display based on current state."""
        if not self._current_file:
            self.current_file_label.setText("No file selected")
            self.current_file_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                    font-style: italic;
                }}
            """)
            self.validation_indicator.setText("")
            self.validation_indicator.setStyleSheet("")
            self.clear_button.setEnabled(False)
        else:
            # Show file name and path
            file_name = os.path.basename(self._current_file)
            file_dir = os.path.dirname(self._current_file)
            
            self.current_file_label.setText(f"{file_name}\n{file_dir}")
            self.current_file_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
                }}
            """)
            self.clear_button.setEnabled(True)
            
            # Update validation indicator
            if self._is_valid:
                self.validation_indicator.setText("✓")
                self.validation_indicator.setStyleSheet(f"""
                    QLabel {{
                        color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR};
                        font-weight: bold;
                        background-color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR}20;
                        border-radius: 10px;
                    }}
                """)
            else:
                self.validation_indicator.setText("⚠")
                self.validation_indicator.setStyleSheet(f"""
                    QLabel {{
                        color: {AnalyticsRunnerStylesheet.WARNING_COLOR};
                        font-weight: bold;
                        background-color: {AnalyticsRunnerStylesheet.WARNING_COLOR}20;
                        border-radius: 10px;
                    }}
                """)
    
    def _update_recent_files_combo(self):
        """Update the recent files dropdown."""
        if not hasattr(self, 'recent_combo'):
            return
        
        self.recent_combo.clear()
        self.recent_combo.addItem("Recent files...")
        
        for file_path in self._recent_files[:self.max_recent_files]:
            if os.path.exists(file_path):
                file_name = os.path.basename(file_path)
                self.recent_combo.addItem(file_name, file_path)
    
    def _validate_file(self, file_path: str) -> tuple[bool, str]:
        """
        Validate a file path.
        
        Args:
            file_path: Path to validate
            
        Returns:
            Tuple of (is_valid, message)
        """
        if not file_path:
            return False, "No file specified"
        
        if not os.path.exists(file_path):
            return False, "File does not exist"
        
        if not os.path.isfile(file_path):
            return False, "Path is not a file"
        
        # Check file extension
        if self.accepted_extensions:
            file_ext = Path(file_path).suffix.lower()
            if file_ext not in [ext.lower() for ext in self.accepted_extensions]:
                return False, f"File type not accepted. Expected: {', '.join(self.accepted_extensions)}"
        
        # Custom validation callback
        if self.validation_callback:
            try:
                return self.validation_callback(file_path)
            except Exception as e:
                return False, f"Validation error: {str(e)}"
        
        return True, "File is valid"
    
    def _perform_validation(self):
        """Perform file validation (called by timer to debounce)."""
        if not self._current_file:
            return
        
        is_valid, message = self._validate_file(self._current_file)
        
        if self._is_valid != is_valid:
            self._is_valid = is_valid
            self._update_status_display()
            self.validationChanged.emit(is_valid)
        
        # Set tooltip with validation message
        self.validation_indicator.setToolTip(message)
        
        logger.debug(f"File validation: {is_valid} - {message}")
    
    # Event handlers
    def _on_drop_zone_click(self, event):
        """Handle click on drop zone."""
        self._browse_file()
    
    def _browse_file(self):
        """Open file browser dialog."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {self.title}",
            "",
            self.file_filters
        )
        
        if file_path:
            self.set_file(file_path)
    
    def _on_recent_file_selected(self, text: str):
        """Handle recent file selection."""
        if not hasattr(self, 'recent_combo') or not text:
            return
        
        # Get the file path from combo data
        current_index = self.recent_combo.currentIndex()
        if current_index > 0:  # Skip the "Recent files..." item
            file_path = self.recent_combo.itemData(current_index)
            if file_path and os.path.exists(file_path):
                self.set_file(file_path)
    
    # Drag and drop event handlers
    def dragEnterEvent(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].isLocalFile():
                file_path = urls[0].toLocalFile()
                
                # Check file extension if specified
                if self.accepted_extensions:
                    file_ext = Path(file_path).suffix.lower()
                    if file_ext in [ext.lower() for ext in self.accepted_extensions]:
                        event.acceptProposedAction()
                        self._drag_active = True
                        self._update_drop_zone_style(True)
                        return
                else:
                    event.acceptProposedAction()
                    self._drag_active = True
                    self._update_drop_zone_style(True)
                    return
        
        event.ignore()
    
    def dragLeaveEvent(self, event):
        """Handle drag leave event."""
        self._drag_active = False
        self._update_drop_zone_style(False)
    
    def dropEvent(self, event: QDropEvent):
        """Handle drop event."""
        self._drag_active = False
        self._update_drop_zone_style(False)
        
        if event.mimeData().hasUrls():
            urls = event.mimeData().urls()
            if len(urls) == 1 and urls[0].isLocalFile():
                file_path = urls[0].toLocalFile()
                self.set_file(file_path)
                event.acceptProposedAction()
                return
        
        event.ignore()
    
    # Public interface
    def set_file(self, file_path: str):
        """
        Set the current file.
        
        Args:
            file_path: Path to the file
        """
        if file_path == self._current_file:
            return
        
        old_file = self._current_file
        self._current_file = file_path
        
        # Update display
        self._update_status_display()
        
        # Start validation timer (debounced)
        self._validation_timer.start(300)  # 300ms delay
        
        # Emit signals
        if old_file != file_path:
            self.fileChanged.emit(file_path)
        
        self.fileSelected.emit(file_path)
        
        logger.info(f"File selected: {os.path.basename(file_path)}")
    
    def get_file(self) -> str:
        """Get the current file path."""
        return self._current_file
    
    def is_valid(self) -> bool:
        """Check if the current file is valid."""
        return self._is_valid
    
    def clear_selection(self):
        """Clear the current file selection."""
        old_file = self._current_file
        self._current_file = ""
        self._is_valid = False
        
        self._update_status_display()
        
        if old_file:
            self.fileChanged.emit("")
        
        logger.debug("File selection cleared")
    
    def set_recent_files(self, recent_files: List[str]):
        """
        Set the recent files list.
        
        Args:
            recent_files: List of recent file paths
        """
        self._recent_files = recent_files
        self._update_recent_files_combo()
    
    def add_recent_file(self, file_path: str):
        """
        Add a file to the recent files list.
        
        Args:
            file_path: Path to add to recent files
        """
        if file_path in self._recent_files:
            self._recent_files.remove(file_path)
        
        self._recent_files.insert(0, file_path)
        self._recent_files = self._recent_files[:self.max_recent_files]
        
        self._update_recent_files_combo()
    
    # Properties
    @property
    def current_file(self) -> str:
        """Current file path property."""
        return self._current_file
    
    @property
    def validation_status(self) -> tuple[bool, str]:
        """Current validation status property."""
        if self._current_file:
            return self._validate_file(self._current_file)
        return False, "No file selected"

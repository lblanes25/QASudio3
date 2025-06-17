"""
Clickable label widget that emits a signal when clicked.
Part of Phase 2, Task 1 for Secondary Source File Integration.
"""

from PySide6.QtWidgets import QLabel
from PySide6.QtCore import Signal
from PySide6.QtGui import QMouseEvent, QCursor
from PySide6.QtCore import Qt


class ClickableLabel(QLabel):
    """A QLabel that emits a clicked signal when clicked."""
    
    # Signal emitted when the label is clicked
    clicked = Signal()
    
    def __init__(self, text: str = "", parent=None):
        """
        Initialize the clickable label.
        
        Args:
            text: Initial text for the label
            parent: Parent widget
        """
        super().__init__(text, parent)
        
        # Make it look clickable
        self.setCursor(QCursor(Qt.PointingHandCursor))
        
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
    
    def enterEvent(self, event):
        """Handle mouse enter event to provide visual feedback."""
        # Store original style to restore later
        if not hasattr(self, '_original_style'):
            self._original_style = self.styleSheet()
        
        # Add underline on hover for better UX
        current_style = self.styleSheet()
        if current_style and "text-decoration" not in current_style:
            self.setStyleSheet(current_style + "; text-decoration: underline;")
        elif not current_style:
            self.setStyleSheet("text-decoration: underline;")
            
    def leaveEvent(self, event):
        """Handle mouse leave event to restore original style."""
        if hasattr(self, '_original_style'):
            self.setStyleSheet(self._original_style)
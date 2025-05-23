"""
Central stylesheet for the Audit Rule Builder UI
Provides consistent styling across all components
"""

from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt

class Stylesheet:
    """Central styling class for the Audit Rule Builder"""
    
    # Color constants
    PRIMARY_COLOR = "#016FD0"  # RGB: 1, 111, 208
    TEXT_COLOR = "#333333"
    BACKGROUND_COLOR = "#FFFFFF"
    INPUT_BACKGROUND = "#F5F5F5"
    BORDER_COLOR = "#E0E0E0"
    HOVER_COLOR = "#0158B3"  # Slightly darker blue
    DISABLED_COLOR = "#CCCCCC"
    SUCCESS_COLOR = "#28A745"
    ERROR_COLOR = "#DC3545"
    WARNING_COLOR = "#FFC107"
    
    # Font sizes
    REGULAR_FONT_SIZE = 14
    HEADER_FONT_SIZE = 16
    TITLE_FONT_SIZE = 20
    
    # Spacing
    STANDARD_SPACING = 12
    FORM_SPACING = 16
    SECTION_SPACING = 24
    
    # Widget dimensions
    BUTTON_HEIGHT = 32
    INPUT_HEIGHT = 32
    HEADER_HEIGHT = 48
    
    @staticmethod
    def get_regular_font():
        """Get the standard font for regular text"""
        font = QFont("Segoe UI", Stylesheet.REGULAR_FONT_SIZE)
        return font
    
    @staticmethod
    def get_header_font():
        """Get the font for headers"""
        font = QFont("Segoe UI", Stylesheet.HEADER_FONT_SIZE)
        font.setBold(True)
        return font
    
    @staticmethod
    def get_title_font():
        """Get the font for main titles"""
        font = QFont("Segoe UI", Stylesheet.TITLE_FONT_SIZE)
        font.setBold(True)
        return font
    
    @staticmethod
    def get_mono_font():
        """Get monospace font for code/formula editing"""
        font = QFont("Consolas", Stylesheet.REGULAR_FONT_SIZE)
        if not font.exactMatch():
            font = QFont("Courier New", Stylesheet.REGULAR_FONT_SIZE)
        return font
    
    @staticmethod
    def get_global_stylesheet():
        """Get the global stylesheet for the entire application"""
        return f"""
        QMainWindow {{
            background-color: {Stylesheet.BACKGROUND_COLOR};
            color: {Stylesheet.TEXT_COLOR};
        }}
        
        QWidget {{
            background-color: {Stylesheet.BACKGROUND_COLOR};
            color: {Stylesheet.TEXT_COLOR};
            font-family: 'Segoe UI';
            font-size: {Stylesheet.REGULAR_FONT_SIZE}px;
        }}
        
        QLabel {{
            color: {Stylesheet.TEXT_COLOR};
            font-size: {Stylesheet.REGULAR_FONT_SIZE}px;
        }}
        
        QLineEdit {{
            background-color: {Stylesheet.INPUT_BACKGROUND};
            border: 1px solid {Stylesheet.BORDER_COLOR};
            border-radius: 4px;
            padding: 6px 8px;
            font-size: {Stylesheet.REGULAR_FONT_SIZE}px;
            min-height: {Stylesheet.INPUT_HEIGHT - 16}px;
            max-height: {Stylesheet.INPUT_HEIGHT}px;
        }}
        
        QLineEdit:focus {{
            border: 2px solid {Stylesheet.PRIMARY_COLOR};
        }}
        
        QTextEdit, QPlainTextEdit {{
            background-color: {Stylesheet.INPUT_BACKGROUND};
            border: 1px solid {Stylesheet.BORDER_COLOR};
            border-radius: 4px;
            padding: 8px;
            font-size: {Stylesheet.REGULAR_FONT_SIZE}px;
        }}
        
        QTextEdit:focus, QPlainTextEdit:focus {{
            border: 2px solid {Stylesheet.PRIMARY_COLOR};
        }}
        
        QPushButton {{
            background-color: {Stylesheet.PRIMARY_COLOR};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 8px 16px;
            font-size: {Stylesheet.REGULAR_FONT_SIZE}px;
            min-height: {Stylesheet.BUTTON_HEIGHT - 16}px;
            font-weight: 500;
        }}
        
        QPushButton:hover {{
            background-color: {Stylesheet.HOVER_COLOR};
        }}
        
        QPushButton:pressed {{
            background-color: {Stylesheet.HOVER_COLOR};
        }}
        
        QPushButton:disabled {{
            background-color: {Stylesheet.DISABLED_COLOR};
            color: #666666;
        }}
        
        QComboBox {{
            background-color: {Stylesheet.INPUT_BACKGROUND};
            border: 1px solid {Stylesheet.BORDER_COLOR};
            border-radius: 4px;
            padding: 6px 8px;
            font-size: {Stylesheet.REGULAR_FONT_SIZE}px;
            min-height: {Stylesheet.INPUT_HEIGHT - 16}px;
        }}
        
        QComboBox:focus {{
            border: 2px solid {Stylesheet.PRIMARY_COLOR};
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 20px;
        }}
        
        QComboBox::down-arrow {{
            image: none;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 4px solid {Stylesheet.TEXT_COLOR};
            margin-right: 6px;
        }}
        
        QScrollArea {{
            border: 1px solid {Stylesheet.BORDER_COLOR};
            border-radius: 4px;
            background-color: {Stylesheet.BACKGROUND_COLOR};
        }}
        
        QScrollBar:vertical {{
            background-color: {Stylesheet.INPUT_BACKGROUND};
            width: 12px;
            border-radius: 6px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {Stylesheet.BORDER_COLOR};
            border-radius: 6px;
            min-height: 20px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {Stylesheet.PRIMARY_COLOR};
        }}
        
        QFrame {{
            border: 1px solid {Stylesheet.BORDER_COLOR};
        }}
        
        QGroupBox {{
            font-weight: bold;
            border: 1px solid {Stylesheet.BORDER_COLOR};
            border-radius: 4px;
            margin-top: 8px;
            padding-top: 8px;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 8px;
            padding: 0 4px 0 4px;
            color: {Stylesheet.PRIMARY_COLOR};
        }}
        
        QStatusBar {{
            background-color: {Stylesheet.INPUT_BACKGROUND};
            border-top: 1px solid {Stylesheet.BORDER_COLOR};
            color: {Stylesheet.TEXT_COLOR};
        }}
        
        QMenuBar {{
            background-color: {Stylesheet.BACKGROUND_COLOR};
            border-bottom: 1px solid {Stylesheet.BORDER_COLOR};
        }}
        
        QMenuBar::item {{
            background-color: transparent;
            padding: 4px 8px;
        }}
        
        QMenuBar::item:selected {{
            background-color: {Stylesheet.PRIMARY_COLOR};
            color: white;
        }}
        
        QMenu {{
            background-color: {Stylesheet.BACKGROUND_COLOR};
            border: 1px solid {Stylesheet.BORDER_COLOR};
        }}
        
        QMenu::item {{
            padding: 4px 16px;
        }}
        
        QMenu::item:selected {{
            background-color: {Stylesheet.PRIMARY_COLOR};
            color: white;
        }}
        """
    
    @staticmethod
    def get_toggle_button_style():
        """Special style for toggle buttons (Simple/Advanced)"""
        return f"""
        QPushButton {{
            background-color: {Stylesheet.INPUT_BACKGROUND};
            color: {Stylesheet.TEXT_COLOR};
            border: 1px solid {Stylesheet.BORDER_COLOR};
            border-radius: 4px;
            padding: 8px 16px;
            font-size: {Stylesheet.REGULAR_FONT_SIZE}px;
            min-height: {Stylesheet.BUTTON_HEIGHT - 16}px;
            font-weight: 500;
        }}
        
        QPushButton:checked {{
            background-color: {Stylesheet.PRIMARY_COLOR};
            color: white;
            border: 1px solid {Stylesheet.PRIMARY_COLOR};
        }}
        
        QPushButton:hover {{
            background-color: {Stylesheet.HOVER_COLOR};
            color: white;
        }}
        
        QPushButton:checked:hover {{
            background-color: {Stylesheet.HOVER_COLOR};
        }}
        """
    
    @staticmethod
    def get_panel_style():
        """Style for panels and grouped sections"""
        return f"""
        QWidget {{
            background-color: {Stylesheet.BACKGROUND_COLOR};
            border: 1px solid {Stylesheet.BORDER_COLOR};
            border-radius: 4px;
            padding: {Stylesheet.FORM_SPACING}px;
        }}
        """
    
    @staticmethod
    def get_section_header_style():
        """Style for section headers"""
        return f"""
        QLabel {{
            color: {Stylesheet.PRIMARY_COLOR};
            font-size: {Stylesheet.HEADER_FONT_SIZE}px;
            font-weight: bold;
            border-bottom: 1px solid {Stylesheet.BORDER_COLOR};
            padding-bottom: 4px;
            margin-bottom: 8px;
        }}
        """
    
    @staticmethod
    def get_validation_message_style(message_type="info"):
        """Style for validation messages"""
        colors = {
            "success": Stylesheet.SUCCESS_COLOR,
            "error": Stylesheet.ERROR_COLOR,
            "warning": Stylesheet.WARNING_COLOR,
            "info": Stylesheet.PRIMARY_COLOR
        }
        
        color = colors.get(message_type, Stylesheet.PRIMARY_COLOR)
        
        return f"""
        QLabel {{
            color: {color};
            font-size: {Stylesheet.REGULAR_FONT_SIZE - 1}px;
            padding: 4px 8px;
            border-radius: 4px;
            background-color: {color}20;
            border: 1px solid {color};
        }}
        """
"""
Analytics Runner Stylesheet
Extends the base stylesheet for Analytics Runner specific styling
"""

from PySide6.QtGui import QFont, QColor
from PySide6.QtCore import Qt

class AnalyticsRunnerStylesheet:
    """Stylesheet specifically for Analytics Runner application"""

    # Color constants - keeping consistent with base stylesheet
    PRIMARY_COLOR = "#016FD0"  # RGB: 1, 111, 208
    TEXT_COLOR = "#333333"
    BACKGROUND_COLOR = "#FFFFFF"
    INPUT_BACKGROUND = "#F5F5F5"
    BORDER_COLOR = "#E0E0E0"
    HOVER_COLOR = "#0158B3"
    DISABLED_COLOR = "#CCCCCC"
    SUCCESS_COLOR = "#28A745"
    ERROR_COLOR = "#DC3545"
    WARNING_COLOR = "#FFC107"
    INFO_COLOR = "#17A2B8"

    # Additional colors for Analytics Runner
    PANEL_BACKGROUND = "#FAFAFA"
    ACCENT_COLOR = "#E3F2FD"
    DARK_TEXT = "#2C3E50"
    LIGHT_TEXT = "#6C757D"

    # Font sizes
    REGULAR_FONT_SIZE = 14
    HEADER_FONT_SIZE = 16
    TITLE_FONT_SIZE = 20
    SMALL_FONT_SIZE = 12

    # Spacing
    STANDARD_SPACING = 12
    FORM_SPACING = 16
    SECTION_SPACING = 24

    # Widget dimensions
    BUTTON_HEIGHT = 36
    INPUT_HEIGHT = 32
    HEADER_HEIGHT = 48
    TOOLBAR_HEIGHT = 44

    @staticmethod
    def get_fonts():
        """Get all font definitions"""
        fonts = {
            'regular': QFont("Segoe UI", AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE),
            'header': QFont("Segoe UI", AnalyticsRunnerStylesheet.HEADER_FONT_SIZE),
            'title': QFont("Segoe UI", AnalyticsRunnerStylesheet.TITLE_FONT_SIZE),
            'small': QFont("Segoe UI", AnalyticsRunnerStylesheet.SMALL_FONT_SIZE),
            'mono': QFont("Consolas", AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE)
        }

        # Set font weights
        fonts['header'].setBold(True)
        fonts['title'].setBold(True)

        # Fallback for mono font
        if not fonts['mono'].exactMatch():
            fonts['mono'] = QFont("Courier New", AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE)

        return fonts

    @staticmethod
    def get_global_stylesheet():
        """Get the comprehensive stylesheet for Analytics Runner"""
        return f"""
        /* Main Application Styling */
        QMainWindow {{
            background-color: {AnalyticsRunnerStylesheet.PANEL_BACKGROUND};
            color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
        }}
        
        QWidget {{
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
            font-family: 'Segoe UI';
            font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
        }}
        
        /* Labels and Text */
        QLabel {{
            color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
            font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            background-color: transparent;
        }}
        
        /* Input Fields */
        QLineEdit {{
            background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 6px;
            padding: 8px 12px;
            font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            min-height: {AnalyticsRunnerStylesheet.INPUT_HEIGHT - 16}px;
            selection-background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
        }}
        
        QLineEdit:focus {{
            border: 2px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
        }}
        
        QLineEdit:disabled {{
            background-color: {AnalyticsRunnerStylesheet.DISABLED_COLOR}40;
            color: {AnalyticsRunnerStylesheet.DISABLED_COLOR};
        }}
        
        /* Text Areas */
        QTextEdit, QPlainTextEdit {{
            background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 6px;
            padding: 12px;
            font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            selection-background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
        }}
        
        QTextEdit:focus, QPlainTextEdit:focus {{
            border: 2px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
        }}
        
        /* Buttons */
        QPushButton {{
            background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            color: white;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            font-weight: 600;
            min-height: {AnalyticsRunnerStylesheet.BUTTON_HEIGHT - 20}px;
        }}
        
        QPushButton:hover {{
            background-color: {AnalyticsRunnerStylesheet.HOVER_COLOR};
            transform: translateY(-1px);
        }}
        
        QPushButton:pressed {{
            background-color: {AnalyticsRunnerStylesheet.HOVER_COLOR};
            transform: translateY(0px);
        }}
        
        QPushButton:disabled {{
            background-color: {AnalyticsRunnerStylesheet.DISABLED_COLOR};
            color: #666666;
        }}
        
        /* Secondary Button Style */
        QPushButton[buttonStyle="secondary"] {{
            background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
        }}
        
        QPushButton[buttonStyle="secondary"]:hover {{
            background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
            border-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
        }}
        
        /* Combo Boxes */
        QComboBox {{
            background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 6px;
            padding: 8px 12px;
            font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            min-height: {AnalyticsRunnerStylesheet.INPUT_HEIGHT - 16}px;
        }}
        
        QComboBox:focus {{
            border: 2px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
        }}
        
        QComboBox::drop-down {{
            border: none;
            width: 24px;
            padding-right: 4px;
        }}
        
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {AnalyticsRunnerStylesheet.TEXT_COLOR};
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 6px;
            selection-background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            selection-color: white;
        }}
        
        /* Tabs */
        QTabWidget::pane {{
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 6px;
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            margin-top: 4px;
        }}
        
        QTabBar::tab {{
            background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            padding: 10px 20px;
            margin-right: 2px;
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            border-bottom: none;
        }}
        
        QTabBar::tab:selected {{
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            font-weight: 500;
            border-bottom: 2px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
        }}
        
        QTabBar::tab:hover:!selected {{
            background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
        }}
        
        /* Splitter */
        QSplitter::handle {{
            background-color: {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 2px;
        }}
        
        QSplitter::handle:horizontal {{
            width: 6px;
            margin: 4px 0px;
        }}
        
        QSplitter::handle:vertical {{
            height: 6px;
            margin: 0px 4px;
        }}
        
        QSplitter::handle:hover {{
            background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
        }}
        
        /* Scroll Areas and Scroll Bars */
        QScrollArea {{
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 6px;
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
        }}
        
        QScrollBar:vertical {{
            background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            width: 14px;
            border-radius: 7px;
            margin: 0px;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 7px;
            min-height: 20px;
            margin: 2px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
        }}
        
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
            border: none;
            background: none;
        }}
        
        /* Group Boxes */
        QGroupBox {{
            font-weight: 500;
            font-size: {AnalyticsRunnerStylesheet.HEADER_FONT_SIZE}px;
            color: {AnalyticsRunnerStylesheet.DARK_TEXT};
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 6px;
            margin-top: 12px;
            padding-top: 12px;
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 12px;
            padding: 0 8px;
            color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
        }}
        
        /* Status Bar */
        QStatusBar {{
            background-color: {AnalyticsRunnerStylesheet.PANEL_BACKGROUND};
            border-top: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
            padding: 4px 8px;
        }}
        
        QStatusBar::item {{
            border: none;
        }}
        
        /* Progress Bar */
        QProgressBar {{
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 4px;
            text-align: center;
            background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
            font-weight: 500;
        }}
        
        QProgressBar::chunk {{
            background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            border-radius: 3px;
        }}
        
        /* Menu Bar */
        QMenuBar {{
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            border-bottom: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            padding: 4px 0px;
        }}
        
        QMenuBar::item {{
            background-color: transparent;
            padding: 6px 12px;
            border-radius: 4px;
            margin: 0px 2px;
        }}
        
        QMenuBar::item:selected {{
            background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            color: white;
        }}
        
        /* Menus */
        QMenu {{
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 6px;
            padding: 4px 0px;
        }}
        
        QMenu::item {{
            padding: 8px 20px;
            margin: 2px 4px;
            border-radius: 4px;
        }}
        
        QMenu::item:selected {{
            background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            color: white;
        }}
        
        QMenu::separator {{
            height: 1px;
            background-color: {AnalyticsRunnerStylesheet.BORDER_COLOR};
            margin: 4px 8px;
        }}
        
        /* Tool Bar */
        QToolBar {{
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            border-bottom: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            spacing: 8px;
            padding: 6px;
        }}
        
        QToolBar::separator {{
            background-color: {AnalyticsRunnerStylesheet.BORDER_COLOR};
            width: 1px;
            margin: 4px 2px;
        }}
        
        /* Tool Buttons in Toolbar */
        QToolButton {{
            background-color: transparent;
            color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
            border: 1px solid transparent;
            border-radius: 4px;
            padding: 6px 10px;
            font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
        }}
        
        QToolButton:hover {{
            background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
            border-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
        }}
        
        QToolButton:pressed {{
            background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            color: white;
        }}
        
        QToolButton:disabled {{
            color: {AnalyticsRunnerStylesheet.DISABLED_COLOR};
        }}
        """

    @staticmethod
    def get_panel_stylesheet():
        """Stylesheet for main panels"""
        return f"""
        QWidget {{
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 8px;
            padding: {AnalyticsRunnerStylesheet.FORM_SPACING}px;
        }}
        """

    @staticmethod
    def get_header_stylesheet():
        """Stylesheet for section headers"""
        return f"""
        QLabel {{
            color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            font-size: {AnalyticsRunnerStylesheet.HEADER_FONT_SIZE}px;
            font-weight: bold;
            border-bottom: 2px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
            padding-bottom: 6px;
            margin-bottom: 12px;
            background-color: transparent;
        }}
        """

    @staticmethod
    def get_info_panel_stylesheet():
        """Stylesheet for info/status panels"""
        return f"""
        QWidget {{
            background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
            border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR}40;
            border-radius: 6px;
            padding: 12px;
        }}
        
        QLabel {{
            color: {AnalyticsRunnerStylesheet.DARK_TEXT};
            background-color: transparent;
        }}
        """

    @staticmethod
    def get_success_style():
        """Success message styling"""
        return f"""
        QLabel {{
            color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR};
            background-color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR}20;
            border: 1px solid {AnalyticsRunnerStylesheet.SUCCESS_COLOR};
            border-radius: 4px;
            padding: 8px 12px;
            font-weight: 500;
        }}
        """

    @staticmethod
    def get_error_style():
        """Error message styling"""
        return f"""
        QLabel {{
            color: {AnalyticsRunnerStylesheet.ERROR_COLOR};
            background-color: {AnalyticsRunnerStylesheet.ERROR_COLOR}20;
            border: 1px solid {AnalyticsRunnerStylesheet.ERROR_COLOR};
            border-radius: 4px;
            padding: 8px 12px;
            font-weight: 500;
        }}
        """

    @staticmethod
    def get_warning_style():
        """Warning message styling"""
        return f"""
        QLabel {{
            color: {AnalyticsRunnerStylesheet.WARNING_COLOR};
            background-color: {AnalyticsRunnerStylesheet.WARNING_COLOR}20;
            border: 1px solid {AnalyticsRunnerStylesheet.WARNING_COLOR};
            border-radius: 4px;
            padding: 8px 12px;
            font-weight: 500;
        }}
        """

    @staticmethod
    def get_table_stylesheet():
        """Stylesheet specifically for QTableWidget with proper headers and sizing"""
        return f"""
        /* Table Widget */
        QTableWidget {{
            gridline-color: {AnalyticsRunnerStylesheet.BORDER_COLOR};
            background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
            alternate-background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
            selection-background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR}30;
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 6px;
        }}

        /* Table Items */
        QTableWidget::item {{
            padding: 6px 8px;
            border: none;
        }}

        QTableWidget::item:selected {{
            background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR}40;
            color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
        }}

        /* Table Headers - Enhanced for better visibility and sizing */
        QTableWidget QHeaderView::section {{
            background-color: #E3F2FD;  /* Light blue background */
            color: #000000;  /* Force black text for maximum contrast */
            border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
            border-radius: 0px;
            padding: 10px 16px;  /* Increased padding for better spacing */
            font-weight: bold;
            font-size: {AnalyticsRunnerStylesheet.REGULAR_FONT_SIZE}px;
            min-height: 40px;  /* Increased minimum height */
            max-height: 60px;  /* Increased maximum height */
            text-align: center;
        }}

        /* Specific styling for horizontal headers */
        QTableWidget QHeaderView::section:horizontal {{
            color: #000000 !important;  /* Force black text with !important */
            background-color: #E3F2FD !important;  /* Light blue background with !important */
            border-bottom: 2px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR};  /* Accent border */
        }}

        /* Hover effect for headers */
        QTableWidget QHeaderView::section:horizontal:hover {{
            background-color: #BBDEFB !important;  /* Slightly darker blue on hover */
            color: #000000 !important;
        }}

        /* Ensure header view itself has proper sizing */
        QTableWidget QHeaderView {{
            font-weight: bold;
            background-color: transparent;
        }}

        /* Override any conflicting styles */
        QTableWidget QHeaderView::section:first {{
            border-left: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
        }}

        QTableWidget QHeaderView::section:last {{
            border-right: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
        }}
        """
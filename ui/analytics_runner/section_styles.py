"""
Section Styles for State-Aware UI
Consistent styling for different section states using AnalyticsRunnerStylesheet
"""

from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PySide6.QtCore import Qt
from ui.common.stylesheet import AnalyticsRunnerStylesheet


class SectionStyles:
    """Consistent styling for section states"""
    
    # Base style matching existing sections
    _BASE_STYLE = """
        QWidget {{
            background-color: {bg_color};
            border: 1px solid {border_color};
            border-radius: 6px;
            padding: {padding}px;
        }}
    """
    
    # Section backgrounds using existing color scheme
    # Complete sections have subtle green border
    SECTION_COMPLETE = _BASE_STYLE.format(
        bg_color=AnalyticsRunnerStylesheet.ACCENT_COLOR,
        border_color=AnalyticsRunnerStylesheet.SUCCESS_COLOR,
        padding=AnalyticsRunnerStylesheet.STANDARD_SPACING
    )
    
    # Incomplete sections match existing style exactly
    SECTION_INCOMPLETE = f"""
        QWidget {{
            background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
            border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR}40;
            border-radius: 6px;
            padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
        }}
    """
    
    # Error sections have light pink background
    SECTION_ERROR = _BASE_STYLE.format(
        bg_color="#FFF0F0",  # Light red
        border_color=AnalyticsRunnerStylesheet.ERROR_COLOR,
        padding=AnalyticsRunnerStylesheet.STANDARD_SPACING
    )
    
    # Warning sections have light yellow background
    SECTION_WARNING = _BASE_STYLE.format(
        bg_color="#FFFBF0",  # Light yellow
        border_color=AnalyticsRunnerStylesheet.WARNING_COLOR,
        padding=AnalyticsRunnerStylesheet.STANDARD_SPACING
    )
    
    # Headers with status icons - using existing font styles
    HEADER_COMPLETE = f"""
        QLabel {{
            color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR};
            font-weight: bold;
            background-color: transparent;
        }}
    """
    
    HEADER_INCOMPLETE = f"""
        QLabel {{
            color: {AnalyticsRunnerStylesheet.DARK_TEXT};
            font-weight: bold;
            background-color: transparent;
        }}
    """
    
    HEADER_ERROR = f"""
        QLabel {{
            color: {AnalyticsRunnerStylesheet.ERROR_COLOR};
            font-weight: bold;
            background-color: transparent;
        }}
    """
    
    # Status labels
    STATUS_LABEL = """
        QLabel {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 12px;
            background-color: transparent;
        }
    """


def create_status_icon(status: str) -> QLabel:
    """Create a subtle status icon label"""
    icon_label = QLabel()
    icon_label.setFixedSize(16, 16)
    icon_label.setAlignment(Qt.AlignCenter)
    
    if status == "complete":
        icon_label.setText("✓")
        icon_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR}; font-size: 12px; font-weight: bold; background-color: transparent;")
        icon_label.setToolTip("Complete")
    elif status == "incomplete":
        icon_label.setText("•")
        icon_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; font-size: 12px; background-color: transparent;")
        icon_label.setToolTip("Incomplete")
    elif status == "error":
        icon_label.setText("✗")
        icon_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.ERROR_COLOR}; font-size: 12px; font-weight: bold; background-color: transparent;")
        icon_label.setToolTip("Error")
    elif status == "warning":
        icon_label.setText("!")
        icon_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.WARNING_COLOR}; font-size: 12px; font-weight: bold; background-color: transparent;")
        icon_label.setToolTip("Warning")
    
    return icon_label


def create_section_header(title: str, status: str = "incomplete") -> QWidget:
    """Create a section header with status indicator"""
    header_widget = QWidget()
    header_widget.setStyleSheet("background-color: transparent;")
    
    layout = QHBoxLayout(header_widget)
    layout.setContentsMargins(0, 0, 0, 8)
    layout.setSpacing(8)
    
    # Status icon
    status_icon = create_status_icon(status)
    layout.addWidget(status_icon)
    
    # Title
    title_label = QLabel(title)
    title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
    title_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.DARK_TEXT}; background-color: transparent;")
    layout.addWidget(title_label)
    
    # Status text (optional)
    status_label = QLabel()
    status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; background-color: transparent; font-size: 12px;")
    layout.addWidget(status_label)
    
    layout.addStretch()
    
    # Store references for updates
    header_widget.status_icon = status_icon
    header_widget.title_label = title_label
    header_widget.status_label = status_label
    
    return header_widget


def update_section_header(header_widget: QWidget, status: str, status_text: str = ""):
    """Update a section header's status"""
    if hasattr(header_widget, 'status_icon'):
        # Update icon
        new_icon = create_status_icon(status)
        header_widget.status_icon.setText(new_icon.text())
        header_widget.status_icon.setStyleSheet(new_icon.styleSheet())
        header_widget.status_icon.setToolTip(new_icon.toolTip())
    
    if hasattr(header_widget, 'title_label'):
        # Update title style
        if status == "complete":
            header_widget.title_label.setStyleSheet(SectionStyles.HEADER_COMPLETE)
        elif status == "error":
            header_widget.title_label.setStyleSheet(SectionStyles.HEADER_ERROR)
        else:
            header_widget.title_label.setStyleSheet(SectionStyles.HEADER_INCOMPLETE)
    
    if hasattr(header_widget, 'status_label'):
        # Update status text
        header_widget.status_label.setText(status_text)
        if status == "complete":
            header_widget.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR}; background-color: transparent; font-size: 12px;")
        elif status == "error":
            header_widget.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.ERROR_COLOR}; background-color: transparent; font-size: 12px;")
        else:
            header_widget.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; background-color: transparent; font-size: 12px;")
"""
Minimal Section Styles for State-Aware UI
Subtle styling that matches existing AnalyticsRunnerStylesheet
"""

from PySide6.QtWidgets import QLabel, QWidget, QHBoxLayout
from PySide6.QtCore import Qt
from ui.common.stylesheet import AnalyticsRunnerStylesheet


class SectionStyles:
    """Minimal styling for section states - only changes border color subtly"""
    
    # All sections use the same base style from existing sections
    # Only the border color changes slightly
    
    # Complete sections - subtle green tint to border
    SECTION_COMPLETE = f"""
        QWidget {{
            background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
            border: 1px solid {AnalyticsRunnerStylesheet.SUCCESS_COLOR}30;
            border-radius: 6px;
            padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
        }}
    """
    
    # Incomplete sections - exactly matches existing style
    SECTION_INCOMPLETE = f"""
        QWidget {{
            background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
            border: 1px solid {AnalyticsRunnerStylesheet.PRIMARY_COLOR}40;
            border-radius: 6px;
            padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
        }}
    """
    
    # Error sections - subtle red tint to border
    SECTION_ERROR = f"""
        QWidget {{
            background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
            border: 1px solid {AnalyticsRunnerStylesheet.ERROR_COLOR}50;
            border-radius: 6px;
            padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
        }}
    """
    
    # Warning sections - subtle yellow tint to border
    SECTION_WARNING = f"""
        QWidget {{
            background-color: {AnalyticsRunnerStylesheet.ACCENT_COLOR};
            border: 1px solid {AnalyticsRunnerStylesheet.WARNING_COLOR}50;
            border-radius: 6px;
            padding: {AnalyticsRunnerStylesheet.STANDARD_SPACING}px;
        }}
    """


def create_section_header(title: str, status: str = "incomplete") -> QWidget:
    """Create a simple section header without status icons"""
    header_widget = QWidget()
    header_widget.setStyleSheet("background-color: transparent;")
    
    layout = QHBoxLayout(header_widget)
    layout.setContentsMargins(0, 0, 0, 8)
    layout.setSpacing(12)
    
    # Title
    title_label = QLabel(title)
    title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
    title_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.DARK_TEXT}; background-color: transparent;")
    layout.addWidget(title_label)
    
    # Status text (optional) - subtle and small
    status_label = QLabel()
    status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; background-color: transparent; font-size: 12px;")
    layout.addWidget(status_label)
    
    layout.addStretch()
    
    # Store references for updates
    header_widget.title_label = title_label
    header_widget.status_label = status_label
    
    return header_widget


def update_section_header(header_widget: QWidget, status: str, status_text: str = ""):
    """Update a section header's status text only"""
    if hasattr(header_widget, 'status_label'):
        # Update status text with appropriate color
        header_widget.status_label.setText(status_text)
        if status == "complete":
            header_widget.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.SUCCESS_COLOR}; background-color: transparent; font-size: 12px; font-style: italic;")
        elif status == "error":
            header_widget.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.ERROR_COLOR}; background-color: transparent; font-size: 12px; font-style: italic;")
        else:
            header_widget.status_label.setStyleSheet(f"color: {AnalyticsRunnerStylesheet.LIGHT_TEXT}; background-color: transparent; font-size: 12px; font-style: italic;")


# For backward compatibility
create_status_icon = lambda status: QLabel()  # Returns empty label
"""
ProgressWidget - Reusable Progress Display Component
Provides animated progress tracking with status messages and cancellation support
"""

import time
from typing import Optional, Callable
import logging

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QProgressBar, QFrame, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont

from ui.common.stylesheet import AnalyticsRunnerStylesheet

logger = logging.getLogger(__name__)


class ProgressWidget(QWidget):
    """
    Reusable progress widget with animation, status messages, and cancellation.
    
    Features:
    - Animated progress bar with smooth transitions
    - Status message display with timestamp
    - Cancel operation button with confirmation
    - Estimated time remaining calculation
    - Pulse animation for indeterminate progress
    - Customizable styling and layout options
    """
    
    # Signals
    cancelRequested = Signal()  # Emitted when user clicks cancel
    progressChanged = Signal(int)  # Emitted when progress value changes
    statusChanged = Signal(str)   # Emitted when status message changes
    
    def __init__(self, 
                 title: str = "Progress",
                 show_percentage: bool = True,
                 show_cancel_button: bool = True,
                 show_time_estimate: bool = True,
                 show_timestamp: bool = False,
                 animate_transitions: bool = True,
                 cancel_callback: Optional[Callable[[], bool]] = None,
                 parent: Optional[QWidget] = None):
        """
        Initialize the progress widget.
        
        Args:
            title: Title text displayed above the progress bar
            show_percentage: Whether to show percentage in progress bar
            show_cancel_button: Whether to show cancel operation button
            show_time_estimate: Whether to show estimated time remaining
            show_timestamp: Whether to show timestamp with status messages
            animate_transitions: Whether to animate progress transitions
            cancel_callback: Function called when cancel is requested (returns bool for confirmation)
            parent: Parent widget
        """
        super().__init__(parent)
        
        # Configuration
        self.title = title
        self.show_percentage = show_percentage
        self.show_cancel_button = show_cancel_button
        self.show_time_estimate = show_time_estimate
        self.show_timestamp = show_timestamp
        self.animate_transitions = animate_transitions
        self.cancel_callback = cancel_callback
        
        # State tracking
        self._current_progress = 0
        self._current_status = ""
        self._is_active = False
        self._is_indeterminate = False
        self._start_time = None
        self._last_progress_time = None
        self._progress_history = []  # For ETA calculation
        self._is_cancelled = False
        
        # Animation
        self._progress_animation = None
        self._pulse_timer = None
        
        # Setup UI
        self._setup_ui()
        self._setup_styles()
        self._setup_animations()
        
        # Initially hidden
        self.setVisible(False)
        
        logger.debug(f"ProgressWidget initialized: {title}")
    
    def _setup_ui(self):
        """Setup the user interface components."""
        # Main layout
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Container frame for styling
        self.container = QFrame()
        self.container.setFrameStyle(QFrame.StyledPanel)
        self.container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        # Container layout
        container_layout = QVBoxLayout(self.container)
        container_layout.setSpacing(8)
        container_layout.setContentsMargins(16, 12, 16, 12)
        
        # Title and cancel button row
        title_row = QHBoxLayout()
        title_row.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        
        # Title label
        self.title_label = QLabel(self.title)
        self.title_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        title_row.addWidget(self.title_label)
        
        title_row.addStretch()
        
        # Cancel button
        if self.show_cancel_button:
            self.cancel_button = QPushButton("Cancel")
            self.cancel_button.setProperty("buttonStyle", "secondary")
            self.cancel_button.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
            self.cancel_button.clicked.connect(self._on_cancel_clicked)
            self.cancel_button.setVisible(False)  # Hidden until operation starts
            title_row.addWidget(self.cancel_button)
        
        container_layout.addLayout(title_row)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(self.show_percentage)
        self.progress_bar.setMinimumHeight(24)
        container_layout.addWidget(self.progress_bar)
        
        # Status and time row
        status_row = QHBoxLayout()
        status_row.setSpacing(AnalyticsRunnerStylesheet.STANDARD_SPACING)
        
        # Status label
        self.status_label = QLabel("Ready")
        self.status_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['regular'])
        self.status_label.setWordWrap(True)
        status_row.addWidget(self.status_label, 1)
        
        # Time estimate label
        if self.show_time_estimate:
            self.time_label = QLabel("")
            self.time_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['small'])
            self.time_label.setAlignment(Qt.AlignRight)
            self.time_label.setMinimumWidth(100)
            status_row.addWidget(self.time_label)
        
        container_layout.addLayout(status_row)
        
        self.main_layout.addWidget(self.container)
    
    def _setup_styles(self):
        """Apply styles to the widget components."""
        # Container styling
        self.container.setStyleSheet(f"""
            QFrame {{
                background-color: {AnalyticsRunnerStylesheet.BACKGROUND_COLOR};
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 8px;
            }}
        """)
        
        # Title styling
        self.title_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                font-weight: bold;
                background-color: transparent;
                border: none;
            }}
        """)
        
        # Progress bar styling
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid {AnalyticsRunnerStylesheet.BORDER_COLOR};
                border-radius: 6px;
                text-align: center;
                background-color: {AnalyticsRunnerStylesheet.INPUT_BACKGROUND};
                color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
                font-weight: 500;
                font-size: {AnalyticsRunnerStylesheet.SMALL_FONT_SIZE}px;
            }}
            
            QProgressBar::chunk {{
                background-color: {AnalyticsRunnerStylesheet.PRIMARY_COLOR};
                border-radius: 5px;
                margin: 1px;
            }}
        """)
        
        # Status label styling
        self.status_label.setStyleSheet(f"""
            QLabel {{
                color: {AnalyticsRunnerStylesheet.TEXT_COLOR};
                background-color: transparent;
                border: none;
            }}
        """)
        
        # Time label styling
        if hasattr(self, 'time_label'):
            self.time_label.setStyleSheet(f"""
                QLabel {{
                    color: {AnalyticsRunnerStylesheet.LIGHT_TEXT};
                    background-color: transparent;
                    border: none;
                }}
            """)
    
    def _setup_animations(self):
        """Setup progress animations."""
        if not self.animate_transitions:
            return
        
        # Progress bar animation
        self._progress_animation = QPropertyAnimation(self.progress_bar, b"value")
        self._progress_animation.setDuration(300)  # 300ms transition
        self._progress_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # Pulse timer for indeterminate progress
        self._pulse_timer = QTimer()
        self._pulse_timer.timeout.connect(self._update_pulse)
        self._pulse_value = 0
        self._pulse_direction = 1
    
    def _update_pulse(self):
        """Update pulse animation for indeterminate progress."""
        if not self._is_indeterminate:
            return
        
        # Create a pulsing effect by moving the progress value back and forth
        self._pulse_value += self._pulse_direction * 5
        
        if self._pulse_value >= 100:
            self._pulse_value = 100
            self._pulse_direction = -1
        elif self._pulse_value <= 0:
            self._pulse_value = 0
            self._pulse_direction = 1
        
        # Update progress bar without triggering our progress change logic
        self.progress_bar.setValue(self._pulse_value)
    
    def _format_time(self, seconds: float) -> str:
        """
        Format time duration in human-readable format.
        
        Args:
            seconds: Time in seconds
            
        Returns:
            Formatted time string
        """
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
    
    def _calculate_eta(self) -> Optional[float]:
        """
        Calculate estimated time of arrival based on progress history.
        
        Returns:
            Estimated seconds remaining, or None if cannot calculate
        """
        if not self._progress_history or self._current_progress <= 0:
            return None
        
        # Use recent progress data (last 5 data points)
        recent_history = self._progress_history[-5:]
        
        if len(recent_history) < 2:
            return None
        
        # Calculate average progress rate
        time_span = recent_history[-1][0] - recent_history[0][0]
        progress_span = recent_history[-1][1] - recent_history[0][1]
        
        if time_span <= 0 or progress_span <= 0:
            return None
        
        progress_rate = progress_span / time_span  # progress per second
        remaining_progress = 100 - self._current_progress
        
        if progress_rate > 0:
            return remaining_progress / progress_rate
        
        return None
    
    def _update_time_display(self):
        """Update the time estimate display."""
        if not hasattr(self, 'time_label') or not self._is_active:
            return
        
        current_time = time.time()
        
        if self._start_time:
            elapsed = current_time - self._start_time
            elapsed_str = f"Elapsed: {self._format_time(elapsed)}"
            
            # Calculate ETA
            eta_seconds = self._calculate_eta()
            if eta_seconds is not None and eta_seconds > 0:
                eta_str = f"ETA: {self._format_time(eta_seconds)}"
                self.time_label.setText(f"{elapsed_str} | {eta_str}")
            else:
                self.time_label.setText(elapsed_str)
        else:
            self.time_label.setText("")
    
    def _on_cancel_clicked(self):
        """Handle cancel button click."""
        # Call cancel callback if provided
        if self.cancel_callback:
            try:
                should_cancel = self.cancel_callback()
                if not should_cancel:
                    return  # User chose not to cancel
            except Exception as e:
                logger.error(f"Error in cancel callback: {e}")
                return
        
        self._is_cancelled = True
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText("Cancelling...")
        
        # Update status
        self.set_status("Cancellation requested...")
        
        # Emit signal
        self.cancelRequested.emit()
        
        logger.info("Progress operation cancellation requested")
    
    # Public interface
    def start_progress(self, status: str = "Starting..."):
        """
        Start a progress operation.
        
        Args:
            status: Initial status message
        """
        self._is_active = True
        self._is_cancelled = False
        self._current_progress = 0
        self._start_time = time.time()
        self._last_progress_time = self._start_time
        self._progress_history = []
        
        # Show widget and components
        self.setVisible(True)
        if hasattr(self, 'cancel_button'):
            self.cancel_button.setVisible(True)
            self.cancel_button.setEnabled(True)
            self.cancel_button.setText("Cancel")
        
        # Set initial state
        self.set_progress(0)
        self.set_status(status)
        
        # Start time update timer
        self._time_timer = QTimer()
        self._time_timer.timeout.connect(self._update_time_display)
        self._time_timer.start(1000)  # Update every second
        
        logger.info("Progress operation started")
    
    def set_progress(self, value: int, status: str = None):
        """
        Update progress value and optionally status.
        
        Args:
            value: Progress value (0-100)
            status: Optional status message
        """
        if not self._is_active:
            return
        
        # Clamp value to valid range
        value = max(0, min(100, value))
        
        # Stop indeterminate mode if it was active
        if self._is_indeterminate:
            self._is_indeterminate = False
            if self._pulse_timer:
                self._pulse_timer.stop()
        
        # Update progress history for ETA calculation
        current_time = time.time()
        self._progress_history.append((current_time, value))
        
        # Keep only recent history (last 10 points)
        if len(self._progress_history) > 10:
            self._progress_history = self._progress_history[-10:]
        
        # Animate progress change
        if self.animate_transitions and self._progress_animation and abs(value - self._current_progress) > 1:
            self._progress_animation.stop()
            self._progress_animation.setStartValue(self._current_progress)
            self._progress_animation.setEndValue(value)
            self._progress_animation.start()
        else:
            self.progress_bar.setValue(value)
        
        old_progress = self._current_progress
        self._current_progress = value
        self._last_progress_time = current_time
        
        # Update status if provided
        if status is not None:
            self.set_status(status)
        
        # Update time display
        self._update_time_display()
        
        # Emit signal
        if old_progress != value:
            self.progressChanged.emit(value)
        
        logger.debug(f"Progress updated: {value}%")
    
    def set_status(self, status: str):
        """
        Update status message.
        
        Args:
            status: Status message to display
        """
        if self.show_timestamp:
            import datetime
            timestamp = datetime.datetime.now().strftime("%H:%M:%S")
            formatted_status = f"[{timestamp}] {status}"
        else:
            formatted_status = status
        
        self.status_label.setText(formatted_status)
        
        old_status = self._current_status
        self._current_status = status
        
        # Emit signal
        if old_status != status:
            self.statusChanged.emit(status)
        
        logger.debug(f"Status updated: {status}")
    
    def set_indeterminate(self, indeterminate: bool = True, status: str = None):
        """
        Set indeterminate progress mode (pulsing animation).
        
        Args:
            indeterminate: Whether to enable indeterminate mode
            status: Optional status message
        """
        if not self._is_active:
            return
        
        self._is_indeterminate = indeterminate
        
        if indeterminate:
            # Start pulse animation
            if self._pulse_timer:
                self._pulse_timer.start(50)  # Update every 50ms for smooth animation
            self.progress_bar.setTextVisible(False)
        else:
            # Stop pulse animation
            if self._pulse_timer:
                self._pulse_timer.stop()
            self.progress_bar.setTextVisible(self.show_percentage)
        
        # Update status if provided
        if status is not None:
            self.set_status(status)
        
        logger.debug(f"Indeterminate mode: {indeterminate}")
    
    def complete_progress(self, status: str = "Completed"):
        """
        Complete the progress operation.
        
        Args:
            status: Completion status message
        """
        if not self._is_active:
            return
        
        # Set to 100% if not cancelled
        if not self._is_cancelled:
            self.set_progress(100, status)
        
        # Stop timers
        if hasattr(self, '_time_timer'):
            self._time_timer.stop()
        if self._pulse_timer:
            self._pulse_timer.stop()
        
        # Update final time display
        self._update_time_display()
        
        # Hide cancel button
        if hasattr(self, 'cancel_button'):
            self.cancel_button.setVisible(False)
        
        self._is_active = False
        self._is_indeterminate = False
        
        logger.info(f"Progress operation completed: {status}")
    
    def hide_progress(self):
        """Hide the progress widget."""
        if hasattr(self, '_time_timer'):
            self._time_timer.stop()
        if self._pulse_timer:
            self._pulse_timer.stop()
        
        self.setVisible(False)
        self._is_active = False
        self._is_indeterminate = False
        
        logger.debug("Progress widget hidden")
    
    def reset_progress(self):
        """Reset progress to initial state."""
        self.complete_progress("Ready")
        self.hide_progress()
        
        # Reset state
        self._current_progress = 0
        self._current_status = ""
        self._is_cancelled = False
        self._start_time = None
        self._progress_history = []
        
        # Reset UI
        self.progress_bar.setValue(0)
        self.status_label.setText("Ready")
        if hasattr(self, 'time_label'):
            self.time_label.setText("")
        
        logger.debug("Progress widget reset")
    
    # Properties
    @property
    def current_progress(self) -> int:
        """Current progress value property."""
        return self._current_progress
    
    @property
    def current_status(self) -> str:
        """Current status message property."""
        return self._current_status
    
    @property
    def is_active(self) -> bool:
        """Whether progress is currently active property."""
        return self._is_active
    
    @property
    def is_cancelled(self) -> bool:
        """Whether progress was cancelled property."""
        return self._is_cancelled
    
    @property
    def elapsed_time(self) -> Optional[float]:
        """Elapsed time in seconds since start property."""
        if self._start_time:
            return time.time() - self._start_time
        return None

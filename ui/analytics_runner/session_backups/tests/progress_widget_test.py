#!/usr/bin/env python3
"""
Test application for ProgressWidget
"""

import sys
import time
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QWidget, 
    QLabel, QPushButton, QHBoxLayout, QGroupBox, 
    QCheckBox, QSpinBox, QTextEdit
)
from PySide6.QtCore import Qt, QTimer, QThread, Signal

# Add parent directory to path for imports (development testing)
sys.path.insert(0, str(Path(__file__).parent))

from progress_widget import ProgressWidget
from analytics_runner_stylesheet import AnalyticsRunnerStylesheet


class MockWorker(QThread):
    """Mock worker thread to simulate long-running operations."""
    
    progressUpdate = Signal(int, str)
    finished = Signal(str)
    
    def __init__(self, duration_seconds=10, steps=20):
        super().__init__()
        self.duration_seconds = duration_seconds
        self.steps = steps
        self.should_stop = False
    
    def run(self):
        """Simulate work with progress updates."""
        step_duration = self.duration_seconds / self.steps
        
        for i in range(self.steps + 1):
            if self.should_stop:
                self.finished.emit("Operation cancelled")
                return
            
            progress = int((i / self.steps) * 100)
            
            if i == 0:
                status = "Initializing..."
            elif i < self.steps // 4:
                status = f"Loading data ({i}/{self.steps})..."
            elif i < self.steps // 2:
                status = f"Processing rules ({i}/{self.steps})..."
            elif i < (3 * self.steps) // 4:
                status = f"Analyzing results ({i}/{self.steps})..."
            elif i < self.steps:
                status = f"Generating reports ({i}/{self.steps})..."
            else:
                status = "Finalizing..."
            
            self.progressUpdate.emit(progress, status)
            
            if i < self.steps:
                time.sleep(step_duration)
        
        self.finished.emit("Operation completed successfully")
    
    def stop(self):
        """Stop the worker thread."""
        self.should_stop = True


class ProgressWidgetTestWindow(QMainWindow):
    """Test window for ProgressWidget."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ProgressWidget Test")
        self.setMinimumSize(700, 600)
        
        # Apply global stylesheet
        self.setStyleSheet(AnalyticsRunnerStylesheet.get_global_stylesheet())
        
        # Worker thread
        self.worker = None
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        title = QLabel("ProgressWidget Test")
        title.setFont(AnalyticsRunnerStylesheet.get_fonts()['title'])
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Configuration group
        config_group = QGroupBox("Configuration")
        config_layout = QVBoxLayout(config_group)
        
        # Checkboxes for features
        checkbox_layout = QHBoxLayout()
        
        self.show_percentage_cb = QCheckBox("Show Percentage")
        self.show_percentage_cb.setChecked(True)
        checkbox_layout.addWidget(self.show_percentage_cb)
        
        self.show_cancel_cb = QCheckBox("Show Cancel Button")
        self.show_cancel_cb.setChecked(True)
        checkbox_layout.addWidget(self.show_cancel_cb)
        
        self.show_time_cb = QCheckBox("Show Time Estimate")
        self.show_time_cb.setChecked(True)
        checkbox_layout.addWidget(self.show_time_cb)
        
        self.show_timestamp_cb = QCheckBox("Show Timestamps")
        self.show_timestamp_cb.setChecked(False)
        checkbox_layout.addWidget(self.show_timestamp_cb)
        
        config_layout.addLayout(checkbox_layout)
        
        # Duration setting
        duration_layout = QHBoxLayout()
        duration_layout.addWidget(QLabel("Duration (seconds):"))
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(3, 60)
        self.duration_spin.setValue(10)
        duration_layout.addWidget(self.duration_spin)
        duration_layout.addStretch()
        config_layout.addLayout(duration_layout)
        
        layout.addWidget(config_group)
        
        # Progress widgets
        self.create_progress_widgets(layout)
        
        # Control buttons
        self.create_control_buttons(layout)
        
        # Log area
        log_label = QLabel("Event Log:")
        log_label.setFont(AnalyticsRunnerStylesheet.get_fonts()['header'])
        layout.addWidget(log_label)
        
        self.log_area = QTextEdit()
        self.log_area.setMaximumHeight(120)
        self.log_area.setFont(AnalyticsRunnerStylesheet.get_fonts()['mono'])
        layout.addWidget(self.log_area)
        
        self.log("ProgressWidget test application started")
    
    def create_progress_widgets(self, layout):
        """Create the progress widget instances."""
        # Standard progress widget
        self.standard_progress = ProgressWidget(
            title="Standard Progress",
            show_percentage=True,
            show_cancel_button=True,
            show_time_estimate=True,
            cancel_callback=self.confirm_cancel
        )
        self.standard_progress.cancelRequested.connect(self.on_cancel_requested)
        self.standard_progress.progressChanged.connect(self.on_progress_changed)
        self.standard_progress.statusChanged.connect(self.on_status_changed)
        layout.addWidget(self.standard_progress)
        
        # Minimal progress widget (no extras)
        self.minimal_progress = ProgressWidget(
            title="Minimal Progress",
            show_percentage=False,
            show_cancel_button=False,
            show_time_estimate=False,
            show_timestamp=False,
            animate_transitions=False
        )
        layout.addWidget(self.minimal_progress)
        
        # Indeterminate progress widget
        self.indeterminate_progress = ProgressWidget(
            title="Indeterminate Progress",
            show_percentage=False,
            show_cancel_button=True,
            show_time_estimate=False
        )
        layout.addWidget(self.indeterminate_progress)
    
    def create_control_buttons(self, layout):
        """Create control buttons."""
        button_layout = QHBoxLayout()
        
        # Start normal progress
        self.start_button = QPushButton("Start Normal Progress")
        self.start_button.clicked.connect(self.start_normal_progress)
        button_layout.addWidget(self.start_button)
        
        # Start indeterminate progress
        self.indeterminate_button = QPushButton("Start Indeterminate")
        self.indeterminate_button.clicked.connect(self.start_indeterminate_progress)
        button_layout.addWidget(self.indeterminate_button)
        
        # Manual progress test
        self.manual_button = QPushButton("Manual Progress Test")
        self.manual_button.clicked.connect(self.start_manual_progress)
        button_layout.addWidget(self.manual_button)
        
        # Reset all
        self.reset_button = QPushButton("Reset All")
        self.reset_button.clicked.connect(self.reset_all_progress)
        button_layout.addWidget(self.reset_button)
        
        layout.addLayout(button_layout)
    
    def confirm_cancel(self) -> bool:
        """Cancel confirmation callback."""
        from PySide6.QtWidgets import QMessageBox
        
        reply = QMessageBox.question(
            self,
            "Confirm Cancel",
            "Are you sure you want to cancel the operation?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        confirmed = reply == QMessageBox.Yes
        self.log(f"Cancel confirmation: {'Confirmed' if confirmed else 'Cancelled'}")
        return confirmed
    
    def start_normal_progress(self):
        """Start a normal progress simulation."""
        if self.worker and self.worker.isRunning():
            self.log("Operation already in progress")
            return
        
        # Update progress widget configuration
        self.update_progress_config()
        
        # Start worker thread
        duration = self.duration_spin.value()
        self.worker = MockWorker(duration_seconds=duration, steps=20)
        self.worker.progressUpdate.connect(self.update_standard_progress)
        self.worker.finished.connect(self.on_worker_finished)
        
        # Start progress
        self.standard_progress.start_progress("Initializing operation...")
        self.worker.start()
        
        # Update button states
        self.start_button.setEnabled(False)
        self.log(f"Started normal progress simulation ({duration}s)")
    
    def start_indeterminate_progress(self):
        """Start indeterminate progress simulation."""
        self.indeterminate_progress.start_progress("Processing...")
        self.indeterminate_progress.set_indeterminate(True, "Analyzing data...")
        
        # Auto-complete after 5 seconds
        QTimer.singleShot(5000, lambda: self.indeterminate_progress.complete_progress("Analysis complete"))
        
        self.log("Started indeterminate progress simulation")
    
    def start_manual_progress(self):
        """Start manual progress test with timer."""
        self.minimal_progress.start_progress("Manual test starting...")
        
        # Create timer for manual updates
        self.manual_timer = QTimer()
        self.manual_progress_value = 0
        self.manual_timer.timeout.connect(self.update_manual_progress)
        self.manual_timer.start(200)  # Update every 200ms
        
        self.log("Started manual progress test")
    
    def update_manual_progress(self):
        """Update manual progress."""
        self.manual_progress_value += 2
        
        if self.manual_progress_value <= 100:
            status_messages = [
                "Preparing...", "Loading...", "Processing...", 
                "Analyzing...", "Finalizing...", "Complete"
            ]
            status_index = min(self.manual_progress_value // 20, len(status_messages) - 1)
            status = status_messages[status_index]
            
            self.minimal_progress.set_progress(self.manual_progress_value, status)
        else:
            self.manual_timer.stop()
            self.minimal_progress.complete_progress("Manual test completed")
    
    def update_progress_config(self):
        """Update progress widget configuration from UI."""
        # Note: In a real implementation, you'd recreate the widget with new settings
        # For this test, we'll just log the current settings
        config = {
            'show_percentage': self.show_percentage_cb.isChecked(),
            'show_cancel': self.show_cancel_cb.isChecked(),
            'show_time': self.show_time_cb.isChecked(),
            'show_timestamp': self.show_timestamp_cb.isChecked()
        }
        self.log(f"Configuration: {config}")
    
    def update_standard_progress(self, progress: int, status: str):
        """Update standard progress widget."""
        self.standard_progress.set_progress(progress, status)
    
    def on_worker_finished(self, message: str):
        """Handle worker thread completion."""
        self.standard_progress.complete_progress(message)
        self.start_button.setEnabled(True)
        self.log(f"Worker finished: {message}")
    
    def on_cancel_requested(self):
        """Handle cancel request."""
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)  # Wait up to 3 seconds
            self.log("Operation cancelled by user")
        
        self.start_button.setEnabled(True)
    
    def on_progress_changed(self, progress: int):
        """Handle progress change."""
        self.log(f"Progress: {progress}%")
    
    def on_status_changed(self, status: str):
        """Handle status change."""
        self.log(f"Status: {status}")
    
    def reset_all_progress(self):
        """Reset all progress widgets."""
        self.standard_progress.reset_progress()
        self.minimal_progress.reset_progress()
        self.indeterminate_progress.reset_progress()
        
        # Stop worker if running
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        
        # Stop manual timer
        if hasattr(self, 'manual_timer'):
            self.manual_timer.stop()
        
        self.start_button.setEnabled(True)
        self.log("All progress widgets reset")
    
    def log(self, message: str):
        """Add a message to the log area."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        self.log_area.append(f"[{timestamp}] {message}")
    
    def closeEvent(self, event):
        """Handle window close event."""
        # Stop worker thread
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.worker.wait(3000)
        
        event.accept()


def main():
    """Run the test application."""
    app = QApplication(sys.argv)
    
    window = ProgressWidgetTestWindow()
    window.show()
    
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

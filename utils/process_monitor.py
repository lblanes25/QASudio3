# utils/process_monitor.py

import os
import logging
import time
from typing import Dict, List, Optional, Tuple
import threading

logger = logging.getLogger(__name__)


class ProcessMonitor:
    """
    Utility to monitor system processes, particularly for detecting leaks.
    """

    def __init__(self, process_names=None, check_interval=10):
        """
        Initialize the process monitor.

        Args:
            process_names: List of process names to monitor (e.g., ['excel.exe'])
            check_interval: How often to check process counts (in seconds)
        """
        self.process_names = process_names or ['excel.exe']
        self.check_interval = check_interval
        self.running = False
        self.thread = None
        self.counts = {}
        self._lock = threading.Lock()

    def start(self):
        """Start monitoring processes in a background thread"""
        if self.running:
            return

        self.running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info(f"Process monitor started for: {', '.join(self.process_names)}")

    def stop(self):
        """Stop the monitoring thread"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1.0)
        logger.info("Process monitor stopped")

    def _monitor_loop(self):
        """Main monitoring loop"""
        while self.running:
            try:
                current_counts = self.count_processes(self.process_names)

                with self._lock:
                    for name, count in current_counts.items():
                        if name in self.counts:
                            prev_count = self.counts[name]
                            if count > prev_count + 5:  # Alert on significant increases
                                logger.warning(
                                    f"Process leak detected: {name} count increased from {prev_count} to {count}"
                                )
                        self.counts[name] = count

            except Exception as e:
                logger.error(f"Error in process monitor: {str(e)}")

            time.sleep(self.check_interval)

    def get_current_counts(self):
        """Get current process counts"""
        with self._lock:
            return self.counts.copy()

    @staticmethod
    def count_processes(process_names):
        """
        Count specified processes.

        Args:
            process_names: List of process names to count

        Returns:
            Dictionary mapping process names to counts
        """
        counts = {}

        try:
            # Try to use psutil if available (most accurate)
            import psutil
            for name in process_names:
                count = sum(1 for p in psutil.process_iter() if p.name().lower() == name.lower())
                counts[name] = count

        except ImportError:
            # Fall back to platform-specific commands
            if os.name == 'nt':  # Windows
                import subprocess
                for name in process_names:
                    cmd = f'tasklist /FI "IMAGENAME eq {name}" /NH'
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    # Count lines containing the process name
                    count = result.stdout.count(name)
                    counts[name] = count
            else:  # Unix-like
                import subprocess
                for name in process_names:
                    cmd = f'ps aux | grep "{name}" | grep -v grep | wc -l'
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
                    try:
                        count = int(result.stdout.strip())
                        counts[name] = count
                    except ValueError:
                        counts[name] = 0

        return counts
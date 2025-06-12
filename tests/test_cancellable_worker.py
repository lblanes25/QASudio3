"""
Test cancellable validation worker functionality
Verifies cancellation mechanism works correctly without UI
"""

import sys
import time
import threading
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from PySide6.QtCore import QCoreApplication, QThreadPool
from ui.analytics_runner.cancellable_validation_worker import (
    CancellableValidationWorker, ExecutionStatus
)


def test_cancellation():
    """Test basic cancellation functionality"""
    app = QCoreApplication(sys.argv)
    threadpool = QThreadPool()
    
    print("=== Testing Cancellable Validation Worker ===")
    
    # Create worker
    worker = CancellableValidationWorker(
        pipeline=None,
        data_source="test_data.xlsx",
        sheet_name="Sheet1",
        rule_ids=["test-rule-1", "test-rule-2"],
        generate_reports=False
    )
    
    # Track signals
    status_changes = []
    cancellation_reasons = []
    
    def on_status_changed(status):
        status_changes.append(status)
        print(f"Status changed to: {status}")
        
    def on_cancelled(reason):
        cancellation_reasons.append(reason)
        print(f"Cancelled: {reason}")
        
    def on_session_started(session_id, timestamp):
        print(f"Session started: {session_id} at {timestamp}")
        
    # Connect signals
    worker.signals.statusChanged.connect(on_status_changed)
    worker.signals.cancelled.connect(on_cancelled)
    worker.signals.sessionStarted.connect(on_session_started)
    
    print(f"Initial status: {worker.get_status()}")
    print(f"Session ID: {worker.get_session_id()}")
    
    # Start worker
    threadpool.start(worker)
    
    # Let it run briefly
    time.sleep(0.5)
    
    # Cancel it
    print("\nRequesting cancellation...")
    worker.cancel("Test cancellation")
    
    # Wait for completion
    threadpool.waitForDone(5000)  # 5 second timeout
    
    # Verify results
    print(f"\nFinal status: {worker.get_status()}")
    print(f"Status changes: {status_changes}")
    print(f"Cancellation reasons: {cancellation_reasons}")
    
    # Assertions
    assert worker.is_cancelled(), "Worker should be cancelled"
    assert worker.get_status() == ExecutionStatus.CANCELLED, "Status should be CANCELLED"
    assert ExecutionStatus.ACTIVE in status_changes, "Should have transitioned to ACTIVE"
    assert ExecutionStatus.CANCELLED in status_changes, "Should have transitioned to CANCELLED"
    assert len(cancellation_reasons) > 0, "Should have cancellation reason"
    
    print("\n✓ All tests passed!")
    

def test_immediate_cancellation():
    """Test cancelling before start"""
    print("\n=== Testing Immediate Cancellation ===")
    
    worker = CancellableValidationWorker(
        pipeline=None,
        data_source="test_data.xlsx"
    )
    
    # Cancel before starting
    worker.cancel("Immediate cancellation")
    
    # Track if it starts
    started = []
    worker.signals.started.connect(lambda: started.append(True))
    
    # Run in thread pool
    threadpool = QThreadPool()
    threadpool.start(worker)
    threadpool.waitForDone(1000)
    
    print(f"Worker started: {len(started) > 0}")
    print(f"Final status: {worker.get_status()}")
    
    assert worker.get_status() == ExecutionStatus.CANCELLED, "Should be cancelled"
    print("✓ Immediate cancellation test passed!")


if __name__ == "__main__":
    test_cancellation()
    test_immediate_cancellation()
    print("\n=== All cancellation tests completed successfully! ===")
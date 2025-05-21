from PySide6.QtWidgets import (QWidget)
import pandas as pd
import traceback

from core.rule_engine.rule_evaluator import RuleEvaluator


class RuleTestPanel(QWidget):
    """Panel for testing rules against loaded data."""

    def __init__(self, rule_model, data_loader):
        super().__init__()
        self.rule_model = rule_model
        self.data_loader = data_loader
        self.test_results = None

        # Create rule evaluator
        self.rule_evaluator = RuleEvaluator(rule_manager=rule_model.rule_manager)

        # Set up UI
        self.init_ui()

    def init_ui(self):
        """Initialize the UI components."""
        from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                       QTableView, QTextEdit, QGroupBox, QSplitter)
        from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

        # Main layout
        main_layout = QVBoxLayout(self)

        # Test button
        test_btn = QPushButton("Run Test")
        test_btn.clicked.connect(self.run_test)
        main_layout.addWidget(test_btn)

        # Create splitter for results
        splitter = QSplitter(Qt.Vertical)

        # Results summary group
        summary_group = QGroupBox("Test Results Summary")
        summary_layout = QVBoxLayout(summary_group)

        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        summary_layout.addWidget(self.summary_text)

        splitter.addWidget(summary_group)

        # Failing items group
        failing_group = QGroupBox("Failing Items")
        failing_layout = QVBoxLayout(failing_group)

        # Create table model for failing items
        class FailingItemsModel(QAbstractTableModel):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.dataframe = pd.DataFrame()

            def rowCount(self, parent=QModelIndex()):
                return len(self.dataframe)

            def columnCount(self, parent=QModelIndex()):
                return len(self.dataframe.columns)

            def data(self, index, role=Qt.DisplayRole):
                if not index.isValid() or role != Qt.DisplayRole:
                    return None

                value = self.dataframe.iloc[index.row(), index.column()]
                return str(value)

            def headerData(self, section, orientation, role=Qt.DisplayRole):
                if role != Qt.DisplayRole:
                    return None

                if orientation == Qt.Horizontal:
                    if section < len(self.dataframe.columns):
                        return str(self.dataframe.columns[section])
                    return None

                if orientation == Qt.Vertical:
                    return str(section + 1)

                return None

            def setDataFrame(self, dataframe):
                self.beginResetModel()
                self.dataframe = dataframe
                self.endResetModel()

        self.failing_model = FailingItemsModel()
        self.failing_view = QTableView()
        self.failing_view.setModel(self.failing_model)
        failing_layout.addWidget(self.failing_view)

        splitter.addWidget(failing_group)

        # Set initial splitter sizes
        splitter.setSizes([200, 400])

        main_layout.addWidget(splitter)

    def set_data(self, df):
        """Set the DataFrame for testing."""
        # Store the DataFrame
        self.data_df = df

        # Clear previous test results
        self.summary_text.clear()
        self.failing_model.setDataFrame(pd.DataFrame())

        # Update status
        self.window().statusBar().showMessage("Data loaded for testing")

    def run_test(self):
        """Run the rule test against loaded data."""
        from PySide6.QtWidgets import QMessageBox

        # Check if data is loaded
        data_df = self.data_loader.get_data()
        if data_df.empty:
            QMessageBox.warning(self, "Warning", "No data loaded. Please load data first.")
            return

        # Validate rule
        is_valid, error = self.rule_model.validate()
        if not is_valid:
            QMessageBox.warning(self, "Rule Error", f"Invalid rule: {error}")
            return

        try:
            # Show status message
            self.window().statusBar().showMessage("Running rule test...")

            # Use RuleEvaluator to evaluate the rule
            rule = self.rule_model.current_rule

            # Validate rule against the DataFrame
            is_valid, error = rule.validate_with_dataframe(data_df)
            if not is_valid:
                QMessageBox.warning(self, "Rule Error", f"Rule is not compatible with data: {error}")
                self.window().statusBar().showMessage("Test failed: Rule is not compatible with data")
                return

            # Evaluate the rule
            result = self.rule_evaluator.evaluate_rule(rule, data_df)

            # Store the result
            self.test_results = result

            # Display results
            self.display_results()

            # Update status
            self.window().statusBar().showMessage("Test completed successfully")

        except Exception as e:
            self.window().statusBar().showMessage("Error running test")
            QMessageBox.critical(self, "Error", f"Error testing rule: {str(e)}")
            traceback.print_exc()

    def display_results(self):
        """Display test results in the UI."""
        if not self.test_results:
            return

        # Get result data
        rule = self.test_results.rule
        compliance_status = self.test_results.compliance_status
        metrics = self.test_results.compliance_metrics

        # Extract metrics
        total_count = metrics.get('total_count', 0)
        gc_count = metrics.get('gc_count', 0)
        pc_count = metrics.get('pc_count', 0)
        dnc_count = metrics.get('dnc_count', 0)
        error_count = metrics.get('error_count', 0)

        # Calculate compliance rate
        compliance_rate = gc_count / total_count if total_count > 0 else 0

        # Format summary text
        summary = f"Rule: {rule.name}\n"
        summary += f"Formula: {rule.formula}\n\n"
        summary += f"Status: {compliance_status}\n"
        summary += f"Compliance Rate: {compliance_rate:.2%}\n"
        summary += f"Total Items: {total_count}\n"
        summary += f"Passing Items: {gc_count}\n"
        summary += f"Partially Conforming: {pc_count}\n"
        summary += f"Non-Conforming: {dnc_count}\n"

        if error_count > 0:
            summary += f"Errors: {error_count}\n"

        summary += f"\nThreshold: {rule.threshold:.2%}\n"

        self.summary_text.setText(summary)

        # Show failing items
        failing_df = self.test_results.get_failing_items()
        self.failing_model.setDataFrame(failing_df)

        # Auto-resize columns to content
        for i in range(len(failing_df.columns)):
            self.failing_view.resizeColumnToContents(i)

    def refresh_test_results(self):
        """Refresh the test results display."""
        if self.test_results:
            self.display_results()
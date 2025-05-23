from PySide6.QtWidgets import (QWidget)
import pandas as pd
import traceback

from core.rule_engine.rule_evaluator import RuleEvaluator
from stylesheet import Stylesheet


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
                                       QTableView, QTextEdit, QGroupBox, QSplitter,
                                       QFrame, QWidget)
        from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
        from PySide6.QtGui import QFont, QColor, QPalette

        # Set default font using stylesheet
        self.setFont(Stylesheet.get_regular_font())

        # Main layout with consistent spacing
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(Stylesheet.STANDARD_SPACING)
        main_layout.setContentsMargins(Stylesheet.STANDARD_SPACING, Stylesheet.STANDARD_SPACING,
                                      Stylesheet.STANDARD_SPACING, Stylesheet.STANDARD_SPACING)

        # Header with test button inline
        header_layout = QHBoxLayout()
        
        test_header = QLabel("Rule Test Results")
        test_header.setFont(Stylesheet.get_header_font())
        test_header.setStyleSheet(Stylesheet.get_section_header_style())
        header_layout.addWidget(test_header)
        
        # Test button aligned right
        test_btn = QPushButton("Run Test")
        test_btn.setMaximumWidth(100)
        test_btn.setMinimumHeight(Stylesheet.BUTTON_HEIGHT)
        test_btn.clicked.connect(self.run_test)
        header_layout.addStretch(1)
        header_layout.addWidget(test_btn)
        
        main_layout.addLayout(header_layout)

        # Summary Cards Layout (horizontal row of cards)
        self.summary_cards = QHBoxLayout()
        self.summary_cards.setSpacing(Stylesheet.STANDARD_SPACING)
        
        # Create card-like compliance summary widgets
        self.create_summary_cards()
        main_layout.addLayout(self.summary_cards)
        
        # Add a separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        main_layout.addWidget(separator)
        
        # Results details section
        failing_header = QLabel("Non-Conforming Items")
        failing_header.setFont(QFont("Segoe UI", 10, QFont.Bold))
        main_layout.addWidget(failing_header)

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
                if not index.isValid():
                    return None
                
                if role == Qt.DisplayRole:
                    value = self.dataframe.iloc[index.row(), index.column()]
                    return str(value)
                
                # Add alternating row colors for better readability
                if role == Qt.BackgroundRole:
                    if index.row() % 2 == 0:
                        return QColor(248, 248, 248)  # Light gray
                
                return None

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

        # Create table view with styling
        self.failing_model = FailingItemsModel()
        self.failing_view = QTableView()
        self.failing_view.setModel(self.failing_model)
        self.failing_view.setAlternatingRowColors(True)
        self.failing_view.setShowGrid(False)  # Remove gridlines for cleaner look
        self.failing_view.horizontalHeader().setHighlightSections(False)
        self.failing_view.verticalHeader().setDefaultSectionSize(24)  # Compact rows
        
        main_layout.addWidget(self.failing_view, 1)  # Give table more space
        
        # Hidden summary text for compatibility
        self.summary_text = QTextEdit()
        self.summary_text.setVisible(False)
    
    def create_summary_cards(self):
        """Create card-like widgets for compliance summary statistics."""
        from PySide6.QtWidgets import QLabel, QFrame, QVBoxLayout
        from PySide6.QtGui import QFont, QColor, QPalette
        from PySide6.QtCore import Qt
        
        # Function to create a summary card
        def create_card(title, value="—", color="#FFFFFF"):
            card = QFrame()
            card.setFrameShape(QFrame.StyledPanel)
            card.setAutoFillBackground(True)
            
            # Set background color
            palette = card.palette()
            palette.setColor(QPalette.Window, QColor(color))
            card.setPalette(palette)
            
            layout = QVBoxLayout(card)
            layout.setSpacing(4)
            
            # Title with smaller font
            title_label = QLabel(title)
            title_label.setFont(QFont("Segoe UI", 9))
            title_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(title_label)
            
            # Value with larger font
            value_label = QLabel(value)
            value_label.setFont(QFont("Segoe UI", 16, QFont.Bold))
            value_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(value_label)
            
            return card, value_label
        
        # Total Items card
        self.total_card, self.total_value = create_card("Total Items", "—", "#F0F0F0")
        self.summary_cards.addWidget(self.total_card)
        
        # Passing Items card
        self.passing_card, self.passing_value = create_card("Passing", "—", "#E3F2FD")  # Light blue
        self.summary_cards.addWidget(self.passing_card)
        
        # Partially Conforming card
        self.partial_card, self.partial_value = create_card("Partially Conforming", "—", "#FFF9C4")  # Light yellow
        self.summary_cards.addWidget(self.partial_card)
        
        # Non-Conforming card
        self.nonconf_card, self.nonconf_value = create_card("Non-Conforming", "—", "#FFEBEE")  # Light red
        self.summary_cards.addWidget(self.nonconf_card)
        
        # Compliance Rate card
        self.rate_card, self.rate_value = create_card("Compliance Rate", "—", "#E8F5E9")  # Light green
        self.summary_cards.addWidget(self.rate_card)

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
        
        # Update the summary cards with values
        self.total_value.setText(str(total_count))
        self.passing_value.setText(str(gc_count))
        self.partial_value.setText(str(pc_count))
        self.nonconf_value.setText(str(dnc_count))
        self.rate_value.setText(f"{compliance_rate:.1%}")
        
        # Apply visual indicator on compliance rate card based on threshold
        from PySide6.QtGui import QColor, QPalette
        
        rate_color = "#E8F5E9"  # Default light green
        if compliance_rate < rule.threshold:
            # Below threshold - use light red
            rate_color = "#FFEBEE"
        
        palette = self.rate_card.palette()
        palette.setColor(QPalette.Window, QColor(rate_color))
        self.rate_card.setPalette(palette)

        # Format summary text (for compatibility - now hidden)
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

        # Show failing items in the table
        failing_df = self.test_results.get_failing_items()
        self.failing_model.setDataFrame(failing_df)

        # Auto-resize columns to content
        for i in range(len(failing_df.columns)):
            self.failing_view.resizeColumnToContents(i)

    def refresh_test_results(self):
        """Refresh the test results display."""
        if self.test_results:
            self.display_results()
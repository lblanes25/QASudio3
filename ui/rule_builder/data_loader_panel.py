from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Signal
import pandas as pd
import traceback

class DataLoaderPanel(QWidget):
    """Panel for loading and previewing data."""

    # Signal emitted when data is loaded
    data_loaded = Signal(pd.DataFrame)

    def __init__(self):
        super().__init__()

        # Initialize data
        self.data_df = pd.DataFrame()
        self.file_path = ""

        # Set up UI
        self.init_ui()

    def init_ui(self):
        """Initialize the UI components."""
        from PySide6.QtWidgets import (QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                                       QLineEdit, QTableView, QFileDialog, QComboBox, QWidget)
        from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex

        # Main layout
        main_layout = QVBoxLayout(self)

        # Data source selection
        source_layout = QHBoxLayout()
        source_layout.addWidget(QLabel("Data Source:"))

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setReadOnly(True)
        source_layout.addWidget(self.file_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_data_file)
        source_layout.addWidget(browse_btn)

        main_layout.addLayout(source_layout)

        # Excel sheet selector (shown only for Excel files)
        self.sheet_widget = QWidget()
        self.sheet_layout = QHBoxLayout(self.sheet_widget)
        self.sheet_layout.addWidget(QLabel("Sheet:"))

        self.sheet_combo = QComboBox()
        self.sheet_layout.addWidget(self.sheet_combo)

        self.sheet_widget.setVisible(False)  # Hide initially
        main_layout.addWidget(self.sheet_widget)

        # Data preview
        main_layout.addWidget(QLabel("Data Preview:"))

        # Create table model for data preview
        class DataTableModel(QAbstractTableModel):
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

        self.table_model = DataTableModel()
        self.table_view = QTableView()
        self.table_view.setModel(self.table_model)
        main_layout.addWidget(self.table_view)

        # Refresh button
        refresh_btn = QPushButton("Reload Data")
        refresh_btn.clicked.connect(self.reload_data)
        main_layout.addWidget(refresh_btn)

        # Connect sheet selector
        self.sheet_combo.currentTextChanged.connect(self.load_selected_sheet)

    def browse_data_file(self):
        """Open file dialog to select data file."""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Data File", "",
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            self.file_path = file_path
            self.file_path_edit.setText(file_path)

            # Load the file
            self.load_data_file()

    def load_data_file(self):
        """Load the selected data file."""
        if not self.file_path:
            return

        try:
            # Check file type
            if self.file_path.lower().endswith(('.xlsx', '.xls')):
                # Excel file - show sheet selector
                self.load_excel_sheets()
                self.sheet_layout.setVisible(True)
            else:
                # CSV or other file - load directly
                self.sheet_layout.setVisible(False)
                df = pd.read_csv(self.file_path)
                self.set_data(df)

        except Exception as e:
            # Show error message
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Error loading data file: {str(e)}")
            traceback.print_exc()

    def load_excel_sheets(self):
        """Load sheet names from Excel file."""
        try:
            # Get sheet names
            import openpyxl
            workbook = openpyxl.load_workbook(self.file_path, read_only=True)
            sheet_names = workbook.sheetnames

            # Update sheet selector
            self.sheet_combo.clear()
            self.sheet_combo.addItems(sheet_names)

            # Load first sheet
            if sheet_names:
                self.load_selected_sheet()

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Error loading Excel sheets: {str(e)}")
            traceback.print_exc()

    def load_selected_sheet(self):
        """Load data from selected Excel sheet."""
        if not self.file_path or not self.file_path.lower().endswith(('.xlsx', '.xls')):
            return

        sheet_name = self.sheet_combo.currentText()
        if not sheet_name:
            return

        try:
            # Load sheet data
            df = pd.read_excel(self.file_path, sheet_name=sheet_name)
            self.set_data(df)

        except Exception as e:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(self, "Error", f"Error loading sheet: {str(e)}")
            traceback.print_exc()

    def set_data(self, df):
        """Set the DataFrame and update UI."""
        self.data_df = df

        # Update table model
        self.table_model.setDataFrame(df)

        # Auto-resize columns to content
        for i in range(len(df.columns)):
            self.table_view.resizeColumnToContents(i)

        # Emit signal
        self.data_loaded.emit(df)

    def reload_data(self):
        """Reload data from current file."""
        if self.file_path:
            self.load_data_file()

    def get_data(self):
        """Get the current DataFrame."""
        return self.data_df
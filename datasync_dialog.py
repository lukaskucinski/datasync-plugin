# -*- coding: utf-8 -*-
"""
DataSync Dialog Controller
"""

import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QFileDialog, QMessageBox, QWidget,
    QHBoxLayout, QComboBox, QPushButton, QSizePolicy
)

from .connection_manager import ConnectionManager
from .excel_reader import ExcelReader
from .preview_model import PreviewModel
from .sync_engine import SyncEngine

# Load UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui', 'datasync_dialog.ui'))


class MappingRow(QWidget):
    """Widget for a single column mapping row."""

    def __init__(self, excel_columns, db_columns, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.combo_excel = QComboBox()
        self.combo_excel.addItems(excel_columns)
        self.combo_excel.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.combo_db = QComboBox()
        self.combo_db.addItems(db_columns)
        self.combo_db.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setFixedWidth(80)

        self.layout.addWidget(self.combo_excel)
        self.layout.addWidget(self.combo_db)
        self.layout.addWidget(self.btn_remove)

    def get_mapping(self):
        """Get the current mapping as (excel_col, db_col)."""
        return (self.combo_excel.currentText(), self.combo_db.currentText())


class DataSyncDialog(QDialog, FORM_CLASS):
    """Main dialog for DataSync plugin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)

        # Initialize components
        self.conn_manager = ConnectionManager()
        self.excel_reader = ExcelReader()
        self.preview_model = PreviewModel(self)
        self.sync_engine = None
        self.diff_data = None

        # Mapping rows storage
        self.mapping_rows = []

        # Column data
        self.excel_columns = []
        self.db_columns = []

        # Setup UI
        self._setup_ui()
        self._connect_signals()
        self._load_connections()

    def _setup_ui(self):
        """Initialize UI components."""
        self.tablePreview.setModel(self.preview_model)
        self.progressBar.setValue(0)
        self.progressBar.setVisible(False)

        # Disable controls until data is loaded
        self.comboSheet.setEnabled(False)
        self.comboTable.setEnabled(False)
        self.comboKeyExcel.setEnabled(False)
        self.comboKeyDb.setEnabled(False)
        self.btnAddMapping.setEnabled(False)
        self.btnPreview.setEnabled(False)

        # Rename OK button to Execute
        self.buttonBox.button(self.buttonBox.Ok).setText("Execute Sync")
        self.buttonBox.button(self.buttonBox.Ok).setEnabled(False)

    def _connect_signals(self):
        """Connect UI signals to slots."""
        self.btnBrowse.clicked.connect(self._browse_file)
        self.comboSheet.currentIndexChanged.connect(self._sheet_changed)
        self.btnConnect.clicked.connect(self._connect_database)
        self.comboTable.currentIndexChanged.connect(self._table_changed)
        self.btnAddMapping.clicked.connect(self._add_mapping_row)
        self.btnPreview.clicked.connect(self._generate_preview)
        self.buttonBox.accepted.connect(self._execute_sync)

    def _load_connections(self):
        """Load available PostgreSQL connections."""
        self.comboConnection.clear()
        connections = ConnectionManager.get_available_connections()
        self.comboConnection.addItems(connections)

        if not connections:
            self.labelStatus.setText("No PostgreSQL connections found in QGIS")

    def _browse_file(self):
        """Open file browser to select Excel file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Excel File",
            "",
            "Excel Files (*.xlsx *.xls);;All Files (*)"
        )

        if file_path:
            self.editFilePath.setText(file_path)
            self._load_excel_file(file_path)

    def _load_excel_file(self, file_path):
        """Load Excel file and populate sheet dropdown."""
        try:
            self.excel_reader.file_path = file_path
            sheets = self.excel_reader.get_sheets()

            self.comboSheet.clear()
            self.comboSheet.addItems(sheets)
            self.comboSheet.setEnabled(True)

            if sheets:
                self._sheet_changed()

            self.labelStatus.setText(f"Loaded: {os.path.basename(file_path)}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load Excel file:\n{str(e)}")
            self.labelStatus.setText("Error loading file")

    def _sheet_changed(self):
        """Handle sheet selection change."""
        sheet_name = self.comboSheet.currentText()
        if not sheet_name:
            return

        try:
            self.excel_reader.load_file(self.editFilePath.text(), sheet_name)
            self.excel_columns = self.excel_reader.get_columns()

            # Update key column dropdown
            self.comboKeyExcel.clear()
            self.comboKeyExcel.addItems(self.excel_columns)
            self.comboKeyExcel.setEnabled(True)

            # Clear existing mappings
            self._clear_mappings()

            self._update_ui_state()
            self.labelStatus.setText(f"Sheet '{sheet_name}' loaded - {self.excel_reader.get_row_count()} rows")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load sheet:\n{str(e)}")

    def _connect_database(self):
        """Connect to selected PostgreSQL database."""
        conn_name = self.comboConnection.currentText()
        if not conn_name:
            QMessageBox.warning(self, "Warning", "Please select a connection")
            return

        try:
            self.labelStatus.setText("Connecting...")
            self.conn_manager.connect(conn_name)

            # Load tables
            tables = self.conn_manager.get_tables()
            self.comboTable.clear()

            for schema, table in tables:
                self.comboTable.addItem(f"{schema}.{table}", (schema, table))

            self.comboTable.setEnabled(True)
            self.labelStatus.setText(f"Connected to {conn_name}")

            if tables:
                self._table_changed()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to connect:\n{str(e)}")
            self.labelStatus.setText("Connection failed")

    def _table_changed(self):
        """Handle table selection change."""
        data = self.comboTable.currentData()
        if not data:
            return

        schema, table = data

        try:
            columns = self.conn_manager.get_columns(schema, table)
            self.db_columns = [col['name'] for col in columns]

            # Update key column dropdown
            self.comboKeyDb.clear()
            self.comboKeyDb.addItems(self.db_columns)
            self.comboKeyDb.setEnabled(True)

            # Try to select primary key
            pk_columns = self.conn_manager.get_primary_key(schema, table)
            if pk_columns:
                idx = self.comboKeyDb.findText(pk_columns[0])
                if idx >= 0:
                    self.comboKeyDb.setCurrentIndex(idx)

            # Clear existing mappings
            self._clear_mappings()

            self._update_ui_state()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load columns:\n{str(e)}")

    def _add_mapping_row(self):
        """Add a new column mapping row."""
        if not self.excel_columns or not self.db_columns:
            return

        row = MappingRow(self.excel_columns, self.db_columns, self)
        row.btn_remove.clicked.connect(lambda: self._remove_mapping_row(row))

        self.layoutMappings.addWidget(row)
        self.mapping_rows.append(row)

        self._update_ui_state()

    def _remove_mapping_row(self, row):
        """Remove a mapping row."""
        self.layoutMappings.removeWidget(row)
        self.mapping_rows.remove(row)
        row.deleteLater()

        self._update_ui_state()

    def _clear_mappings(self):
        """Clear all mapping rows."""
        for row in self.mapping_rows:
            self.layoutMappings.removeWidget(row)
            row.deleteLater()
        self.mapping_rows = []

    def _get_column_mapping(self):
        """Get current column mapping as dictionary."""
        mapping = {}
        for row in self.mapping_rows:
            excel_col, db_col = row.get_mapping()
            if excel_col and db_col:
                mapping[excel_col] = db_col
        return mapping

    def _update_ui_state(self):
        """Update UI state based on current selections."""
        has_excel = bool(self.excel_columns)
        has_db = bool(self.db_columns)
        has_mappings = len(self.mapping_rows) > 0

        self.btnAddMapping.setEnabled(has_excel and has_db)
        self.btnPreview.setEnabled(has_excel and has_db and has_mappings)

    def _generate_preview(self):
        """Generate preview of changes."""
        try:
            # Get configuration
            table_data = self.comboTable.currentData()
            if not table_data:
                QMessageBox.warning(self, "Warning", "Please select a table")
                return

            schema, table = table_data
            key_excel = self.comboKeyExcel.currentText()
            key_db = self.comboKeyDb.currentText()
            mapping = self._get_column_mapping()

            if not mapping:
                QMessageBox.warning(self, "Warning", "Please add at least one column mapping")
                return

            # Create sync engine
            self.sync_engine = SyncEngine(self.conn_manager, self)
            self.sync_engine.configure(schema, table, key_excel, key_db, mapping)

            # Connect progress signals
            self.sync_engine.progress_changed.connect(self._on_progress)
            self.sync_engine.status_changed.connect(self._on_status)

            # Show progress
            self.progressBar.setVisible(True)
            self.progressBar.setValue(0)

            # Generate diff
            self.diff_data = self.sync_engine.generate_diff(self.excel_reader)

            # Update preview model
            self.preview_model.set_key_column_name(key_db)
            self.preview_model.set_diff_data(self.diff_data)

            # Resize columns
            self.tablePreview.resizeColumnsToContents()

            # Update summary
            summary = self.sync_engine.get_change_summary(self.diff_data)
            self.labelSummary.setText(
                f"<b>{summary['added']}</b> to add, "
                f"<b>{summary['modified']}</b> to update, "
                f"<b>{summary['unchanged']}</b> unchanged"
            )

            # Enable execute if there are changes
            has_changes = summary['added'] > 0 or summary['modified'] > 0
            self.buttonBox.button(self.buttonBox.Ok).setEnabled(has_changes)

            self.progressBar.setVisible(False)

        except Exception as e:
            self.progressBar.setVisible(False)
            QMessageBox.critical(self, "Error", f"Failed to generate preview:\n{str(e)}")
            self.labelStatus.setText("Preview failed")

    def _execute_sync(self):
        """Execute the sync operation."""
        if not self.diff_data or not self.sync_engine:
            return

        # Confirm execution
        summary = self.sync_engine.get_change_summary(self.diff_data)
        result = QMessageBox.question(
            self,
            "Confirm Sync",
            f"This will:\n"
            f"- Insert {summary['added']} new records\n"
            f"- Update {summary['modified']} existing records\n\n"
            f"Continue?",
            QMessageBox.Yes | QMessageBox.No
        )

        if result != QMessageBox.Yes:
            return

        try:
            self.progressBar.setVisible(True)
            self.progressBar.setValue(0)

            success, message = self.sync_engine.execute_sync(self.diff_data)

            self.progressBar.setVisible(False)

            if success:
                QMessageBox.information(self, "Success", message)
                self.labelStatus.setText("Sync completed successfully")
                # Clear preview after successful sync
                self.preview_model.clear()
                self.diff_data = None
                self.buttonBox.button(self.buttonBox.Ok).setEnabled(False)
                self.labelSummary.setText("")
            else:
                QMessageBox.critical(self, "Error", message)
                self.labelStatus.setText("Sync failed - changes rolled back")

        except Exception as e:
            self.progressBar.setVisible(False)
            QMessageBox.critical(self, "Error", f"Sync failed:\n{str(e)}")
            self.labelStatus.setText("Sync failed")

    def _on_progress(self, current, total):
        """Handle progress update."""
        if total > 0:
            self.progressBar.setValue(int(current * 100 / total))

    def _on_status(self, message):
        """Handle status update."""
        self.labelStatus.setText(message)

    def closeEvent(self, event):
        """Handle dialog close."""
        # Disconnect from database
        self.conn_manager.disconnect()
        # Close Excel reader
        self.excel_reader.close()
        super().closeEvent(event)

# -*- coding: utf-8 -*-
"""
DataSync Dialog Controller
"""

import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog, QFileDialog, QMessageBox, QWidget,
    QHBoxLayout, QVBoxLayout, QComboBox, QPushButton, QSizePolicy,
    QCompleter, QInputDialog, QTableView
)

from .connection_manager import ConnectionManager
from .excel_reader import ExcelReader
from .preview_model import PreviewModel
from .sync_engine import SyncEngine
from .mapping_store import MappingStore

# Load UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'ui', 'datasync_dialog.ui'))


class PreviewDialog(QDialog):
    """Pop-out dialog for full-screen preview."""

    def __init__(self, model, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DataSync Preview")
        self.resize(1000, 600)

        layout = QVBoxLayout(self)
        self.table = QTableView()
        self.table.setModel(model)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        # Resize columns to content
        self.table.resizeColumnsToContents()


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
        self.mapping_store = MappingStore()

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

        # Enhancement 1: Make table dropdown searchable
        self.comboTable.setEditable(True)
        self.comboTable.setInsertPolicy(QComboBox.NoInsert)
        completer = self.comboTable.completer()
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setFilterMode(Qt.MatchContains)

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
        self.btnSaveMapping.clicked.connect(self._save_mapping)
        self.btnLoadMapping.clicked.connect(self._load_mapping)
        self.btnDeleteMapping.clicked.connect(self._delete_mapping)
        self.btnPreview.clicked.connect(self._generate_preview)
        self.btnPopout.clicked.connect(self._popout_preview)
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

            # Clear existing mappings and auto-populate
            self._clear_mappings()
            self._auto_populate_mappings()

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

            # Clear existing mappings and auto-populate
            self._clear_mappings()
            self._auto_populate_mappings()

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

    def _auto_populate_mappings(self):
        """Auto-create mappings for columns with matching names (case-insensitive)."""
        if not self.excel_columns or not self.db_columns:
            return

        db_col_lower = {col.lower(): col for col in self.db_columns}

        for excel_col in self.excel_columns:
            if excel_col.lower() in db_col_lower:
                db_col = db_col_lower[excel_col.lower()]
                row = MappingRow(self.excel_columns, self.db_columns, self)
                row.btn_remove.clicked.connect(lambda checked, r=row: self._remove_mapping_row(r))
                row.combo_excel.setCurrentText(excel_col)
                row.combo_db.setCurrentText(db_col)
                self.layoutMappings.addWidget(row)
                self.mapping_rows.append(row)

    def _save_mapping(self):
        """Save current mapping configuration."""
        if not self.mapping_rows:
            QMessageBox.warning(self, "Warning", "No mappings to save")
            return

        table_data = self.comboTable.currentData()
        if not table_data:
            QMessageBox.warning(self, "Warning", "Please select a table first")
            return

        name, ok = QInputDialog.getText(
            self, "Save Mapping", "Enter a name for this mapping:"
        )
        if not ok or not name.strip():
            return

        schema, table = table_data
        full_table = f"{schema}.{table}"
        key_excel = self.comboKeyExcel.currentText()
        key_db = self.comboKeyDb.currentText()
        column_mappings = self._get_column_mapping()

        # Get required columns
        excel_cols_required = [key_excel] + list(column_mappings.keys())
        db_cols_required = [key_db] + list(column_mappings.values())

        self.mapping_store.save_mapping(
            name.strip(),
            full_table,
            key_excel,
            key_db,
            column_mappings,
            excel_cols_required,
            db_cols_required
        )

        self.labelStatus.setText(f"Mapping '{name.strip()}' saved")

    def _load_mapping(self):
        """Load a saved mapping configuration."""
        table_data = self.comboTable.currentData()
        if not table_data:
            QMessageBox.warning(self, "Warning", "Please select a table first")
            return

        schema, table = table_data
        full_table = f"{schema}.{table}"

        # Get compatible mappings
        compatible = self.mapping_store.get_compatible_mappings(
            full_table,
            self.excel_columns,
            self.db_columns
        )

        if not compatible:
            QMessageBox.information(
                self, "No Mappings",
                "No saved mappings are compatible with current Excel/table columns"
            )
            return

        # Let user select from compatible mappings
        name, ok = QInputDialog.getItem(
            self, "Load Mapping", "Select a mapping:",
            compatible, 0, False
        )
        if not ok or not name:
            return

        # Load the selected mapping
        mapping_data = self.mapping_store.load_mapping(name)
        if not mapping_data:
            QMessageBox.warning(self, "Error", f"Failed to load mapping '{name}'")
            return

        # Apply the mapping
        self._clear_mappings()

        # Set key columns
        idx = self.comboKeyExcel.findText(mapping_data['key_excel'])
        if idx >= 0:
            self.comboKeyExcel.setCurrentIndex(idx)
        idx = self.comboKeyDb.findText(mapping_data['key_db'])
        if idx >= 0:
            self.comboKeyDb.setCurrentIndex(idx)

        # Create mapping rows
        for excel_col, db_col in mapping_data['column_mappings'].items():
            row = MappingRow(self.excel_columns, self.db_columns, self)
            row.btn_remove.clicked.connect(lambda checked, r=row: self._remove_mapping_row(r))
            row.combo_excel.setCurrentText(excel_col)
            row.combo_db.setCurrentText(db_col)
            self.layoutMappings.addWidget(row)
            self.mapping_rows.append(row)

        self._update_ui_state()
        self.labelStatus.setText(f"Mapping '{name}' loaded")

    def _delete_mapping(self):
        """Delete a saved mapping."""
        all_mappings = self.mapping_store.list_all()

        if not all_mappings:
            QMessageBox.information(self, "No Mappings", "No saved mappings to delete")
            return

        name, ok = QInputDialog.getItem(
            self, "Delete Mapping", "Select mapping to delete:",
            all_mappings, 0, False
        )

        if ok and name:
            confirm = QMessageBox.question(
                self, "Confirm Delete",
                f"Delete mapping '{name}'?",
                QMessageBox.Yes | QMessageBox.No
            )
            if confirm == QMessageBox.Yes:
                self.mapping_store.delete_mapping(name)
                self.labelStatus.setText(f"Mapping '{name}' deleted")

    def _popout_preview(self):
        """Open preview in a pop-out window."""
        if not self.diff_data:
            QMessageBox.warning(self, "Warning", "Generate a preview first")
            return

        dialog = PreviewDialog(self.preview_model, self)
        dialog.exec_()

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
                f"<b>{summary['modified']}</b> to update, "
                f"<b>{summary['skipped']}</b> skipped (not in DB), "
                f"<b>{summary['unchanged']}</b> unchanged"
            )

            # Enable execute if there are changes
            has_changes = summary['modified'] > 0
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
            f"This will update {summary['modified']} existing records.\n"
            f"({summary['skipped']} rows skipped - not in DB)\n\n"
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

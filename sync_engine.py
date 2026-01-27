# -*- coding: utf-8 -*-
"""
Sync Engine - Core sync logic with transaction support
"""

from qgis.PyQt.QtCore import QObject, pyqtSignal

# Change types
UNCHANGED = 'UNCHANGED'
ADDED = 'ADDED'
MODIFIED = 'MODIFIED'


class SyncEngine(QObject):
    """Engine for synchronizing Excel data with PostgreSQL database."""

    # Signals for progress reporting
    progress_changed = pyqtSignal(int, int)  # current, total
    status_changed = pyqtSignal(str)  # status message
    sync_complete = pyqtSignal(bool, str)  # success, message

    def __init__(self, connection_manager, parent=None):
        super().__init__(parent)
        self.conn_manager = connection_manager
        self.schema = None
        self.table = None
        self.key_column_excel = None
        self.key_column_db = None
        self.column_mapping = {}  # {excel_col: db_col}

    def configure(self, schema, table, key_column_excel, key_column_db, column_mapping):
        """Configure the sync engine.

        :param schema: Database schema name
        :param table: Database table name
        :param key_column_excel: Excel column to use as key
        :param key_column_db: Database column to use as key
        :param column_mapping: Dictionary mapping Excel columns to DB columns
        """
        self.schema = schema
        self.table = table
        self.key_column_excel = key_column_excel
        self.key_column_db = key_column_db
        self.column_mapping = column_mapping

    def generate_diff(self, excel_reader):
        """Generate diff between Excel data and database records.

        :param excel_reader: ExcelReader instance with loaded data
        :return: List of diff items
        """
        self.status_changed.emit("Fetching database records...")

        # Get DB columns we need (mapped from Excel)
        db_value_columns = list(self.column_mapping.values())

        # Fetch existing records from database
        db_records = self.conn_manager.fetch_records(
            self.schema,
            self.table,
            self.key_column_db,
            db_value_columns
        )

        self.status_changed.emit("Comparing records...")

        diff_data = []
        excel_rows = excel_reader.get_all_rows()
        total_rows = len(excel_rows)

        for i, excel_row in enumerate(excel_rows):
            self.progress_changed.emit(i + 1, total_rows)

            # Get key value from Excel
            key_value = excel_row.get(self.key_column_excel)
            if key_value is None:
                continue  # Skip rows without key

            # Build mapped values from Excel
            excel_values = {}
            for excel_col, db_col in self.column_mapping.items():
                excel_values[db_col] = excel_row.get(excel_col)

            # Check if record exists in database
            if key_value in db_records:
                # Record exists - check for changes
                db_record = db_records[key_value]
                changes = {}

                for db_col, excel_val in excel_values.items():
                    db_val = db_record.get(db_col)
                    if not self._values_equal(excel_val, db_val):
                        changes[db_col] = {
                            'excel': excel_val,
                            'db': db_val
                        }

                if changes:
                    diff_data.append({
                        'change_type': MODIFIED,
                        'key_value': key_value,
                        'changes': changes,
                        'excel_values': excel_values
                    })
                else:
                    diff_data.append({
                        'change_type': UNCHANGED,
                        'key_value': key_value
                    })
            else:
                # New record
                diff_data.append({
                    'change_type': ADDED,
                    'key_value': key_value,
                    'excel_values': excel_values
                })

        self.status_changed.emit("Diff complete")
        return diff_data

    def _values_equal(self, val1, val2):
        """Compare two values, handling type differences and None."""
        if val1 is None and val2 is None:
            return True
        if val1 is None or val2 is None:
            return False

        # Convert to strings for comparison (handles numeric type differences)
        str1 = str(val1).strip() if val1 is not None else ''
        str2 = str(val2).strip() if val2 is not None else ''

        return str1 == str2

    def execute_sync(self, diff_data):
        """Execute the sync operation with transaction support.

        :param diff_data: List of diff items from generate_diff()
        :return: Tuple (success, message)
        """
        conn = self.conn_manager.connection
        if not conn:
            return False, "Not connected to database"

        # Filter to only changes
        changes = [d for d in diff_data if d['change_type'] in (ADDED, MODIFIED)]

        if not changes:
            return True, "No changes to apply"

        cur = conn.cursor()
        inserted = 0
        updated = 0

        try:
            self.status_changed.emit("Applying changes...")

            for i, item in enumerate(changes):
                self.progress_changed.emit(i + 1, len(changes))

                if item['change_type'] == ADDED:
                    self._insert_record(cur, item)
                    inserted += 1
                elif item['change_type'] == MODIFIED:
                    self._update_record(cur, item)
                    updated += 1

            # Commit transaction
            conn.commit()
            self.status_changed.emit("Sync complete")
            self.sync_complete.emit(True, f"Success: {inserted} inserted, {updated} updated")
            return True, f"Successfully applied changes: {inserted} inserted, {updated} updated"

        except Exception as e:
            # Rollback on any error
            conn.rollback()
            error_msg = f"Sync failed: {str(e)}"
            self.status_changed.emit(error_msg)
            self.sync_complete.emit(False, error_msg)
            return False, error_msg

        finally:
            cur.close()

    def _insert_record(self, cursor, item):
        """Insert a new record into the database.

        :param cursor: Database cursor
        :param item: Diff item with change_type ADDED
        """
        # Build column list including key
        columns = [self.key_column_db] + list(item['excel_values'].keys())
        values = [item['key_value']] + list(item['excel_values'].values())

        # Build parameterized query
        col_sql = ', '.join([f'"{c}"' for c in columns])
        placeholders = ', '.join(['%s'] * len(values))
        table_sql = f'"{self.schema}"."{self.table}"'

        sql = f"INSERT INTO {table_sql} ({col_sql}) VALUES ({placeholders})"
        cursor.execute(sql, values)

    def _update_record(self, cursor, item):
        """Update an existing record in the database.

        :param cursor: Database cursor
        :param item: Diff item with change_type MODIFIED
        """
        # Only update changed columns
        set_clauses = []
        values = []

        for col, change in item['changes'].items():
            set_clauses.append(f'"{col}" = %s')
            values.append(change['excel'])

        # Add key value for WHERE clause
        values.append(item['key_value'])

        table_sql = f'"{self.schema}"."{self.table}"'
        set_sql = ', '.join(set_clauses)

        sql = f'UPDATE {table_sql} SET {set_sql} WHERE "{self.key_column_db}" = %s'
        cursor.execute(sql, values)

    def get_change_summary(self, diff_data):
        """Get summary of changes.

        :param diff_data: Diff data from generate_diff()
        :return: Dictionary with counts
        """
        counts = {
            'added': 0,
            'modified': 0,
            'unchanged': 0
        }

        for item in diff_data:
            if item['change_type'] == ADDED:
                counts['added'] += 1
            elif item['change_type'] == MODIFIED:
                counts['modified'] += 1
            else:
                counts['unchanged'] += 1

        return counts

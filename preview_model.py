# -*- coding: utf-8 -*-
"""
Preview Model - QAbstractTableModel for displaying diff preview
"""

from qgis.PyQt.QtCore import Qt, QAbstractTableModel, QModelIndex
from qgis.PyQt.QtGui import QColor, QBrush


# Change types
UNCHANGED = 'UNCHANGED'
ADDED = 'ADDED'
MODIFIED = 'MODIFIED'


class PreviewModel(QAbstractTableModel):
    """Table model for displaying sync diff preview with color coding."""

    # Colors for different change types
    COLOR_ADDED = QColor(200, 255, 200)      # Light green
    COLOR_MODIFIED = QColor(255, 220, 180)   # Light orange
    COLOR_UNCHANGED = QColor(255, 255, 255)  # White

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data = []
        self._headers = ['Key', 'Column', 'Excel Value', 'DB Value', 'Action']
        self._key_column_name = 'Key'

    def set_key_column_name(self, name):
        """Set the display name for the key column."""
        self._key_column_name = name
        self._headers[0] = name

    def set_diff_data(self, diff_data):
        """Set the diff data to display.

        :param diff_data: List of diff items from SyncEngine.generate_diff()
        """
        self.beginResetModel()
        self._data = []

        for item in diff_data:
            change_type = item['change_type']
            key_value = item['key_value']

            if change_type == UNCHANGED:
                continue  # Skip unchanged rows in preview

            if change_type == ADDED:
                # Show all columns for new rows
                for col, value in item['excel_values'].items():
                    self._data.append({
                        'key': key_value,
                        'column': col,
                        'excel_value': value,
                        'db_value': None,
                        'change_type': ADDED
                    })
            elif change_type == MODIFIED:
                # Show only changed columns
                for col, values in item['changes'].items():
                    self._data.append({
                        'key': key_value,
                        'column': col,
                        'excel_value': values['excel'],
                        'db_value': values['db'],
                        'change_type': MODIFIED
                    })

        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._data)

    def columnCount(self, parent=QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._headers)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        row = index.row()
        col = index.column()

        if row >= len(self._data):
            return None

        item = self._data[row]

        if role == Qt.DisplayRole:
            if col == 0:
                return str(item['key']) if item['key'] is not None else ''
            elif col == 1:
                return item['column']
            elif col == 2:
                return str(item['excel_value']) if item['excel_value'] is not None else '(null)'
            elif col == 3:
                return str(item['db_value']) if item['db_value'] is not None else '(null)'
            elif col == 4:
                return 'ADD' if item['change_type'] == ADDED else 'UPDATE'

        elif role == Qt.BackgroundRole:
            if item['change_type'] == ADDED:
                return QBrush(self.COLOR_ADDED)
            elif item['change_type'] == MODIFIED:
                return QBrush(self.COLOR_MODIFIED)
            return QBrush(self.COLOR_UNCHANGED)

        elif role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if section < len(self._headers):
                    return self._headers[section]
            else:
                return str(section + 1)
        return None

    def get_summary(self):
        """Get summary statistics of the diff.

        :return: Dictionary with counts
        """
        added_keys = set()
        modified_keys = set()

        for item in self._data:
            if item['change_type'] == ADDED:
                added_keys.add(item['key'])
            elif item['change_type'] == MODIFIED:
                modified_keys.add(item['key'])

        return {
            'added': len(added_keys),
            'modified': len(modified_keys),
            'total_changes': len(added_keys) + len(modified_keys)
        }

    def clear(self):
        """Clear all data from the model."""
        self.beginResetModel()
        self._data = []
        self.endResetModel()

# -*- coding: utf-8 -*-
"""
Mapping Store - Persistent storage for column mapping configurations
"""

import json
import os
from datetime import datetime


class MappingStore:
    """Persistent storage for column mapping configurations."""

    def __init__(self):
        plugin_dir = os.path.dirname(__file__)
        self.storage_path = os.path.join(plugin_dir, 'saved_mappings.json')

    def _load_all(self):
        """Load all mappings from file.

        :return: Dictionary of all saved mappings
        """
        if not os.path.exists(self.storage_path):
            return {}

        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}

    def _save_all(self, data):
        """Save all mappings to file.

        :param data: Dictionary of mappings to save
        """
        with open(self.storage_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def save_mapping(self, name, table, key_excel, key_db, column_mappings,
                     excel_cols_required, db_cols_required):
        """Save a named mapping configuration.

        :param name: Unique name for the mapping
        :param table: Full table name (schema.table)
        :param key_excel: Excel key column name
        :param key_db: Database key column name
        :param column_mappings: Dict mapping Excel columns to DB columns
        :param excel_cols_required: List of required Excel columns
        :param db_cols_required: List of required DB columns
        """
        data = self._load_all()

        data[name] = {
            'table': table,
            'key_excel': key_excel,
            'key_db': key_db,
            'column_mappings': column_mappings,
            'excel_cols_required': excel_cols_required,
            'db_cols_required': db_cols_required,
            'created_at': datetime.now().isoformat()
        }

        self._save_all(data)

    def get_compatible_mappings(self, table, excel_cols, db_cols):
        """Return list of mapping names compatible with current columns.

        :param table: Current table name (schema.table)
        :param excel_cols: List of available Excel columns
        :param db_cols: List of available DB columns
        :return: List of compatible mapping names
        """
        data = self._load_all()
        compatible = []

        excel_cols_set = set(excel_cols)
        db_cols_set = set(db_cols)

        for name, mapping in data.items():
            # Check if table matches
            if mapping['table'] != table:
                continue

            # Check if all required Excel columns exist
            required_excel = set(mapping.get('excel_cols_required', []))
            if not required_excel.issubset(excel_cols_set):
                continue

            # Check if all required DB columns exist
            required_db = set(mapping.get('db_cols_required', []))
            if not required_db.issubset(db_cols_set):
                continue

            compatible.append(name)

        return compatible

    def load_mapping(self, name):
        """Load a mapping by name.

        :param name: Name of the mapping to load
        :return: Dictionary with mapping config, or None if not found
        """
        data = self._load_all()
        return data.get(name)

    def delete_mapping(self, name):
        """Delete a mapping by name.

        :param name: Name of the mapping to delete
        :return: True if deleted, False if not found
        """
        data = self._load_all()
        if name in data:
            del data[name]
            self._save_all(data)
            return True
        return False

    def list_all(self):
        """List all saved mapping names.

        :return: List of mapping names
        """
        return list(self._load_all().keys())

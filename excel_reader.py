# -*- coding: utf-8 -*-
"""
Excel Reader - Read Excel files using OGR/QGIS
"""

import os
from qgis.core import QgsVectorLayer, QgsFeature


class ExcelReader:
    """Read Excel files using QGIS OGR provider."""

    def __init__(self):
        self.file_path = None
        self.layer = None
        self.sheet_name = None

    def load_file(self, file_path, sheet_name=None):
        """Load an Excel file.

        :param file_path: Path to Excel file (.xlsx or .xls)
        :type file_path: str
        :param sheet_name: Name of sheet to load (first sheet if None)
        :type sheet_name: str
        :return: True if loaded successfully
        :rtype: bool
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        self.file_path = file_path

        # If no sheet specified, get first sheet
        if sheet_name is None:
            sheets = self.get_sheets()
            if not sheets:
                raise ValueError("No sheets found in Excel file")
            sheet_name = sheets[0]

        self.sheet_name = sheet_name

        # Build URI for OGR provider
        # Format: filepath|layername=sheetname
        uri = f"{file_path}|layername={sheet_name}"

        self.layer = QgsVectorLayer(uri, "excel_data", "ogr")

        if not self.layer.isValid():
            raise ValueError(f"Failed to load Excel file: {file_path}")

        return True

    def get_sheets(self):
        """Get list of sheet names from Excel file.

        :return: List of sheet names
        :rtype: list
        """
        if not self.file_path:
            return []

        from osgeo import ogr

        # Open Excel file with OGR
        ds = ogr.Open(self.file_path)
        if ds is None:
            return []

        sheets = []
        for i in range(ds.GetLayerCount()):
            layer = ds.GetLayerByIndex(i)
            sheets.append(layer.GetName())

        ds = None  # Close dataset
        return sheets

    def get_columns(self):
        """Get column names from loaded sheet.

        :return: List of column names
        :rtype: list
        """
        if not self.layer or not self.layer.isValid():
            return []

        fields = self.layer.fields()
        return [field.name() for field in fields]

    def get_row_count(self):
        """Get number of rows in loaded sheet.

        :return: Row count
        :rtype: int
        """
        if not self.layer or not self.layer.isValid():
            return 0
        return self.layer.featureCount()

    def iterate_rows(self):
        """Iterate over rows in the Excel sheet.

        :yield: Dictionary with column names as keys
        """
        if not self.layer or not self.layer.isValid():
            return

        columns = self.get_columns()

        for feature in self.layer.getFeatures():
            row_dict = {}
            for col in columns:
                value = feature[col]
                # Convert NULL values to None
                if value == NULL:
                    value = None
                row_dict[col] = value
            yield row_dict

    def get_all_rows(self):
        """Get all rows as a list of dictionaries.

        :return: List of row dictionaries
        :rtype: list
        """
        return list(self.iterate_rows())

    def close(self):
        """Close the Excel file and release resources."""
        self.layer = None
        self.file_path = None
        self.sheet_name = None


# Handle QGIS NULL value
try:
    from qgis.core import NULL
except ImportError:
    NULL = None

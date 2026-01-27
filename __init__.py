# -*- coding: utf-8 -*-
"""
DataSync QGIS Plugin
Bulk-import Excel updates into PostgreSQL/PostGIS databases
"""


def classFactory(iface):
    """Load DataSyncPlugin class from datasync_main module.

    :param iface: A QGIS interface instance.
    :type iface: QgsInterface
    """
    from .datasync_main import DataSyncPlugin
    return DataSyncPlugin(iface)

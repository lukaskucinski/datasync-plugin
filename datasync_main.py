# -*- coding: utf-8 -*-
"""
DataSync Main Plugin Class
"""

import os
from qgis.PyQt.QtCore import QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import QgsApplication


class DataSyncPlugin:
    """Main plugin class for DataSync."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that provides access to QGIS
        :type iface: QgsInterface
        """
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.actions = []
        self.menu = '&DataSync'
        self.toolbar = self.iface.addToolBar('DataSync')
        self.toolbar.setObjectName('DataSync')
        self.dialog = None

    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None
    ):
        """Add a toolbar icon to the toolbar."""
        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            self.toolbar.addAction(action)

        if add_to_menu:
            self.iface.addPluginToDatabaseMenu(self.menu, action)

        self.actions.append(action)
        return action

    def initGui(self):
        """Create the menu entries and toolbar icons."""
        icon_path = os.path.join(self.plugin_dir, 'icon.png')
        self.add_action(
            icon_path,
            text='DataSync - Excel to PostgreSQL',
            callback=self.run,
            parent=self.iface.mainWindow(),
            status_tip='Sync Excel data with PostgreSQL database'
        )

    def unload(self):
        """Remove the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginDatabaseMenu('&DataSync', action)
            self.iface.removeToolBarIcon(action)
        del self.toolbar

    def run(self):
        """Run method that shows the plugin dialog."""
        from .datasync_dialog import DataSyncDialog

        if self.dialog is None:
            self.dialog = DataSyncDialog(self.iface.mainWindow())

        self.dialog.show()
        result = self.dialog.exec_()

        if result:
            pass  # Dialog handles sync execution

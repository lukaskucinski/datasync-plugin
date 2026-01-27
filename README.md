# DataSync QGIS Plugin

Bulk-import Excel updates into PostgreSQL/PostGIS databases with preview and column mapping.

## Features

- **Use existing QGIS connections**: Leverages PostgreSQL connections already configured in QGIS Browser
- **Configurable column mapping**: Map any Excel column to any database column via UI
- **Preview before commit**: See all changes color-coded before applying them
- **Transaction safety**: All changes applied in a single transaction with rollback on error
- **Cross-platform**: Works on Windows and macOS using native QGIS libraries

## Installation

### From QGIS Plugin Manager

1. Open QGIS
2. Go to **Plugins > Manage and Install Plugins**
3. Click **Settings** tab
4. Click **Add** to add a custom repository
5. Enter:
   - Name: `DataSync Plugin`
   - URL: `https://raw.githubusercontent.com/lukaskucinski/datasync-plugin/main/plugins.xml`
6. Click **OK**, then go to **All** tab
7. Search for "DataSync" and click **Install**

### Manual Installation

1. Download the latest release zip from [Releases](https://github.com/lukaskucinski/datasync-plugin/releases)
2. In QGIS, go to **Plugins > Manage and Install Plugins**
3. Click **Install from ZIP**
4. Select the downloaded zip file

## Usage

### Prerequisites

1. Configure a PostgreSQL connection in QGIS Browser panel
2. Have an Excel file (.xlsx or .xls) with data to sync

### Steps

1. Click the **DataSync** button in the toolbar (or Database menu > DataSync)
2. **Step 1**: Browse and select your Excel file, choose the sheet
3. **Step 2**: Select PostgreSQL connection and click Connect, then choose target table
4. **Step 3**: Configure column mapping:
   - Select the key column in both Excel and database (used to match records)
   - Add value column mappings for each column you want to sync
5. **Step 4**: Click **Generate Preview** to see changes
   - Green rows = new records to be added
   - Orange rows = existing records to be updated
6. Click **Execute Sync** to apply changes

### Preview Color Coding

| Color | Meaning |
|-------|---------|
| Green | New row to be inserted |
| Orange | Existing row to be updated |
| White | Unchanged (not shown in preview) |

## Requirements

- QGIS 3.0 or later
- PostgreSQL/PostGIS database
- psycopg2 (included with QGIS)

## License

MIT License

## Contributing

Issues and pull requests welcome at https://github.com/lukaskucinski/datasync-plugin

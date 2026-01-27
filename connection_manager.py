# -*- coding: utf-8 -*-
"""
Connection Manager - Handle PostgreSQL connections from QGIS settings
"""

from qgis.PyQt.QtCore import QSettings


class ConnectionManager:
    """Manages PostgreSQL database connections using QGIS stored connections."""

    SSL_MODE_MAP = {
        'SslDisable': 'disable',
        'SslAllow': 'allow',
        'SslPrefer': 'prefer',
        'SslRequire': 'require',
        'SslVerifyCa': 'verify-ca',
        'SslVerifyFull': 'verify-full',
        'disable': 'disable',
        'allow': 'allow',
        'prefer': 'prefer',
        'require': 'require',
        'verify-ca': 'verify-ca',
        'verify-full': 'verify-full',
    }

    def __init__(self):
        self.connection = None
        self.current_conn_name = None

    @staticmethod
    def get_available_connections():
        """Get list of PostgreSQL connections configured in QGIS.

        :return: List of connection names
        :rtype: list
        """
        s = QSettings()
        s.beginGroup("/PostgreSQL/connections")
        connections = s.childGroups()
        s.endGroup()
        return connections

    @staticmethod
    def get_connection_params(conn_name):
        """Get connection parameters for a named connection.

        :param conn_name: Name of the PostgreSQL connection
        :type conn_name: str
        :return: Dictionary with connection parameters
        :rtype: dict
        """
        s = QSettings()
        base_key = f"/PostgreSQL/connections/{conn_name}"

        params = {
            'host': s.value(f"{base_key}/host", "localhost"),
            'port': s.value(f"{base_key}/port", "5432"),
            'database': s.value(f"{base_key}/database", ""),
            'username': s.value(f"{base_key}/username", ""),
            'password': s.value(f"{base_key}/password", ""),
            'sslmode': s.value(f"{base_key}/sslmode", "disable"),
        }

        # Handle authcfg (authentication configuration)
        authcfg = s.value(f"{base_key}/authcfg", "")
        if authcfg:
            params['authcfg'] = authcfg

        return params

    def connect(self, conn_name):
        """Establish connection to PostgreSQL database.

        :param conn_name: Name of the PostgreSQL connection
        :type conn_name: str
        :return: Database connection object
        :raises: Exception if connection fails
        """
        import psycopg2

        params = self.get_connection_params(conn_name)

        # Handle QGIS authentication config if present
        if params.get('authcfg'):
            from qgis.core import QgsApplication, QgsAuthMethodConfig
            auth_mgr = QgsApplication.authManager()
            auth_cfg = QgsAuthMethodConfig()
            auth_mgr.loadAuthenticationConfig(params['authcfg'], auth_cfg, True)
            if auth_cfg.isValid():
                params['username'] = auth_cfg.config('username', '')
                params['password'] = auth_cfg.config('password', '')

        conn_string = (
            f"host='{params['host']}' "
            f"port='{params['port']}' "
            f"dbname='{params['database']}' "
            f"user='{params['username']}' "
            f"password='{params['password']}'"
        )

        sslmode = self.SSL_MODE_MAP.get(params.get('sslmode', ''), 'prefer')
        if sslmode and sslmode != 'disable':
            conn_string += f" sslmode='{sslmode}'"

        self.connection = psycopg2.connect(conn_string)
        self.current_conn_name = conn_name
        return self.connection

    def disconnect(self):
        """Close the current database connection."""
        if self.connection:
            self.connection.close()
            self.connection = None
            self.current_conn_name = None

    def get_tables(self):
        """Get list of tables from the connected database.

        :return: List of (schema, table_name) tuples
        :rtype: list
        """
        if not self.connection:
            raise Exception("Not connected to database")

        cur = self.connection.cursor()
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
              AND table_type = 'BASE TABLE'
            ORDER BY table_schema, table_name
        """)
        tables = cur.fetchall()
        cur.close()
        return tables

    def get_columns(self, schema, table):
        """Get column information for a table.

        :param schema: Schema name
        :type schema: str
        :param table: Table name
        :type table: str
        :return: List of column info dicts (name, data_type, is_nullable)
        :rtype: list
        """
        if not self.connection:
            raise Exception("Not connected to database")

        cur = self.connection.cursor()
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
        """, (schema, table))

        columns = []
        for row in cur.fetchall():
            columns.append({
                'name': row[0],
                'data_type': row[1],
                'is_nullable': row[2] == 'YES',
                'has_default': row[3] is not None
            })

        cur.close()
        return columns

    def get_primary_key(self, schema, table):
        """Get primary key column(s) for a table.

        :param schema: Schema name
        :type schema: str
        :param table: Table name
        :type table: str
        :return: List of primary key column names
        :rtype: list
        """
        if not self.connection:
            raise Exception("Not connected to database")

        cur = self.connection.cursor()
        cur.execute("""
            SELECT a.attname
            FROM pg_index i
            JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = ANY(i.indkey)
            JOIN pg_class c ON c.oid = i.indrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE i.indisprimary
              AND n.nspname = %s
              AND c.relname = %s
            ORDER BY array_position(i.indkey, a.attnum)
        """, (schema, table))

        pk_columns = [row[0] for row in cur.fetchall()]
        cur.close()
        return pk_columns

    def fetch_records(self, schema, table, key_column, value_columns):
        """Fetch existing records from database for comparison.

        :param schema: Schema name
        :param table: Table name
        :param key_column: Column to use as key
        :param value_columns: List of value columns to fetch
        :return: Dictionary mapping key values to row dicts
        """
        if not self.connection:
            raise Exception("Not connected to database")

        columns = [key_column] + value_columns
        columns_sql = ', '.join([f'"{c}"' for c in columns])
        table_sql = f'"{schema}"."{table}"'

        cur = self.connection.cursor()
        cur.execute(f"SELECT {columns_sql} FROM {table_sql}")

        records = {}
        for row in cur.fetchall():
            key_value = row[0]
            record = {key_column: key_value}
            for i, col in enumerate(value_columns):
                record[col] = row[i + 1]
            records[key_value] = record

        cur.close()
        return records

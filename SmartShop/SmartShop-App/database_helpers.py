import os
import sqlite3

import pandas as pd


def open_database_connection(database):
    """Creates a connection to the specified database.

    Args:
        database (str): The name of the database to connect to.

    Returns:
        sqlite3.Connection: A connection to the specified database.
    """
    return sqlite3.connect(database)


def close_database_connection(connection: sqlite3.Connection):
    """Closes the connection to the database.

    Args:
        connection: The connection that was opened earlier.
    """
    connection.close()


def create_history_table(connection: sqlite3.Connection):
    """Create a 'products_history' table in the database, if it does not exist.

    Args:
        connection (sqlite3.Connection): A connection to the SQLite database.
    """
    connection.execute("""
        CREATE TABLE IF NOT EXISTS products_history (
            code TEXT,
            store TEXT,
            link TEXT,
            product_name TEXT,
            starting_price REAL,
            final_price REAL,
            price_per_unit REAL,
            metric_unit TEXT,
            discounted INTEGER,
            scan_date DATE
        );
    """)
    connection.commit()


def create_products(connection: sqlite3.Connection, data: pd.DataFrame, scan_date: str):
    """Create a 'products' table in the database and write data to it.
    Then insert a copy of data with the additional scan date column to products_history table
    if the product code is the same but the price_per_unit or the final_price has changed.

    Args:
        connection (sqlite3.Connection): A connection to the SQLite database.
        data (pd.DataFrame): The data that will be saved in the database.
        scan_date (str): The date the data was scanned in yyyy-mm-dd format.
    """
    create_history_table(connection)  # create history table if not exist

    # Get existing data for products with same code from products_history table
    existing_data = pd.read_sql_query(
        f"SELECT * FROM products_history WHERE code IN {tuple(data['code'].tolist())}", connection)

    # Check if the new data has any changes to price_per_unit or final_price compared to the existing data
    merged_data = pd.merge(
        data, existing_data[['code', 'starting_price']], how='left', on='code')
    changes = merged_data[merged_data['starting_price_x']
                          != merged_data['starting_price_y']]
    if changes.empty:
        return

    # create products table
    connection.execute("DROP TABLE IF EXISTS products;")
    data.to_sql("products", connection, if_exists="replace", index=False, dtype={
        'code': 'TEXT',
        'store': 'TEXT',
        'link': 'TEXT',
        'product_name': 'TEXT',
        'starting_price': 'REAL',
        'final_price': 'REAL',
        'price_per_unit': 'REAL',
        'metric_unit': 'TEXT',
        'discounted': 'INTEGER'})
    connection.commit()

    # insert data with scan date to products_history table
    data['scan_date'] = scan_date
    data.to_sql("products_history", connection, if_exists="append", index=False, dtype={
        'code': 'TEXT',
        'store': 'TEXT',
        'link': 'TEXT',
        'product_name': 'TEXT',
        'starting_price': 'REAL',
        'final_price': 'REAL',
        'price_per_unit': 'REAL',
        'metric_unit': 'TEXT',
        'discounted': 'INTEGER',
        'scan_date': 'DATE'})
    connection.commit()


def get_all_products(connection: sqlite3.Connection) -> pd.DataFrame:
    """Get all data from the 'products' table.

    Args:
        connection (sqlite3.Connection): A connection to the SQLite database.

    Returns:
        pd.DataFrame: A DataFrame containing all data from the 'products' table.
    """
    query = "SELECT * FROM products;"
    return pd.read_sql_query(query, connection)


def create_correlations(connection: sqlite3.Connection, data: dict):
    """Create a 'correlations' table in the database and write data to it.

    Args:
        connection (sqlite3.Connection): A connection to the SQLite database.
        data (dict): A dictionary of key-value pairs to write to the 'correlations' table.
    """
    connection.execute("DROP TABLE IF EXISTS correlations;")
    df = pd.DataFrame.from_dict(data, orient='index', columns=['value'])
    df.index.name = 'key'
    df.to_sql("correlations", connection, index=True,
              dtype={'key': 'TEXT', 'value': 'TEXT'})
    connection.commit()

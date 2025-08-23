# # db_utils.py
# # Utility functions for SQLite database operations

# import sqlite3
# import pandas as pd
# from datetime import datetime
# import logging
# import os

# def query_db(query: str, db_name: str, table_name: str):
#     try:
#         conn = sqlite3.connect(db_name)
#         df = pd.read_sql_query(query, conn)
#         conn.close()
#         logging.info(f"Loaded {len(df)} records from {table_name}.")
#         return df
#     except Exception as e:
#         logging.error(f"Error loading {table_name} table from the database: {e}")
#         return pd.DataFrame()
    
# def load_table_from_db(db_name:str, table_name: str):
#     '''
#     Load the staging_dim_movie table from the SQLite database into a pandas DataFrame.
    
#     Args:
#     - db_name (str): Name of the SQLite database file.
    
#     Returns:
#     - pd.DataFrame: DataFrame containing the staging_dim_movie data.
#     '''

#     select_query = f"""
#         SELECT * FROM {table_name};
#     """
#     df = query_db(query=select_query, db_name=db_name, table_name=table_name)
#     return df
    
# def push_to_sqlite(df, table_name, db_name='movie_data.db'):
#     ''' 
#     Push the DataFrame to a local SQLite database.
    
#     Args:
#     - df (pd.DataFrame): DataFrame to be inserted into the database.
#     - table_name (str): Name of the table in the SQLite database.
#     - db_name (str): Name of the SQLite database file.
#     '''
#     # Create a connection to the SQLite database
#     conn = sqlite3.connect(db_name)
    
#     # Push the DataFrame to the database
#     df.to_sql(table_name, conn, if_exists='replace', index=False)
    
#     # Close the connection
#     conn.close()
#     print(f"Data successfully pushed to the '{table_name}' table in '{db_name}'.")


# def push_to_sqlite_view(df, table_name, db_name='movie_data.db'):
#     ''' 
#     Push the DataFrame to a local SQLite database as a view.
    
#     Args:
#     - df (pd.DataFrame): DataFrame to be inserted into the database.
#     - table_name (str): Name of the view in the SQLite database.
#     - db_name (str): Name of the SQLite database file.
#     '''
#     # Create a connection to the SQLite database
#     conn = sqlite3.connect(db_name)
    
#     # First, create a temporary table with the data
#     temp_table_name = f"temp_{table_name}"
#     df.to_sql(temp_table_name, conn, if_exists='replace', index=False)
    
#     # Create a view based on the temporary table
#     cursor = conn.cursor()
    
#     # Drop the view if it exists
#     cursor.execute(f"DROP VIEW IF EXISTS {table_name}")
    
#     # Create the view
#     cursor.execute(f"CREATE VIEW {table_name} AS SELECT * FROM {temp_table_name}")
    
#     # Delete the temporary table
#     cursor.execute(f"DROP TABLE {temp_table_name}")
    
#     # Close the connection
#     conn.close()
#     print(f"Data successfully pushed to the '{table_name}' view in '{db_name}'.")


# def push_json_to_sqlite(data_dict, table_name, db_name):
#     import sqlite3
#     import json
    
#     conn = sqlite3.connect(db_name)
#     cursor = conn.cursor()
    
#     # Create table with JSON column
#     cursor.execute(f'''
#         CREATE TABLE IF NOT EXISTS {table_name} (
#             id INTEGER PRIMARY KEY AUTOINCREMENT,
#             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
#             data JSON
#         )
#     ''')
    
#     # Insert as JSON
#     json_data = json.dumps(data_dict, default=str)  # default=str handles Timestamp
#     cursor.execute(f'INSERT INTO {table_name} (data) VALUES (?)', (json_data,))
    
#     conn.commit()
#     conn.close()


# def load_csv_to_db(base_data_directory: str, filename: str, db_name='movie_data.db', table_name='dim_event'):
#     ''' 
#     Load the CSV file into the SQLite database.
    
#     Args:
#     - db_name (str): Name of the SQLite database file.
#     '''
#     try:
#         file_path = os.path.join(base_data_directory, filename)
#         df = pd.read_csv(file_path)
#         push_to_sqlite(df, table_name, db_name=db_name)
#         logging.info(f"{table_name} loaded into the database with {len(df)} records.")
#     except Exception as e:
#         logging.error(f"Error loading {table_name} into the database: {e}")
        
# def execute_sql_script(sql_file_path, db_name='movie_data.db'):
#     '''
#     Execute an SQL script to modify the SQLite database.
    
#     Args:
#     - sql_file_path (str): Path to the SQL file containing the SQL script.
#     - db_name (str): Name of the SQLite database file.
#     '''
#     # Read the SQL query from the file
#     with open(sql_file_path, 'r') as file:
#         sql_script = file.read()
    
#     # Create a connection to the SQLite database
#     conn = sqlite3.connect(db_name)
#     cursor = conn.cursor()
    
#     # Execute the SQL script
#     cursor.executescript(sql_script)
    
#     # Commit and close the connection
#     conn.commit()
#     conn.close()
#     print(f"SQL script '{sql_file_path}' executed successfully.")
    
# def create_and_save_tables(existing_df, new_df, date_tagged_prefix='staging_daily_movie_sales_data',db_name='movie_data.db'):
#     '''
#     Combine existing data and new data, and create two tables:
#     - <date_tagged_prefix>_latest: Contains the latest combined data.
#     - <date_tagged_prefix>_<date>: Contains the latest combined data tagged with the current date.
    
#     Args:
#     - existing_df (pd.DataFrame): DataFrame containing existing data.
#     - new_df (pd.DataFrame): DataFrame containing new data.
#     - date_tagged_prefix (str): Prefix for the table names.
#     '''
#     conn = sqlite3.connect(db_name)
#     try:
#         # Combine existing data with new data
#         combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        
#         # Create the latest combined table
#         latest_table_name = f"{date_tagged_prefix}_latest"
#         combined_df.to_sql(latest_table_name, conn, if_exists='replace', index=False)
#         print(f"Created table: {latest_table_name}")

#         # Create the date-tagged table
#         date_str = datetime.now().strftime("%Y%m%d")
#         table_name_with_date = f"{date_tagged_prefix}_{date_str}"
#         combined_df.to_sql(table_name_with_date, conn, if_exists='replace', index=False)
#         print(f"Created table: {table_name_with_date}")
        
#         print(combined_df.shape)
        
#     except Exception as e:
#         print(f"Error creating and saving tables: {e}")
#     finally:
#         conn.close()
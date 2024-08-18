import sqlite3
import os
import time
from resources.log import LoggerSingleton

def retry_db_operation(func, max_retries=5, delay=5):
    def wrapper(*args, **kwargs):
        retries = 0
        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except sqlite3.OperationalError as e:
                LoggerSingleton().error('(db) Trying again in 5 seconds. Error: '+ e.__str__())
                print(f'(db) Trying again in 5 seconds. Error: {e}')
                retries += 1
                time.sleep(delay)
        raise sqlite3.OperationalError(f"Failed after {max_retries} retries")
    return wrapper

@retry_db_operation
def initialize_db():
    conn = sqlite3.connect(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH") + '/folders.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS books
                      (name TEXT PRIMARY KEY, state TEXT, bad_pages TEXT)''')
    conn.commit()
    conn.close()

@retry_db_operation
def update_folder_state(name, state, bad_pages=None):
    name = os.path.basename(name)
    conn = sqlite3.connect(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH") + '/folders.db')
    cursor = conn.cursor()
    cursor.execute('''INSERT OR REPLACE INTO books (name, state, bad_pages)
                      VALUES (?, ?, ?)''', (name, state, str(bad_pages)))
    conn.commit()
    conn.close()

@retry_db_operation
def get_all_folders():
    conn = sqlite3.connect(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH") + '/folders.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT name, state FROM books''')
    folders = cursor.fetchall()
    conn.close()
    return folders

@retry_db_operation
def get_folder_state(name):
    name = os.path.basename(name)
    conn = sqlite3.connect(os.getenv("INSPECTION_CLIENT_FOLDERS_PATH") + '/folders.db')
    cursor = conn.cursor()
    cursor.execute('''SELECT state FROM books WHERE name = ?''', (name,))
    state = cursor.fetchone()
    conn.close()
    if not state:
        return None
    return state[0]


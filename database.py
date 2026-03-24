import sqlite3
import os

DATABASE = 'masjid.db'

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Create Members Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT NOT NULL,
            area TEXT NOT NULL,
            member_id TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create Events Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_name TEXT NOT NULL,
            item_name TEXT NOT NULL,
            total_quantity INTEGER NOT NULL,
            remaining_quantity INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create Distributions Table
    # The UNIQUE constraint on event_id, member_id prevents a member from claiming twice for the same event
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS distributions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER NOT NULL,
            member_id TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES events (id),
            FOREIGN KEY (member_id) REFERENCES members (member_id),
            UNIQUE(event_id, member_id)
        )
    ''')

    # Create Admin Table (Optional but requested)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Insert default admin if not exists (password is plain text for simplicity per requirements)
    cursor.execute('''
        INSERT OR IGNORE INTO admins (username, password) 
        VALUES ('admin', 'admin123')
    ''')
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database masjid.db initialized successfully.")

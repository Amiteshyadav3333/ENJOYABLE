import sqlite3, os

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'users.db'))
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    mobile TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT 0,
    sid TEXT,
    room TEXT
)
''')

conn.commit()
conn.close()
print("✅ Database created successfully.")
import sqlite3, os
from werkzeug.security import generate_password_hash

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'database', 'users.db'))
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

username = "admin"
password = "admin123"
password_hash = generate_password_hash(password)

try:
    cursor.execute("INSERT INTO users (username, password_hash, is_admin) VALUES (?, ?, ?)",
                   (username, password_hash, True))
    conn.commit()
    print("✅ Admin user created: admin / admin123")
except sqlite3.IntegrityError:
    print("⚠️ Admin user already exists")

conn.close()
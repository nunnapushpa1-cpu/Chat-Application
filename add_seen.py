import sqlite3

conn = sqlite3.connect("instance/users.db")
cur = conn.cursor()

try:
    cur.execute("""
        ALTER TABLE private_message
        ADD COLUMN seen BOOLEAN DEFAULT 0
    """)
    conn.commit()
    print("seen column added successfully.")
except Exception as e:
    print(e)

conn.close()
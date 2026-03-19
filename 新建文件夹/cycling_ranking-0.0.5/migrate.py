import sqlite3
DATABASE = 'database.db'
conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()
try:
    cursor.execute("ALTER TABLE rides ADD COLUMN is_anonymous BOOLEAN DEFAULT 0")
    cursor.execute("ALTER TABLE rides ADD COLUMN anonymous_id TEXT")
    print("数据库迁移成功！")
except sqlite3.OperationalError as e:
    print(f"迁移提示（可能字段已存在）：{e}")
conn.commit()
conn.close()
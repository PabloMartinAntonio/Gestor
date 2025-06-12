import sqlite3

# Crea una conexión y un cursor
conn = sqlite3.connect("tareas.db")
cursor = conn.cursor()

# Crea la tabla solo si no existe
cursor.execute('''
    CREATE TABLE IF NOT EXISTS tareas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        descripcion TEXT NOT NULL,
        completada INTEGER NOT NULL DEFAULT 0
    )
''')

conn.commit()
conn.close()

import sqlite3
conn = sqlite3.connect(r"C:\CSAI_OS\06 Data\databases\ebos_master.db")
print(conn.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())

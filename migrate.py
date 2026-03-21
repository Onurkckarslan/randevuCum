import sqlite3, os

db_files = ["RandevuCum.db"]

for f in db_files:
    if not os.path.exists(f):
        continue
    conn = sqlite3.connect(f)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(businesses)")
    cols = [r[1] for r in cur.fetchall()]
    if "plan" not in cols:
        cur.execute('ALTER TABLE businesses ADD COLUMN plan TEXT DEFAULT "temel"')
        print(f"{f}: plan kolonu eklendi")
    else:
        print(f"{f}: plan zaten var")
    if "plan_expires_at" not in cols:
        cur.execute("ALTER TABLE businesses ADD COLUMN plan_expires_at DATETIME")
        print(f"{f}: plan_expires_at kolonu eklendi")
    else:
        print(f"{f}: plan_expires_at zaten var")
    conn.commit()
    conn.close()
    print(f"{f}: OK")

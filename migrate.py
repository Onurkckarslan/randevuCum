import sqlite3, os
import random, string

def generate_unique_code(cursor, existing_codes):
    """6 haneli benzersiz kod üret"""
    while True:
        code = ''.join(random.choices(string.digits, k=6))
        if code not in existing_codes:
            existing_codes.add(code)
            return code

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

    if "business_code" not in cols:
        cur.execute("ALTER TABLE businesses ADD COLUMN business_code VARCHAR(6) UNIQUE")
        print(f"{f}: business_code kolonu eklendi")

        # Mevcut işletmelere kod ata
        cur.execute("SELECT id FROM businesses WHERE business_code IS NULL")
        existing_codes = set()

        # Zaten atanmış kodları oku
        cur.execute("SELECT business_code FROM businesses WHERE business_code IS NOT NULL")
        for (code,) in cur.fetchall():
            if code:
                existing_codes.add(code)

        # Boş kodlara yeni kodlar ata
        for (biz_id,) in cur.fetchall():
            new_code = generate_unique_code(cur, existing_codes)
            cur.execute("UPDATE businesses SET business_code = ? WHERE id = ?", (new_code, biz_id))
            print(f"  → Business ID {biz_id}: {new_code}")

        print(f"{f}: business_code ataması tamamlandı")
    else:
        print(f"{f}: business_code zaten var")

    conn.commit()
    conn.close()
    print(f"{f}: OK")

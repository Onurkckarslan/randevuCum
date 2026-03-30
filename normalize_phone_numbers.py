#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database'deki tüm WhatsApp numaralarını normalize et (boşlukları kaldır)
"""
from app.database import SessionLocal
from app.models import Business

def normalize_numbers():
    db = SessionLocal()

    try:
        print("[TOOL] WhatsApp Numaralarini Normalize Etme Araci")
        print("=" * 60)

        # Tüm businesses'ı oku
        businesses = db.query(Business).all()
        print(f"[INFO] Toplam {len(businesses)} işletme bulundu\n")

        updated_count = 0

        for biz in businesses:
            if biz.whatsapp_phone:
                original = biz.whatsapp_phone
                normalized = original.replace(" ", "")

                if original != normalized:
                    print(f"Business {biz.id} ({biz.name}):")
                    print(f"  Onceki:  '{original}'")
                    print(f"  Yeni:    '{normalized}'")

                    biz.whatsapp_phone = normalized
                    updated_count += 1
                else:
                    print(f"Business {biz.id} ({biz.name}): Zaten normalize ('{normalized}')")
            else:
                print(f"Business {biz.id} ({biz.name}): WhatsApp numarasi yok")

            print()

        # Commit
        if updated_count > 0:
            db.commit()
            print("=" * 60)
            print(f"[OK] Toplam {updated_count} işletme güncellendi!")
            print("=" * 60)
        else:
            print("=" * 60)
            print("[INFO] Güncellenecek işletme yok (zaten normalize)")
            print("=" * 60)

    except Exception as e:
        print(f"[FAIL] Hata: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    normalize_numbers()

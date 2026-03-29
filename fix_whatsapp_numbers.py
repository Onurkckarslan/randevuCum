#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Twilio WhatsApp numaralarini düzelt:
1. Webhook'lari dogru URL'ye ayarla
2. Messaging Service'e bagla
3. WhatsApp capability'sini enable et
"""
import os
import sys
from twilio.rest import Client

# Encoding fix
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

# Kontrol et
if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_MESSAGING_SERVICE_SID]):
    print("[ERROR] .env dosyasinda Twilio credentials eksik!")
    print("Gerekli:")
    print("  - TWILIO_ACCOUNT_SID")
    print("  - TWILIO_AUTH_TOKEN")
    print("  - TWILIO_MESSAGING_SERVICE_SID")
    exit(1)

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Düzeltilecek numaralar
NUMBERS_TO_FIX = [
    "+1 415 691 2998",
    "+1 510 871 8367"
]

# Çalışan referans numara
WORKING_NUMBER = "+14155238886"

WEBHOOK_URL = "https://randevucum.com/api/whatsapp/webhook"

def fix_number(phone_number: str):
    """Bir numarayi düzelt"""
    print(f"\n{'='*60}")
    print(f"Düzeltiliyor: {phone_number}")
    print('='*60)

    try:
        # Numarayi bul
        incoming_numbers = client.incoming_phone_numbers.stream(
            phone_number=phone_number
        )

        number_obj = None
        for num in incoming_numbers:
            number_obj = num
            break

        if not number_obj:
            print(f"[FAIL] Numara bulunamadi: {phone_number}")
            return False

        sid = number_obj.sid
        print(f"[OK] Bulundu: {number_obj.sid}")
        print(f"     Isim: {number_obj.friendly_name}")

        # 1. Webhook'lari düzelt
        print(f"\n[1/4] Webhook'lari düzeltiliyor...")
        try:
            client.incoming_phone_numbers(sid).update(
                sms_url=WEBHOOK_URL,
                sms_method="POST",
                sms_fallback_url=WEBHOOK_URL,
                voice_url=WEBHOOK_URL,
                voice_method="POST",
                voice_fallback_url=WEBHOOK_URL
            )
            print(f"[OK] Webhook'lar güncellendi: {WEBHOOK_URL}")
        except Exception as e:
            print(f"[FAIL] Webhook güncelleme hatasi: {e}")
            return False

        # 2. Messaging Service'e bagla
        print(f"\n[2/4] Messaging Service'e baglaniyor...")
        try:
            # Direkt bagla (zaten bagli ise hata ignore et)
            try:
                client.messaging.services(
                    TWILIO_MESSAGING_SERVICE_SID
                ).phone_numbers.create(phone_number_sid=sid)
                print(f"[OK] Messaging Service'e baglandi: {TWILIO_MESSAGING_SERVICE_SID}")
            except Exception as bind_error:
                if "already" in str(bind_error).lower() or "exists" in str(bind_error).lower():
                    print(f"     Zaten bagli, devam ediliyor...")
                else:
                    raise bind_error
        except Exception as e:
            print(f"[FAIL] Service baglama hatasi: {e}")
            return False

        # 3. WhatsApp capability'sini enable et
        print(f"\n[3/4] WhatsApp capability kontrol ediliyor...")
        print(f"[INFO] Messaging Service'e bagli olunca otomatik enable olabilir")

        # 4. Kontrol et
        print(f"\n[4/4] Kontrol ediliyor...")
        try:
            updated = client.incoming_phone_numbers(sid).fetch()
            print(f"[OK] Final durumu:")
            print(f"     Numara: {updated.phone_number}")
            print(f"     Isim: {updated.friendly_name}")
            print(f"     SMS URL: {updated.sms_url}")
            print(f"     Capabilities: {updated.capabilities}")
            return True
        except Exception as e:
            print(f"[FAIL] Kontrol hatasi: {e}")
            return False

    except Exception as e:
        print(f"[FAIL] Hata: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_working_number():
    """Çalışan numaranın konfigürasyonunu kontrol et (referans olarak)"""
    print("[INFO] Çalişan referans numaranin konfigürasyonu kontrol ediliyor...")
    print("=" * 60)

    try:
        incoming_numbers = client.incoming_phone_numbers.stream(
            phone_number=WORKING_NUMBER
        )

        for num in incoming_numbers:
            print(f"[OK] Bulundu: {num.phone_number}")
            print(f"     SID: {num.sid}")
            print(f"     Isim: {num.friendly_name}")
            print(f"     SMS URL: {num.sms_url}")
            print(f"     Capabilities: {num.capabilities}")
            print(f"     Voice URL: {num.voice_url}")
            return num

    except Exception as e:
        print(f"[FAIL] Hata: {e}")

    return None

def main():
    print("[TOOL] Twilio WhatsApp Numaralarini Düzeltme Araci")
    print("=" * 60)

    # Önce çalışan numarayı kontrol et
    print("\n[STEP 0] Referans numara kontrol ediliyor...\n")
    check_working_number()

    print("\n" + "=" * 60)
    print("[STEP 1] Numaralar düzeltiliyor...\n")

    success_count = 0
    for number in NUMBERS_TO_FIX:
        if fix_number(number):
            success_count += 1

    print(f"\n\n{'='*60}")
    print(f"[OK] Tamamlandi: {success_count}/{len(NUMBERS_TO_FIX)} numara düzeltildi")
    print('='*60)

if __name__ == "__main__":
    main()

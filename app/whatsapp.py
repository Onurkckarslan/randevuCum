"""
Twilio WhatsApp entegrasyonu
"""
import os
import httpx
from twilio.rest import Client
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "")
TWILIO_ENABLED = os.getenv("TWILIO_ENABLED", "false").lower() == "true"

# Twilio client
if TWILIO_ENABLED and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    twilio_client = None


async def send_whatsapp_message(to_number: str, message: str, buttons: list = None) -> bool:
    """
    WhatsApp mesajı gönder.
    to_number: whatsapp:+905551234567 formatında
    message: mesaj içeriği
    buttons: [{"text": "Seç", "id": "1"}] formatında buton listesi
    """
    print(f"[WhatsApp] → {to_number}: {message[:60]}...")

    if not TWILIO_ENABLED or not twilio_client:
        print("[WhatsApp] Test modu — gerçek mesaj gönderilmedi")
        return True

    try:
        # Basit mesaj gönder
        msg = twilio_client.messages.create(
            from_=f"whatsapp:{TWILIO_WHATSAPP_NUMBER}",
            body=message,
            to=to_number
        )
        print(f"[WhatsApp] Gönderildi: {msg.sid}")
        return True
    except Exception as e:
        print(f"[WhatsApp] Hata: {e}")
        return False


def format_service_list(services) -> str:
    """Hizmetleri buton formatında listele"""
    if not services:
        return "Henüz hizmet eklenmemiş"

    lines = ["*Hangi hizmet istiyorsunuz?*"]
    for i, svc in enumerate(services, 1):
        lines.append(f"{i}. {svc.name} ({svc.duration} dk) - {svc.price}₺")
    return "\n".join(lines)


def format_date_list() -> str:
    """Sonraki 7 günü listele"""
    lines = ["*Hangi tarihi seçiyorsunuz?*"]
    today = datetime.now()
    for i in range(1, 8):
        d = today + timedelta(days=i)
        day_name = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"][d.weekday()]
        lines.append(f"{i}. {d.strftime('%d.%m.%Y')} ({day_name})")
    return "\n".join(lines)


def format_slot_list(slots: list) -> str:
    """Saatleri listele"""
    if not slots or all(not s.get("available") for s in slots):
        return "Seçtiğiniz tarihe uygun saat bulunamadı. Lütfen başka bir tarih seçin."

    lines = ["*Uygun saatler:*"]
    for i, slot in enumerate(slots, 1):
        if slot.get("available"):
            lines.append(f"{i}. {slot['time']}")
    return "\n".join(lines)


def parse_selection(message: str, max_options: int) -> int | None:
    """Müşterinin seçimini parse et (1-indexed)"""
    try:
        choice = int(message.strip())
        if 1 <= choice <= max_options:
            return choice
        return None
    except ValueError:
        return None


def get_next_available_date_str(choice: int) -> str:
    """Müşteri seçimine göre tarihi ISO formatında döndür"""
    today = datetime.now()
    selected = today + timedelta(days=choice)
    return selected.strftime("%Y-%m-%d")


async def purchase_twilio_number() -> str | None:
    """
    Twilio'dan yeni WhatsApp-capable numara satın al ve WhatsApp'ı etkinleştir.
    Başarılı olursa numarayı döndür, hata olursa None.
    """
    if not twilio_client or not TWILIO_ENABLED:
        print("[Twilio] Disabled - number purchase skipped (test mode)")
        return None

    try:
        print("[Twilio] Purchasing new WhatsApp number...")

        # Twilio'dan uygun bir numara al (US bölgesinde)
        # Birden fazla area code dene çünkü bazıları bitebilir
        area_codes = ["415", "510", "408", "650", "707", "209", "530"]  # California area codes
        available_numbers = None

        for area_code in area_codes:
            try:
                available_numbers = twilio_client.available_phone_numbers("US").local.list(
                    area_code=area_code,
                    limit=1
                )
                if available_numbers:
                    print(f"[Twilio] Found numbers in area code {area_code}")
                    break
            except Exception as e:
                print(f"[Twilio] Area code {area_code} failed: {e}")
                continue

        if not available_numbers:
            print("[Twilio] No available numbers in any area code")
            return None

        phone_number = available_numbers[0].phone_number

        # Numarayı satın al
        result = twilio_client.incoming_phone_numbers.create(
            phone_number=phone_number,
            friendly_name=f"RandevuCum Business WhatsApp"
        )

        purchased_number = result.phone_number
        phone_number_sid = result.sid
        print(f"[Twilio] Purchased number: {purchased_number}")

        # ✅ WhatsApp'ı bu numaraya etkinleştir
        try:
            print(f"[Twilio] Enabling WhatsApp on {purchased_number}...")
            twilio_client.messaging.phone_numbers(phone_number_sid).update(
                address_sid=None,  # WhatsApp için gerekli
                sms_fallback_method="POST",
                sms_method="POST",
                voice_fallback_method="POST",
                voice_method="POST"
            )
            print(f"[Twilio] WhatsApp enabled on {purchased_number}")
        except Exception as e:
            print(f"[Twilio] Warning enabling WhatsApp: {e}")
            # Devam et, numara yine de satın alındı

        return purchased_number

    except Exception as e:
        print(f"[Twilio] Error purchasing number: {e}")
        return None

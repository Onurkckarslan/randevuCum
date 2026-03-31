"""
Twilio WhatsApp entegrasyonu
"""
import os
import json
import httpx
from twilio.rest import Client
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER", "")
TWILIO_ENABLED = os.getenv("TWILIO_ENABLED", "false").lower() == "true"
TWILIO_MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID", "")
TWILIO_APPOINTMENT_TEMPLATE_SID = os.getenv("TWILIO_APPOINTMENT_TEMPLATE_SID", "")

# Twilio client
if TWILIO_ENABLED and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
else:
    twilio_client = None


async def send_whatsapp_message(to_number: str, message: str, from_number: str = None, buttons: list = None) -> bool:
    """
    WhatsApp mesajı gönder (plain text).
    to_number: whatsapp:+905551234567
    message: Mesaj içeriği
    from_number: Gönderen numara (default: TWILIO_WHATSAPP_NUMBER)
    """
    print(f"[WhatsApp] → {to_number}: {message[:60] if message else '(no message)'}...")

    if not TWILIO_ENABLED or not twilio_client:
        print("[WhatsApp] Test modu — gerçek mesaj gönderilmedi")
        return True

    try:
        # Gönderecek numarayı belirle
        sender_number = from_number if from_number else TWILIO_WHATSAPP_NUMBER
        if not sender_number:
            print(f"[WhatsApp] Hata: Gönderecek numara yok!")
            return False

        # Mesaj gönder
        msg = twilio_client.messages.create(
            from_=f"whatsapp:{sender_number}",
            body=message,
            to=to_number
        )
        print(f"[WhatsApp] Gönderildi: {msg.sid} (from {sender_number})")
        return True
    except Exception as e:
        print(f"[WhatsApp] Hata: {e}")
        import traceback
        traceback.print_exc()
        return False


async def send_whatsapp_template(to_number: str, template_variables: list, from_number: str = None) -> bool:
    """
    WhatsApp template mesajı gönder (approved template).
    to_number: whatsapp:+905551234567
    template_variables: ["customer_name", "business_name", "date", "time", "service_name"]
    from_number: Gönderen numara (default: TWILIO_WHATSAPP_NUMBER)
    """
    print(f"[WhatsApp Template] → {to_number} (vars: {template_variables[:2]}...)")

    if not TWILIO_ENABLED or not twilio_client:
        print("[WhatsApp Template] Test modu — gerçek mesaj gönderilmedi")
        return True

    if not TWILIO_APPOINTMENT_TEMPLATE_SID:
        print(f"[WhatsApp Template] Hata: Template SID yok! .env'e TWILIO_APPOINTMENT_TEMPLATE_SID ekle")
        return False

    try:
        sender_number = from_number if from_number else TWILIO_WHATSAPP_NUMBER
        if not sender_number:
            print(f"[WhatsApp Template] Hata: Gönderecek numara yok!")
            return False

        # Template gönder
        msg = twilio_client.messages.create(
            messaging_service_sid=TWILIO_MESSAGING_SERVICE_SID,
            from_=f"whatsapp:{sender_number}",
            to=to_number,
            content_sid=TWILIO_APPOINTMENT_TEMPLATE_SID,
            content_variables=json.dumps(template_variables)
        )
        print(f"[WhatsApp Template] ✅ Gönderildi: {msg.sid}")
        return True
    except Exception as e:
        print(f"[WhatsApp Template] ❌ Hata: {e}")
        import traceback
        traceback.print_exc()
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


async def get_or_create_messaging_service() -> str | None:
    """
    Twilio Messaging Service oluştur veya var olanı kullan (WhatsApp için).
    Service SID döndür.
    """
    if not twilio_client or not TWILIO_ENABLED:
        return None

    if TWILIO_MESSAGING_SERVICE_SID:
        print(f"[Twilio] Using existing Messaging Service: {TWILIO_MESSAGING_SERVICE_SID}")
        return TWILIO_MESSAGING_SERVICE_SID

    try:
        print("[Twilio] Creating new Messaging Service for WhatsApp...")
        service = twilio_client.messaging.services.create(
            friendly_name="RandevuCum WhatsApp Business",
            inbound_request_url="https://randevucum.com/api/whatsapp/webhook",
            inbound_method="POST"
        )
        print(f"[Twilio] Messaging Service created: {service.sid}")
        print(f"[Twilio] ⚠️  Add this to .env: TWILIO_MESSAGING_SERVICE_SID={service.sid}")
        return service.sid
    except Exception as e:
        print(f"[Twilio] Error creating Messaging Service: {e}")
        return None


async def purchase_twilio_number() -> str | None:
    """
    Twilio'dan yeni WhatsApp-capable numara satın al (UK).
    Messaging Service'e bağla.
    Başarılı olursa numarayı döndür, hata olursa None.
    """
    if not twilio_client or not TWILIO_ENABLED:
        print("[Twilio] Disabled - number purchase skipped (test mode)")
        return None

    try:
        print("[Twilio] Purchasing new WhatsApp number (UK)...")

        # Messaging Service'i al/oluştur
        service_sid = await get_or_create_messaging_service()
        if not service_sid:
            print("[Twilio] Failed to get/create Messaging Service")
            return None

        # Twilio'dan UK numarası al
        available_numbers = None

        try:
            available_numbers = twilio_client.available_phone_numbers("GB").local.list(
                limit=1
            )
            if available_numbers:
                print(f"[Twilio] Found UK number")
        except Exception as e:
            print(f"[Twilio] UK number search failed: {e}")
            return None

        if not available_numbers:
            print("[Twilio] No available numbers in any area code")
            return None

        phone_number = available_numbers[0].phone_number

        # Numarayı satın al
        result = twilio_client.incoming_phone_numbers.create(
            phone_number=phone_number,
            friendly_name="RandevuCum Business WhatsApp",
            sms_fallback_url="https://randevucum.com/api/whatsapp/webhook",
            sms_url="https://randevucum.com/api/whatsapp/webhook",
            sms_method="POST",
            voice_fallback_url="https://randevucum.com/api/whatsapp/webhook",
            voice_url="https://randevucum.com/api/whatsapp/webhook",
            voice_method="POST"
        )

        purchased_number = result.phone_number
        phone_number_sid = result.sid
        print(f"[Twilio] Purchased number: {purchased_number}")

        # ✅ Numarayı Messaging Service'e bağla
        try:
            print(f"[Twilio] Binding {purchased_number} to Messaging Service...")
            twilio_client.messaging.services(service_sid).phone_numbers.create(
                phone_number_sid=phone_number_sid
            )
            print(f"[Twilio] ✅ Number {purchased_number} bound to WhatsApp Service!")
        except Exception as e:
            print(f"[Twilio] Error binding to service: {e}")
            return None

        # ✅ WhatsApp capability'sini enable et
        try:
            print(f"[Twilio] Enabling WhatsApp capability on {purchased_number}...")
            twilio_client.incoming_phone_numbers(phone_number_sid).update(
                capabilities={'whatsapp': True}
            )
            print(f"[Twilio] ✅ WhatsApp enabled on {purchased_number}!")
        except Exception as e:
            print(f"[Twilio] Error enabling WhatsApp: {e}")
            return None

        return purchased_number

    except Exception as e:
        print(f"[Twilio] Error purchasing number: {e}")
        import traceback
        traceback.print_exc()
        return None

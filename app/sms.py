"""
Twilio SMS entegrasyonu
"""
import os
import asyncio
from datetime import datetime
from twilio.rest import Client

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_SMS_NUMBER = "+15108718367"  # Twilio SMS numarası
TWILIO_ENABLED = os.getenv("TWILIO_ENABLED", "false").lower() == "true"

twilio_client = None
if TWILIO_ENABLED and TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


async def send_sms(phone: str, message: str) -> bool:
    """Twilio üzerinden SMS gönder."""
    # Telefon numarasını format'la: 05... → +905...
    formatted_phone = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if formatted_phone.startswith("0"):
        formatted_phone = "+9" + formatted_phone
    elif not formatted_phone.startswith("+"):
        formatted_phone = "+" + formatted_phone

    print(f"[SMS] → {formatted_phone}: {message[:60]}...")

    if not TWILIO_ENABLED or not twilio_client:
        print("[SMS] Test modu — gerçek SMS gönderilmedi")
        return True

    try:
        msg = twilio_client.messages.create(
            body=message,
            from_=TWILIO_SMS_NUMBER,
            to=formatted_phone
        )
        print(f"[SMS] Gönderildi: {msg.sid}")
        return True
    except Exception as e:
        print(f"[SMS] Hata: {e}")
        return False


async def send_appointment_confirm(customer_name: str, phone: str,
                                    business_name: str, service: str,
                                    date: str, time: str) -> bool:
    msg = (
        f"Merhaba {customer_name}, {business_name} icin {date} {time} "
        f"tarihli {service} randevunuz olusturuldu. "
        f"Iptal: randevucum.com"
    )
    return await send_sms(phone, msg)


async def send_day_before_reminder(customer_name: str, phone: str,
                                    business_name: str, date: str, time: str) -> bool:
    msg = (
        f"Hatirlatma: Yarin {time} icin {business_name} randevunuz var. "
        f"Iptal icin: randevucum.com"
    )
    return await send_sms(phone, msg)


async def send_2h_reminder(customer_name: str, phone: str,
                            business_name: str, time: str) -> bool:
    msg = (
        f"Hatirlatma: Bugun {time} icin {business_name} randevunuz 2 saat sonra. "
        f"Iyi gunler!"
    )
    return await send_sms(phone, msg)


async def send_booking_with_products_customer(customer_phone: str, customer_name: str,
                                              business_name: str, service_name: str,
                                              date: str, time: str, products: list) -> bool:
    """Müşteriye randevu + ürün bilgisi ile SMS gönder"""
    product_line = ""
    if products:
        product_names = [f"{p.product.name} x{p.quantity}" for p in products]
        product_line = " | Urunler: " + ", ".join(product_names)

    msg = (
        f"Merhaba {customer_name}, {business_name} icin {date} {time} "
        f"tarihli {service_name} randevunuz olusturuldu.{product_line}"
    )
    return await send_sms(customer_phone, msg)


async def send_booking_with_products_business(business_phone: str, customer_name: str,
                                              service_name: str, date: str, time: str,
                                              products: list, customer_notes: str = "") -> bool:
    """İşletme sahibine yeni randevu + ürün bilgisi + müşteri notları ile SMS gönder"""
    product_line = ""
    if products:
        product_names = [f"{p.product.name} x{p.quantity}" for p in products]
        product_line = " | Urunler: " + ", ".join(product_names)

    notes_line = ""
    if customer_notes and customer_notes.strip():
        notes_line = f" | Notlar: {customer_notes[:100]}"

    msg = (
        f"Yeni randevu: {customer_name} - {service_name} - {date} saat {time}{product_line}{notes_line}"
    )
    return await send_sms(business_phone, msg)


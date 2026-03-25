"""
İletibilgi.com SMS entegrasyonu
API belgesi: https://www.iletibilgi.com.tr/api
"""
import httpx
import os
import asyncio
from datetime import datetime

SMS_USER    = os.getenv("SMS_USER", "")
SMS_PASS    = os.getenv("SMS_PASS", "")
SMS_SENDER  = os.getenv("SMS_SENDER", "RANDEVUCUM")   # Başlık (max 11 karakter)
SMS_ENABLED = os.getenv("SMS_ENABLED", "false").lower() == "true"


async def send_sms(phone: str, message: str) -> bool:
    """SMS gönder. SMS_ENABLED=false ise sadece loglar."""
    phone = phone.replace(" ", "").replace("-", "").replace("+90", "").replace("(", "").replace(")", "")
    if phone.startswith("0"):
        phone = phone[1:]

    print(f"[SMS] → {phone}: {message[:60]}...")

    if not SMS_ENABLED:
        print("[SMS] Test modu — gerçek SMS gönderilmedi")
        return True

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                "https://api.iletibilgi.com.tr/SendSms",
                params={
                    "username": SMS_USER,
                    "password": SMS_PASS,
                    "sender":   SMS_SENDER,
                    "tel":      phone,
                    "msg":      message,
                    "datacoding": "0",
                }
            )
            ok = resp.status_code == 200 and "Error" not in resp.text
            if not ok:
                print(f"[SMS] Hata: {resp.text}")
            return ok
    except Exception as e:
        print(f"[SMS] Bağlantı hatası: {e}")
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


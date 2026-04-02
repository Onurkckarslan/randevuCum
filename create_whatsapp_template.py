#!/usr/bin/env python3
"""
Twilio WhatsApp Template oluştur (REST API)
"""
import os
import sys
import requests
from requests.auth import HTTPBasicAuth
import json

# Encoding
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_MESSAGING_SERVICE_SID]):
    print("[ERROR] Twilio credentials eksik!")
    exit(1)

# Template oluştur
print("=" * 70)
print("WhatsApp Template Oluşturuluyor...")
print("=" * 70)

template_body = """Merhaba {{1}},

{{2}} için {{3}} {{4}}'de {{5}} randevunuz onaylandı.

Teşekkür ederiz!"""

try:
    # Twilio REST API
    url = f"https://messaging.twilio.com/v1/Services/{TWILIO_MESSAGING_SERVICE_SID}/PhoneNumberQuality/PhoneNumbers/Templates"

    data = {
        "FriendlyName": "appointment_confirmation_v2",
        "Language": "tr",
        "Content": {
            "Body": template_body,
            "Variables": ["customer_name", "business_name", "date", "time", "service_name"]
        }
    }

    print(f"\n📡 API Call: POST {url}")
    print(f"   FriendlyName: appointment_confirmation_v2")
    print(f"   Language: tr")

    response = requests.post(
        url,
        json=data,
        auth=HTTPBasicAuth(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    )

    print(f"\n   Status Code: {response.status_code}")

    if response.status_code in [200, 201]:
        result = response.json()
        print(f"\n✅ Template Başarıyla Oluşturuldu!")
        print(f"   Template SID: {result.get('sid')}")
        print(f"   Status: {result.get('status')}")

        print(f"\n📝 Template Body:")
        print(f"   {template_body}")

        print(f"\n💾 .env'e Ekle:")
        print(f"   TWILIO_APPOINTMENT_TEMPLATE_SID={result.get('sid')}")

        print(f"\n⏳ Onay Bekleyen: {result.get('status')}")
        print(f"   1-2 saat sonra onaylanmalı...")

    else:
        print(f"\n❌ Hata: HTTP {response.status_code}")
        print(f"   Response: {response.text}")

except Exception as e:
    print(f"\n❌ Hata: {type(e).__name__}")
    print(f"   {str(e)}")
    import traceback
    traceback.print_exc()

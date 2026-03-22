import requests
import os
import logging
from base64 import b64encode

logger = logging.getLogger(__name__)

# Mailgun API configuration
MAILGUN_DOMAIN = "www.randevucum.com"
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_API_URL = f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages"
SENDER_EMAIL = "noreply@www.randevucum.com"

def send_password_reset_email(to_email: str, reset_link: str):
    """Şifre sıfırlama emaili gönder (Mailgun API ile)"""
    try:
        logger.info(f"[EMAIL] Mailgun API ile başlıyor... {to_email} adresine")

        body_html = f"""
        <html>
            <body style="font-family: Arial, sans-serif; direction: rtl;">
                <h2 style="color: #7c3aed;">Şifre Sıfırlama Talebi</h2>
                <p>Merhaba,</p>
                <p>Şifrenizi sıfırlamak için aşağıdaki bağlantıya tıklayın:</p>
                <p>
                    <a href="{reset_link}" style="background: #7c3aed; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block;">
                        Şifremi Sıfırla
                    </a>
                </p>
                <p>Bu bağlantı 1 saat geçerlidir.</p>
                <p>Eğer bu talebini sen yapmadıysan, bu emaili görmezden gel.</p>
                <p>
                    <strong>RandevuCum Ekibi</strong>
                </p>
            </body>
        </html>
        """

        # Mailgun API isteği
        auth = ("api", MAILGUN_API_KEY)
        data = {
            "from": SENDER_EMAIL,
            "to": to_email,
            "subject": "RandevuCum - Şifre Sıfırlama",
            "html": body_html
        }

        response = requests.post(MAILGUN_API_URL, auth=auth, data=data, timeout=10)

        if response.status_code == 200:
            logger.info(f"[EMAIL] ✅ Başarılı: {to_email}")
            return True
        else:
            logger.error(f"[EMAIL] ❌ Mailgun hatası: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        logger.error(f"[EMAIL] ❌ HATA: {type(e).__name__}: {e}", exc_info=True)
        return False

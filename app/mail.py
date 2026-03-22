from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
import logging

logger = logging.getLogger(__name__)

# SendGrid configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDER_EMAIL = "noreply@randevucum.com"

def send_password_reset_email(to_email: str, reset_link: str):
    """Şifre sıfırlama emaili gönder (SendGrid ile)"""
    try:
        if not SENDGRID_API_KEY:
            logger.error("[EMAIL] ❌ SENDGRID_API_KEY ayarlanmamış")
            return False

        logger.info(f"[EMAIL] SendGrid ile başlıyor... {to_email} adresine")

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

        # SendGrid mesajı oluştur
        message = Mail(
            from_email=SENDER_EMAIL,
            to_emails=to_email,
            subject="RandevuCum - Şifre Sıfırlama",
            html_content=body_html
        )

        # SendGrid ile gönder
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)

        if response.status_code == 202:
            logger.info(f"[EMAIL] ✅ Başarılı: {to_email}")
            return True
        else:
            logger.error(f"[EMAIL] ❌ SendGrid hatası: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"[EMAIL] ❌ HATA: {type(e).__name__}: {e}", exc_info=True)
        return False

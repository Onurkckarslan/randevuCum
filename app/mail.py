import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = "randevucum.noreply@gmail.com"
SENDER_PASSWORD = "smqw ivad fhpv xwmj"  # App Password

def send_password_reset_email(to_email: str, reset_link: str):
    """Şifre sıfırlama emaili gönder"""
    try:
        print(f"[EMAIL] Başlıyor... {to_email} adresine")

        message = MIMEMultipart()
        message["From"] = SENDER_EMAIL
        message["To"] = to_email
        message["Subject"] = "RandevuCum - Şifre Sıfırlama"

        body = f"""
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

        message.attach(MIMEText(body, "html", "utf-8"))

        # Gmail'e bağlan ve gönder
        print(f"[EMAIL] SMTP bağlantısı kuruluyor: {SMTP_SERVER}:{SMTP_PORT}")
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10)
        print(f"[EMAIL] TLS başlatılıyor")
        server.starttls()
        print(f"[EMAIL] {SENDER_EMAIL} ile giriş yapılıyor")
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        print(f"[EMAIL] Email gönderiliyor")
        server.send_message(message)
        server.quit()
        print(f"[EMAIL] ✅ Başarılı: {to_email}")

        return True
    except Exception as e:
        print(f"[EMAIL] ❌ HATA: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return False

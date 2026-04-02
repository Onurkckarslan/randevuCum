"""
Sistem sağlık kontrolleri — AWS S3, Twilio, SendGrid, Database
"""
import os
import asyncio
from datetime import datetime
from pathlib import Path
from botocore.exceptions import ClientError
import httpx

# S3
from .s3_upload import s3_client, S3_BUCKET

# Twilio
from twilio.rest import Client as TwilioClient

# Database
from .database import engine, SQLALCHEMY_DATABASE_URL


async def check_s3() -> dict:
    """AWS S3 kontrol: kaç dosya, toplam boyut"""
    try:
        if not S3_BUCKET:
            return {
                "status": "HATA",
                "file_count": 0,
                "total_mb": 0,
                "checked_at": datetime.now().isoformat(),
                "error": "S3_BUCKET ayarlanmamış"
            }

        # Sync boto3 operasyonunu executor'da çalıştır
        def _list_objects():
            paginator = s3_client.get_paginator("list_objects_v2")
            pages = paginator.paginate(Bucket=S3_BUCKET)

            file_count = 0
            total_size = 0
            for page in pages:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        file_count += 1
                        total_size += obj.get("Size", 0)

            return file_count, total_size

        loop = asyncio.get_event_loop()
        file_count, total_size = await loop.run_in_executor(None, _list_objects)
        total_mb = round(total_size / 1024 / 1024, 2)

        status = "OK" if file_count > 0 else "UYARI"
        return {
            "status": status,
            "file_count": file_count,
            "total_mb": total_mb,
            "checked_at": datetime.now().isoformat()
        }

    except ClientError as e:
        return {
            "status": "HATA",
            "file_count": 0,
            "total_mb": 0,
            "checked_at": datetime.now().isoformat(),
            "error": f"S3 hatası: {str(e)[:50]}"
        }
    except Exception as e:
        return {
            "status": "HATA",
            "file_count": 0,
            "total_mb": 0,
            "checked_at": datetime.now().isoformat(),
            "error": f"{type(e).__name__}: {str(e)[:50]}"
        }


async def check_twilio() -> dict:
    """Twilio kontrol: account bakiyesi"""
    try:
        twilio_enabled = os.getenv("TWILIO_ENABLED", "false").lower() == "true"
        if not twilio_enabled:
            return {
                "status": "UYARI",
                "balance": None,
                "currency": None,
                "checked_at": datetime.now().isoformat(),
                "message": "Twilio devre dışı"
            }

        account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")

        if not account_sid or not auth_token:
            return {
                "status": "HATA",
                "balance": None,
                "currency": None,
                "checked_at": datetime.now().isoformat(),
                "error": "Twilio credentials eksik"
            }

        # Sync API call'ını executor'da çalıştır
        def _fetch_balance():
            client = TwilioClient(account_sid, auth_token)
            account = client.api.v2010.accounts(account_sid).fetch()
            return float(account.balance), account.currency

        loop = asyncio.get_event_loop()
        balance, currency = await loop.run_in_executor(None, _fetch_balance)

        if balance < 0.01:
            status = "HATA"
        elif balance < 1:
            status = "UYARI"
        else:
            status = "OK"

        return {
            "status": status,
            "balance": round(balance, 2),
            "currency": currency,
            "checked_at": datetime.now().isoformat()
        }

    except Exception as e:
        return {
            "status": "HATA",
            "balance": None,
            "currency": None,
            "checked_at": datetime.now().isoformat(),
            "error": f"{type(e).__name__}: {str(e)[:50]}"
        }


async def check_sendgrid() -> dict:
    """SendGrid kontrol: bugünkü email sayısı, plan limiti"""
    try:
        api_key = os.getenv("SENDGRID_API_KEY", "")
        if not api_key:
            return {
                "status": "HATA",
                "today_sent": 0,
                "plan_limit": None,
                "remaining": None,
                "checked_at": datetime.now().isoformat(),
                "error": "SendGrid API key eksik"
            }

        today = datetime.now().strftime("%Y-%m-%d")

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Bugünkü istatistikleri al
            stats_response = await client.get(
                f"https://api.sendgrid.com/v3/stats?start_date={today}&end_date={today}",
                headers={"Authorization": f"Bearer {api_key}"}
            )

            # Plan limitlerini al
            credits_response = await client.get(
                "https://api.sendgrid.com/v3/user/credits",
                headers={"Authorization": f"Bearer {api_key}"}
            )

            if stats_response.status_code != 200 or credits_response.status_code != 200:
                return {
                    "status": "HATA",
                    "today_sent": 0,
                    "plan_limit": None,
                    "remaining": None,
                    "checked_at": datetime.now().isoformat(),
                    "error": f"API error: {stats_response.status_code}"
                }

            stats_data = stats_response.json()
            credits_data = credits_response.json()

            # Bugünkü gönderim sayısı
            today_sent = 0
            if stats_data and len(stats_data) > 0:
                today_sent = stats_data[0].get("stats", [{}])[0].get("requests", 0)

            # Plan limiti ve kalan
            plan_limit = credits_data.get("limit", None)
            remaining = credits_data.get("remaining", None)

            if remaining is not None:
                if remaining > 100:
                    status = "OK"
                elif remaining > 0:
                    status = "UYARI"
                else:
                    status = "HATA"
            else:
                status = "OK"

            return {
                "status": status,
                "today_sent": today_sent,
                "plan_limit": plan_limit,
                "remaining": remaining,
                "checked_at": datetime.now().isoformat()
            }

    except Exception as e:
        return {
            "status": "HATA",
            "today_sent": 0,
            "plan_limit": None,
            "remaining": None,
            "checked_at": datetime.now().isoformat(),
            "error": f"{type(e).__name__}: {str(e)[:50]}"
        }


async def check_database() -> dict:
    """Database kontrol: SQLite boyutu ya da PostgreSQL bağlantısı"""
    try:
        if "sqlite" in SQLALCHEMY_DATABASE_URL.lower():
            # SQLite: dosya boyutu
            db_path = Path(__file__).parent.parent / "RandevuCum.db"
            if db_path.exists():
                size_bytes = db_path.stat().st_size
                size_mb = round(size_bytes / 1024 / 1024, 2)
            else:
                size_mb = 0

            return {
                "status": "OK",
                "db_type": "sqlite",
                "size_mb": size_mb,
                "checked_at": datetime.now().isoformat()
            }
        else:
            # PostgreSQL: bağlantı testi
            def _test_connection():
                with engine.connect() as conn:
                    from sqlalchemy import text
                    conn.execute(text("SELECT 1"))
                return True

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _test_connection)

            return {
                "status": "OK",
                "db_type": "postgresql",
                "size_mb": None,
                "checked_at": datetime.now().isoformat()
            }

    except Exception as e:
        return {
            "status": "HATA",
            "db_type": "unknown",
            "size_mb": None,
            "checked_at": datetime.now().isoformat(),
            "error": f"{type(e).__name__}: {str(e)[:50]}"
        }


async def get_system_status() -> dict:
    """Tüm sistem sağlık kontrolleri — paralel çalıştır"""
    results = await asyncio.gather(
        check_s3(),
        check_twilio(),
        check_sendgrid(),
        check_database(),
        return_exceptions=True
    )

    # Exception'ları düzenle
    def wrap_exception(result):
        if isinstance(result, Exception):
            return {
                "status": "HATA",
                "checked_at": datetime.now().isoformat(),
                "error": f"{type(result).__name__}: {str(result)[:50]}"
            }
        return result

    return {
        "s3": wrap_exception(results[0]),
        "twilio": wrap_exception(results[1]),
        "sendgrid": wrap_exception(results[2]),
        "database": wrap_exception(results[3])
    }

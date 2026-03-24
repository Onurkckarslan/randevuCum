# Comprehensive Security Test Plan

## 1️⃣ Registration Security Tests

### Test 1.1: Zayıf Şifre Reddetme
```
Email: test1@test.com
Şifre: 123 (3 karakter)
Beklenti: ❌ "Şifre en az 6 karakter olmalı."
```

### Test 1.2: Invalid Email Format
```
Email: invalidemail
Şifre: ValidPassword123
Beklenti: ❌ "Geçerli bir e-posta adresi girin."
```

### Test 1.3: Duplicate Email
```
Email: bjk_onur64@hotmail.com (var olan)
Beklenti: ❌ "Bu e-posta zaten kayıtlı."
```

### Test 1.4: Valid Registration
```
Email: security_test_123@gmail.com
Şifre: SecurePass123
Beklenti: ✅ Panel'e yönlendir + login cookie set
```

**Kontrol:**
- Cookie'de token var mı? (DevTools → Application → Cookies)
- Token httponly=true mi? (Cookie detaylında HttpOnly flag görülmemeli)
- Token secure=true mi? (HTTPS'de gönderiliyor mu?)

---

## 2️⃣ Login Security Tests

### Test 2.1: Yanlış Şifre
```
Email: security_test_123@gmail.com
Şifre: WrongPassword
Beklenti: ❌ "E-posta veya şifre hatalı."
```

### Test 2.2: Olmayan Email
```
Email: nonexistent@test.com
Beklenti: ❌ "E-posta veya şifre hatalı."
```

### Test 2.3: Doğru Giriş
```
Email: security_test_123@gmail.com
Şifre: SecurePass123
Beklenti: ✅ Panel açılsın
```

---

## 3️⃣ Password Reset Security Tests

### Test 3.1: Reset Link Gönderme
```
Email: security_test_123@gmail.com
Beklenti: ✅ Mail gelsin
```

### Test 3.2: Şifre Eşleşmiyor
```
Yeni Şifre: NewPass123
Onayla: DifferentPass123
Beklenti: ❌ "Şifreler eşleşmiyor."
```

### Test 3.3: Çok Kısa Şifre
```
Yeni Şifre: 123
Onayla: 123
Beklenti: ❌ "Yeni şifre en az 6 karakter olmalı."
```

### Test 3.4: Başarılı Reset
```
Yeni Şifre: NewSecurePass456
Onayla: NewSecurePass456
Beklenti: ✅ /giris'e redirect
```

### Test 3.5: Reset Sonrası Login
```
Email: security_test_123@gmail.com
Şifre: NewSecurePass456
Beklenti: ✅ Panel açılsın
```

### Test 3.6: Invalid Token
```
URL'yi düzelt: /sifremi-sifirla/fake-token-123
Beklenti: ❌ "Geçersiz veya süresi dolmuş reset linki."
```

---

## 4️⃣ File & API Security Tests

### Test 4.1: Profil Resmi Upload
```
1. Panel → Resmi Yükle
2. Resim seç ve upload yap
Beklenti: ✅ S3'e yüklensim
```

### Test 4.2: Email Gönderme
```
1. /sifremi-unuttum
2. Email gir
Beklenti: ✅ SendGrid üzerinden mail gelsin
```

---

## 5️⃣ Cookie & Session Security Tests

### Test 5.1: Cookie Settings (Chrome DevTools)
```
1. F12 → Application → Cookies
2. Token cookie'yi kontrol et:
   - ✅ HttpOnly: true (script tarafından erişilemez)
   - ✅ Secure: true (HTTPS only)
   - ✅ SameSite: strict (CSRF koruması)
   - ✅ Path: / (tüm sayfalarda)
```

### Test 5.2: Session Timeout
```
1. Login yap
2. Cookie'yi sil (DevTools)
3. Sayfayı refresh et
Beklenti: ❌ /giris'e yönlendir
```

### Test 5.3: Token Tampering
```
1. Token cookie'yi edit et (DevTools)
2. İlk 5 karakteri değiştir
3. Sayfayı refresh et
Beklenti: ❌ /giris'e yönlendir (invalid token)
```

---

## 6️⃣ Database & Password Security Tests

### Test 6.1: Database Check
```bash
# Local'de:
sqlite3 RandevuCum.db
SELECT email, password_hash FROM businesses WHERE email='security_test_123@gmail.com';
```
**Beklenti:**
- Password $2b$ ile başlamalı (bcrypt format)
- Hash 60 karakter olmalı
- Şifre açık görülmemeli

### Test 6.2: Hash Verification
```bash
python3
>>> from app.auth import hash_password, verify_password
>>> old_hash = "$2b$..."  # Veritabanından al
>>> verify_password("NewSecurePass456", old_hash)
True
>>> verify_password("WrongPassword", old_hash)
False
```

---

## 7️⃣ Git & Environment Security Tests

### Test 7.1: .env Protection
```bash
git status
# Beklenti: .env görülmemeli (ignored)
```

### Test 7.2: .env.example Check
```bash
cat .env.example
# Beklenti: Gerçek key'ler değil, placeholders olmalı
```

### Test 7.3: GitHub Check
```
https://github.com/Onurkckarslan/randevuCum
→ Search for "AWS_SECRET" veya "SENDGRID"
# Beklenti: Hiç sonuç çıkmamalı ✅
```

---

## ✅ Test Completion Checklist

- [ ] Registration validation tests (1.1-1.4)
- [ ] Login security tests (2.1-2.3)
- [ ] Password reset tests (3.1-3.6)
- [ ] File upload works (4.1)
- [ ] Email sending works (4.2)
- [ ] Cookie settings correct (5.1)
- [ ] Session timeout works (5.2)
- [ ] Token tampering rejected (5.3)
- [ ] Password hashing verified (6.1-6.2)
- [ ] Git security verified (7.1-7.3)

---

## 🚨 If Any Test Fails

1. Check Render logs:
   ```
   Render Dashboard → randevucum-app → Logs
   ```

2. Check local:
   ```bash
   python3 -c "from app.auth import verify_password; print(verify_password('test', '\$2b\$12\$...'))"
   ```

3. Check database:
   ```bash
   sqlite3 RandevuCum.db "SELECT COUNT(*) FROM businesses;"
   ```

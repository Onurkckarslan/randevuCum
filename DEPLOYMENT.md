# Production Deployment Checklist

## 🔐 Security & Keys Setup (DO THIS FIRST!)

### Step 1: Create AWS Access Keys
1. Go to https://console.aws.amazon.com
2. IAM → Users → Select your user
3. Security Credentials → Create access key
4. Copy and save:
   - `AWS_ACCESS_KEY_ID`
   - `AWS_SECRET_ACCESS_KEY`

### Step 2: Get SendGrid API Key
1. Go to https://app.sendgrid.com/settings/api_keys
2. Create new API key (Full Access)
3. Copy and save the key

### Step 3: Generate Strong SECRET_KEY
Run this in terminal:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```
Copy the output (it's your SECRET_KEY)

---

## 🚀 Deploy to Render

### Step 1: Update Render Environment Variables
1. Go to https://dashboard.render.com
2. Select your service (randevucum-app)
3. Click "Environment"
4. Add/Update these variables:

```
ENVIRONMENT=production
SECRET_KEY=<paste-from-step-3-above>
AWS_ACCESS_KEY_ID=<paste-from-step-1>
AWS_SECRET_ACCESS_KEY=<paste-from-step-1>
SENDGRID_API_KEY=<paste-from-step-2>
AWS_S3_BUCKET=randevucum-app
AWS_S3_REGION=eu-north-1
```

### Step 2: Push to GitHub
```bash
git add .env.example DEPLOYMENT.md
git commit -m "Add deployment documentation"
git push origin main
```

**Render will automatically deploy!**

---

## ✅ Verification Checklist

After deployment:

- [ ] Registration works (test at randevucum.com/kayit)
- [ ] Login works (test at randevucum.com/giris)
- [ ] Email is sent on password reset
- [ ] Profile pictures upload to S3
- [ ] No errors in Render logs

Check logs:
```
Render Dashboard → randevucum-app → Logs
```

---

## 🔒 Security Notes

- ✅ `.env.example` is in Git (safe - no real keys)
- ✅ `.env` is in `.gitignore` (never in Git)
- ✅ Render stores secrets encrypted
- ✅ Cookies use HTTPS in production (secure=True)
- ✅ CSRF protection: samesite=strict

---

## ⚠️ If Something Goes Wrong

Check these:
1. All environment variables are set in Render
2. No typos in variable names
3. AWS keys are still active (not deleted)
4. SendGrid key is still valid
5. Check Render logs for errors

```
Render Dashboard → randevucum-app → Logs
```

# AI Voice Appointment Assistant (Django + Twilio + Celery + Postgres + Redis)

A minimal **AI receptionist / appointment booking** backend.

- **Django** (webhooks + admin)
- **Celery** (background booking jobs)
- **PostgreSQL** (data)
- **Redis** (queue)
- **Twilio** (voice + speech recognition)
- **Docker Compose** (one-command dev stack)

> Built for learning and interview demos.  
> Handles a real phone call, collects details, books a slot, stores it, and sends notifications.

---

## 🚀 Features

- `/webhooks/twilio/voice/` – Twilio hits this when a call comes in; greets and starts `<Gather>` (speech)
- `/webhooks/twilio/gather-action/` – Twilio posts transcription results here; continues the dialog or books
- **Slot filling** (service + time), confirmation, then **Celery** creates a booking
- **Django Admin** to inspect calls and bookings
- Optional **SMS** (Twilio REST) and **Email** (SMTP or console backend)

---

## 🧩 Running Locally (Docker)

**Requirements:** Docker Desktop, PowerShell/Terminal.

### 1. Clone repo & create `.env`
```bash
git clone https://github.com/<your-username>/<repo>.git
cd <repo>
cp .env.example .env
# Fill .env (at least PUBLIC_BASE_URL once you have a tunnel)
```

### 2. Start services
```bash
docker compose up -d
```

### 3. Initialize DB & admin user
```bash
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

### 4. Open Admin
Visit:  
**http://localhost:8000/admin**  
→ Login → See Calls & Bookings

---

## 🌐 Exposing Locally to Twilio (Dev)

Twilio needs to reach your local server. Use a tunnel:

```bash
cloudflared tunnel --protocol http2 --url http://localhost:8000
```

> Note the URL it prints, e.g. `https://xyz.trycloudflare.com`

Set this domain in your `.env`:

```bash
PUBLIC_BASE_URL=https://xyz.trycloudflare.com
```

Then rebuild:

```bash
docker compose up -d --build
```

In **Twilio Console → Phone Numbers → Your Number → Voice & Fax**,  
set **A CALL COMES IN = Webhook (POST):**

```
https://xyz.trycloudflare.com/webhooks/twilio/voice/
```

### Sanity Checks
- [https://xyz.trycloudflare.com/health/](https://xyz.trycloudflare.com/health/) → `OK`
- [https://xyz.trycloudflare.com/webhooks/twilio/voice/](https://xyz.trycloudflare.com/webhooks/twilio/voice/) → `POST required`
- [https://xyz.trycloudflare.com/webhooks/twilio/gather-action/](https://xyz.trycloudflare.com/webhooks/twilio/gather-action/) → `POST required`

### Logs
```bash
docker compose logs -f web
docker compose logs -f worker
```

---


## 📧 Email Notifications

**Dev (default):** emails print to web logs (console backend).

### Real Gmail SMTP
1. Enable 2-Step Verification in your Google Account.  
2. Create a Google **App Password** for Mail (16 chars).  
3. Set in `.env`:

```bash
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=<your-app-password>
EMAIL_USE_TLS=True
NOTIFY_EMAIL=you@gmail.com
```

Rebuild:
```bash
docker compose up -d --build
```

Test:
```bash
docker compose exec web python manage.py shell -c "from django.core.mail import send_mail; print(send_mail('Test','Hello','you@gmail.com',['you@gmail.com'], fail_silently=False))"
```

---

## 📱 SMS Confirmations (Optional)

Set Twilio creds in `.env`:

```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_FROM_NUMBER=+1xxxxxxxxxx
```

Rebuild:
```bash
docker compose up -d --build
```

> Trial accounts: SMS/calls only to verified numbers.

---

## 🔗 Endpoints Summary

| Method | Endpoint | Description |
|--------|-----------|-------------|
| `GET` | `/health/` | Uptime check |
| `GET` | `/admin/` | Django Admin |
| `POST` | `/webhooks/twilio/voice/` | First Twilio webhook (returns TwiML with `<Gather>`) |
| `POST` | `/webhooks/twilio/gather-action/` | Twilio speech results (returns next `<Gather>` or final `<Say>`) |
| `POST` | `/webhooks/retell/events/` | Optional JSON test hook |

---

## 🧠 Tech Decisions

- **Django** for fast production readiness (ORM, admin, security)
- **Celery + Redis** for async booking jobs
- **Postgres** for reliability & indexing (Docker volume persists data)
- **Cloudflare Tunnel** only for dev exposure
- **Full containerization** for consistent dev setup

---

## ☁️ Production Notes (Brief)

- Put behind ALB or reverse proxy (HTTPS)
- Use RDS Postgres, ElastiCache Redis, S3 for blobs
- Add **Twilio signature verification** on webhooks
- Store secrets in **AWS Secrets Manager** or env vars
- Add observability: metrics, logs, alerts

---

## License

**MIT** (or choose another)


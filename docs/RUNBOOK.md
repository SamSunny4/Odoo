# Brightloop Subscription Management System — Production Operations Runbook

This runbook outlines standard operating procedures, failure recovery paths, backup/restore runbooks, and staff guidelines for running the Brightloop platform in production.

---

## 1. System Architecture & Topology

| Service | Component | Responsibility | Standard Port |
|---|---|---|---|
| **Reverse Proxy** | Caddy / Nginx | Automated TLS/HTTPS, security headers, request routing | `80`, `443` |
| **Web UI** | React 19 + Vite | Admin & Customer single-page application | `5173` (dev) / `80` (prod) |
| **API** | FastAPI (Python 3.13) | REST API, validation, auth, invoice engine, report generation | `8000` |
| **Database** | PostgreSQL 18 | ACID persistence, financial ledger, relational constraints | `5432` |
| **Cache & Broker** | Redis 7 | Celery broker, session revocations, distributed rate limiting | `6379` |
| **Background Worker** | Celery Worker | Async billing runs, email delivery, retry queue execution | Internal |
| **Scheduler** | Celery Beat | Automated cron triggers (daily recurring billing, overdue checks) | Internal |
| **Mail Gateway** | Mailpit (dev) / SMTP (prod) | Transactional email delivery and inspection | `1025`, `8025` |

---

## 2. Environment Variables & Secrets Management

The platform enforces strict secrets validation:
- **`SECRET_KEY`**: Minimum 32-character cryptographically random string (e.g. `openssl rand -hex 32`). Development keys are rejected at startup when `ENVIRONMENT=production`.
- **`SESSION_COOKIE_SECURE`**: Automatically enforced in production (`Secure; HttpOnly; SameSite=Lax`).
- **`DATABASE_URL`**: Async PostgreSQL driver (`postgresql+asyncpg://...`).
- **`SYNC_DATABASE_URL`**: Synchronous driver for Alembic and Celery sync sessions (`postgresql://...`).
- **`REDIS_URL`**: Redis connection string with password protection.
- **`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`**: Transactional email gateway credentials.

---

## 3. Deployment & Local Setup

### 3.1 Local Development (with Docker)
```bash
# 1. Copy environment template
cp .env.example .env

# 2. Start all services (PostgreSQL, Redis, Mailpit, API, Worker, Beat, Frontend)
docker compose up -d

# 3. Seed demo accounts and catalog
docker compose exec backend python -m app.seed
```

### 3.2 Production Release Launch
```bash
# 1. Configure production environment
cp .env.production.example .env.production
# Edit .env.production with domain and real credentials

# 2. Start production stack with automated TLS and Caddy
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build

# 3. Apply all database migrations
docker compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

---

## 4. Database Backups, Restore & Disaster Recovery

### 4.1 Scheduled Backups
Run automated backups daily via cron:
```bash
# Linux / macOS / POSIX
./scripts/backup.sh /var/backups/brightloop_daily_$(date +\%F).sql

# Windows PowerShell
.\scripts\backup.ps1 -OutputFile "C:\backups\brightloop_daily.sql"
```

### 4.2 Restoring from Backup
```bash
# Restore specific snapshot into PostgreSQL
./scripts/restore.sh /var/backups/brightloop_daily_2026-10-31.sql --force

# Or interactively in PowerShell:
.\scripts\restore.ps1 -BackupFile "C:\backups\brightloop_daily.sql"
```

### 4.3 Automated Backup & Restore Rehearsal
Verify disaster recovery readiness and table integrity before any release:
```bash
python scripts/rehearse_backup_restore.py
```
*Expected exit code: `0` (`CERTIFIED_PRODUCTION_READY`).*

---

## 5. Billing Control Tower & Recurring Billing Operations

### 5.1 Automated Schedule
- **Trigger:** Celery Beat task `tasks.generate_recurring_invoices` runs daily at 00:00 UTC.
- **Pipeline:**
  1. Identifies active subscriptions where `next_billing_date <= today`.
  2. Generates draft/confirmed invoices enforcing idempotency keys (`sub_{id}_{period_start}_{period_end}`).
  3. Copies customer snapshots, products, variants, taxes, and active discount rules.
  4. Advances subscription `next_billing_date` by the plan cadence.
  5. Queues outbox email delivery to customer.

### 5.2 Standout Manual Control Tower Workflow
Staff can preview and approve billing before issuing documents:
1. Navigate to **Control Tower** (`/control-tower`).
2. Click **Generate Preview Batch** (select batch size: 25, 50, 100, 250).
3. Review projected totals and variance explanations against prior invoices.
4. If flagged items exist:
   - Click **Inspect** to see missing tax IDs or exhausted discount rules.
   - Click **Retry Item** after fixing customer details in Catalog/Subscriptions.
   - Click **Skip Item** with an audit justification if holding billing for AE review.
5. Click **Commit Clean Batch** to execute atomically.
6. Click **Export Batch CSV** for accounting record-keeping.

---

## 6. Outbox Email & Communications Troubleshooting

### 6.1 Architecture
The system uses the **Transactional Outbox Pattern**:
- Email messages are written to the `outbox_messages` table within the same database transaction as the financial change.
- The background worker dispatches messages asynchronously with exponential backoff retries.
- Failed email delivery **never** rolls back or voids a valid financial invoice.

### 6.2 Managing Failed Emails
1. Navigate to **Communications** (`/communications`).
2. Filter by status: `Failed` or `Pending`.
3. Inspect error details (e.g. SMTP connection timeout or invalid recipient address).
4. Click **Retry Delivery** to reset retry counter and schedule immediate dispatch.

---

## 7. Health Checks, Monitoring & Alerting

### 7.1 Liveness & Readiness Probes
- Endpoint: `GET /health` or `GET /api/v1/health`
- **Output Schema:**
```json
{
  "status": "ok",
  "database_connected": true,
  "redis_connected": true,
  "environment": "production",
  "version": "1.0.0",
  "outbox_failed_count": 0,
  "stuck_billing_runs_count": 0
}
```
- **Alert Conditions:**
  - `status: "unhealthy"` (HTTP 503): Database down. Critical alert to on-call engineer.
  - `status: "degraded"` (HTTP 200): Redis down, >10 failed outbox emails, or failed billing run.
  - `stuck_billing_runs_count > 0`: Trigger investigation in Control Tower exception queue.

---

## 8. Role Matrix & Access Boundaries

| Role | Catalog & Plans | Quotes & Subscriptions | Invoices & Payments | Control Tower | Staff Management |
|---|---|---|---|---|---|
| **Admin** | Full CRUD | Full CRUD | Full CRUD + Reversals | Full Commit & Retry | Full CRUD |
| **Staff** | Read Only | Issue Quote, Confirm, Activate | Record Payment, Send | Preview & Retry | Denied |
| **Customer** | Denied | View Own Subscriptions | View Own Invoices & Pay | Denied | Denied |


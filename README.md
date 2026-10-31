# Brightloop — Subscription Management System

[![CI Quality Gates](https://github.com/SamSunny4/Odoo/actions/workflows/ci.yml/badge.svg)](https://github.com/SamSunny4/Odoo/actions/workflows/ci.yml)
[![FastAPI](https://img.shields.io/badge/API-FastAPI%200.115-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/Frontend-React%2019%20%2B%20TypeScript-61DAFB.svg?logo=react)](https://react.dev)
[![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL%2018-336791.svg?logo=postgresql)](https://www.postgresql.org)

Brightloop Software's unified platform for managing subscription plans, quotation lifecycles, automated recurring billing, collections, and financial reporting. Designed to replace spreadsheet tracking with an auditable, idempotent, and role-controlled billing operating system.

---

## 1. Standout Feature: Billing Control Tower

Before recurring runs generate real invoices, Brightloop operations teams open the **Billing Control Tower**:
- **Pre-Flight Run Audit**: Previews line-level calculations, expected discounts, and taxes for every due subscription.
- **Anomaly Detection**: Automatically flags expired plans, exhausted discount limits, missing customer tax details, or prior-invoice price variances.
- **Transactional Idempotency**: Guarantees that repeating or retrying a run will never double-bill a customer or skip a billing cycle.

---

## 2. Default Seeded Credentials

When running `python -m app.seed`, the following accounts are provisioned:

| Role | Email | Password | Scope & Permissions |
|---|---|---|---|
| **Admin** | `admin@brightloop.local` | `Admin@12345!` | Full control: user management, catalog, cost prices, tax/discount rules, billing run commit, full revenue reports. |
| **Staff** | `staff@brightloop.local` | `Staff@12345!` | Operational workflow: quotes, subscriptions, invoices, payments, Control Tower preview. (Cost prices & discounts hidden). |
| **Customer** | `customer@acme.com` | `Customer@12345!` | Isolated Customer Portal: views own subscriptions, invoices, and company profile for **Acme Corporation**. |

---

## 3. Quickstart & Local Setup

### Prerequisites
- **Python 3.12+** (Tested on Python 3.13)
- **Node.js 20+** (Tested on Node 22)
- **PostgreSQL 18** (Native service running locally or via Docker Compose)

---

### Option A: Local Development (Native)

#### 1. Configure Environment
```bash
cp .env.example .env
```
Ensure your local PostgreSQL 18 service is running and credentials match in `.env`.

#### 2. Backend Setup
```bash
cd backend
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations & seed baseline records
python -m app.seed

# Start FastAPI server
uvicorn app.main:app --reload --port 8000
```
API Documentation will be live at: [http://localhost:8000/docs](http://localhost:8000/docs)  
Health Check: [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health)

#### 3. Frontend Setup
In a new terminal:
```bash
cd frontend
npm install
npm run dev
```
Open your browser at: [http://localhost:5173](http://localhost:5173)

---

### Option B: Multi-Container Setup (Docker Compose)

If Docker Desktop is installed:
```bash
docker compose up -d --build
```
- Frontend: [http://localhost:5173](http://localhost:5173)
- Backend API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- Mailpit Web UI (Email test inbox): [http://localhost:8025](http://localhost:8025)

---

## 4. Architectural Documents

- **Domain Model & ER Specifications**: [docs/architecture.md](file:///e:/Odoo/docs/architecture.md)
- **Phase 0 Architecture Plan**: [phase_0_plan.md](file:///C:/Users/samsu/.gemini/antigravity/brain/7496c2b0-3276-4862-8850-55f4b8fd0380/phase_0_plan.md)
- **Contribution & Git Guidelines**: [CONTRIBUTING.md](file:///e:/Odoo/CONTRIBUTING.md)

---

## 5. Verification & Testing

```bash
# Run backend test suite
cd backend
pytest -v

# Run frontend typecheck and production bundle build
cd frontend
npm run build
```


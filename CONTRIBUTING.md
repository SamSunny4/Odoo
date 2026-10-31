# Contributing to Brightloop Subscription Management System

Thank you for contributing to the Brightloop Subscription OS. To ensure architectural integrity, financial accuracy, and smooth collaboration across contributors, all development follows these guidelines established in **Phase 0**.

---

## 1. Git Workflow & Branching Strategy

- **Protected Main Branch**: Direct commits to `main` are strictly forbidden. All production-ready code merges into `main` solely via reviewed Pull Requests (PRs).
- **Short-Lived Feature Branches**:
  - `feat/<feature-name>` for new capabilities (e.g. `feat/phase-1-auth`, `feat/billing-control-tower`).
  - `fix/<issue-name>` for bug fixes and patches.
  - `docs/<topic>` for documentation and runbook updates.
- **Pull Request Checklist**:
  - [ ] Contributor has run backend test suite (`pytest`) and frontend build (`npm run build`).
  - [ ] Any schema modifications include corresponding Alembic migrations in `backend/alembic/versions/`.
  - [ ] RBAC permissions verified (Admin vs Staff vs Customer).
  - [ ] Monetary arithmetic uses `Decimal` and standard rounding.
  - [ ] No secrets or personal `.env` files are committed.

---

## 2. Coding & Architecture Invariants

1. **Authority on Truth**: The backend API and PostgreSQL database are the single authoritative source of truth for calculations, eligibility, and state transitions. Never trust client-supplied status or role values.
2. **Money & Math**: Always use `Decimal` with `ROUND_HALF_UP` to two decimal places. Binary floating-point (`float`) is strictly prohibited in financial logic.
3. **Auditability**:
   - Never overwrite or delete issued financial documents (`invoices`, `payments`).
   - Use `payment_reversals` and invoice cancellation reasons.
4. **Idempotent Billing**:
   - Recurring runs must enforce `unique(subscription_id, billing_period)`.
   - Never allow double billing or silent skips.

---

## 3. Local Development Commands

### Backend
```bash
cd backend
python -m venv .venv
# On Windows: .venv\Scripts\activate | On macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Seed initial admin and catalog data
python -m app.seed

# Start development API server
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Verification
```bash
# Backend tests
pytest backend/tests/

# Frontend typecheck & bundle build
cd frontend && npm run build
```


# SentinelIQ

> **Real-Time Authentication Anomaly Detection for Nobel — Global Financial Intelligence Platform**

[![Status](https://img.shields.io/badge/status-in%20development-orange)](https://github.com/Rojin-Dhami/SentinelIQ)
[![Version](https://img.shields.io/badge/version-0.1--alpha-blue)](https://github.com/Rojin-Dhami/SentinelIQ)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136.1-009688)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## What is SentinelIQ?

SentinelIQ is an active-development, real-time authentication security layer built for **Nobel**, a globally-oriented digital financial services platform. It detects and blocks malicious login attempts — credential stuffing, brute-force attacks, bot-driven logins, and impossible-travel fraud — **before a session is ever established**.

The system runs four independent signal analyzers in parallel on every login attempt and aggregates them into a weighted risk score, optionally blended with an ML model output. High-risk logins are blocked or routed to MFA. Every attempt is fully audit-logged with raw signals for compliance and investigation.

---

## The Problem We Solve

Digital financial platforms face a relentless stream of automated attacks at the authentication layer. Traditional defenses (rate limiting, CAPTCHA) are increasingly bypassed by sophisticated bots. SentinelIQ brings together:

- **Velocity analysis** — sliding-window rate limiting per user and per IP
- **Geo-IP / Impossible Travel** — Haversine-distance detection of physically impossible logins
- **Device Fingerprinting** — headless browser / bot detection and device trust registry
- **Behavioral Biometrics** — keystroke dynamics, mouse linearity, and form-interaction signals
- **ML Anomaly Detection** *(in development)* — Isolation Forest trained on the RBA dataset for complex pattern detection invisible to rule-based systems

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Login Request                       │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────▼───────────────┐
         │       FastAPI Backend          │
         │   /auth/login · /auth/register │
         └───────────────┬───────────────┘
                         │
    ┌────────────────────▼────────────────────┐
    │          Detection Engine               │
    │  (runs all 4 modules in parallel)       │
    │                                         │
    │  ┌──────────┐  ┌──────────┐             │
    │  │ Velocity │  │  Geo-IP  │             │
    │  │ (Redis)  │  │ ip-api   │             │
    │  └────┬─────┘  └────┬─────┘             │
    │       │             │                   │
    │  ┌────▼─────┐  ┌────▼─────┐             │
    │  │  Device  │  │Behavioral│             │
    │  │Fingerprint│ │Biometrics│             │
    │  └────┬─────┘  └────┬─────┘             │
    │       └──────┬───────┘                  │
    │         ┌────▼─────┐                    │
    │         │Aggregator│ ◄── ML Score       │
    │         └────┬─────┘                    │
    └──────────────┼──────────────────────────┘
                   │
       ┌───────────▼───────────┐
       │     Login Outcome     │
       │  success / blocked /  │
       │  mfa_required / fail  │
       └───────────────────────┘
```

**Three-tier system:**

| Tier | Language | Role |
|------|----------|------|
| `backend/` | Python 53.8% | FastAPI REST API, detection engine, DB models, auth services |
| `frontend/` | TypeScript 24.4% / CSS 15.7% | Login UI, device fingerprinting client, behavioral signal collection |
| `ml_core/` | Python (Jupyter) | Isolation Forest model, RBA dataset baseline, SHAP explainability |

---

## Detection Signals & Weights

| Signal | Weight | Method |
|--------|--------|--------|
| Velocity Check | 0.40 | Redis sorted-set sliding window (per-user + per-IP) |
| Geo / Impossible Travel | 0.35 | Haversine distance + speed check via ip-api.com |
| Device Fingerprinting | 0.15 | Device trust registry + headless/bot scoring |
| Behavioral Biometrics | 0.10 | Keystroke dynamics, mouse linearity, form-fill timing |

```
final_risk = (rule_based_risk × RULE_BASE_WEIGHT) + (ml_risk × ML_WEIGHT)
```

Risk score gates login outcomes: `success` → `mfa_required` → `blocked_risk` → `failed_credentials`. Every attempt is logged to `login_events` with the full raw signals JSONB payload for auditing.

---

## Tech Stack

### Backend
- **FastAPI** 0.136.1 + **Uvicorn** 0.47.0 (async ASGI)
- **PostgreSQL** via SQLAlchemy 2.0 (ORM, async sessions) + Alembic migrations
- **Redis** 7.4.0 — velocity tracking (sorted sets) + geo-location cache
- **JWT** (HS256) via python-jose + **Argon2** password hashing via passlib
- **Brevo** (Sendinblue) — transactional email for MFA codes and security alerts
- **ip-api.com** — free geo-IP resolution (lat/lon, city, country, ASN)

### ML Core
- **Isolation Forest** (scikit-learn) — unsupervised anomaly detection
- **SHAP** — TreeExplainer for per-prediction feature attribution
- **RBA Dataset** — baseline training corpus (Doowon Kim et al., "You Are Who You Appear to Be")
- Pandas, NumPy, Matplotlib, Seaborn, Jupyter

### Frontend
- TypeScript + CSS (Vite + React SPA)
- Collects: hardware fingerprint, canvas hash, WebGL renderer, keystroke dynamics, mouse events, webRTC local IP, and 20+ behavioral signals per login attempt

---

## Repository Structure

```
SentinelIQ/
├── backend/
│   ├── main.py                    # FastAPI app factory, middleware, lifespan
│   ├── requirements.txt           # Pinned dependency lockfile
│   └── app/
│       ├── api/
│       │   └── auth.py            # POST /auth/login, POST /auth/register
│       ├── core/
│       │   ├── config.py          # Pydantic-Settings — all env vars
│       │   ├── security.py        # JWT + Argon2 password hashing
│       │   └── logging.py         # Logging setup
│       ├── db/
│       │   ├── models.py          # SQLAlchemy ORM: User, UserDevice, UserBehaviorProfile, LoginEvent
│       │   └── session.py         # Engine and SessionLocal factory
│       ├── detection/
│       │   ├── velocity.py        # Redis sliding-window velocity checks
│       │   ├── geo.py             # Haversine impossible-travel detection
│       │   ├── device.py          # Device trust + headless/bot scoring
│       │   ├── behavioral.py      # Keystroke/mouse bot behavior scoring
│       │   └── aggregate.py       # Weighted risk aggregation + ML blend
│       ├── schemas/
│       │   ├── auth.py            # LoginRequest, DeviceSpec, BehavioralSignals
│       │   └── dto.py             # VelocityResult, GeoLocation, EmailSchema
│       ├── services/
│       │   ├── auth.py            # auth_flow(), register_flow() business logic
│       │   └── email.py           # send_email() via Brevo API
│       └── deps.py                # FastAPI dependencies: get_db, get_redis, is_authenticated
│
├── frontend/                      # TypeScript + CSS (Vite/React SPA — in progress)
│   └── ...
│
└── ml_core/
    ├── requirements.txt           # scikit-learn, shap, pandas, numpy, jupyter
    └── notebooks/                 # EDA, feature engineering, training (planned)
```

---

## Database Schema

| Table | Key Fields |
|-------|-----------|
| `users` | UUID, email, hashed_password, role, failed_login_count, locked_until |
| `user_devices` | device_fingerprint (128-char), first_seen_at, last_seen_at, total_logins |
| `user_behavior_profiles` | avg_dwell_time_ms, avg_flight_time_ms, keystroke_variance, typical_hour_histogram (JSONB) |
| `login_events` | ip_address (INET), device_fingerprint, risk_score (Float), outcome (Enum), raw_signals (JSONB) |

---

## Configuration

All parameters are tunable via environment variables (`.env` / Pydantic-Settings):

| Variable | Default | Description |
|----------|---------|-------------|
| `VELOCITY_WINDOW_SECONDS` | `60` | Sliding window length for velocity checks |
| `USER_MAX_ATTEMPTS` | `5` | Max attempts per user before high risk score |
| `IP_MAX_ATTEMPTS` | `20` | Max attempts per IP before high risk score |
| `VELOCITY_WEIGHT` | `0.40` | Velocity signal weight in aggregate score |
| `GEO_MAX_SPEED_KMH` | `900` | Max plausible travel speed (km/h) |
| `GEO_WEIGHT` | `0.35` | Geo signal weight in aggregate score |
| `DEVICE_WEIGHT` | `0.15` | Device fingerprint signal weight |
| `BEHAVIORAL_WEIGHT` | `0.10` | Behavioral biometrics signal weight |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | JWT access token TTL |
| `REFRESH_TOKEN_EXPIRE_MINUTES` | `1440` | JWT refresh token TTL (24 hours) |
| `BREVO_API_KEY` | — | Brevo transactional email API key |
| `SECRET_KEY` | — | Session signing key |

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Node.js 20+ (frontend)

### Backend Setup

```bash
# Clone the repo
git clone https://github.com/Rojin-Dhami/SentinelIQ.git
cd SentinelIQ

# Install backend dependencies (uv recommended)
cd backend
pip install uv
uv pip install -r requirements.txt

# Copy and configure environment
cp .env.example .env
# Edit .env with your DB, Redis, and Brevo credentials

# Run database migrations
alembic upgrade head

# Start the development server
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`.

### ML Core Setup

```bash
cd ml_core
pip install -r requirements.txt
jupyter notebook
```

> **Note:** The ML training pipeline is currently scaffolded. Training notebooks and RBA dataset integration are in progress.

### Frontend Setup

> **Note:** `frontend/package.json` and Vite configuration are pending. Setup instructions will be added when the frontend build configuration is complete.

---
## Known Issues & Next Steps

- **ML Core activation** — Training pipeline on the RBA dataset must be built before the `RULE_BASE_WEIGHT / ML_WEIGHT` blend in `aggregate.py` is functional
- **Device check async fix** — `check_device()` uses `db.execute()` without `await`; needs correction for `AsyncSession` compatibility
- **Alembic migrations** — Migration scripts not yet generated from model definitions
- **Frontend build config** — `vite.config.ts`, `tsconfig.json`, and `frontend/package.json` are missing
- **MFA implementation** — `LoginOutcome.mfa_required` is defined but no TOTP/OTP service exists
- **Geo TTL strategy** — Redis TTL for cached geo-locations needs explicit definition to prevent stale impossible-travel calculations
- **Admin endpoints** — Monitoring, dashboard, and admin APIs not yet built

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/register` | Register a new user |
| `POST` | `/auth/login` | Authenticate + run full detection pipeline |

Interactive API documentation available at `/docs` (Swagger UI) and `/redoc` when the server is running.

---

## ML Approach

SentinelIQ uses an **Isolation Forest** for unsupervised anomaly detection — well-suited to sparse, imbalanced security event data. The model is trained on the **Synthetic(based on real logs) datasets** by Doowon Kim et al. as a cold-start baseline, covering real-world labeled authentication events with IP, device, and temporal features.

**Feature vector domains:**
- Velocity features: `user_count`, `ip_count`
- Geo features: `distance_km`, `speed_kmh`, `is_impossible_travel`
- Device features: `hardware_concurrency`, `device_memory`, `device_tier`, `headless_score`, `is_known_device`
- Behavioral features: `form_time_ms`, `keystroke_variance`, `bot_behavior_score`, `mouse_linearity`

**SHAP TreeExplainer** provides per-prediction feature attribution for compliance and audit explainability.

Once Nobel production telemetry accumulates, the model will be fine-tuned or replaced with region-specific behavioral baselines.

---

## Contributing

This project is currently in active early-stage development as part of the eSewa Hackathon (The Innovators team). Contribution guidelines will be published once the core architecture stabilizes.

---

## Team

**The Innovators** — Built for the eSewa Hackathon, May 2026.

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

*SentinelIQ — Protecting authentication before the session begins.*

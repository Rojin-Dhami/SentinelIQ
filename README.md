# SentinelIQ

> **Adaptive Authentication Anomaly Detection for Nobel(mainly Nepal centric) Financial Intelligence Platform**

[![Status](https://img.shields.io/badge/status-in%20development-orange)](https://github.com/Rojin-Dhami/SentinelIQ)
[![Version](https://img.shields.io/badge/version-0.1--alpha-blue)](https://github.com/Rojin-Dhami/SentinelIQ)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.136.1-009688)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## What is SentinelIQ?

SentinelIQ is an active-development, real-time authentication security layer built for **Nobel**, a globally-oriented digital financial services platform. It detects and blocks malicious login attempts - credential stuffing, brute-force attacks, bot-driven logins, and impossible-travel fraud — **before a session is ever established**.

The system runs four independent signal analyzers in parallel on every login attempt and aggregates them into a weighted risk score, optionally blended with an ML model output. High-risk logins are blocked or routed to MFA. Every attempt is fully audit-logged with raw signals for compliance and investigation.

---

## The Problem We Solve

Digital financial platforms face a relentless stream of automated attacks at the authentication layer. Traditional defenses (rate limiting, CAPTCHA) are increasingly bypassed by sophisticated bots. SentinelIQ brings together:

- **Velocity analysis** — sliding-window rate limiting per user and per IP
- **Geo-IP / Impossible Travel** — Haversine-distance detection of physically impossible logins
- **Device Fingerprinting** — headless browser / bot detection and device trust registry
- **Behavioral Biometrics** — keystroke dynamics, mouse linearity, and form-interaction signals
- **ML Anomaly Detection** — Isolation Forest trained on the RBA dataset for complex pattern detection invisible to rule-based systems

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                     Login Request                       │
└────────────────────────┬────────────────────────────────┘
                         │
         ┌───────────────▼───────────────┐
         │       FastAPI Backend         │
         │   /auth/login · /auth/register│
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
| Velocity Check | 0.30 | Redis sorted-set sliding window (per-user + per-IP) |
| Geo / Impossible Travel | 0.35 | Haversine distance + speed check via ip-api.com |
| Device Fingerprinting | 0.20 | Device trust registry + headless/bot scoring |
| Behavioral Biometrics | 0.15 | Keystroke dynamics, mouse linearity, form-fill timing |

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
- **Synthetic Dataset** — Dataset in which model is trained 
- Pandas, NumPy, Matplotlib, Seaborn, Jupyter

### Frontend
- TypeScript + CSS (Vite + Next.js SPA)
- Collects: hardware fingerprint, canvas hash, WebGL renderer, keystroke dynamics, mouse events, webRTC local IP, and 20+ behavioral signals per login attempt

---

## Repository Structure

```text
.
├── backend/
│   ├── alembic/                      # Database migration management
│   │   ├── versions/
│   │   ├── README
│   │   ├── env.py
│   │   └── script.py.mako
│   ├── app/                          # Core FastAPI Application
│   │   ├── actions/                  # State execution logic
│   │   ├── api/                      # Routing and endpoint controllers
│   │   ├── core/                     # App configuration & security settings
│   │   ├── db/                       # Session management and database engines
│   │   ├── detection/                # Core logic for impossible-velocity filters
│   │   ├── ml/                       # Isolation Forest pipeline scripts
│   │   ├── schemas/                  # Pydantic data validation constraints
│   │   ├── services/                 # Independent utility micro-logic
│   │   ├── templates/email/          # Notification asset structures
│   │   └── deps.py                   # Global routing dependencies
│   ├── scripts/                      # Utility and verification toolkits
│   │   ├── attack_simulator.py       # Simulates adversarial toolkit spikes
│   │   ├── clear_cache.py            # Purges running Redis velocity states
│   │   └── make_admin.py             # Configures SecOps administrative balances
│   ├── .env.example                  # Environment configuration layout
│   ├── .gitignore
│   ├── .python-version
│   ├── README.md
│   ├── alembic.ini
│   ├── main.py                       # Application execution entrypoint
│   ├── pyproject.toml
│   ├── requirements.txt              # Standard package manager dependencies
│   └── uv.lock                       # Fast package dependency lockfile
├── frontend/
│   ├── admin-dashboard/              # Explanatory diagnostics interface for SecOps
│   └── client/                       # Minimal client application simulation
├── ml_core/notebook/                 # Training sandbox models
│   ├── .ipynb_checkpoints/
│   ├── artifacts/                    # Saved pipeline binaries (.pkl)
│   ├── data/                         # Sample historical velocity datasets
│   ├── fixdataset.ipynb              # Dataset formatting and preparation adjustments
│   └── model.ipynb                   # Isolation Forest prototyping workspace
└── README.md                         # Project documentation root
```
---

## 🗄️ Database Schema Architecture

The relational database layer stores configuration metadata, active user sessions, baseline behavioral profiles, and comprehensive audit logs. The tables are optimized using structured indexes on foreign keys, lookups, and unique strings.

### 1. `users` Table
Stores primary user identity, cryptographic passwords, role configurations, and adaptive account lockout metrics.

| Column Name | Data Type | Constraints / Defaults | Description |
| :--- | :--- | :--- | :--- |
| `id` | `Integer` | Primary Key, Auto-Increment | Internal sequential unique identifier. |
| `uuid` | `UUID` | Unique, Not Null, Indexed | Public-facing unique identifier generated via `uuid4`. |
| `email` | `String(255)` | Unique, Not Null, Indexed | User login email identity string. |
| `hashed_password` | `String(255)` | Not Null | Scrypt/Bcrypt hashed credential string. |
| `full_name` | `String(255)` | Nullable | Optional consumer full name. |
| `is_active` | `Boolean` | Default: `false` | Status flag for general account access. |
| `is_verified` | `Boolean` | Default: `false` | Account identity verification state. |
| `role` | `Enum(UserRole)` | Default: `user` | ACL enforcement level (`user`, `admin`, etc.). |
| `last_login_at` | `DateTime(TZ)`| Nullable | Temporal log of the last successful access point. |
| `failed_login_count`| `Integer` | Default: `0` | Running sequential count of credential mismatches. |
| `locked_until` | `DateTime(TZ)`| Nullable | Timestamp flag for escalating account lock timeouts. |
| `lock_level` | `Integer` | Default: `0` | Escalation state tracking tier (15m → 1h → 6h → hard block). |

---

### 2. `user_devices` Table
Maintains hardware fingerprints and browser property configurations to evaluate client similarity variations.

| Column Name | Data Type | Constraints / Defaults | Description |
| :--- | :--- | :--- | :--- |
| `id` | `Integer` | Primary Key, Auto-Increment | Sequential internal identifier. |
| `user_id` | `Integer` | ForeignKey(`users.id`), Indexed| Relational owner mapping back to primary account. |
| `device_fingerprint`| `String(128)` | Not Null | Combined SHA-256 structural hardware string. |
| `user_agent` | `String(512)` | Nullable | Complete raw browser/app agent identity string. |
| `platform` | `String(64)` | Nullable | Operational platform (e.g., `Win32`, `iOS`, `Android`). |
| `screen` | `String(32)` | Nullable | Display viewport configuration grid bounds (e.g., `1920x1080`). |
| `canvas_hash` | `String(128)` | Nullable | Graphical Canvas rendering signature artifact. |
| `webgl_renderer` | `String(256)` | Nullable | Underlying GPU/hardware graphic driver metadata string. |
| `hardware_concurrency`| `Integer`| Nullable | Available CPU core processing thread execution scales. |
| `first_seen_at` | `DateTime(TZ)`| Default: `now()` | Registration timestamp trace for this specific terminal. |
| `last_seen_at` | `DateTime(TZ)`| Nullable | Last observed request timestamp vector. |
| `trusted_until` | `DateTime(TZ)`| Nullable | Time bounds to bypass multi-tiered authentication hurdles. |

* **Constraints:** `UniqueConstraint("user_id", "device_fingerprint", name="uq_user_device")`

---

### 3. `user_behavior_profiles` Table
Stores sliding context parameters calculated using Exponentially Weighted Moving Averages (EWMA) to gauge biometric typing variance.

| Column Name | Data Type | Constraints / Defaults | Description |
| :--- | :--- | :--- | :--- |
| `id` | `Integer` | Primary Key, Auto-Increment | Sequential profile key identifier. |
| `user_id` | `Integer` | ForeignKey(`users.id`), Unique, Indexed | One-to-one strict linkage back to primary user row. |
| `avg_dwell_time_ms` | `Float` | Nullable | Running EWMA average of individual key hold durations. |
| `avg_flight_time_ms`| `Float` | Nullable | Running EWMA average of key transition frequencies. |
| `std_dwell_time_ms` | `Float` | Nullable | Running calculated standard deviation for hold durations. |
| `std_flight_time_ms`| `Float` | Nullable | Running calculated standard deviation for key transitions. |
| `total_logins` | `Integer` | Default: `0` | Absolute count of baseline observation logs compiled. |

---

### 4. `login_events` Table
An append-only telemetry timeline log tracking raw vectors, location mappings, and risk metrics for audit inspection.

| Column Name | Data Type | Constraints / Defaults | Description |
| :--- | :--- | :--- | :--- |
| `id` | `Integer` | Primary Key, Auto-Increment | Audit ledger event sequence number. |
| `user_id` | `Integer` | ForeignKey(`users.id`), Nullable | Targeted account context (null for non-existent users). |
| `created_at` | `DateTime(TZ)`| Default: `now()` | Precise intercept transaction time marker. |
| `ip_address` | `String(45)` | Not Null | Request incoming IP source (handles IPv4 and IPv6 layouts). |
| `city` | `String(128)` | Nullable | Geo-IP resolution context map for regional evaluation. |
| `country` | `String(128)` | Nullable | Country designation resolved via regional edge networks. |
| `device_fingerprint`| `String(128)` | Nullable | Captured terminal fingerprint during intercept window. |
| `risk_score` | `Float` | Nullable | Aggregated rule and Isolation Forest risk index evaluation. |
| `outcome` | `Enum(LoginOutcome)`| Default: `failed_credentials` | Operational status (`success`, `failed_mfa`, etc.). |
| `decision` | `String(32)` | Nullable, Indexed | Enforced routing path directive (`allow`, `verify`, `block`). |
| `breakdown` | `JSONB` | Nullable | Deep multi-signal variance telemetry for SecOps logs. |

---

### 5. `sessions` Table
Maintains structural token reference hashes to track persistent cryptographically signed user authentications.

| Column Name | Data Type | Constraints / Defaults | Description |
| :--- | :--- | :--- | :--- |
| `id` | `Integer` | Primary Key, Auto-Increment | Session entry unique tracking row key. |
| `user_id` | `Integer` | ForeignKey(`users.id`), Indexed| Associated target user account structure. |
| `device_id` | `Integer` | ForeignKey(`user_devices.id`), Nullable | Verified terminal origin mapping framework. |
| `refresh_token_hash`| `String(128)` | Not Null, Indexed | Hashed version of the refresh token. |
| `ip_address` | `String(45)` | Nullable | Active transaction network connection pointer. |
| `created_at` | `DateTime(TZ)`| Default: `now()` | Structural generation timestamp. |
| `expires_at` | `DateTime(TZ)`| Not Null | Strict expiration cutoff threshold boundary. |
| `revoked_at` | `DateTime(TZ)`| Nullable | Express revocation marker triggered by logout or compromise. |

---

## Configuration

All parameters are tunable via environment variables (`.env` / Pydantic-Settings):

| Variable | Default | Description |
|----------|---------|-------------|
| `VELOCITY_WINDOW_SECONDS` | `60` | Sliding window length for velocity checks |
| `USER_MAX_ATTEMPTS` | `5` | Max attempts per user before high risk score |
| `IP_MAX_ATTEMPTS` | `20` | Max attempts per IP before high risk score |
| `VELOCITY_WEIGHT` | `0.30` | Velocity signal weight in aggregate score |
| `GEO_MAX_SPEED_KMH` | `900` | Max plausible travel speed (km/h) |
| `GEO_WEIGHT` | `0.35` | Geo signal weight in aggregate score |
| `DEVICE_WEIGHT` | `0.20` | Device fingerprint signal weight |
| `BEHAVIORAL_WEIGHT` | `0.15` | Behavioral biometrics signal weight |
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

## 🧠 ML Approach & Algorithmic Architecture

SentinelIQ deploys an advanced machine learning engine running an optimized **Isolation Forest** topology. Unlike traditional classification frameworks that require extensive, highly balanced fraud sets, an Isolation Forest separates anomalies natively by randomly partitioning multivariate feature splits. This makes the pipeline exceptionally well-suited to sparse, highly imbalanced security telemetry.

To prevent high false-positive spikes during heavy traffic anomalies (such as local holiday transactions like Dashain and Tihar), the architecture integrates **Nadaraya–Watson Kernel Regression** to scale tree isolation outputs dynamically without relying on heavy, time-consuming gradient optimization loops.

### 1. Mathematical Formulation

The anomaly scoring pipeline weights individual decision trees contextually based on running baseline density shifts:

$$Score(x) = \sum_{i=1}^{n} w_i(x) \cdot \frac{h_i(x)}{E(h)}$$

Where:
* **$h_i(x)$**: Explores the absolute path length (number of edges crossed from root to terminating leaf) for a given request vector $x$ within isolation tree $i$.
* **$E(h)$**: Represents the average path length of an unsuccessful search in a standard Binary Search Tree (BST), serving as the normalization constant.
* **$w_i(x)$**: Denotes context-dependent attention weights computed dynamically via kernel regression to adjust anomaly thresholds during high-throughput baseline traffic shifts.

---

### 2. Feature Vector Space Breakdown

On every authentication request intercept, raw metrics are extracted into a continuous multi-signal feature vector mapped across four primary functional domains:

| Domain | Feature Flag | Data Type / Unit | Description |
| :--- | :--- | :--- | :--- |
| **Velocity** | `user_count` | `Integer` | Request frequency from the specific user ID inside the sliding Redis window. |
| | `ip_count` | `Integer` | Request frequency originating from the source IP address string. |
| **Geo-Spatial** | `distance_km` | `Float` (km) | Spatial delta calculated via Haversine equations from the last active location. |
| | `speed_kmh` | `Float` (km/h) | Implied velocity over the temporal delta since the prior session state. |
| | `is_impossible_travel`| `Boolean` | Binary flag triggered if calculated travel speed exceeds **900 km/h**. |
| **Device Core** | `hardware_concurrency`| `Integer` | Reported CPU core count collected from client thread layers. |
| | `device_memory` | `Integer` (GB) | Approximate RAM capacity reported via device properties. |
| | `headless_score` | `Float` (0.0 - 1.0)| Computed automation likelihood index (evaluating canvas and webgl artifacts). |
| | `is_known_device` | `Boolean` | Structural lookup checking if device signature exists in the trust registry. |
| **Behavioral** | `form_time_ms` | `Float` (ms) | Duration between form interaction init and submittal actions. |
| | `keystroke_variance` | `Float` | Statistical variance of key dwell and flight times against the running profile. |
| | `mouse_linearity` | `Float` | Linearity index of pointing device coordinates during authentication. |

---

### 3. Compliance Audit & SHAP Explainability Telemetry

To overcome the "black box" opacity typical of traditional tree-based models, SentinelIQ embeds a native **SHAP (SHapley Additive exPlanations) TreeExplainer** sub-module.

```text
[High Anomaly Risk Score] 
         │
         ▼ (SHAP TreeExplainer Transformation Layer)
┌────────────────────────────────────────────────────────┐
│ Administrative Diagnostic Dashboard (Audit-Ready Logs) │
│ ────────────────────────────────────────────────────── │
│ 🟩 +32% Device Mismatch (Hardware Profile Delta)       |   
│ 🟨 +18% Unusual Transaction Window                     │
│ 🟦 +10% Biometric Typing Acceleration Variance         |
└────────────────────────────────────────────────────────┘

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

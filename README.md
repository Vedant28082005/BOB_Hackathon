# TrustLayer — Identity Trust Framework v2.0

Production-grade, privacy-first KYC risk-decisioning system. AI-powered real-time document forensics, biometric verification, and graph-based fraud-ring detection.

---

## Architecture

```
Channels (Mobile / Branch / NetBanking / VideoKYC)
           │  HTTPS + API-Key + HMAC
    ┌──────▼──────────────────────────────┐
    │  FastAPI Backend  (8000)            │
    │  Auth · RBAC · Rate-limit · CORS    │
    └──────┬─────────────┬───────────────┘
           │             │ Celery tasks
    ┌──────▼──────┐ ┌────▼──────────────┐  ┌──────────────────┐
    │ PostgreSQL  │ │  Redis (broker +  │  │ ML Service (8001)│
    │ (SQLModel + │ │  cache + progress)│  │ PaddleOCR        │
    │  Alembic)   │ └────────────────── ┘  │ InsightFace ArcF │
    └─────────────┘                        │ MiniFASNet Live  │
    ┌─────────────┐                        │ EfficientNet-B4  │
    │ Neo4j Graph │  ◄──── Celery ────────►│ ELA / EXIF / ORB │
    │ Louvain     │                        └──────────────────┘
    │ Ring detect │
    └─────────────┘
    ┌─────────────┐
    │ MinIO       │  Encrypted media, auto-purge after 24h
    └─────────────┘
```

---

## Quick Start — Local (Docker Compose)

### Prerequisites
- Docker + Docker Compose v2
- NVIDIA GPU optional (models fall back to CPU)
- 16 GB RAM recommended

```bash
# 1. Clone and enter project
git clone <repo> && cd BOB_Hackathon

# 2. Download ML model weights
bash scripts/download_models.sh

# 3. (Optional) Add GeoLite2 DB for real IP geolocation
#    Download from https://dev.maxmind.com/ → place at infra/geoip/GeoLite2-City.mmdb

# 4. Set your Gemini API key (optional; falls back to templated explanations)
echo "GEMINI_API_KEY=your_key_here" > .env

# 5. Start the full stack
docker compose -f infra/docker-compose.yml up --build

# 6. Seed the Neo4j graph with synthetic applicants + fraud rings
docker compose -f infra/docker-compose.yml exec backend python scripts/seed_graph.py

# 7. Run DB migrations
docker compose -f infra/docker-compose.yml exec backend alembic upgrade head
```

**Access points:**
| Service | URL |
|---------|-----|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000/docs |
| Grafana | http://localhost:3001 (admin / trustlayer) |
| Neo4j Browser | http://localhost:7474 |
| MinIO Console | http://localhost:9001 |
| Prometheus | http://localhost:9090 |

**Default console logins:**
| Email | Password | Role |
|-------|----------|------|
| analyst@trustlayer.in | analyst123 | analyst |
| admin@trustlayer.in | admin123 | admin |
| auditor@trustlayer.in | auditor123 | auditor |

---

## Production Deployment — Kubernetes

```bash
# Apply manifests
kubectl apply -f infra/k8s/namespace.yaml
kubectl apply -f infra/k8s/

# Create secrets (example — use Vault or sealed-secrets in production)
kubectl create secret generic trustlayer-secrets \
  --from-literal=DATABASE_URL="postgresql+asyncpg://..." \
  --from-literal=NEO4J_PASSWORD="..." \
  --from-literal=JWT_SECRET_KEY="$(openssl rand -hex 32)" \
  --from-literal=AES_ENCRYPTION_KEY="$(openssl rand -hex 32)" \
  --from-literal=ML_SERVICE_API_KEY="$(openssl rand -hex 16)" \
  -n trustlayer

# GPU node labelling (for ML service pod scheduling)
kubectl label node <gpu-node> accelerator=nvidia-rtx-3060
```

---

## Running Tests

```bash
# Unit tests (no running services needed)
pip install pytest pytest-asyncio
pytest tests/unit/ -v

# Integration tests (requires running stack)
TRUSTLAYER_TEST_URL=http://localhost:8000 pytest tests/integration/ -v -m integration
```

---

## What Is Production-Real vs What Needs Regulated Integration

### ✅ Production-Real (this codebase)

| Component | Technology | Status |
|-----------|-----------|--------|
| OCR — text extraction | PaddleOCR (multilingual: Hindi + English) | Real |
| Tampering — ELA | PIL recompression diff | Real |
| Tampering — EXIF consistency | piexif metadata analysis | Real |
| Tampering — copy-move | OpenCV ORB feature matching | Real |
| Tampering — noise analysis | Laplacian noise residual | Real |
| ID validation — PAN | Regex format check | Real |
| ID validation — Aadhaar | Verhoeff checksum | Real |
| Face match | InsightFace ArcFace / buffalo_l (cosine similarity) | Real |
| Liveness — passive | Silent-Face-Anti-Spoofing / MiniFASNet | Real |
| Liveness — active | MediaPipe landmark EAR blink + head-turn | Real |
| Deepfake detection | EfficientNet-B4 (FaceForensics++ weights) | Real (probabilistic) |
| Device fingerprinting | Client-side Web Crypto SHA-256 | Real |
| Emulator detection | UA + hardware concurrency heuristics | Real |
| GeoIP | MaxMind GeoLite2-City | Real |
| VPN/datacenter detection | GeoIP hosting provider flag | Real |
| Behavioural biometrics | Keystroke timing via `performance.now()` | Real |
| Identity graph | Neo4j + Louvain community detection | Real |
| Duplicate detection | Email / phone hash matching | Real |
| Fraud ring detection | Connected-component + BFS path analysis | Real |
| Fusion engine | Weighted score + hard-fail overrides | Real |
| Audit log | SHA-256 hash-chained tamper-evident log | Real |
| Encryption | AES-256-GCM for PII at rest | Real |
| Auth | OAuth2 + JWT + HMAC API signing | Real |
| RBAC | analyst / admin / auditor roles | Real |
| Async pipeline | Celery + Redis + SSE progress streaming | Real |
| Media storage | MinIO S3-compatible + auto-purge | Real |
| Observability | Prometheus metrics + Grafana dashboard | Real |

### ⚠️ What Needs Regulated / Certified Integration for Bank Production

| Requirement | Current State | What to Add |
|-------------|--------------|-------------|
| **Aadhaar OTP / DigiLocker eKYC** | Not implemented (requires UIDAI API license) | Integrate via UIDAI-authorized KUA / ASA partner |
| **Video KYC (RBI circular)** | Frame-based only | Add SEBI/RBI-compliant VKYC platform (Jocata, IDfy, etc.) |
| **Certified deepfake vendor** | Open-source EfficientNet (probabilistic) | Augment with iProov, Veriff, or Acuant for regulated decisions |
| **PAN/ITR verification** | Format check only | Call Income Tax dept API (Protean eGov) for real verification |
| **CIBIL / credit bureau check** | Not implemented | Integrate via CRIF, Experian, or CIBIL API |
| **DPDP Act consent management** | Basic consent flag | Full consent management platform with audit trail per DPDP 2023 |
| **RBI KYC Master Direction audit** | Partial | Full CKYC Registry integration + quarterly KYC refresh |
| **HSM for key management** | AES key in env var | Replace with AWS KMS / Azure Key Vault / Thales HSM |
| **SOC 2 / ISO 27001** | Not certified | Requires formal audit + controls framework |

---

## Folder Structure

```
BOB_Hackathon/
├── backend/            FastAPI + Celery + auth + engines
│   ├── engines/        fusion, device, behavioural, identity_graph
│   ├── graph/          Neo4j client + Louvain ring detection
│   ├── routers/        assessment, auth, audit, channel, admin
│   ├── security/       auth (JWT+HMAC), RBAC, AES-256 encryption
│   ├── storage/        Redis client, MinIO client
│   ├── tasks/          Celery pipeline task
│   └── alembic/        DB migrations
├── ml-service/         GPU model inference (separate process)
│   └── models/         OCR, face, liveness, deepfake, forensics
├── frontend/           React + Vite + TailwindCSS
│   └── src/
│       ├── api/        client.ts (SSE polling, JWT auth)
│       └── components/ pipeline UI, result view, graph, audit
├── infra/
│   ├── docker-compose.yml   Full local stack
│   ├── k8s/                 Kubernetes manifests
│   ├── prometheus/          Scrape config
│   └── grafana/             Dashboard provisioning
├── tests/
│   ├── unit/           fusion, audit chain, document validators
│   └── integration/    full assessment flow, channel API
├── scripts/
│   ├── download_models.sh   Model weight downloader
│   └── seed_graph.py        Neo4j seed with fraud rings
└── .github/workflows/ci.yml  Lint + test + build CI
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | postgres://... | PostgreSQL async DSN |
| `REDIS_URL` | redis://localhost:6379/0 | Redis connection |
| `NEO4J_URI` | bolt://localhost:7687 | Neo4j bolt URI |
| `NEO4J_PASSWORD` | trustlayer_neo4j | Neo4j password |
| `MINIO_ACCESS_KEY` | trustlayer_minio | MinIO access key |
| `MINIO_SECRET_KEY` | ... | MinIO secret |
| `JWT_SECRET_KEY` | CHANGE_ME | 256-bit JWT signing key |
| `AES_ENCRYPTION_KEY` | 000...0 | 64-char hex (32 bytes) for PII encryption |
| `ML_SERVICE_API_KEY` | change_me | Internal ML service auth |
| `GEMINI_API_KEY` | (empty) | Google Gemini for LLM narration |
| `GEOIP_DB_PATH` | data/GeoLite2-City.mmdb | MaxMind DB path |
| `USE_GPU` | false | Enable CUDA in ML service |
| `ENVIRONMENT` | development | development / production |

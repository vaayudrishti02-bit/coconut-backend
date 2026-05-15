# 🌴 Deekshith - Survey Orchestration System

**Complete integration of Topview + Sideview for coconut tree health surveying**

---

## 📋 Overview

The Deekshith module orchestrates the entire survey workflow:

1. **Survey Creation** - Start a new farmer visit
2. **Topview Upload** - Drone captures tree layout (positions + numbering)
3. **Tree Video Upload** - Individual tree health videos
4. **Dashboard Generation** - Aggregated health statistics
5. **Health Map** - Visual map (green/red) of tree health

---

## 🏗️ Architecture

```
Deekshith/
├── survey/          → Survey CRUD
├── topview_link/    → Connects to /topview/detect
├── sideview_link/   → Connects to /sideview/process_video
├── dashboard/       → Multi-level aggregation
├── map/             → Health visualization
└── storage/         → File-based storage
    └── surveys/
        └── SURVEY_17/
            ├── meta.json
            └── topviews/
                ├── 17a/
                │   ├── image.jpg
                │   ├── topview_detection.json
                │   ├── trees/
                │   │   ├── tree_01/
                │   │   │   ├── tree_01.mp4
                │   │   │   ├── dashboard.json
                │   │   │   └── sideview_full_result.json
                │   │   └── tree_02/
                │   ├── dashboard_17a.json
                │   └── health_map_17a.json
                └── 17b/
```

---

## 🔗 API Endpoints

### 1️⃣ Create Survey

**POST** `/survey/create`

```json
// Request
{
  "farmer_id": "F001",
  "location": {
    "lat": 12.97,
    "lon": 77.59
  }
}

// Response
{
  "survey_id": 17,
  "timestamp": "2026-01-05T10:12:00"
}
```

---

### 2️⃣ Upload Topview Image

**POST** `/survey/{survey_id}/topview`

**Form Data:**

- `topview_order`: "a" (or "b", "c", etc.)
- `image`: file

```json
// Response
{
  "topview_id": "17a",
  "tree_count": 20,
  "detection_path": ".../topview_detection.json"
}
```

**What happens:**

- Calls `/topview/detect` internally
- Stores detection + image
- Creates `tree_01`, `tree_02`, ... subdirectories

---

### 3️⃣ Upload Tree Video

**POST** `/survey/{survey_id}/topview/{topview_order}/tree/{tree_index}/video`

**Example:**

```
POST /survey/17/topview/a/tree/3/video
```

**Form Data:**

- `video`: file

```json
// Response
{
  "tree_id": "17a_tree_03",
  "tree_index": "tree_03",
  "dashboard": {
    "tree_id": "17a_tree_03",
    "tree": {
      "health": "unhealthy",
      "weighted_score": 45.2,
      "primary_disease": "leaf rot"
    },
    "parts": {...},
    "meta": {...}
  }
}
```

**What happens:**

- Calls `/sideview/process_video`
- Stores tree dashboard in `trees/tree_03/dashboard.json`
- Health determined by: `weighted_score >= 70` → healthy

---

### 4️⃣ Generate Topview Dashboard

**POST** `/survey/{survey_id}/topview/{topview_order}/dashboard`

```json
// Response
{
  "topview_id": "17a",
  "total_trees": 20,
  "healthy": 14,
  "unhealthy": 6,
  "health_score": 70.0,
  "dominant_disease": "leaf rot",
  "disease_distribution": {
    "leaf rot": 4,
    "stem bleeding": 2
  }
}
```

**Aggregates:** All tree dashboards in `17a/trees/`

---

### 5️⃣ Generate Health Map

**GET** `/survey/{survey_id}/topview/{topview_order}/health-map`

```json
// Response
{
  "survey_id": 17,
  "topview_id": "17a",
  "total_trees": 20,
  "map": [
    {
      "tree": 1,
      "tree_index": "tree_01",
      "x": 120,
      "y": 98,
      "health": "healthy",
      "color": "green"
    },
    {
      "tree": 3,
      "tree_index": "tree_03",
      "x": 412,
      "y": 265,
      "health": "unhealthy",
      "color": "red"
    }
  ]
}
```

**Color Rules:**

- `healthy` → green
- `unhealthy` → red
- `unknown` (no video uploaded) → grey

---

### 6️⃣ Generate Final Survey Dashboard

**POST** `/survey/{survey_id}/dashboard`

```json
// Response
{
  "survey_id": 17,
  "total_topviews": 2,
  "total_trees": 40,
  "healthy": 28,
  "unhealthy": 12,
  "overall_health_score": 70.0,
  "primary_disease": "leaf rot",
  "disease_distribution": {
    "leaf rot": 8,
    "stem bleeding": 4
  },
  "topview_summaries": [
    {
      "topview_id": "17a",
      "trees": 20,
      "health_score": 70.0
    },
    {
      "topview_id": "17b",
      "trees": 20,
      "health_score": 70.0
    }
  ]
}
```

**Aggregates:** All topview dashboards (weighted by tree count)

---

### 7️⃣ Get Complete Survey Result

**GET** `/survey/{survey_id}/result`

```json
// Response
{
  "survey_id": 17,
  "meta": {
    "survey_id": 17,
    "farmer_id": "F001",
    "location": {"lat": 12.97, "lon": 77.59},
    "timestamp": "2026-01-05T10:12:00",
    "status": "active"
  },
  "topviews": {
    "17a": {
      "detection": {...},
      "dashboard": {...},
      "health_map": {...},
      "trees": {
        "tree_01": {...},
        "tree_02": {...}
      }
    }
  },
  "final_dashboard": {...}
}
```

---

### 8️⃣ List All Surveys

**GET** `/survey/list`

```json
// Response
{
  "surveys": [
    {
      "survey_id": 17,
      "farmer_id": "F001",
      "timestamp": "2026-01-05T10:12:00",
      "status": "active"
    }
  ],
  "total": 1
}
```

---

## 🔄 Complete Workflow Example

### Real-life scenario: Farmer visit with 2 topview images

```bash
# 1. Create survey
curl -X POST http://localhost:800/survey/create \
  -H "Content-Type: application/json" \
  -d '{
    "farmer_id": "F001",
    "location": {"lat": 12.97, "lon": 77.59}
  }'

# Response: {"survey_id": 17, "timestamp": "..."}

# 2. Upload first topview image (20 trees)
curl -X POST http://localhost:800/survey/17/topview \
  -F "topview_order=a" \
  -F "image=@topview_a.jpg"

# Response: {"topview_id": "17a", "tree_count": 20}

# 3. Upload videos for all 20 trees
for i in {1..20}; do
  curl -X POST http://localhost:800/survey/17/topview/a/tree/$i/video \
    -F "video=@tree_$i.mp4"
done

# 4. Generate topview dashboard
curl -X POST http://localhost:800/survey/17/topview/a/dashboard

# 5. Generate health map
curl http://localhost:800/survey/17/topview/a/health-map

# 6. Repeat for second topview (17b)
curl -X POST http://localhost:800/survey/17/topview \
  -F "topview_order=b" \
  -F "image=@topview_b.jpg"

# ... upload tree videos for 17b ...

curl -X POST http://localhost:800/survey/17/topview/b/dashboard
curl http://localhost:800/survey/17/topview/b/health-map

# 7. Generate final survey dashboard
curl -X POST http://localhost:800/survey/17/dashboard

# 8. Get complete result
curl http://localhost:800/survey/17/result
```

---

## 🎨 Health Determination Logic

**Tree health comes from sideview:**

```python
# From tree dashboard (sideview result)
weighted_score = tree_dashboard["tree"]["weighted_score"]

if weighted_score >= 70:
    health = "healthy"  # Green
else:
    health = "unhealthy"  # Red
```

**No ML in orchestration** - only ID wiring + aggregation.

---

## 📊 Dashboard Aggregation Rules

### Topview Dashboard

- Counts healthy/unhealthy trees
- Health score = `(healthy_count / total_trees) * 100`
- Dominant disease = most common disease among unhealthy trees

### Survey Dashboard

- Aggregates all topview dashboards
- Weighted health score = `Σ(topview_score × tree_count) / total_trees`
- Primary disease = most common disease across all topviews

---

## 🗂️ File Storage Structure

```
Deekshith/storage/surveys/
└── SURVEY_17/
    ├── meta.json                      # Survey metadata
    ├── dashboard_17.json              # Final survey dashboard
    └── topviews/
        ├── 17a/
        │   ├── image.jpg              # Original topview image
        │   ├── topview_detection.json # YOLO detection result
        │   ├── dashboard_17a.json     # Topview dashboard
        │   ├── health_map_17a.json    # Health map
        │   └── trees/
        │       ├── tree_01/
        │       │   ├── tree_01.mp4             # Tree video
        │       │   ├── dashboard.json          # Tree health dashboard
        │       │   └── sideview_full_result.json  # Full sideview result
        │       ├── tree_02/
        │       └── ...
        └── 17b/
            └── ...
```

---

## 🔧 Configuration

### Internal API URLs (in service files)

```python
# topview_link/service.py
TOPVIEW_API_URL = "http://localhost:800/topview/detect"

# sideview_link/service.py
SIDEVIEW_API_URL = "http://localhost:800/sideview/process_video"
```

**Change these if your server runs on a different port.**

---

## ⚠️ Error Handling

### Common Errors

1. **Survey not found (404)**
   - Ensure survey was created first

2. **Topview not found (404)**
   - Upload topview image before uploading tree videos

3. **Tree directory not found (404)**
   - Topview detection creates tree directories automatically
   - Tree index must match detected tree number

4. **Topview/Sideview API connection failed (500)**
   - Check if server is running on correct port
   - Verify internal API URLs in service files

---

## 🚀 Production Considerations

### 1. Storage Backend

Current: File-based storage in `Deekshith/storage/`

**For production:**

- Move to object storage (S3, Azure Blob)
- Use database for metadata (PostgreSQL)
- Keep file structure but store paths in DB

### 2. API Configuration

Current: Hardcoded `localhost:800`

**For production:**

- Use environment variables
- Service discovery (Kubernetes)
- Load balancer URLs

### 3. Async Processing

Current: Synchronous video processing

**For production:**

- Use task queue (Celery, RQ)
- Background workers for video processing
- Webhook notifications when complete

### 4. Validation

- Add farmer authentication
- Validate topview_order uniqueness
- Enforce tree_index range from detection

---

## 📦 Dependencies

New dependency added: **httpx** (for internal API calls)

```bash
pip install httpx>=0.24.0
```

Already in `requirements.txt`.

---

## 🧪 Testing

```bash
# Start server
uvicorn main:app --reload --host 0.0.0.0 --port 800

# Run tests (create these)
pytest tests/test_deekshith.py -v
```

---

## 📝 Production Status & Pending Items

### ✅ Core Workflow (Functional)

1. ✅ Survey creation (DB-first with auto ID)
2. ✅ Topview detection link (ML called directly, not via HTTP)
3. ✅ Tree video processing link (ML called directly)
4. ✅ Dashboard aggregation (OOD penalty, formal thresholds)
5. ✅ Health map generation
6. ✅ Transaction support (multi-step operations wrapped)
7. ✅ Idempotency (duplicate upload detection via hash)
8. ✅ StorageService (opaque file paths, never parsed)

### 🔲 Production Hardening (Pending)

1. 🔲 Authentication & authorization (currently no auth middleware)
2. 🔲 Rate limiting
3. 🔲 Input validation (stricter payload checks)
4. 🔲 Async video processing (queue-based)
5. 🔲 Deployment (Docker + K8s)
6. 🔲 CORS hardening (currently `allow_origins=["*"]`)
7. 🔲 Credentials externalization (via env vars)

---

## 🎯 Key Design Decisions

### 1. Database is Source of Truth

```
Database (PostgreSQL)
├── Survey records
├── Topview records
├── Tree records (with tree_uuid for stable identity)
└── ml_raw_output (NOT dashboard_data - clarifies it's raw ML output)

Files (CACHE ONLY)
├── uploads/ → Images, videos
├── dashboard.json → Cached for debug/audit
└── Never parsed for IDs (opaque paths)
```

### 2. ML Modules are INTERNAL ONLY

ML endpoints (`/topview/*`, `/sideview/*`) are **disabled** in main.py.
Services call ML models **directly via import**, not HTTP.

### 3. ID Hierarchy

```
Survey: 17 (auto-generated by PostgreSQL)
Topview: 17a, 17b
Tree: tree_uuid (UUID, stable across re-uploads)
```

### 4. Health Determination

- `weighted_score >= 70` → healthy
- `weighted_score < 30` → critical
- OOD penalty applied when OOD confidence > 0.3

### 5. Transaction Guarantees

Multi-step operations (topview upload, video processing) are wrapped in single transactions.
If any step fails, entire operation rolls back.

### 6. Idempotency

Re-uploading same image/video is safe - hash check detects duplicates.

---

**Status: Core workflow functional. Production hardening pending.**

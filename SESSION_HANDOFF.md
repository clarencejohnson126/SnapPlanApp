# SnapGrid Session Handoff

**Last Updated**: 2026-01-01

## Quick Start for Next Session

```bash
# Start backend
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Start frontend
cd frontend
npm run dev
```

---

## Current Working State

### What's Working
1. **Door Schedule Extraction**: Upload Türliste PDF → get door counts, fire ratings, dimensions
2. **Flooring Extraction**: Extract NRF (floor area) values from annotated CAD PDFs
3. **Drywall Calculation**: Uses room perimeter (U values) × wall height
4. **Web UI**: Upload page → Results page with tabs for doors, flooring, drywall

### API Endpoints (Active)
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/gewerke/doors/from-schedule` | POST | Door schedule → structured list |
| `/api/v1/gewerke/doors/from-plan` | POST | Door detection from floor plan |
| `/api/v1/gewerke/flooring/from-plan` | POST | Extract flooring m² from plan |
| `/api/v1/gewerke/drywall/from-plan` | POST | Calculate drywall m² |

---

## Roboflow Integration: COMPLETED

### What Was Built
1. **Input Router** (`app/services/input_router.py`) - Detects PDF type automatically
2. **Roboflow Service** (`app/services/roboflow_service.py`) - Full Roboflow API integration
3. **CV API Endpoints** (`app/api/cv.py`) - Direct CV detection endpoints
4. **Smart Gewerke Endpoints** - Auto-routing with CV fallback

### New API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/cv/status` | GET | Check CV pipeline status |
| `/api/v1/cv/analyze-input` | POST | Detect input type (CAD/scanned/photo) |
| `/api/v1/cv/detect/rooms` | POST | Roboflow room detection |
| `/api/v1/cv/detect/walls` | POST | Roboflow wall detection |
| `/api/v1/cv/detect/doors` | POST | Roboflow door detection |
| `/api/v1/cv/analyze` | POST | Full floor plan analysis |
| `/api/v1/gewerke/flooring/smart` | POST | Auto-route flooring extraction |
| `/api/v1/gewerke/drywall/smart` | POST | Auto-route drywall calculation |

### Input Type Detection

```python
from app.services.input_router import analyze_input, InputType

analysis = analyze_input("blueprint.pdf")
# analysis.input_type: CAD_WITH_TEXT, CAD_NO_TEXT, SCANNED_PDF, PHOTO
# analysis.recommended_pipeline: TEXT_EXTRACTION, HYBRID, ROBOFLOW_CV
# analysis.detected_annotations: ["NRF", "U", "ROOM_ID", ...]
```

### Roboflow Models Configured

```python
# In config.py
roboflow_floor_plan_model = "floor-plan-segmentation-dtr4r/1"
roboflow_room_segmentation_model = "room-segmentation-model/1"
roboflow_door_detection_model = "detecting-doors-from-floor-plan/2"
roboflow_wall_floor_model = "wall-floor-2zskh/1"
```

---

## Key Files

### Backend
- `backend/app/api/gewerke.py` - Trade module endpoints (doors, flooring, drywall)
- `backend/app/services/gewerke.py` - Trade-specific data models and functions
- `backend/app/services/vector_measurement.py` - Vector line extraction
- `backend/.env` - API keys (Supabase, YOLO, Firecrawl)

### Frontend
- `frontend/app/[locale]/upload/page.tsx` - Upload and configure
- `frontend/app/[locale]/results/[id]/page.tsx` - Results display

### Configuration
```
backend/.env:
- SNAPGRID_SUPABASE_URL
- SNAPGRID_SUPABASE_SERVICE_KEY
- SNAPGRID_YOLO_MODEL_PATH
- FIRECRAWL_API_KEY (new)
```

---

## Recent Bug Fixes

### Drywall/Flooring Showing Same Value (FIXED)
- **Problem**: Both showed 2,268.30 m²
- **Cause**: Vector extraction captured ALL 28,798 line segments (furniture, text, etc.)
- **Fix**: Changed to perimeter × wall height calculation
- **Result**: Flooring = 2,268.31 m², Drywall = 2,914.69 m²

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    SNAPGRID                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │  INPUT ROUTER                                    │    │
│  │  ├── CAD PDF with annotations → Text Extraction │    │
│  │  ├── CAD PDF no annotations → Vector + CV       │    │
│  │  ├── Scanned PDF → CV only (Roboflow)           │    │
│  │  └── Photo → CV only (Roboflow)                 │    │
│  └─────────────────────────────────────────────────┘    │
│                          │                               │
│         ┌────────────────┼────────────────┐             │
│         ▼                ▼                ▼             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │Text/Vector  │  │ Roboflow    │  │ Local YOLO  │     │
│  │Extraction   │  │ API         │  │ (backup)    │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│         │                │                │             │
│         └────────────────┼────────────────┘             │
│                          ▼                               │
│  ┌─────────────────────────────────────────────────┐    │
│  │  MEASUREMENT ENGINE                              │    │
│  │  Scale + Detections → m², quantities            │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

---

## Implementation Phases

| Phase | Focus | Status |
|-------|-------|--------|
| 1. MVP | German CAD PDFs | ✅ Working (text extraction) |
| 2. Photos | On-site photo capture | ✅ Roboflow CV |
| 3. Scans | Scanned blueprints | ✅ Roboflow CV |
| 4. Global | International symbols | ✅ Multi-model support |

### Next Steps
- Fine-tune Roboflow model selection based on accuracy testing
- Add OCR layer for scanned PDFs with text
- Implement user feedback loop for model improvement

---

## Test Commands

```bash
# Run backend tests
cd backend
pytest tests/ -v

# Test door extraction
curl -X POST "http://localhost:8000/api/v1/gewerke/doors/from-schedule" \
     -F "file=@Tuerenliste_Bauteil_B_OG1.pdf"

# Test flooring extraction
curl -X POST "http://localhost:8000/api/v1/gewerke/flooring/from-plan" \
     -F "file=@floor_plan.pdf"
```

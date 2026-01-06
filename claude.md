# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Mission

SnapGrid: Deterministic extraction of construction document data with 100% traceability and zero hallucination. All extracted numbers must come from vector geometry, table extraction, computer vision, or OCR - never generated.

## Development Commands

```bash
# Backend (FastAPI)
cd backend && source venv/bin/activate
uvicorn app.main:app --reload --port 8000   # Dev server with hot reload
pytest tests/ -v                              # Run all tests
pytest tests/test_gewerke_doors.py -v         # Run single test file
pytest tests/test_gewerke_doors.py::test_door_category_classification -v  # Single test

# Frontend (Next.js)
cd frontend
npm run dev      # Dev server at localhost:3000
npm run build    # Production build
npm run lint     # ESLint

# API Documentation
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```

## Architecture

```
INPUT ROUTER (input_router.py)
├── CAD PDF with annotations → Text Extraction (pdfplumber)
├── CAD PDF no annotations → Vector + CV (PyMuPDF + YOLO)
├── Scanned PDF → Roboflow CV
└── Photo → Roboflow CV
          ↓
MEASUREMENT ENGINE → Quantities (m², count, dimensions)
```

### Key Service Flow

1. **Input Router** (`app/services/input_router.py`): Detects `InputType.CAD_WITH_TEXT`, `CAD_NO_TEXT`, `SCANNED_PDF`, or `PHOTO`
2. **Trade Modules** (`app/services/gewerke.py`): Door classification, flooring/drywall area extraction
3. **Vector Measurement** (`app/services/vector_measurement.py`): PDF geometry parsing with PyMuPDF
4. **Roboflow Service** (`app/services/roboflow_service.py`): CV for scans/photos
5. **Persistence** (`app/services/persistence.py`): Supabase storage (optional)

### Trade Modules (Gewerke)

| Trade | Primary Method | Key Patterns |
|-------|----------------|--------------|
| Doors | Schedule text extraction | `DoorCategory` enum (T30, T90, DSS, Standard) |
| Flooring | NRF text values | Area in m² from annotations |
| Drywall | Perimeter × height | U-values × wall_height_m |

## Core Patterns

**Traceability**: Every extracted quantity must include `page_number`, `source_type`, `confidence_score`, `raw_value`.

**German CAD Priority**: Optimized for German construction documents. Key terms:
- Türenliste = Door schedule
- NRF = Net floor area (m²)
- U = Perimeter values (m)
- Maßstab = Scale (1:100)
- T30-RS, T90 = Fire ratings

**Drywall vs Flooring**: Flooring uses NRF area values. Drywall uses `perimeter × wall_height` (not raw vector segments, which include furniture/text).

## API Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/v1/gewerke/doors/from-schedule` | Door schedule → structured list |
| `POST /api/v1/gewerke/flooring/from-plan` | NRF extraction (m²) |
| `POST /api/v1/gewerke/drywall/from-plan` | Perimeter × height (m²) |
| `POST /api/v1/gewerke/*/smart` | Auto-route based on input type |
| `POST /api/v1/cv/detect/{rooms,walls,doors}` | Roboflow CV |
| `POST /api/v1/cv/analyze-input` | Detect input type |

## Environment Variables

Backend `.env`:
```
SNAPGRID_SUPABASE_URL=https://xxx.supabase.co
SNAPGRID_SUPABASE_SERVICE_KEY=sb_secret_xxx
SNAPGRID_YOLO_MODEL_PATH=/path/to/door_detector_custom.pt
ROBOFLOW_API_KEY=xxx
```

Frontend `.env.local`:
```
NEXT_PUBLIC_SNAPGRID_API_URL=http://localhost:8000
```

## Test Files

Sample PDFs in `PLANS/` directory. Sample door schedule: `Tuerenliste_Bauteil_B_OG1.pdf`.

```bash
# Test with sample
curl -X POST "http://localhost:8000/api/v1/schedules/extract?use_sample=true"
```

## Database Schema (Supabase)

Core tables: `projects`, `files`, `extractions`, `scale_contexts`, `sectors`, `detected_objects`, `measurements`. Schema in `backend/infra/supabase/schema.sql`.

## Custom Skills

- `/vector-measurement` - Extract and measure vector geometry from CAD-derived PDFs
- `/pdf-ingestion` - Ingest PDF blueprints and classify pages
- `/schedule-extraction` - Extract structured tables from schedule pages
- `/project-docs` - Read and update project documentation

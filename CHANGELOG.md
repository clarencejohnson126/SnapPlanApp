# SnapGrid Changelog

Historical development log moved from CLAUDE.md for size optimization.

---

## 2025-12-22 - Gewerke (Trade Modules): Doors & Drywall

**Session Focus**: Implement first two trade-specific quantity takeoff modules

**Changes**:
- Door Gewerk: DoorCategory enum, classification logic, API endpoint
- Drywall Gewerk: Sector measurement, area calculation, API endpoint
- 36 new tests (285 total passing)

---

## 2025-12-22 - Phase D: Vector Wall Measurement

**Changes**:
- LineSegment/WallSegment data models
- Vector extraction from CAD-style PDFs (PyMuPDF)
- Wall length calculation in sectors
- Drywall area = wall_length × wall_height
- 50 new tests

---

## 2025-12-21 - Phase C: Sectors, Area Calculation, CV Pipeline

**Changes**:
- Sector model with polygon support
- Shoelace algorithm for area calculation
- Point-in-polygon (ray casting)
- CV pipeline skeleton with YOLO integration
- 85 new tests

---

## 2025-12-21 - Phase B: Scale Detection & Calibration

**Changes**:
- PDF ingestion with PyMuPDF
- Scale detection from text annotations (M 1:100, Maßstab 1:50)
- User-assisted calibration
- ScaleContext persistence to Supabase
- 69 new tests

---

## 2025-12-21 - Phase A: Architecture & Scaffolding

**Changes**:
- Service modules: plan_ingestion, scale_calibration, cv_pipeline, measurement_engine
- API endpoint stubs
- Supabase schema for detected_objects, sectors, measurements, scale_contexts

---

## 2025-12-21 - Supabase Persistence Layer

**Changes**:
- SQL schema for projects, files, extractions
- Conditional persistence (works without Supabase configured)
- PDF storage in Supabase Storage bucket

---

## 2025-12-21 - Backend POC: Schedule Extraction

**Changes**:
- FastAPI scaffold
- pdfplumber table extraction
- German header normalization
- 34 doors extracted from sample Türliste

---

## YOLO Training (2024-12-22)

- Model: YOLOv8n fine-tuned for door detection
- Training Data: 5,508 door annotations from 260 floor plans
- Projects: BTB 2 (9), Omniturm (178), Haardtring (73)
- Model path: backend/models/door_detector_custom.pt

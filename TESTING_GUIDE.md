# SnapGrid CV Testing Guide

## System Status

Your SnapGrid system is now fully configured with:
- **Roboflow SDK**: Installed (inference-sdk)
- **OpenCV**: Installed
- **API Key**: Configured

## Starting the Backend

```bash
cd /Users/clarence/Desktop/SnapGrid/backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

Verify it's running:
```bash
curl http://localhost:8000/health
```

---

## API Endpoints for Testing

### 1. Check CV Status
```bash
curl http://localhost:8000/api/v1/cv/status
```

### 2. Analyze Input Type
Detects if your file is CAD with text, scanned PDF, or photo:
```bash
curl -X POST "http://localhost:8000/api/v1/cv/analyze-input" \
     -F "file=@your_file.pdf"
```

---

## Extracting Construction Quantities

### A. Flooring Area (m²)

**For German CAD PDFs with annotations (NRF values):**
```bash
curl -X POST "http://localhost:8000/api/v1/gewerke/flooring/from-plan" \
     -F "file=@floor_plan.pdf"
```

**For scanned PDFs, photos, or international blueprints (Roboflow CV):**
```bash
curl -X POST "http://localhost:8000/api/v1/gewerke/flooring/smart" \
     -F "file=@scanned_blueprint.pdf" \
     -F "scale=100"
```

**For images (PNG/JPG):**
```bash
curl -X POST "http://localhost:8000/api/v1/cv/detect/rooms" \
     -F "file=@floor_plan.png" \
     -F "scale=100" \
     -F "dpi=150"
```

---

### B. Drywall Area (m²)

**For German CAD PDFs with perimeter (U) values:**
```bash
curl -X POST "http://localhost:8000/api/v1/gewerke/drywall/from-plan" \
     -F "file=@floor_plan.pdf" \
     -F "wall_height_m=2.6"
```

**For scanned PDFs, photos, or international blueprints (Roboflow CV):**
```bash
curl -X POST "http://localhost:8000/api/v1/gewerke/drywall/smart" \
     -F "file=@scanned_blueprint.pdf" \
     -F "wall_height_m=2.6" \
     -F "scale=100"
```

**For images (PNG/JPG) - Wall Detection:**
```bash
curl -X POST "http://localhost:8000/api/v1/cv/detect/walls" \
     -F "file=@floor_plan.png" \
     -F "scale=100" \
     -F "dpi=150"
```

---

### C. Door Count (pcs)

**From door schedule PDF (Türenliste):**
```bash
curl -X POST "http://localhost:8000/api/v1/gewerke/doors/from-schedule" \
     -F "file=@door_schedule.pdf"
```

**From floor plan using CV (Roboflow):**
```bash
curl -X POST "http://localhost:8000/api/v1/cv/detect/doors" \
     -F "file=@floor_plan.png" \
     -F "scale=100" \
     -F "dpi=150"
```

---

### D. Full Floor Plan Analysis (All at Once)

Analyze walls, rooms, and doors in a single request:

```bash
curl -X POST "http://localhost:8000/api/v1/cv/analyze" \
     -F "file=@floor_plan.png" \
     -F "scale=100" \
     -F "dpi=150"
```

**Returns:**
- Room count and total floor area (m²)
- Door count with estimated widths
- Wall perimeter (m) for drywall calculation

---

## Input Type Support

| Input Type | Best Endpoint | Detection Method |
|------------|---------------|------------------|
| German CAD PDF (with NRF/U text) | `/gewerke/flooring/from-plan` | Text extraction |
| Scanned PDF | `/gewerke/flooring/smart` | Roboflow CV |
| Photo of blueprint | `/cv/analyze` | Roboflow CV |
| PNG/JPG floor plan | `/cv/detect/rooms` | Roboflow CV |
| US/International blueprint | `/cv/analyze` | Roboflow CV |

---

## Scale Parameter

The `scale` parameter is critical for accurate measurements:

| Scale Value | Meaning |
|-------------|---------|
| 50 | 1:50 (2cm = 1m) |
| 100 | 1:100 (1cm = 1m) - **Most common** |
| 200 | 1:200 (0.5cm = 1m) |

---

## Example Outputs

### Room Detection Response:
```json
{
  "room_count": 5,
  "total_area_m2": 125.50,
  "scale": "1:100",
  "rooms": [
    {
      "class_name": "room",
      "confidence": 0.89,
      "area_m2": 24.5,
      "perimeter_m": 20.3
    }
  ]
}
```

### Door Detection Response:
```json
{
  "door_count": 8,
  "by_width": {
    "0.9": 5,
    "1.0": 3
  },
  "doors": [
    {
      "class_name": "door",
      "confidence": 0.92,
      "estimated_width_m": 0.9
    }
  ]
}
```

### Full Analysis Response:
```json
{
  "summary": {
    "total_rooms": 5,
    "total_doors": 8,
    "total_floor_area_m2": 125.50,
    "total_wall_perimeter_m": 85.2
  },
  "walls": { ... },
  "rooms": { ... },
  "doors": { ... }
}
```

---

## Python Script Example

```python
import requests

# Full floor plan analysis
with open("floor_plan.png", "rb") as f:
    response = requests.post(
        "http://localhost:8000/api/v1/cv/analyze",
        files={"file": f},
        params={"scale": 100, "dpi": 150}
    )

result = response.json()

print(f"Rooms: {result['summary']['total_rooms']}")
print(f"Floor Area: {result['summary']['total_floor_area_m2']} m²")
print(f"Doors: {result['summary']['total_doors']} pcs")
print(f"Wall Perimeter: {result['summary']['total_wall_perimeter_m']} m")

# Calculate drywall area
wall_height = 2.6  # meters
drywall_area = result['summary']['total_wall_perimeter_m'] * wall_height
print(f"Drywall Area: {drywall_area:.2f} m²")
```

---

## Troubleshooting

### "Roboflow not configured"
Check that your `.env` file has:
```
SNAPGRID_ROBOFLOW_API_KEY=wIN31RzZDE6McxfvrSea
```

### "Image not found"
Make sure the file path is correct and the file exists.

### Low confidence detections
Try:
1. Higher DPI (e.g., `dpi=200`)
2. Better quality scan/image
3. Cleaner floor plan with less clutter

### Wrong measurements
Verify the `scale` parameter matches your blueprint's scale bar.

---

## API Documentation

Full interactive API docs available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

# Roboflow Training Guide for German Floor Plans

## Overview

Train a custom door/window detection model for German architectural floor plans.

**Why needed:** The pre-trained Roboflow models are not trained on German CAD floor plans and fail to detect doors/windows correctly.

**Goal:** Create a model that detects:
- Doors (with swing arc symbol)
- Windows (parallel lines with hatching)
- Optionally: Fire-rated doors (T30, T90)

---

## Prerequisites

- Roboflow account (free tier works for small datasets)
- 50-200 floor plan images (more = better accuracy)
- Your Roboflow API key: `wIN31RzZDE6McxfvrSea`

---

## Step 1: Convert PDFs to Images

**Roboflow does NOT accept PDFs.** You must convert to PNG/JPG first.

### Option A: Use the SnapGrid Script

```bash
cd /Users/clarence/Desktop/SnapGrid/backend
source venv/bin/activate

# Convert all PDFs in a folder
python scripts/pdf_to_training_images.py \
    "/path/to/your/floor_plan_pdfs" \
    "/path/to/output/training_images" \
    --dpi 150
```

### Option B: Manual Conversion (Single File)

```python
import fitz  # PyMuPDF

doc = fitz.open("floor_plan.pdf")
page = doc[0]

# 150 DPI is good balance of quality vs file size
zoom = 150 / 72
mat = fitz.Matrix(zoom, zoom)
pix = page.get_pixmap(matrix=mat)

pix.save("floor_plan.png", "png")
doc.close()
```

### Recommended Settings

| Setting | Value | Notes |
|---------|-------|-------|
| DPI | 150-200 | Higher = more detail, larger files |
| Format | PNG | Lossless, better for line drawings |
| Pages | All | Include variety of floor layouts |

---

## Step 2: Create Roboflow Project

1. Go to [app.roboflow.com](https://app.roboflow.com)
2. Click **"Create New Project"**
3. Configure:
   - **Project Name:** `german-floor-plan-doors`
   - **Project Type:** `Object Detection`
   - **Annotation Group:** Create new or use existing workspace

4. Click **"Create Project"**

---

## Step 3: Upload Images

1. In your project, click **"Upload"** (or drag & drop)
2. Select your converted PNG/JPG images
3. Click **"Save and Continue"**

**Tip:** Start with 50-100 images. You can add more later.

---

## Step 4: Annotate Images

This is the most time-consuming step. You need to draw bounding boxes around every door and window.

### Open Annotation Interface

1. Click **"Annotate"** in the left sidebar
2. Click on an image to start labeling

### Create Classes

Create these classes (labels):

| Class Name | Description |
|------------|-------------|
| `door` | Standard doors |
| `door_t30` | T30 fire-rated doors |
| `door_t90` | T90 fire-rated doors |
| `door_double` | Double doors |
| `window` | Windows |

### Draw Bounding Boxes

1. Select **Bounding Box** tool (or press `B`)
2. Click and drag to draw box around each door/window
3. Select the correct class from dropdown
4. Press `Enter` to confirm

### Tips for Faster Annotation

**Use Smart Polygon (AI-Assisted):**
1. Click magic wand icon in toolbar
2. Enable "Enhanced labeling"
3. Click on door symbol → AI suggests boundary
4. Adjust if needed → Confirm

**Keyboard Shortcuts:**
- `B` = Bounding box tool
- `Enter` = Confirm annotation
- `Delete` = Remove selected annotation
- `→` = Next image
- `←` = Previous image

### What to Annotate

**DO annotate:**
- Door swing arcs (quarter circles)
- Door leaf lines
- Window frames (parallel lines)
- Both open and closed door symbols

**DON'T annotate:**
- Furniture
- Room labels
- Dimension lines
- Scale bars

---

## Step 5: Generate Dataset Version

Once you have annotated at least 50 images:

1. Click **"Generate"** in left sidebar
2. Configure preprocessing:
   - **Auto-Orient:** ✓ Enabled
   - **Resize:** Stretch to 640x640 (or 1024x1024 for higher accuracy)

3. Configure augmentation (optional but recommended):
   - **Flip:** Horizontal
   - **Rotation:** ±15°
   - **Brightness:** ±15%

4. Click **"Generate"**

---

## Step 6: Train Model

1. Click **"Train"** button on your dataset version
2. Select model:
   - **Recommended:** `Roboflow 3.0 Object Detection` (fast, accurate)
   - **Alternative:** `YOLOv11` (if you need to export)

3. Select size:
   - **Nano:** Fastest, lower accuracy
   - **Small:** Good balance ← **Recommended**
   - **Medium:** Higher accuracy, slower

4. Click **"Start Training"**

**Training time:** 30 minutes to 2 hours depending on dataset size.

---

## Step 7: Test Your Model

After training completes:

1. Click **"Visualize"** to see predictions on test images
2. Click **"Deploy"** to get your model ID

Your model ID will be: `your-workspace/german-floor-plan-doors/1`

### Test via API

```python
from inference_sdk import InferenceHTTPClient

client = InferenceHTTPClient(
    api_url="https://detect.roboflow.com",
    api_key="wIN31RzZDE6McxfvrSea"
)

# Use YOUR trained model ID
result = client.infer(
    "floor_plan.png",
    model_id="your-workspace/german-floor-plan-doors/1"
)

print(f"Doors found: {len([p for p in result['predictions'] if 'door' in p['class']])}")
print(f"Windows found: {len([p for p in result['predictions'] if p['class'] == 'window'])}")
```

---

## Step 8: Integrate with SnapGrid

Once your model works, update SnapGrid config:

### Update config.py

```python
# In backend/app/core/config.py

# Replace with your trained model
roboflow_door_detection_model: str = "your-workspace/german-floor-plan-doors/1"
```

### Update .env

```bash
# If using different workspace
SNAPGRID_ROBOFLOW_DOOR_MODEL=your-workspace/german-floor-plan-doors/1
```

---

## Recommended Dataset Size

| Images | Expected Accuracy |
|--------|-------------------|
| 50 | ~60-70% (minimum viable) |
| 100 | ~75-85% (good) |
| 200 | ~85-90% (production ready) |
| 500+ | ~90-95% (excellent) |

**Quality > Quantity:** 50 well-annotated images beat 200 poorly-annotated ones.

---

## Troubleshooting

### Model not detecting doors

- Add more training images with that door style
- Check if annotations are accurate (box covers full door symbol)
- Lower confidence threshold in API call

### False positives (detecting non-doors)

- Add "negative" examples (images without doors)
- Make sure you're not annotating furniture

### Training fails

- Check image sizes aren't too large (resize to max 4096px)
- Ensure annotations are valid (no zero-width boxes)

---

## Cost

| Tier | Images | Training | Price |
|------|--------|----------|-------|
| Free | 1,000 | 3 trains/month | $0 |
| Starter | 10,000 | Unlimited | $249/month |

For SnapGrid prototype, **Free tier is sufficient**.

---

## Summary Checklist

- [ ] Convert PDFs to PNG (150 DPI)
- [ ] Create Roboflow project (Object Detection)
- [ ] Upload 50-200 images
- [ ] Create classes: door, door_t30, door_t90, window
- [ ] Annotate all doors/windows in each image
- [ ] Generate dataset version with augmentation
- [ ] Train model (Roboflow 3.0, Small)
- [ ] Test on new floor plans
- [ ] Update SnapGrid config with new model ID

---

## Sources

- [Roboflow: Train a Model](https://docs.roboflow.com/train/train)
- [Upload Images and Annotations](https://docs.roboflow.com/datasets/adding-data)
- [Supported Annotation Formats](https://roboflow.com/formats)
- [How to Train YOLOv11 Custom Model](https://blog.roboflow.com/yolov11-how-to-train-custom-data/)
- [Getting Started with Roboflow](https://blog.roboflow.com/getting-started-with-roboflow/)

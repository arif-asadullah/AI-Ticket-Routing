# OCR Screenshot Analysis

> DeskMind reads screenshots uploaded with tickets, extracts text, detects entities, and uses that information to improve classification accuracy.

---

## How It Works

```
User attaches screenshot of error dialog
        |
        v
POST /api/upload — saves file, runs Tesseract OCR
        |
        v
Image preprocessed: grayscale + contrast + sharpen
        |
        v
OCR extracts text: "ERROR: PostgreSQL connection refused on prod-db-01"
        |
        v
Screenshot type classified: "log_output" (keyword heuristics)
        |
        v
Entity extractor finds: server=prod-db-01, service=PostgreSQL
        |
        v
Frontend shows: thumbnail + extracted text + entity chips
        |
        v
User submits ticket — OCR text appended to description
        |
        v
4-classifier ensemble classifies enriched description
```

---

## Screenshot Type Detection

The OCR engine classifies screenshots into 6 types using keyword heuristics:

| Type | Keywords Detected | Example |
|------|------------------|---------|
| **Stack Trace** | Traceback, Exception, at line, caused by | Python/Java stack trace |
| **HTTP Error** | 502, 503, 500, Bad Gateway, Internal Server Error | Browser error page |
| **Log Output** | ERROR, WARN, INFO + timestamps (2026-05-19 10:30:00) | Application or system logs |
| **Terminal** | $, #, root@, C:\>, command not found | Terminal/SSH session |
| **Monitoring Dashboard** | CPU%, Memory%, Disk%, usage, utilization | Grafana/Prometheus dashboard |
| **General Screenshot** | None of the above | Any other screenshot |

Classification requires 2+ keyword matches to trigger. Confidence is based on hit count.

---

## Image Preprocessing

Before OCR, images are preprocessed for better accuracy:

1. **Resize** — max 2000px width (reduces processing time)
2. **Grayscale** — convert to single channel (removes color noise)
3. **Contrast enhancement** — 1.5x contrast boost (makes text sharper)
4. **Sharpening** — PIL SHARPEN filter (improves edge detection)

This pipeline significantly improves Tesseract accuracy on screenshots with dark backgrounds, low contrast, or small text.

---

## Entity Extraction from OCR Text

After text extraction, the same entity extractor used in the classification pipeline scans the OCR text for:

- **Server names** — matched against the `servers` collection (e.g., prod-db-01, prod-app-01)
- **Service names** — matched against the `services` collection (e.g., PostgreSQL, Redis, NGINX)
- **Error codes** — matched against the `error_codes` collection patterns

These entities are:
1. Displayed as colored chips in the frontend (blue=servers, orange=services, red=errors)
2. Appended to the ticket description for classification
3. Used by the quality scorer (entities present = higher quality)

---

## How OCR Text Feeds into Classification

When a ticket has attachments, the OCR text is appended to the description before the 4-classifier pipeline runs:

```
Original description: "postgresql service failed on the server"

[Screenshot Analysis]
Type: Terminal / Command Line
Extracted text: root@prod-db-01:~# systemctl status postgresql
postgresql.service - PostgreSQL database server
Active: failed (Result: exit-code)
FATAL: could not open relation mapping file

Summary: Terminal on prod-db-01 related to postgresql
```

The combined text then goes through:
- **Entity extractor** — finds prod-db-01 and postgresql from OCR text
- **Quality scorer** — upgrades to HIGH (has server name + error details)
- **LLM classifier** — sees the full terminal output for better reasoning
- **KNN classifier** — embedding of combined text finds similar resolved tickets
- **Centroid classifier** — embedding is closer to correct category centroid
- **Keyword classifier** — matches domain-specific terms from OCR text

---

## API Endpoints

### Upload Screenshot

```
POST /api/upload
Content-Type: multipart/form-data
Authorization: Bearer <token>

Body: file (image/png, image/jpeg, image/gif, image/webp, max 5MB)
```

Response:
```json
{
    "file_id": "ba123a24-fd62-4bda-8897-e9bd96166425",
    "file_url": "/api/upload/ba123a24-fd62-4bda-8897-e9bd96166425",
    "filename": "error_screenshot.png",
    "ocr_result": {
        "raw_text": "root@prod-db-01:~# systemctl status postgresql...",
        "screenshot_type": "terminal",
        "screenshot_type_label": "Terminal / Command Line",
        "entities": {
            "servers": ["prod-db-01"],
            "services": ["postgresql"],
            "error_codes": []
        },
        "summary": "Terminal on prod-db-01 related to postgresql",
        "confidence": 0.90
    }
}
```

### Serve Uploaded File

```
GET /api/upload/{file_id}
```

Returns the image file directly (for thumbnail display).

### Create Ticket with Attachments

```
POST /api/tickets
Content-Type: application/json

{
    "title": "database not starting",
    "description": "postgresql service failed",
    "priority": "high",
    "attachment_ids": ["ba123a24-fd62-4bda-8897-e9bd96166425"]
}
```

The `attachment_ids` reference files previously uploaded via `/api/upload`. OCR results are automatically combined with the description for classification.

---

## Frontend UX

### Ticket Creation Form
- Drag-and-drop zone below description field
- Thumbnail previews with upload spinner during OCR
- After OCR: green badge showing screenshot type + extracted text preview + entity chips
- Remove button on each thumbnail
- Max 5 attachments

### Ticket Detail View
- Clickable thumbnails (open full-size in new tab)
- OCR Analysis card: screenshot type badge, extracted text in code block, detected entity chips
- OCR confidence percentage

---

## Technical Stack

| Component | Technology | Size |
|-----------|-----------|------|
| OCR Engine | Tesseract OCR | ~20 MB |
| Python Wrapper | pytesseract | ~50 KB |
| Image Processing | Pillow (PIL) | Already installed |
| Storage | Local filesystem + Docker volume | Persistent |

---

## Limitations

- **Generated images** (not real screenshots) have lower OCR accuracy due to default fonts
- **Handwritten text** is not supported — Tesseract is optimized for printed/screen text
- **Very small text** (< 10px) may not be readable — preprocessing helps but has limits
- **Non-English text** — only English OCR model installed (tesseract-ocr-eng)

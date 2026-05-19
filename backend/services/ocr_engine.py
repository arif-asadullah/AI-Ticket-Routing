"""Advanced OCR Engine — extracts text from screenshots, classifies image type,
detects entities, and generates summaries for the classification pipeline.

Supports: error dialogs, terminal output, log files, HTTP errors,
monitoring dashboards, stack traces.
"""

import logging
import re

from PIL import Image, ImageEnhance, ImageFilter

logger = logging.getLogger(__name__)

# Screenshot type patterns (checked in priority order)
SCREENSHOT_PATTERNS = {
    "stack_trace": [
        r"traceback", r"exception", r"at line \d+", r"at com\.", r"at org\.",
        r"file \".*\", line", r"raise \w+", r"caused by:",
    ],
    "http_error": [
        r"\b[45]\d{2}\b", r"bad gateway", r"internal server error",
        r"service unavailable", r"not found", r"forbidden", r"unauthorized",
        r"http.*error", r"status.?code",
    ],
    "log_output": [
        r"\b(ERROR|WARN|WARNING|INFO|DEBUG|FATAL|CRITICAL)\b",
        r"\d{4}-\d{2}-\d{2}", r"\d{2}:\d{2}:\d{2}",
        r"\[error\]", r"\[warn\]", r"\[info\]",
    ],
    "terminal": [
        r"^\s*[\$#]", r"root@", r"C:\\>", r"PS C:\\", r"~\$",
        r"command not found", r"permission denied", r"segmentation fault",
    ],
    "monitoring_dashboard": [
        r"cpu.*\d+%", r"memory.*\d+%", r"disk.*\d+%", r"usage",
        r"utilization", r"load average", r"iops", r"throughput",
    ],
}

SCREENSHOT_LABELS = {
    "stack_trace": "Stack Trace",
    "http_error": "HTTP Error",
    "log_output": "Log Output",
    "terminal": "Terminal / Command Line",
    "monitoring_dashboard": "Monitoring Dashboard",
    "general_screenshot": "General Screenshot",
}


def preprocess_image(image: Image.Image) -> Image.Image:
    """Preprocess image for better OCR accuracy."""
    # Resize if too large
    max_width = 2000
    if image.width > max_width:
        ratio = max_width / image.width
        image = image.resize((max_width, int(image.height * ratio)), Image.LANCZOS)

    # Convert to grayscale
    image = image.convert("L")

    # Enhance contrast
    image = ImageEnhance.Contrast(image).enhance(1.5)

    # Sharpen
    image = image.filter(ImageFilter.SHARPEN)

    return image


def classify_screenshot_type(text: str) -> tuple[str, float]:
    """Classify screenshot type using keyword heuristics.

    Returns (type, confidence).
    """
    text_lower = text.lower()
    scores = {}

    for stype, patterns in SCREENSHOT_PATTERNS.items():
        hits = 0
        for pattern in patterns:
            if re.search(pattern, text_lower, re.MULTILINE):
                hits += 1
        if hits >= 2:
            scores[stype] = hits

    if not scores:
        return "general_screenshot", 0.3

    best = max(scores, key=scores.get)
    confidence = min(0.5 + scores[best] * 0.1, 0.95)
    return best, round(confidence, 2)


def extract_from_image(image_path: str, db=None) -> dict:
    """Extract text from screenshot, classify type, detect entities.

    Returns structured OCR result with extracted text, screenshot type,
    detected entities, summary, and confidence.
    """
    try:
        import pytesseract
    except ImportError:
        logger.warning("pytesseract not installed — OCR disabled")
        return _empty_result("pytesseract not available")

    try:
        # Open and preprocess
        image = Image.open(image_path)
        processed = preprocess_image(image)

        # Run OCR
        raw_text = pytesseract.image_to_string(processed).strip()

        if not raw_text or len(raw_text) < 5:
            return _empty_result("No text detected in image")

        # Get OCR confidence
        try:
            data = pytesseract.image_to_data(processed, output_type=pytesseract.Output.DICT)
            confidences = [int(c) for c in data["conf"] if int(c) > 0]
            ocr_confidence = round(sum(confidences) / len(confidences) / 100, 2) if confidences else 0.5
        except Exception:
            ocr_confidence = 0.5

        # Classify screenshot type
        screenshot_type, type_confidence = classify_screenshot_type(raw_text)

        # Extract entities using existing entity extractor
        entities = {"servers": [], "services": [], "error_codes": []}
        try:
            from backend.services.entity_extractor import entity_extractor
            entities = entity_extractor.extract(raw_text, db=db)
        except Exception as exc:
            logger.warning("Entity extraction from OCR text failed: %s", exc)

        # Build summary
        summary = _build_summary(raw_text, screenshot_type, entities)

        logger.info(
            "OCR: type=%s, confidence=%.2f, text_len=%d, servers=%s, errors=%d",
            screenshot_type, ocr_confidence, len(raw_text),
            entities.get("servers", []), len(entities.get("error_codes", [])),
        )

        return {
            "raw_text": raw_text[:2000],  # Cap at 2000 chars
            "screenshot_type": screenshot_type,
            "screenshot_type_label": SCREENSHOT_LABELS.get(screenshot_type, "Screenshot"),
            "entities": {
                "servers": entities.get("servers", []),
                "services": entities.get("services", []),
                "error_codes": [e.get("pattern", "") for e in entities.get("error_codes", [])],
            },
            "summary": summary,
            "confidence": ocr_confidence,
        }

    except Exception as exc:
        logger.error("OCR extraction failed: %s", exc)
        return _empty_result(f"OCR failed: {exc}")


def _build_summary(raw_text: str, screenshot_type: str, entities: dict) -> str:
    """Build a human-readable summary of what was found."""
    label = SCREENSHOT_LABELS.get(screenshot_type, "Screenshot")
    parts = [label]

    servers = entities.get("servers", [])
    services = entities.get("services", [])
    errors = entities.get("error_codes", [])

    if servers:
        parts.append(f"on {servers[0]}")
    if services:
        parts.append(f"related to {services[0]}")
    if errors:
        err_text = errors[0].get("pattern", "") if isinstance(errors[0], dict) else str(errors[0])
        parts.append(f"showing '{err_text}'")

    return " ".join(parts)


def _empty_result(reason: str) -> dict:
    return {
        "raw_text": "",
        "screenshot_type": "general_screenshot",
        "screenshot_type_label": "General Screenshot",
        "entities": {"servers": [], "services": [], "error_codes": []},
        "summary": reason,
        "confidence": 0.0,
    }

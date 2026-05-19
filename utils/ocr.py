"""
utils/ocr.py
PaddleOCR wrapper — extract text from images and scanned PDFs.
"""

from pathlib import Path
from loguru import logger


class OCREngine:
    """
    Lazy-loads PaddleOCR (heavy import) only when needed.
    Usage:
        from utils.ocr import ocr
        text = ocr.extract_from_image("screenshot.png")
        text = ocr.extract_from_pdf("scanned.pdf")
    """

    def __init__(self):
        self._ocr = None

    def _get_ocr(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR
            self._ocr = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
            logger.info("PaddleOCR initialized")
        return self._ocr

    def extract_from_image(self, image_path: str) -> str:
        """Extract text from an image file."""
        path = Path(image_path)
        if not path.exists():
            logger.error(f"Image not found: {image_path}")
            return ""
        try:
            engine = self._get_ocr()
            result = engine.ocr(str(path), cls=True)
            lines = []
            for page in result:
                if page:
                    for line in page:
                        if line and len(line) >= 2:
                            text, confidence = line[1]
                            if confidence > 0.5:
                                lines.append(text)
            extracted = "\n".join(lines)
            logger.info(f"OCR extracted {len(lines)} lines from {path.name}")
            return extracted
        except Exception as e:
            logger.error(f"OCR failed on {image_path}: {e}")
            return ""

    def extract_from_pdf(self, pdf_path: str) -> str:
        """
        Extract text from a PDF — tries digital text first, falls back to OCR.
        """
        import fitz  # PyMuPDF
        path = Path(pdf_path)
        if not path.exists():
            logger.error(f"PDF not found: {pdf_path}")
            return ""
        try:
            doc = fitz.open(str(path))
            all_text = []
            for page_num, page in enumerate(doc):
                # Try direct text extraction
                text = page.get_text("text").strip()
                if text and len(text) > 50:
                    all_text.append(text)
                else:
                    # Render page to image and OCR it
                    pix = page.get_pixmap(dpi=150)
                    img_path = path.parent / f"_ocr_page_{page_num}.png"
                    pix.save(str(img_path))
                    ocr_text = self.extract_from_image(str(img_path))
                    img_path.unlink(missing_ok=True)
                    if ocr_text:
                        all_text.append(ocr_text)
            doc.close()
            result = "\n\n".join(all_text)
            logger.info(f"PDF extraction complete: {len(result)} chars from {path.name}")
            return result
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return ""

    def extract_from_screenshot(self, screenshot_bytes: bytes) -> str:
        """Extract text from screenshot bytes (e.g. from Playwright)."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(screenshot_bytes)
            tmp_path = f.name
        text = self.extract_from_image(tmp_path)
        Path(tmp_path).unlink(missing_ok=True)
        return text


ocr = OCREngine()

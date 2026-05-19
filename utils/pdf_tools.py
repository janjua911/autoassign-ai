"""
utils/pdf_tools.py
PDF reading and text extraction utilities using PyMuPDF (fitz).
"""

from pathlib import Path
from loguru import logger


def read_pdf_text(pdf_path: str) -> str:
    """Extract all text from a PDF file."""
    import fitz
    path = Path(pdf_path)
    if not path.exists():
        logger.error(f"PDF not found: {pdf_path}")
        return ""
    try:
        doc = fitz.open(str(path))
        pages = [page.get_text("text") for page in doc]
        doc.close()
        text = "\n\n".join(p.strip() for p in pages if p.strip())
        logger.info(f"Read {len(pages)} pages from {path.name}")
        return text
    except Exception as e:
        logger.error(f"PDF read error: {e}")
        return ""


def pdf_page_count(pdf_path: str) -> int:
    """Return number of pages in a PDF."""
    import fitz
    try:
        doc = fitz.open(str(pdf_path))
        count = len(doc)
        doc.close()
        return count
    except Exception:
        return 0


def merge_pdfs(pdf_paths: list[str], output_path: str) -> bool:
    """Merge multiple PDFs into one."""
    import fitz
    try:
        merged = fitz.open()
        for p in pdf_paths:
            doc = fitz.open(str(p))
            merged.insert_pdf(doc)
            doc.close()
        merged.save(str(output_path))
        merged.close()
        logger.info(f"Merged {len(pdf_paths)} PDFs → {output_path}")
        return True
    except Exception as e:
        logger.error(f"PDF merge failed: {e}")
        return False


def pdf_to_images(pdf_path: str, output_dir: str, dpi: int = 150) -> list[str]:
    """Convert each PDF page to a PNG image. Returns list of image paths."""
    import fitz
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    image_paths = []
    try:
        doc = fitz.open(str(pdf_path))
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=dpi)
            img_path = out_dir / f"page_{i+1:03d}.png"
            pix.save(str(img_path))
            image_paths.append(str(img_path))
        doc.close()
        logger.info(f"Converted {len(image_paths)} pages to images")
    except Exception as e:
        logger.error(f"PDF to image failed: {e}")
    return image_paths

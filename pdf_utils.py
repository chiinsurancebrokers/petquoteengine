"""
PETSHEALTH Quote Engine - Secure PDF Utilities
Safe PDF merging and validation
"""
import io
import logging
from pathlib import Path
from typing import Optional, Union, List, Dict

from pypdf import PdfReader, PdfWriter
from pypdf.errors import PdfReadError

from config import IPID_MAP

logger = logging.getLogger(__name__)


class PDFError(Exception):
    """Custom exception for PDF-related errors"""
    pass


# --------------------------
# PDF Validation
# --------------------------

def validate_pdf_bytes(pdf_bytes: bytes, max_size_mb: int = 50) -> bool:
    """
    Validate PDF file content.

    Args:
        pdf_bytes: PDF content as bytes
        max_size_mb: Maximum allowed size in MB

    Returns:
        True if valid

    Raises:
        PDFError: If PDF is invalid
    """
    if not pdf_bytes:
        raise PDFError("PDF is empty")

    # Check size
    size_mb = len(pdf_bytes) / (1024 * 1024)
    if size_mb > max_size_mb:
        raise PDFError(f"PDF too large: {size_mb:.1f}MB (max: {max_size_mb}MB)")

    # Check magic bytes (PDF signature)
    if not pdf_bytes.startswith(b'%PDF-'):
        raise PDFError("Invalid PDF file (missing PDF signature)")

    # Try to read PDF
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        page_count = len(reader.pages)

        if page_count == 0:
            raise PDFError("PDF has no pages")

        if page_count > 100:  # Sanity check
            logger.warning(f"PDF has many pages: {page_count}")

        logger.info(f"PDF validated: {page_count} pages, {size_mb:.2f}MB")
        return True

    except PdfReadError as e:
        raise PDFError(f"Corrupted or invalid PDF: {str(e)}") from e

    except Exception as e:
        raise PDFError(f"Failed to validate PDF: {str(e)}") from e


def validate_pdf_file(filepath: Union[str, Path]) -> bool:
    """
    Validate PDF file from disk.

    Args:
        filepath: Path to PDF file

    Returns:
        True if valid

    Raises:
        PDFError: If file doesn't exist or is invalid
    """
    filepath = Path(filepath)

    if not filepath.exists():
        raise PDFError(f"PDF file not found: {filepath}")

    if not filepath.is_file():
        raise PDFError(f"Not a file: {filepath}")

    # Check file extension
    if filepath.suffix.lower() != '.pdf':
        raise PDFError(f"Not a PDF file: {filepath}")

    # Read and validate
    try:
        with open(filepath, 'rb') as f:
            pdf_bytes = f.read()
        return validate_pdf_bytes(pdf_bytes)

    except IOError as e:
        raise PDFError(f"Cannot read PDF file: {str(e)}") from e


# --------------------------
# PDF Merging
# --------------------------

def merge_quote_with_ipids(
        quote_pdf_bytes: bytes,
        selected_plans: List[str],
        validate_ipids: bool = True,
) -> bytes:
    """
    Merge quote PDF with IPID documents (SECURE).

    Args:
        quote_pdf_bytes: Main quote PDF as bytes
        selected_plans: List of selected plan keys
        validate_ipids: Whether to validate IPID files

    Returns:
        Merged PDF as bytes

    Raises:
        PDFError: If merge fails
    """
    try:
        # Validate main quote PDF
        logger.info("Validating main quote PDF...")
        validate_pdf_bytes(quote_pdf_bytes)

        # Create writer
        writer = PdfWriter()

        # Add quote pages
        quote_reader = PdfReader(io.BytesIO(quote_pdf_bytes))
        for page in quote_reader.pages:
            writer.add_page(page)

        quote_pages = len(quote_reader.pages)
        logger.info(f"Added {quote_pages} pages from quote PDF")

        # Add IPID documents
        ipids_added = 0
        missing_ipids = []

        for plan_key in selected_plans:
            ipid_path = IPID_MAP.get(plan_key)

            if not ipid_path:
                logger.warning(f"No IPID mapping for plan: {plan_key}")
                continue

            ipid_path = Path(ipid_path)

            if not ipid_path.exists():
                logger.warning(f"IPID file not found: {ipid_path}")
                missing_ipids.append(str(ipid_path))
                continue

            try:
                # Validate IPID if requested
                if validate_ipids:
                    validate_pdf_file(ipid_path)

                # Add IPID pages
                ipid_reader = PdfReader(str(ipid_path))
                ipid_page_count = len(ipid_reader.pages)

                for page in ipid_reader.pages:
                    writer.add_page(page)

                logger.info(f"Added {ipid_page_count} pages from {ipid_path.name}")
                ipids_added += 1

            except Exception as e:
                logger.error(f"Failed to add IPID {ipid_path}: {e}")
                missing_ipids.append(str(ipid_path))
                continue

        # Write merged PDF
        output = io.BytesIO()
        writer.write(output)
        merged_bytes = output.getvalue()

        # Validate merged PDF
        validate_pdf_bytes(merged_bytes)

        total_pages = len(writer.pages)
        logger.info(
            f"✅ Merged PDF created: {total_pages} pages "
            f"(quote: {quote_pages}, IPIDs: {ipids_added})"
        )

        if missing_ipids:
            logger.warning(f"Missing IPIDs: {missing_ipids}")

        return merged_bytes

    except PDFError:
        raise

    except Exception as e:
        logger.error(f"Unexpected error merging PDFs: {e}")
        raise PDFError(f"Failed to merge PDFs: {str(e)}") from e


def get_ipid_status(selected_plans: List[str]) -> Dict:
    """
    Check which IPID files are available.

    Args:
        selected_plans: List of selected plan keys

    Returns:
        Dictionary with IPID availability info
    """
    status = {
        "available": [],
        "missing": [],
        "total_required": len(selected_plans),
    }

    for plan_key in selected_plans:
        ipid_path = IPID_MAP.get(plan_key)

        if not ipid_path:
            status["missing"].append({
                "plan": plan_key,
                "reason": "No IPID mapping configured",
            })
            continue

        ipid_path = Path(ipid_path)

        if not ipid_path.exists():
            status["missing"].append({
                "plan": plan_key,
                "path": str(ipid_path),
                "reason": "File not found",
            })
        else:
            try:
                validate_pdf_file(ipid_path)
                status["available"].append({
                    "plan": plan_key,
                    "path": str(ipid_path),
                    "size_kb": ipid_path.stat().st_size / 1024,
                })
            except PDFError as e:
                status["missing"].append({
                    "plan": plan_key,
                    "path": str(ipid_path),
                    "reason": f"Invalid PDF: {str(e)}",
                })

    return status


# --------------------------
# PDF Metadata
# --------------------------

def add_pdf_metadata(pdf_bytes: bytes, metadata: Dict) -> bytes:
    """
    Add metadata to PDF (optional enhancement).

    Args:
        pdf_bytes: PDF content
        metadata: Dictionary of metadata fields

    Returns:
        PDF with metadata
    """
    try:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        writer = PdfWriter()

        # Copy all pages
        for page in reader.pages:
            writer.add_page(page)

        # Add metadata
        writer.add_metadata({
            '/Title': metadata.get('title', 'PETSHEALTH Quote'),
            '/Author': metadata.get('author', 'PETSHEALTH'),
            '/Subject': metadata.get('subject', 'Pet Insurance Quotation'),
            '/Creator': 'PETSHEALTH Quote Engine',
            '/Producer': 'PETSHEALTH Quote Engine v1.0',
        })

        output = io.BytesIO()
        writer.write(output)
        return output.getvalue()

    except Exception as e:
        logger.error(f"Failed to add metadata: {e}")
        return pdf_bytes  # Return original if metadata addition fails
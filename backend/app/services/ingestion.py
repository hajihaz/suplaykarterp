from __future__ import annotations

import csv
import ipaddress
import io
import json
import re
import shutil
import socket
import subprocess
import tempfile
from pathlib import Path
from typing import List
from urllib.parse import parse_qs, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from pypdf import PdfReader

try:
    import fitz  # type: ignore
except ImportError:  # pragma: no cover - optional runtime dependency
    fitz = None

RapidOCR = None  # type: ignore
_RAPID_OCR_IMPORT_ATTEMPTED = False

from app.core.config import settings
from app.services.rag import normalize_group_name, normalize_source_url, normalize_tags


TEXT_EXTENSIONS = {"txt", "md", "markdown", "log", "text", "rtf"}
IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "tif", "tiff", "bmp"}
MAX_IMPORT_REDIRECTS = 4
TRUSTED_IMPORT_HOSTS = {"docs.google.com", "drive.google.com"}
ALLOWED_IMPORT_CONTENT_TYPES = (
    "text/html",
    "application/xhtml+xml",
    "text/plain",
    "text/csv",
    "application/csv",
    "application/json",
    "application/pdf",
    "application/octet-stream",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "image/",
)


def _title_from_filename(name: str) -> str:
    return " ".join(Path(name).stem.replace("_", " ").replace("-", " ").split()).strip() or "Imported document"


def _truncate_content(value: str, maximum: int = 60000) -> str:
    cleaned = "\n".join(line.rstrip() for line in value.splitlines()).strip()
    if len(cleaned) <= maximum:
        return cleaned
    return cleaned[: maximum - 1].rstrip() + "…"


def _merged_tags(existing: List[str] | str | None, extra: List[str] | None = None) -> List[str]:
    raw_tags: List[str]
    if isinstance(existing, list):
        raw_tags = [str(tag) for tag in existing]
    else:
        raw_tags = str(existing or "").split(",")
    return normalize_tags(raw_tags + list(extra or []))


def _normalize_document(
    item: dict,
    fallback_title: str,
    source: str,
    group_name: str = "",
    source_url: str | None = None,
    default_tags: List[str] | None = None,
) -> dict | None:
    content = _truncate_content(str(item.get("content") or item.get("body") or item.get("text") or ""))
    if len(content.strip()) < 10:
        return None
    return {
        "title": str(item.get("title") or item.get("name") or fallback_title).strip()[:200],
        "content": content,
        "tags": _merged_tags(item.get("tags", []), default_tags),
        "source": source,
        "group_name": normalize_group_name(item.get("group_name") or group_name),
        "source_url": normalize_source_url(item.get("source_url") or source_url),
    }


def _parse_csv_documents(text: str, filename: str, source: str, group_name: str, base_tags: List[str]) -> List[dict]:
    reader = csv.DictReader(io.StringIO(text))
    documents: List[dict] = []
    for index, row in enumerate(reader, start=1):
        normalized = _normalize_document(row, f"{_title_from_filename(filename)} {index}", source, group_name, default_tags=base_tags)
        if normalized:
            documents.append(normalized)
    return documents


def _parse_json_documents(text: str, filename: str, source: str, group_name: str, base_tags: List[str]) -> List[dict]:
    payload = json.loads(text)
    if isinstance(payload, dict) and "documents" in payload:
        payload = payload["documents"]
    if isinstance(payload, list):
        return [
            normalized
            for index, entry in enumerate(payload, start=1)
            if (normalized := _normalize_document(entry, f"{_title_from_filename(filename)} {index}", source, group_name, default_tags=base_tags))
        ]
    if isinstance(payload, dict):
        normalized = _normalize_document(payload, _title_from_filename(filename), source, group_name, default_tags=base_tags)
        return [normalized] if normalized else []
    return []


def _ocr_command_available() -> bool:
    return bool(shutil.which(settings.tesseract_command))


def _pdftoppm_available() -> bool:
    return bool(shutil.which(settings.pdftoppm_command))


_RAPID_OCR_ENGINE = None


def _load_rapidocr_class():
    global RapidOCR, _RAPID_OCR_IMPORT_ATTEMPTED
    if not _RAPID_OCR_IMPORT_ATTEMPTED:
        _RAPID_OCR_IMPORT_ATTEMPTED = True
        try:
            from rapidocr_onnxruntime import RapidOCR as RapidOCRClass  # type: ignore
        except Exception:  # pragma: no cover - optional OCR dependency
            RapidOCR = None
        else:
            RapidOCR = RapidOCRClass
    return RapidOCR


def _rapidocr_available() -> bool:
    return _load_rapidocr_class() is not None


def _rapidocr_engine():
    global _RAPID_OCR_ENGINE
    RapidOCRClass = _load_rapidocr_class()
    if RapidOCRClass is None:
        return None
    if _RAPID_OCR_ENGINE is None:
        _RAPID_OCR_ENGINE = RapidOCRClass()
    return _RAPID_OCR_ENGINE


def _rapidocr_text_from_path(path: Path) -> str:
    engine = _rapidocr_engine()
    if engine is None:
        return ""
    try:
        result, _elapsed = engine(str(path))
    except Exception:
        return ""
    if not result:
        return ""
    lines: List[str] = []
    for item in result:
        if len(item) >= 2 and item[1]:
            lines.append(str(item[1]).strip())
    return "\n".join(line for line in lines if line).strip()


def _ocr_image_bytes(content: bytes, suffix: str) -> str:
    if not settings.ocr_enabled:
        return ""
    with tempfile.TemporaryDirectory() as temp_dir:
        image_path = Path(temp_dir) / f"image.{suffix}"
        image_path.write_bytes(content)
        if _ocr_command_available():
            try:
                result = subprocess.run(
                    [settings.tesseract_command, str(image_path), "stdout", "-l", settings.ocr_languages],
                    capture_output=True,
                    check=True,
                    text=True,
                )
                return result.stdout.strip()
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        if _rapidocr_available():
            return _rapidocr_text_from_path(image_path)
        return ""


def _ocr_pdf_bytes(content: bytes) -> str:
    if not settings.ocr_enabled:
        return ""
    with tempfile.TemporaryDirectory() as temp_dir:
        pdf_path = Path(temp_dir) / "input.pdf"
        image_prefix = Path(temp_dir) / "page"
        pdf_path.write_bytes(content)
        texts: List[str] = []
        if _ocr_command_available() and _pdftoppm_available():
            try:
                subprocess.run(
                    [settings.pdftoppm_command, "-png", str(pdf_path), str(image_prefix)],
                    capture_output=True,
                    check=True,
                    text=True,
                )
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
            else:
                for image_path in sorted(Path(temp_dir).glob("page-*.png")):
                    try:
                        result = subprocess.run(
                            [settings.tesseract_command, str(image_path), "stdout", "-l", settings.ocr_languages],
                            capture_output=True,
                            check=True,
                            text=True,
                        )
                        output = result.stdout.strip()
                        if output:
                            texts.append(output)
                    except (subprocess.CalledProcessError, FileNotFoundError):
                        continue
        if texts:
            return "\n\n".join(texts).strip()

        if fitz is None or not _rapidocr_available():
            return ""
        try:
            document = fitz.open(stream=content, filetype="pdf")
        except Exception:
            return ""
        try:
            for index in range(document.page_count):
                page = document.load_page(index)
                pixmap = page.get_pixmap(dpi=180, alpha=False)
                image_path = Path(temp_dir) / f"page-{index + 1}.png"
                pixmap.save(str(image_path))
                output = _rapidocr_text_from_path(image_path)
                if output:
                    texts.append(output)
        finally:
            document.close()
        return "\n\n".join(texts).strip()


def _extract_pdf_text(content: bytes) -> str:
    reader = PdfReader(io.BytesIO(content))
    pages = []
    for page in reader.pages:
        extracted = (page.extract_text() or "").strip()
        if extracted:
            pages.append(extracted)
    text = "\n\n".join(pages).strip()
    if text:
        return text
    return _ocr_pdf_bytes(content)


def _extract_docx_text(content: bytes) -> str:
    document = DocxDocument(io.BytesIO(content))
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    return "\n\n".join(paragraphs)


def import_documents_from_file(filename: str, content: bytes, group_name: str = "", tags: List[str] | None = None) -> List[dict]:
    if len(content) > settings.max_import_file_bytes:
        raise ValueError(f"{filename} is larger than the {settings.max_import_file_bytes // (1024 * 1024)} MB upload limit.")

    suffix = Path(filename).suffix.lower().removeprefix(".")
    base_tags = normalize_tags(tags or [])
    source = f"upload:{suffix or 'file'}"

    if suffix in TEXT_EXTENSIONS:
        text = content.decode("utf-8", errors="ignore")
        normalized = _normalize_document(
            {"title": _title_from_filename(filename), "content": text, "tags": base_tags},
            _title_from_filename(filename),
            source,
            group_name,
        )
        return [normalized] if normalized else []

    if suffix == "json":
        return _parse_json_documents(content.decode("utf-8", errors="ignore"), filename, source, group_name, base_tags)

    if suffix == "csv":
        return _parse_csv_documents(content.decode("utf-8", errors="ignore"), filename, source, group_name, base_tags)

    if suffix == "pdf":
        text = _extract_pdf_text(content)
        normalized = _normalize_document(
            {"title": _title_from_filename(filename), "content": text, "tags": base_tags},
            _title_from_filename(filename),
            source,
            group_name,
        )
        return [normalized] if normalized else []

    if suffix == "docx":
        text = _extract_docx_text(content)
        normalized = _normalize_document(
            {"title": _title_from_filename(filename), "content": text, "tags": base_tags},
            _title_from_filename(filename),
            source,
            group_name,
        )
        return [normalized] if normalized else []

    if suffix in IMAGE_EXTENSIONS:
        text = _ocr_image_bytes(content, suffix)
        normalized = _normalize_document(
            {"title": _title_from_filename(filename), "content": text, "tags": base_tags},
            _title_from_filename(filename),
            f"upload:{suffix}-ocr",
            group_name,
        )
        return [normalized] if normalized else []

    raise ValueError(f"{filename} is not a supported import format.")


def _html_to_text(html: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "form"]):
        tag.decompose()
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        heading = soup.find(["h1", "h2"])
        if heading:
            title = heading.get_text(" ", strip=True)

    pieces: List[str] = []
    for node in soup.find_all(["p", "li", "h2", "h3", "blockquote"]):
        text = node.get_text(" ", strip=True)
        if text and len(text) > 20:
            pieces.append(text)
    if not pieces:
        fallback_text = soup.get_text(" ", strip=True)
        pieces = [fallback_text]
    return title or "Imported page", _truncate_content("\n\n".join(pieces))


def _content_disposition_filename(header_value: str) -> str | None:
    match = re.search(r'filename="?([^";]+)"?', header_value or "", flags=re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None


def _is_trusted_import_host(hostname: str) -> bool:
    return (
        hostname in TRUSTED_IMPORT_HOSTS
        or hostname.endswith(".notion.so")
        or hostname.endswith(".notion.site")
        or hostname in {"notion.so", "notion.site"}
    )


def _is_blocked_ip(value: str) -> bool:
    try:
        address = ipaddress.ip_address(value)
    except ValueError:
        return False
    return any(
        (
            address.is_private,
            address.is_loopback,
            address.is_link_local,
            address.is_multicast,
            address.is_reserved,
            address.is_unspecified,
        )
    )


def _validate_import_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Only http and https URLs can be imported.")
    if not parsed.hostname:
        raise ValueError("A valid import host is required.")
    if parsed.username or parsed.password:
        raise ValueError("URLs with embedded credentials cannot be imported.")
    if parsed.port and parsed.port not in {80, 443}:
        raise ValueError("Only standard web ports 80 and 443 can be imported.")

    hostname = parsed.hostname.rstrip(".").lower()
    if hostname in {"localhost"} or hostname.endswith(".localhost") or _is_blocked_ip(hostname):
        raise ValueError("Internal and localhost URLs cannot be imported.")
    if _is_trusted_import_host(hostname):
        return

    try:
        resolved = socket.getaddrinfo(hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("The import host could not be validated.") from exc
    for item in resolved:
        resolved_ip = item[4][0]
        if _is_blocked_ip(resolved_ip):
            raise ValueError("Internal and private network URLs cannot be imported.")


def _validate_response_metadata(response: httpx.Response, filename: str) -> None:
    content_length = response.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > settings.max_import_file_bytes:
        raise ValueError(f"The remote file is larger than the {settings.max_import_file_bytes // (1024 * 1024)} MB import limit.")
    if len(response.content) > settings.max_import_file_bytes:
        raise ValueError(f"The remote file is larger than the {settings.max_import_file_bytes // (1024 * 1024)} MB import limit.")

    content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type and not any(content_type == allowed or content_type.startswith(allowed) for allowed in ALLOWED_IMPORT_CONTENT_TYPES):
        suffix = Path(filename).suffix.lower()
        if suffix not in {".html", ".htm", ".txt", ".csv", ".json", ".pdf", ".docx", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}:
            raise ValueError("The remote content type is not supported for import.")


async def _safe_get(client: httpx.AsyncClient, url: str) -> httpx.Response:
    current_url = url
    headers = {"user-agent": "HajiHazAI/1.0 (+https://hajihazai.allbeesolutions.com)"}
    for _ in range(MAX_IMPORT_REDIRECTS + 1):
        _validate_import_url(current_url)
        response = await client.get(current_url, headers=headers)
        status_code = int(getattr(response, "status_code", 200))
        if status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("location", "")
            if not location:
                raise ValueError("The import URL redirected without a target location.")
            current_url = urljoin(current_url, location)
            continue
        return response
    raise ValueError("The import URL redirected too many times.")


def _resolve_import_target(url: str) -> dict:
    normalized_url = normalize_source_url(url)
    if not normalized_url:
        raise ValueError("A valid URL is required.")
    _validate_import_url(normalized_url)

    parsed = urlparse(normalized_url)
    host = parsed.netloc.lower()
    query = parse_qs(parsed.query)
    path = parsed.path

    google_doc = re.search(r"/document/(?:u/\d+/)?d/([a-zA-Z0-9_-]+)", path)
    if host == "docs.google.com" and google_doc:
        doc_id = google_doc.group(1)
        return {
            "source": "google-docs",
            "fetch_url": f"https://docs.google.com/document/d/{doc_id}/export?format=txt",
            "mode": "file",
            "filename": f"{doc_id}.txt",
            "normalized_url": normalized_url,
        }

    google_sheet = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", path)
    if host == "docs.google.com" and google_sheet:
        sheet_id = google_sheet.group(1)
        gid = query.get("gid", ["0"])[0]
        return {
            "source": "google-sheets",
            "fetch_url": f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}",
            "mode": "file",
            "filename": f"{sheet_id}.csv",
            "normalized_url": normalized_url,
        }

    drive_file = re.search(r"/file/d/([a-zA-Z0-9_-]+)", path)
    if host == "drive.google.com" and drive_file:
        file_id = drive_file.group(1)
        return {
            "source": "google-drive",
            "fetch_url": f"https://drive.google.com/uc?export=download&id={file_id}",
            "mode": "auto",
            "filename": f"{file_id}.bin",
            "normalized_url": normalized_url,
        }

    if host.endswith("notion.so") or host.endswith("notion.site"):
        return {
            "source": "notion",
            "fetch_url": normalized_url,
            "mode": "html",
            "filename": "notion.html",
            "normalized_url": normalized_url,
        }

    return {
        "source": "url",
        "fetch_url": normalized_url,
        "mode": "html",
        "filename": Path(parsed.path or "/index.html").name or "page.html",
        "normalized_url": normalized_url,
    }


def _looks_like_download(content_type: str, filename: str) -> bool:
    lowered = (content_type or "").lower()
    suffix = Path(filename).suffix.lower()
    return any(
        marker in lowered
        for marker in (
            "application/pdf",
            "application/json",
            "text/plain",
            "text/csv",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/octet-stream",
            "image/",
        )
    ) or suffix in {".pdf", ".json", ".txt", ".csv", ".docx", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}


async def import_documents_from_url(url: str, group_name: str = "", tags: List[str] | None = None) -> List[dict]:
    target = _resolve_import_target(url)
    normalized_url = target["normalized_url"]
    default_tags = normalize_tags(tags or [])

    async with httpx.AsyncClient(timeout=settings.online_search_timeout_seconds, follow_redirects=False) as client:
        response = await _safe_get(client, target["fetch_url"])
        response.raise_for_status()

    filename = _content_disposition_filename(response.headers.get("content-disposition", "")) or target["filename"]
    content_type = response.headers.get("content-type", "")
    _validate_response_metadata(response, filename)

    if target["mode"] == "file" or _looks_like_download(content_type, filename):
        documents = import_documents_from_file(filename, response.content, group_name, default_tags)
        for document in documents:
            document["source"] = target["source"]
            document["source_url"] = normalized_url
            document["group_name"] = normalize_group_name(group_name or document.get("group_name"))
            document["tags"] = normalize_tags(document.get("tags", []) + default_tags)
        if documents:
            return documents

    title, text = _html_to_text(response.text)
    normalized = _normalize_document(
        {"title": title, "content": text, "tags": default_tags},
        title,
        target["source"],
        group_name,
        normalized_url,
    )
    if not normalized:
        raise ValueError("The requested page did not contain enough readable text to import.")
    return [normalized]


async def import_document_from_url(url: str, group_name: str = "", tags: List[str] | None = None) -> dict:
    documents = await import_documents_from_url(url, group_name, tags)
    if not documents:
        raise ValueError("The requested URL did not produce any importable documents.")
    return documents[0]

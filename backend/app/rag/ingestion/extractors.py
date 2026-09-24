"""Multi-format document extractors for Markdown, Plain Text, and PDF files."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import io
import os
import re
from typing import Any, Dict, List, Optional, Union


@dataclass
class ExtractedSection:
    """Logical section of a document extracted during preprocessing."""

    title: str
    content: str
    page_number: Optional[int] = None


@dataclass
class ExtractedDocument:
    """Parsed document containing raw content, structured sections, and metadata."""

    title: str
    raw_content: str
    file_format: str
    sections: List[ExtractedSection] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseExtractor(ABC):
    """Abstract base class for format-specific document extractors."""

    @abstractmethod
    def extract(
        self,
        content_or_path: Union[str, bytes],
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExtractedDocument:
        pass


class MarkdownExtractor(BaseExtractor):
    """Extracts structural sections, headings, and code snippets from Markdown."""

    HEADER_REGEX = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

    def extract(
        self,
        content_or_path: Union[str, bytes],
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExtractedDocument:
        meta = metadata.copy() if metadata else {}
        if isinstance(content_or_path, bytes):
            text = content_or_path.decode("utf-8", errors="replace")
        elif os.path.exists(content_or_path) and os.path.isfile(content_or_path):
            with open(content_or_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            if not filename:
                filename = os.path.basename(content_or_path)
        else:
            text = str(content_or_path)

        # Infer title from first H1 or filename
        title = meta.get("title")
        lines = text.splitlines()
        for line in lines:
            h1_match = re.match(r"^#\s+(.+)$", line.strip())
            if h1_match and not title:
                title = h1_match.group(1).strip()
                break

        if not title:
            title = filename or "Untitled Document"

        # Split into sections based on headers
        sections: List[ExtractedSection] = []
        matches = list(self.HEADER_REGEX.finditer(text))

        if not matches:
            sections.append(ExtractedSection(title="Overview", content=text.strip()))
        else:
            # Preamble before first header
            first_start = matches[0].start()
            if first_start > 0:
                preamble = text[:first_start].strip()
                if preamble:
                    sections.append(ExtractedSection(title="Introduction", content=preamble))

            for i, match in enumerate(matches):
                sec_title = match.group(2).strip()
                sec_start = match.end()
                sec_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                sec_content = text[sec_start:sec_end].strip()
                if sec_content:
                    sections.append(ExtractedSection(title=sec_title, content=sec_content))

        return ExtractedDocument(
            title=title,
            raw_content=text,
            file_format="markdown",
            sections=sections,
            metadata=meta,
        )


class PlainTextExtractor(BaseExtractor):
    """Extracts sections from plain text files using paragraph and numbered blocks."""

    def extract(
        self,
        content_or_path: Union[str, bytes],
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExtractedDocument:
        meta = metadata.copy() if metadata else {}
        if isinstance(content_or_path, bytes):
            text = content_or_path.decode("utf-8", errors="replace")
        elif os.path.exists(content_or_path) and os.path.isfile(content_or_path):
            with open(content_or_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
            if not filename:
                filename = os.path.basename(content_or_path)
        else:
            text = str(content_or_path)

        title = meta.get("title") or filename or "Plain Text Document"

        # Break text into paragraphs
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        sections: List[ExtractedSection] = []

        curr_title = "General"
        curr_buf: List[str] = []

        for p in paragraphs:
            # Check if paragraph looks like a section header (short line, ends with colon or uppercase)
            if len(p) < 80 and (p.isupper() or p.endswith(":") or re.match(r"^\d+\.\s+", p)):
                if curr_buf:
                    sections.append(ExtractedSection(title=curr_title, content="\n\n".join(curr_buf)))
                    curr_buf = []
                curr_title = p.rstrip(":")
            else:
                curr_buf.append(p)

        if curr_buf:
            sections.append(ExtractedSection(title=curr_title, content="\n\n".join(curr_buf)))

        if not sections:
            sections.append(ExtractedSection(title="Body", content=text.strip()))

        return ExtractedDocument(
            title=title,
            raw_content=text,
            file_format="txt",
            sections=sections,
            metadata=meta,
        )


class PDFExtractor(BaseExtractor):
    """Extracts text page-by-page from PDF files using pypdf."""

    def extract(
        self,
        content_or_path: Union[str, bytes],
        filename: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ExtractedDocument:
        meta = metadata.copy() if metadata else {}
        import pypdf

        if isinstance(content_or_path, bytes):
            stream = io.BytesIO(content_or_path)
            reader = pypdf.PdfReader(stream)
        elif os.path.exists(content_or_path) and os.path.isfile(content_or_path):
            reader = pypdf.PdfReader(content_or_path)
            if not filename:
                filename = os.path.basename(content_or_path)
        else:
            raise ValueError("PDF extractor requires valid file path or bytes")

        title = meta.get("title") or (reader.metadata.title if reader.metadata else None) or filename or "PDF Document"
        full_text_parts: List[str] = []
        sections: List[ExtractedSection] = []

        for page_idx, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                full_text_parts.append(page_text.strip())
                sections.append(
                    ExtractedSection(
                        title=f"Page {page_idx}",
                        content=page_text.strip(),
                        page_number=page_idx,
                    )
                )

        raw_text = "\n\n--- PAGE BREAK ---\n\n".join(full_text_parts)
        return ExtractedDocument(
            title=title,
            raw_content=raw_text,
            file_format="pdf",
            sections=sections,
            metadata=meta,
        )


def get_extractor_for_file(filename_or_path: str) -> BaseExtractor:
    """Factory returning the appropriate extractor based on file extension."""
    ext = os.path.splitext(filename_or_path)[1].lower()
    if ext in (".md", ".markdown"):
        return MarkdownExtractor()
    elif ext == ".pdf":
        return PDFExtractor()
    elif ext in (".txt", ".text", ".log", ""):
        return PlainTextExtractor()
    else:
        raise ValueError(f"Unsupported file format: {ext}")

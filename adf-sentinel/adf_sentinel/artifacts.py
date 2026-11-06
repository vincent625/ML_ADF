from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import stat
import subprocess
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from .common import ROOT, digest, file_hash, now, scrub, stable, write_json, write_jsonl

TEXT = {".txt", ".log", ".ini", ".cfg", ".conf", ".json", ".xml", ".csv", ".tsv", ".bed", ".vcf", ".properties", ".yaml", ".yml", ".md", ".py", ".sh", ".r", ".R", ".sql"}
LIMITS = {"members": 10000, "expanded_bytes": 512 * 1024 * 1024,
          "member_bytes": 32 * 1024 * 1024, "depth": 3, "compression_ratio": 1000}


def safe_member(name, mode=0):
    p = PurePosixPath(name.replace("\\", "/"))
    if p.is_absolute() or ".." in p.parts or (p.parts and ":" in p.parts[0]) or stat.S_ISLNK(mode):
        raise ValueError("Unsafe archive path or symbolic link")
    return str(p)


def archive_records(data, prefix="", depth=0, budget=None):
    budget = budget if budget is not None else {"bytes": 0, "members": 0}
    if depth > LIMITS["depth"]:
        return [{"path": prefix, "state": "partial", "reason": "nested archive depth limit"}]
    rows = []
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            budget["members"] += 1
            path = prefix + entry.filename
            try:
                safe_member(entry.filename, entry.external_attr >> 16)
                if budget["members"] > LIMITS["members"]:
                    raise ValueError("archive member-count limit")
                if entry.file_size / max(1, entry.compress_size) > LIMITS["compression_ratio"]:
                    raise ValueError("archive compression-ratio limit")
                if budget["bytes"] + entry.file_size > LIMITS["expanded_bytes"]:
                    raise ValueError("archive expanded-byte limit")
                if entry.is_dir():
                    continue
                suffix = Path(entry.filename).suffix.lower()
                if entry.file_size > LIMITS["member_bytes"]:
                    h, md5, actual = hashlib.sha256(), hashlib.md5(usedforsecurity=False), 0
                    with archive.open(entry) as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            actual += len(chunk)
                            if budget["bytes"] + actual > LIMITS["expanded_bytes"]:
                                raise ValueError("archive expanded-byte limit")
                            h.update(chunk)
                            md5.update(chunk)
                    budget["bytes"] += actual
                    rows.append({"path": path, "bytes": actual, "sha256": h.hexdigest(), "md5": md5.hexdigest(),
                                 "state": "partial" if suffix in TEXT or suffix in {".zip", ".xlsx", ".docx"} else "collected",
                                 "method": "streaming_hash_no_deserialization_or_execution",
                                 "extraction_state": "unsupported_opaque_binary" if suffix == ".ser" else "not_extracted_above_member_memory_limit"})
                    continue
                content = archive.read(entry)
                budget["bytes"] += len(content)
                row = {"path": path, "bytes": len(content), "sha256": digest(content), "md5": hashlib.md5(content, usedforsecurity=False).hexdigest(), "state": "collected",
                       "method": "zipfile_read_no_execution", "archive_timestamp": list(entry.date_time)}
                if suffix in TEXT:
                    row["text"] = scrub(content.decode("utf-8", "replace"))
                elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
                    row["extraction_state"] = "image_bytes_hashed_ocr_not_performed"
                elif suffix in {".ser", ".deb", ".h5"}:
                    row["extraction_state"] = "binary_bytes_hashed_no_deserialization_or_execution"
                rows.append(row)
                if suffix in {".zip", ".docx", ".xlsx"}:
                    rows.extend(archive_records(content, path + "!", depth + 1, budget))
            except (ValueError, RuntimeError, zipfile.BadZipFile, NotImplementedError) as exc:
                rows.append({"path": path, "state": "partial", "reason": str(exc)})
    return rows


def extract_one(path):
    path = Path(path).resolve()
    row = {"id": stable("artifact", str(path), file_hash(path)), "path": str(path), "sha256": file_hash(path),
           "bytes": path.stat().st_size, "extracted_at": now(), "state": "collected", "executed": False}
    suffix = path.suffix.lower()
    if suffix in TEXT:
        row.update(method="utf8_text", text=scrub(path.read_text(errors="replace")))
    elif suffix in {".zip", ".docx", ".xlsx"}:
        row["method"] = "safe_zip_inventory"
        row["members"] = archive_records(path.read_bytes())
        row["state"] = "partial" if any(m["state"] != "collected" for m in row["members"]) else "collected"
        names = [m["path"].lower() for m in row["members"]]
        row["artifact_type"] = "archive_unclassified"
        if any(n.endswith(".ser") for n in names):
            row["artifact_type"] = "historical_adf_archive_with_serialized_core"
            row["build_limitation"] = "Serialized core is hashed, never deserialized or rewritten; approved ADF builder is unavailable"
        elif all(n.endswith(".json") for n in names) and any("analysisargs" in n for n in names):
            row["artifact_type"] = "parameter_export_archive_not_adf"
        elif any("seeddata/" in n or "analysisargs" in n or "assaydev/" in n for n in names):
            row["artifact_type"] = "adf_source_or_bundle_archive_requires_build_verification"
        elif any(n.endswith(".html") for n in names) and any(n.endswith(".js") for n in names):
            row["artifact_type"] = "browser_resource_archive_not_adf"
        if suffix == ".docx":
            from .common import plain
            row["text"] = "\n".join(plain(m["text"]) for m in row["members"] if m["path"].endswith("document.xml") and "text" in m)
        if suffix == ".xlsx":
            try:
                import openpyxl
                book = openpyxl.load_workbook(path, read_only=True, data_only=False, keep_links=False)
                lines = []
                for sheet in book:
                    for i, values in enumerate(sheet.iter_rows(values_only=True)):
                        if i >= 10000:
                            row.update(state="partial", reason="10,000 spreadsheet rows per sheet extraction limit")
                            break
                        lines.append(sheet.title + ": " + " | ".join(scrub(v) for v in values if v is not None))
                book.close()
                row["text"] = "\n".join(lines)
                row["method"] = "openpyxl_readonly_formulas_not_executed"
            except ImportError:
                row.update(state="partial", reason="openpyxl unavailable; XML inventory retained")
    elif suffix == ".pdf" and shutil.which("pdftotext"):
        result = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, timeout=45)
        row.update(method="pdftotext", text=scrub(result.stdout.decode(errors="replace")))
        if result.returncode:
            row.update(state="partial", reason="PDF text extraction failed; original retained")
    elif suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff"}:
        row["method"] = "image_metadata"
        try:
            from PIL import Image
            with Image.open(path) as im:
                row["dimensions"] = list(im.size)
        except ImportError:
            pass
        if shutil.which("tesseract"):
            result = subprocess.run(["tesseract", str(path), "stdout"], capture_output=True, timeout=45)
            row.update(method="tesseract_ocr", text=scrub(result.stdout.decode(errors="replace")), ocr_uncertain=True)
        else:
            row.update(state="unsupported", reason="OCR engine unavailable; image bytes retained, values require visual review")
    else:
        row.update(method="hash_only", state="unsupported", reason="No approved extractor; original bytes retained")
    return row


def extract_downloads(root=ROOT):
    rows = []
    for path in sorted((Path(root) / "data/raw/attachments").glob("*/*")):
        if path.is_file() and not path.name.endswith(".part"):
            try:
                rows.append(extract_one(path))
            except Exception as exc:
                rows.append({"path": str(path), "state": "partial", "reason": str(exc), "sha256": file_hash(path)})
    write_jsonl(Path(root) / "data/extracted/downloaded_artifacts.jsonl", rows)
    return {"files": len(rows), "collected": sum(r["state"] == "collected" for r in rows), "limits": LIMITS}

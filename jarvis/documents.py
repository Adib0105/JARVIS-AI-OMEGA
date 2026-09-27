from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

from .local_files import LocalFiles


DOCUMENT_EXTENSIONS = {'.pdf', '.docx', '.xlsx', '.xlsm', '.csv', '.txt', '.md'}


class DocumentReader:
    def __init__(self, files: LocalFiles | None = None):
        self.files = files or LocalFiles()

    def extract(self, file_path: str, max_chars: int = 120000) -> dict:
        from .safe_files import read_bounded
        path, stat, raw = read_bounded(self.files, file_path, DOCUMENT_EXTENSIONS)
        cap = max(2000, min(int(max_chars), 250000))
        suffix = path.suffix.lower()
        content_sha256 = hashlib.sha256(raw).hexdigest()
        if suffix in {'.docx', '.xlsx', '.xlsm'}:
            _validate_archive(raw)
        if suffix in {'.pdf', '.docx', '.xlsx', '.xlsm'}:
            text, meta = _bounded_parse(raw, suffix, cap)
        elif suffix == '.csv':
            text, meta = self._csv(io.StringIO(raw.decode('utf-8-sig', errors='replace')), cap)
        else:
            if b'\0' in raw:
                raise ValueError('Binary content is not a text file.')
            text = raw.decode('utf-8', errors='replace')[:cap]
            meta = {'type': suffix.lstrip('.'), 'characters': len(text)}

        extracted = text[:cap]
        extracted_sha256 = hashlib.sha256(extracted.encode('utf-8', errors='replace')).hexdigest()
        meta = dict(meta)
        meta.update({
            'content_sha256': content_sha256,
            'extracted_sha256': extracted_sha256,
            'mtime_ns': int(stat.st_mtime_ns),
        })
        return {
            'path': str(path),
            'name': path.name,
            'size_bytes': stat.st_size,
            'mtime_ns': int(stat.st_mtime_ns),
            'content_sha256': content_sha256,
            'extracted_sha256': extracted_sha256,
            'metadata': meta,
            'text': extracted,
        }

    @staticmethod
    def _pdf(path: Path, cap: int) -> tuple[str, dict]:
        from pypdf import PdfReader

        reader = PdfReader(path)
        parts: list[str] = []
        total = 0
        for idx, page in enumerate(reader.pages):
            chunk = page.extract_text() or ''
            header = f'\n--- PAGE {idx + 1} ---\n'
            parts.append(header + chunk)
            total += len(header) + len(chunk)
            if total >= cap:
                break
        text = ''.join(parts)[:cap]
        return text, {'type': 'pdf', 'pages': len(reader.pages), 'characters': len(text)}

    @staticmethod
    def _docx(path: Path, cap: int) -> tuple[str, dict]:
        from docx import Document

        doc = Document(path)
        parts: list[str] = []
        for p in doc.paragraphs:
            if p.text.strip():
                parts.append(p.text)
            if sum(map(len, parts)) >= cap:
                break
        text = '\n'.join(parts)[:cap]
        return text, {'type': 'docx', 'paragraphs': len(doc.paragraphs), 'characters': len(text)}

    @staticmethod
    def _xlsx(path: Path, cap: int) -> tuple[str, dict]:
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        try:
            out = io.StringIO()
            row_count = 0
            for ws in wb.worksheets[:20]:
                out.write(f'\n--- SHEET: {ws.title} ---\n')
                for row in ws.iter_rows(values_only=True):
                    values = [str(v) if v is not None else '' for v in row]
                    out.write('\t'.join(values).rstrip() + '\n')
                    row_count += 1
                    if out.tell() >= cap or row_count >= 10000:
                        break
                if out.tell() >= cap or row_count >= 10000:
                    break
            text = out.getvalue()[:cap]
            return text, {'type': 'xlsx', 'sheets': len(wb.sheetnames), 'rows_read': row_count, 'characters': len(text)}
        finally:
            wb.close()

    @staticmethod
    def _csv(path: Path, cap: int) -> tuple[str, dict]:
        out = io.StringIO()
        rows = 0
        with path as handle:
            reader = csv.reader(handle)
            for row in reader:
                out.write('\t'.join(row) + '\n')
                rows += 1
                if out.tell() >= cap or rows >= 20000:
                    break
        text = out.getvalue()[:cap]
        return text, {'type': 'csv', 'rows_read': rows, 'characters': len(text)}


def _validate_archive(raw):
    import zipfile
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) > 1000 or sum(i.file_size for i in entries) > 16_000_000:
            raise ValueError('Document archive exceeds expanded size/entry budget.')
        for item in entries:
            if item.flag_bits & 1 or item.file_size > 8_000_000 or item.file_size > max(1, item.compress_size) * 200:
                raise ValueError('Encrypted or excessively compressed document is blocked.')


def _parse_worker(connection, raw, suffix, cap):
    # This is a trusted, fixed document parser, NOT a generated-code sandbox.
    try:
        import logging
        logging.getLogger('pypdf').disabled = True
        if __import__('os').name != 'nt':
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (768 * 1024**2, 768 * 1024**2))
        parser = {'.pdf': DocumentReader._pdf, '.docx': DocumentReader._docx,
                  '.xlsx': DocumentReader._xlsx, '.xlsm': DocumentReader._xlsx}[suffix]
        connection.send(('ok', parser(io.BytesIO(raw), cap)))
    except Exception as exc:
        try:
            connection.send(('error', type(exc).__name__ + ': document could not be parsed within limits.'))
        except (BrokenPipeError, EOFError, OSError):
            pass  # deadline/cancellation already closed the parent connection
    finally:
        connection.close()


def _bounded_parse(raw, suffix, cap, timeout=15.0):
    import multiprocessing
    import time
    import psutil
    context = multiprocessing.get_context('spawn')
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=_parse_worker, args=(child, raw, suffix, cap), daemon=True)
    try:
        process.start()
        child.close()
        deadline = time.monotonic() + timeout
        while not parent.poll(0.05):
            if time.monotonic() >= deadline:
                raise TimeoutError('Document parser exceeded its 15-second budget.')
            if not process.is_alive():
                raise ValueError('Document parser stopped before returning a result.')
            try:
                if psutil.Process(process.pid).memory_info().rss > 512 * 1024**2:
                    raise ValueError('Document parser exceeded its memory budget.')
            except psutil.NoSuchProcess:
                pass
        status, result = parent.recv()
        if status != 'ok':
            raise ValueError(result)
        return result
    finally:
        parent.close()
        child.close()
        if process.pid is not None:
            process.join(timeout=0.1)
            if process.is_alive():
                process.kill()
                process.join(timeout=1)
            process.close()

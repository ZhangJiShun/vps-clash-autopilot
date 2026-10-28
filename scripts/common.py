"""Local-only safety primitives. No credentials are included in exceptions."""
from __future__ import annotations

SCRIPT_INTERFACE = "internal-module"
SCRIPT_INTERFACE_REASON = "Imported by the explicit autopilot CLI; not a standalone command."

import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile


class SafeError(Exception):
    pass


def explicit_path(value: str | Path, *, existing: bool = False) -> Path:
    path = Path(value).expanduser().absolute()
    if any(part == '.env' or part.startswith('.env.') for part in path.parts):
        raise SafeError('Refusing credential .env paths.')
    if path.is_symlink():
        raise SafeError('Refusing a symlink target; select the real file explicitly.')
    resolved = path.resolve()
    if any(part == '.env' or part.startswith('.env.') for part in resolved.parts):
        raise SafeError('Refusing credential .env paths.')
    if existing and not resolved.is_file():
        raise SafeError('Expected an existing regular file.')
    return resolved


def read_bytes(value: str | Path) -> bytes:
    return explicit_path(value, existing=True).read_bytes()


def read_json(value: str | Path):
    try:
        return json.loads(read_bytes(value))
    except (ValueError, UnicodeError):
        raise SafeError('Invalid JSON input; details withheld to protect credentials.') from None


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def new_private_dir(value: str | Path) -> Path:
    path = explicit_path(value)
    # Do not silently adopt a shared directory or overwrite another run.
    try:
        path.mkdir(mode=0o700, parents=False, exist_ok=False)
    except FileExistsError:
        raise SafeError('Output directory already exists; use a new run directory.') from None
    return path


def private_file(path: Path, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    flags |= getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, 'wb') as out:
        out.write(data)
        out.flush()
        os.fsync(out.fileno())


def private_json(path: Path, data: dict | list) -> None:
    private_file(path, (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode())


def atomic_replace(path: Path, data: bytes, expected_hash: str) -> None:
    path = explicit_path(path, existing=True)
    if digest(path.read_bytes()) != expected_hash:
        raise SafeError('File changed since planning; preserving current work. Prepare again.')
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, tmp = tempfile.mkstemp(prefix='.autopilot-', dir=path.parent)
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, 'wb') as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        # The Agent must hold the single-writer lock while applying.
        if path.is_symlink() or digest(path.read_bytes()) != expected_hash:
            raise SafeError('File changed during apply; preserving current work.')
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)  # Only our own unpublished temporary file.

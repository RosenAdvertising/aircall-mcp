"""Fail-closed atomic secret storage (stdlib only)."""

import os
import secrets
import stat
from pathlib import Path


def atomic_private_write(path: Path, content: str) -> None:
    """Establish private permissions before writing any secret bytes."""
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.parent.chmod(0o700)
    if stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
        raise OSError("Private credential directory permissions are required.")
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(16))
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(fd, 0o600)
        if stat.S_IMODE(os.fstat(fd).st_mode) != 0o600:
            raise OSError("Private credential file permissions are required.")
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            fd = -1
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if fd != -1:
            os.close(fd)
        temporary.unlink(missing_ok=True)

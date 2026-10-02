"""Atomic secret writes: POSIX mode 0600, Windows inherited profile ACLs."""

import os
import secrets
import stat
from pathlib import Path


def atomic_private_write(path: Path, content: str) -> None:
    """Establish private permissions before writing any secret bytes."""
    path = Path(path)
    if os.name == "nt" and not path.resolve().is_relative_to(Path.home().resolve()):
        raise PermissionError(
            "Windows secret files must be stored in the user profile."
        )
    path.parent.mkdir(
        mode=0o777 if os.name == "nt" else 0o700, parents=True, exist_ok=True
    )
    if os.name != "nt":
        path.parent.chmod(0o700)
        if stat.S_IMODE(path.parent.stat().st_mode) != 0o700:
            raise OSError("Private credential directory permissions are required.")
    temporary = path.with_name("." + path.name + "." + secrets.token_hex(16))
    fd = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o666 if os.name == "nt" else 0o600,
    )
    try:
        if os.name != "nt":
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

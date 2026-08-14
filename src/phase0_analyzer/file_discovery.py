"""Read-only discovery of files placed in the shared upload directory."""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


SUPPORTED_EXTENSIONS = frozenset({"xlsx", "csv", "pdf", "png", "jpg", "jpeg"})
HASH_CHUNK_SIZE = 1024 * 1024


class FileDiscoveryError(RuntimeError):
    """Raised when the upload directory cannot be scanned safely."""


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    """Metadata used to identify one immutable version of a file."""

    source_path: str
    file_name: str
    extension: str
    size_bytes: int
    modified_at: str
    sha256: str
    status: str


def calculate_sha256(path: Path) -> str:
    """Calculate a file SHA-256 without loading the whole file into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()


def discover_files(upload_dir: Path) -> list[DiscoveredFile]:
    """Scan only direct, non-hidden files in the shared upload directory."""
    try:
        upload_dir.mkdir(parents=True, exist_ok=True)
        paths = sorted(
            (
                path
                for path in upload_dir.iterdir()
                if path.is_file() and not path.name.startswith(".")
            ),
            key=lambda path: path.name.casefold(),
        )
    except OSError as error:
        raise FileDiscoveryError(
            f"アップロードフォルダを確認できませんでした: {upload_dir}"
        ) from error

    discovered: list[DiscoveredFile] = []
    for path in paths:
        try:
            file_stat = path.stat()
            extension = path.suffix.lower().removeprefix(".")
            discovered.append(
                DiscoveredFile(
                    source_path=str(path.resolve()),
                    file_name=path.name,
                    extension=extension,
                    size_bytes=file_stat.st_size,
                    modified_at=datetime.fromtimestamp(
                        file_stat.st_mtime, tz=UTC
                    ).isoformat(),
                    sha256=calculate_sha256(path),
                    status="READY" if extension in SUPPORTED_EXTENSIONS else "UNSUPPORTED",
                )
            )
        except OSError as error:
            raise FileDiscoveryError(
                f"ファイル情報を取得できませんでした: {path.name}"
            ) from error

    return discovered

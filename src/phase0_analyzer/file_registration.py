"""Manual file-list refresh orchestration."""

from dataclasses import dataclass
from pathlib import Path

from phase0_analyzer.file_discovery import discover_files
from phase0_analyzer.file_repository import FileRepository
from phase0_analyzer.snapshot import SnapshotService


@dataclass(frozen=True, slots=True)
class RegistrationSummary:
    """Result counts shown after a manual refresh."""

    detected_count: int
    registered_count: int
    duplicate_count: int


def register_discovered_files(
    upload_dir: Path, repository: FileRepository, snapshot_service: SnapshotService
) -> RegistrationSummary:
    """Discover and register files only when explicitly called by the UI."""
    discovered = discover_files(upload_dir)
    registered_count = sum(
        snapshot_service.register(file, repository) for file in discovered
    )
    return RegistrationSummary(
        detected_count=len(discovered),
        registered_count=registered_count,
        duplicate_count=len(discovered) - registered_count,
    )

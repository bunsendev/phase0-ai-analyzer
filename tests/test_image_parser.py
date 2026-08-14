from pathlib import Path

import pytest
from PIL import Image

from phase0_analyzer.parsers.image import ImageParser


@pytest.mark.parametrize(
    ("suffix", "image_format"), [("png", "PNG"), ("jpg", "JPEG"), ("jpeg", "JPEG")]
)
def test_image_parser_reads_dimensions_and_requires_ocr(
    tmp_path: Path, suffix: str, image_format: str
) -> None:
    path = tmp_path / f"document.{suffix}"
    Image.new("RGB", (800, 600), "white").save(path, format=image_format)

    result = ImageParser().parse(1, path.name, path)

    assert result.success
    assert result.metadata["width"] == 800
    assert result.metadata["height"] == 600
    assert result.metadata["image_format"] == image_format
    assert result.metadata["file_size"] == path.stat().st_size
    assert result.requires_ocr is True


def test_low_resolution_image_has_warnings(tmp_path: Path) -> None:
    path = tmp_path / "small.png"
    Image.new("RGB", (400, 300), "white").save(path)

    result = ImageParser().parse(2, path.name, path)

    assert result.success
    assert {warning.code for warning in result.warnings} == {
        "IMAGE_WIDTH_LOW",
        "IMAGE_HEIGHT_LOW",
    }


def test_broken_image_returns_failure_result(tmp_path: Path) -> None:
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"not an image")

    result = ImageParser().parse(3, path.name, path)

    assert not result.success
    assert result.error_code == "IMAGE_READ_FAILED"
    assert result.error_message
    assert [warning.code for warning in result.warnings] == ["IMAGE_OPEN_FAILED"]

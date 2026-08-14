"""Image metadata parser without OCR execution."""

from pathlib import Path

from PIL import Image, UnidentifiedImageError

from phase0_analyzer.parsers.base import BaseParser
from phase0_analyzer.parsers.models import ParseResult, ParseWarning


MIN_IMAGE_DIMENSION = 500


class ImageParser(BaseParser):
    """Read image dimensions and flag files requiring OCR."""

    parser_name = "image"
    supported_extensions = frozenset({"png", "jpg", "jpeg"})

    def _parse(self, file_id: int, file_name: str, path: Path) -> ParseResult:
        try:
            with Image.open(path) as image:
                image.load()
                width, height = image.size
                image_format = image.format or path.suffix.removeprefix(".").upper()
        except (UnidentifiedImageError, OSError, ValueError):
            message = "画像ファイルを正常に開けませんでした。"
            return ParseResult(
                file_id=file_id,
                file_name=file_name,
                file_type=path.suffix.lower().removeprefix("."),
                parser_name=self.parser_name,
                success=False,
                warnings=[ParseWarning(code="IMAGE_OPEN_FAILED", message=message)],
                error_code="IMAGE_READ_FAILED",
                error_message=message,
            )

        warnings: list[ParseWarning] = []
        if width < MIN_IMAGE_DIMENSION:
            warnings.append(
                ParseWarning(
                    code="IMAGE_WIDTH_LOW",
                    message=f"画像の幅が{MIN_IMAGE_DIMENSION}px未満です。",
                )
            )
        if height < MIN_IMAGE_DIMENSION:
            warnings.append(
                ParseWarning(
                    code="IMAGE_HEIGHT_LOW",
                    message=f"画像の高さが{MIN_IMAGE_DIMENSION}px未満です。",
                )
            )

        return ParseResult(
            file_id=file_id,
            file_name=file_name,
            file_type=path.suffix.lower().removeprefix("."),
            parser_name=self.parser_name,
            success=True,
            metadata={
                "width": width,
                "height": height,
                "image_format": image_format,
                "file_size": path.stat().st_size,
            },
            warnings=warnings,
            requires_ocr=True,
        )

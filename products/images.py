"""The gatekeeper for product images.

``prepare_product_image`` is the one path by which a raw file becomes a
stored product image: the back-office image form and the seed command
both call it. It decides whether a file is usable — rejecting anything
else with a plain-language message that names the file and its real
numbers — and turns a usable file into a web-sized WebP.

Checks run cheapest first, and the first problem found is the one
reported: file size, then "is it an image at all", then the format
Pillow actually detects (never the extension), then pixel dimensions.
"""

import math
from io import BytesIO
from pathlib import PurePath

from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

MEGABYTE = 1024 * 1024
MAX_FILE_MEGABYTES = 5

# Formats every browser displays. MPO is the JPEG variant many phone
# cameras write; browsers show it as an ordinary JPEG.
ACCEPTED_FORMATS = {"PNG", "JPEG", "MPO", "WEBP"}

MIN_SIDE = 600
MAX_SIDE = 8000

# Stored images are shrunk to fit this box: sharp on a high-density
# detail page, a fraction of an original's weight.
DISPLAY_SIDE = 1600


def prepare_product_image(file: File) -> ContentFile:
    """Validate an image file and return it as a web-ready WebP.

    Returns a ``ContentFile`` named ``<original stem>.webp``, resized so its
    longest side is at most ``DISPLAY_SIDE`` pixels (never upscaled), with
    the camera's rotation applied and any transparency kept.

    Raises ``ValidationError`` with a plain-language message — the first
    problem found — when the file cannot be used. Nothing is saved either
    way; storing the result is the caller's job.
    """
    name = PurePath(file.name).name

    if file.size > MAX_FILE_MEGABYTES * MEGABYTE:
        megabytes = math.ceil(file.size / MEGABYTE * 10) / 10
        raise ValidationError(
            f'"{name}" is {megabytes:.1f} MB. The largest image we can accept '
            f"is {MAX_FILE_MEGABYTES} MB. Try exporting a smaller version.",
            code="file_too_big",
        )

    image = _open(file, name)

    if image.format not in ACCEPTED_FORMATS:
        article = "an" if image.format[0] in "AEIOU" else "a"
        raise ValidationError(
            f'"{name}" is {article} {image.format} image. We accept PNG, JPEG, '
            "or WebP. Save it in one of those formats and try again.",
            code="wrong_format",
        )

    width, height = image.size
    if max(width, height) > MAX_SIDE:
        raise ValidationError(
            f'"{name}" is {width} × {height} pixels. Images can be at most '
            f"{MAX_SIDE} pixels on each side.",
            code="too_many_pixels",
        )
    if min(width, height) < MIN_SIDE:
        raise ValidationError(
            f'"{name}" is {width} × {height} pixels. Images need to be at least '
            f"{MIN_SIDE} pixels wide and {MIN_SIDE} pixels tall so they look "
            "sharp in the store.",
            code="too_few_pixels",
        )

    # Only a damaged file reveals itself when its pixels are decoded.
    try:
        image.load()
    except (OSError, SyntaxError, ValueError) as error:
        raise _unopenable(name) from error

    try:
        return _to_webp(image, name)
    except Exception as error:
        raise ValidationError(
            f'We couldn\'t prepare "{name}" for the store. Try saving it again '
            "as a PNG or JPEG and uploading that copy. Your current image "
            "hasn't changed.",
            code="processing_failed",
        ) from error


def _open(file: File, name: str) -> Image.Image:
    """Open ``file`` with Pillow, reading only its header."""
    file.seek(0)
    try:
        return Image.open(file)
    except Image.DecompressionBombError as error:
        # Pillow refuses to read the header of an absurdly large image, so
        # its exact dimensions are unknowable here.
        raise ValidationError(
            f'"{name}" is far too large in pixels. Images can be at most '
            f"{MAX_SIDE} pixels on each side.",
            code="too_many_pixels",
        ) from error
    except (OSError, SyntaxError, ValueError) as error:
        raise _unopenable(name) from error


def _unopenable(name: str) -> ValidationError:
    return ValidationError(
        f'"{name}" isn\'t an image we can open. Upload a PNG, JPEG, or WebP picture.',
        code="not_an_image",
    )


def _to_webp(image: Image.Image, name: str) -> ContentFile:
    """Rotate upright, shrink to fit ``DISPLAY_SIDE``, and encode as WebP."""
    image = ImageOps.exif_transpose(image)
    has_transparency = "A" in image.getbands() or "transparency" in image.info
    image = image.convert("RGBA" if has_transparency else "RGB")
    image.thumbnail((DISPLAY_SIDE, DISPLAY_SIDE), Image.Resampling.LANCZOS)

    buffer = BytesIO()
    image.save(buffer, format="WEBP", quality=85)
    return ContentFile(buffer.getvalue(), name=f"{PurePath(name).stem}.webp")

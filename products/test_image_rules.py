"""The product image gatekeeper, products/images.py.

The second non-negotiable: a file the site cannot use is rejected with a
plain-language explanation. Each rule is tested against its exact
message; usable files come out as web-sized WebP.
"""

from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from .images import MEGABYTE, prepare_product_image


def rejection(file):
    """The single message prepare_product_image rejects ``file`` with."""
    with pytest.raises(ValidationError) as caught:
        prepare_product_image(file)
    [message] = caught.value.messages
    return message


def opened(content_file):
    return Image.open(BytesIO(content_file.read()))


# --- Rejections, cheapest check first --------------------------------------


def test_rejects_file_over_five_megabytes():
    file = SimpleUploadedFile("photo.png", b"x" * int(7.3 * MEGABYTE))
    assert rejection(file) == (
        '"photo.png" is 7.3 MB. The largest image we can accept is 5 MB. '
        "Try exporting a smaller version."
    )


def test_file_of_exactly_five_megabytes_passes_the_size_check():
    file = SimpleUploadedFile("photo.png", b"x" * (5 * MEGABYTE))
    assert "isn't an image we can open" in rejection(file)


def test_rejects_a_file_that_is_not_an_image():
    file = SimpleUploadedFile("report.pdf", b"%PDF-1.7 quarterly thoughts")
    assert rejection(file) == (
        '"report.pdf" isn\'t an image we can open. Upload a PNG, JPEG, or WebP picture.'
    )


def test_rejects_a_damaged_image(make_image):
    whole = make_image().read()
    file = SimpleUploadedFile("photo.png", whole[: len(whole) // 2])
    assert rejection(file) == (
        '"photo.png" isn\'t an image we can open. Upload a PNG, JPEG, or WebP picture.'
    )


def test_rejects_other_formats_by_content_not_extension(make_image):
    file = make_image(format="TIFF", name="scan.png")
    assert rejection(file) == (
        '"scan.png" is a TIFF image. We accept PNG, JPEG, or WebP. '
        "Save it in one of those formats and try again."
    )


@pytest.mark.parametrize(
    "format, phrase", [("GIF", "is a GIF image."), ("ICO", "is an ICO image.")]
)
def test_wrong_format_message_names_the_format(make_image, format, phrase):
    file = make_image(format=format, name="icon.png")
    assert rejection(file).startswith(f'"icon.png" {phrase}')


def test_rejects_too_many_pixels(make_image):
    file = make_image(width=8001, height=700, name="poster.png")
    assert rejection(file) == (
        '"poster.png" is 8001 × 700 pixels. Images can be at most 8000 pixels '
        "on each side."
    )


def test_rejects_an_image_too_big_for_pillow_to_measure(make_image, monkeypatch):
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    file = make_image(name="poster.png")
    assert rejection(file) == (
        '"poster.png" is far too large in pixels. Images can be at most 8000 '
        "pixels on each side."
    )


@pytest.mark.parametrize("width, height", [(150, 120), (599, 800), (800, 599)])
def test_rejects_too_few_pixels(make_image, width, height):
    file = make_image(width=width, height=height, name="logo.png")
    assert rejection(file) == (
        f'"logo.png" is {width} × {height} pixels. Images need to be at least '
        "600 pixels wide and 600 pixels tall so they look sharp in the store."
    )


def test_processing_failure_is_reported_plainly(make_image, monkeypatch):
    def explode(*args, **kwargs):
        raise OSError("encoder exploded")

    monkeypatch.setattr(Image.Image, "thumbnail", explode)
    assert rejection(make_image()) == (
        'We couldn\'t prepare "photo.png" for the store. Try saving it again as '
        "a PNG or JPEG and uploading that copy. Your current image hasn't "
        "changed."
    )


# --- Accepted files --------------------------------------------------------


@pytest.mark.parametrize(
    "format, name", [("PNG", "a.png"), ("JPEG", "a.jpg"), ("WEBP", "a.webp")]
)
def test_accepts_png_jpeg_and_webp_as_webp(make_image, format, name):
    result = prepare_product_image(make_image(format=format, name=name))
    assert result.name == "a.webp"
    assert opened(result).format == "WEBP"


def test_shrinks_to_fit_1600_keeping_shape(make_image):
    result = prepare_product_image(make_image(width=2244, height=2804))
    assert opened(result).size == (1280, 1600)


def test_never_upscales(make_image):
    result = prepare_product_image(make_image(width=600, height=600))
    assert opened(result).size == (600, 600)


def test_keeps_transparency():
    buffer = BytesIO()
    Image.new("RGBA", (800, 800), (0, 0, 0, 0)).save(buffer, format="PNG")
    result = prepare_product_image(SimpleUploadedFile("cutout.png", buffer.getvalue()))
    image = opened(result)
    assert image.mode == "RGBA"
    assert image.getpixel((0, 0))[3] == 0


def test_applies_camera_rotation():
    """A phone photo stored sideways with an EXIF "rotate 90°" tag."""
    image = Image.new("RGB", (800, 1000), "steelblue")
    exif = image.getexif()
    exif[0x0112] = 6  # Orientation: rotate 90° clockwise to view
    buffer = BytesIO()
    image.save(buffer, format="JPEG", exif=exif.tobytes())
    result = prepare_product_image(SimpleUploadedFile("phone.jpg", buffer.getvalue()))
    assert opened(result).size == (1000, 800)


def test_reads_a_file_that_was_already_read(make_image):
    file = make_image()
    file.read()
    assert prepare_product_image(file).name == "photo.webp"

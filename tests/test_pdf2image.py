import base64
import io

import fitz
import pytest

from mdparse.pdf2image import pdf_to_images


@pytest.fixture
def sample_pdf_path(tmp_path):
    path = tmp_path / "sample.pdf"
    doc = fitz.open()
    for _ in range(3):
        doc.new_page()
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def encrypted_pdf_data(tmp_path):
    path = tmp_path / "encrypted.pdf"
    userpw = "userpass"
    ownerpw = "ownerpass"
    doc = fitz.open()
    doc.new_page()
    doc.save(str(path), encryption=fitz.PDF_ENCRYPT_AES_256, owner_pw=ownerpw, user_pw=userpw)
    doc.close()
    return path, userpw, "wrongpass"


def test_pdf_to_images_default_jpeg_bytes(sample_pdf_path):
    images = pdf_to_images(sample_pdf_path)
    assert isinstance(images, list)
    assert len(images) == 3
    for img in images:
        assert isinstance(img, (bytes, bytearray))
        assert img[:2] == b"\xff\xd8"
        assert img[-2:] == b"\xff\xd9"


def test_pdf_to_images_png_bytes(sample_pdf_path):
    images = pdf_to_images(sample_pdf_path, fmt="png")
    assert len(images) == 3
    for img in images:
        assert isinstance(img, (bytes, bytearray))
        assert img.startswith(b"\x89PNG\r\n\x1a\n")


def test_pdf_to_images_filelike_bytes(sample_pdf_path):
    data = sample_pdf_path.read_bytes()
    bio = io.BytesIO(data)
    images = pdf_to_images(bio, fmt="jpeg")
    assert len(images) == 3
    for img in images:
        assert isinstance(img, (bytes, bytearray))
        assert img[:2] == b"\xff\xd8"


def test_pdf_to_images_page_range(sample_pdf_path):
    full = pdf_to_images(sample_pdf_path)
    subset = pdf_to_images(sample_pdf_path, first_page=1, last_page=1)
    assert isinstance(subset, list)
    assert len(subset) == 1
    assert subset[0] == full[1]


def test_pdf_to_images_invalid_page_range(sample_pdf_path):
    with pytest.raises(IndexError):
        pdf_to_images(sample_pdf_path, first_page=5, last_page=6)


def test_pdf_to_images_as_base64(sample_pdf_path):
    images_bytes = pdf_to_images(sample_pdf_path, fmt="png")
    images_b64 = pdf_to_images(sample_pdf_path, fmt="png", as_base64=True)
    assert len(images_bytes) == len(images_b64)
    for raw, data_url in zip(images_bytes, images_b64, strict=False):
        assert isinstance(data_url, str)
        assert data_url.startswith("data:image/png;base64,")
        b64part = data_url.split(",", 1)[1]
        decoded = base64.b64decode(b64part)
        assert decoded == raw


def test_pdf_to_images_zoom_effect(sample_pdf_path):
    img1 = pdf_to_images(sample_pdf_path, zoom=1.0)[0]
    img2 = pdf_to_images(sample_pdf_path, zoom=2.0)[0]
    assert len(img2) > len(img1)


def test_pdf_to_images_userpw_on_unencrypted(sample_pdf_path):
    no_pw = pdf_to_images(sample_pdf_path)
    with_pw = pdf_to_images(sample_pdf_path, userpw="anything")
    assert no_pw == with_pw


def test_pdf_to_images_encrypted_correct_password(encrypted_pdf_data):
    path, correct_pw, _ = encrypted_pdf_data
    images = pdf_to_images(path, userpw=correct_pw)
    assert isinstance(images, list)
    assert len(images) == 1
    img = images[0]
    assert isinstance(img, (bytes, bytearray))
    assert img[:2] == b"\xff\xd8"


def test_pdf_to_images_encrypted_wrong_password(encrypted_pdf_data):
    path, _, wrong_pw = encrypted_pdf_data
    with pytest.raises(Exception):
        pdf_to_images(path, userpw=wrong_pw)

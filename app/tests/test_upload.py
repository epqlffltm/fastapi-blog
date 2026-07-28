#app/tests/test_upload.py

'''
2026-07-24
파일 업로드 API / 마크다운 추출 테스트

2026-07-28
실제 이미지 검증 / 크기 제한 / DB 실패 시 파일 정리 테스트
'''

from io import BytesIO

import pytest
from fastapi import HTTPException, UploadFile
from PIL import Image
from starlette.datastructures import Headers

from app.database.connection import settings
from app.service import upload as upload_module
from app.service.markdown import extract_first_image
from app.service.upload import ALLOWED_TYPES, UploadService


def _image_bytes(format: str = "PNG", size: tuple[int, int] = (2, 2)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size).save(buffer, format=format)
    return buffer.getvalue()


def _upload_file(data: bytes, content_type: str, filename: str) -> UploadFile:
    return UploadFile(
        file=BytesIO(data),
        filename=filename,
        headers=Headers({"content-type": content_type}),
    )


# ---------- 업로드 ----------

def test_upload(admin_client, mock_upload_service, mock_upload_repo):
    mock_upload_service.save.return_value = ("abc123.png", 1234)

    response = admin_client.post(
        "/upload",
        files={"file": ("사진.png", b"fake-bytes", "image/png")},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["url"] == "/img/abc123.png"     # 사이트 기준 상대 경로
    assert data["size"] == 1234
    mock_upload_repo.save.assert_called_once()


def test_upload_records_original_name(admin_client, mock_upload_service, mock_upload_repo):
    """저장 이름은 UUID 지만 원본 이름은 기록에 남는다"""
    mock_upload_service.save.return_value = ("abc123.png", 1234)

    admin_client.post("/upload", files={"file": ("사진.png", b"x", "image/png")})

    saved = mock_upload_repo.save.call_args.args[0]
    assert saved.filename == "abc123.png"
    assert saved.original_name == "사진.png"
    assert saved.user_id == 1


def test_upload_deletes_file_when_db_save_fails(
    admin_client, mock_upload_service, mock_upload_repo
):
    """디스크 저장 후 DB 기록이 실패하면 고아 파일을 삭제한다."""
    mock_upload_service.save.return_value = ("abc123.png", 1234)
    mock_upload_repo.save.side_effect = RuntimeError("db failed")

    with pytest.raises(RuntimeError, match="db failed"):
        admin_client.post(
            "/upload",
            files={"file": ("사진.png", b"fake-bytes", "image/png")},
        )

    mock_upload_service.delete.assert_awaited_once_with("abc123.png")


def test_upload_without_permission(auth_client, mock_upload_service, mock_upload_repo):
    """업로드 권한이 없으면 디스크를 채울 수 없다"""
    response = auth_client.post("/upload", files={"file": ("a.png", b"x", "image/png")})

    assert response.status_code == 403
    assert response.json()["detail"] == "permission denied: can_upload"
    mock_upload_repo.save.assert_not_called()


def test_upload_without_token(client, mock_upload_service, mock_upload_repo):
    response = client.post("/upload", files={"file": ("a.png", b"x", "image/png")})

    assert response.status_code == 401
    mock_upload_repo.save.assert_not_called()


def test_upload_unverified(unverified_client, mock_upload_service, mock_upload_repo):
    """이메일 인증 전에는 업로드할 수 없다 (권한보다 먼저 걸린다)"""
    response = unverified_client.post(
        "/upload", files={"file": ("a.png", b"x", "image/png")}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "email not verified"
    mock_upload_repo.save.assert_not_called()


def test_upload_when_suspended(suspended_client, mock_upload_service, mock_upload_repo):
    response = suspended_client.post(
        "/upload", files={"file": ("a.png", b"x", "image/png")}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "suspended"
    mock_upload_repo.save.assert_not_called()


# ---------- 업로드 서비스 ----------

@pytest.mark.asyncio
async def test_upload_service_saves_valid_image(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_module, "UPLOAD_DIR", tmp_path)
    data = _image_bytes()

    filename, size = await UploadService().save(
        _upload_file(data, "image/png", "image.png")
    )

    assert filename.endswith(".png")
    assert size == len(data)
    assert (tmp_path / filename).read_bytes() == data


@pytest.mark.asyncio
async def test_upload_service_rejects_fake_image():
    with pytest.raises(HTTPException) as exc_info:
        await UploadService().save(
            _upload_file(b"not-an-image", "image/png", "fake.png")
        )

    assert exc_info.value.status_code == 415
    assert exc_info.value.detail == "invalid image file"


@pytest.mark.asyncio
async def test_upload_service_rejects_content_type_mismatch():
    jpeg = _image_bytes(format="JPEG")

    with pytest.raises(HTTPException) as exc_info:
        await UploadService().save(
            _upload_file(jpeg, "image/png", "spoofed.png")
        )

    assert exc_info.value.status_code == 415
    assert exc_info.value.detail == "file type does not match content"


@pytest.mark.asyncio
async def test_upload_service_rejects_large_dimensions(monkeypatch):
    monkeypatch.setattr(settings, "upload_max_width", 1)

    with pytest.raises(HTTPException) as exc_info:
        await UploadService().save(
            _upload_file(_image_bytes(size=(2, 2)), "image/png", "large.png")
        )

    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "image dimensions too large"


@pytest.mark.asyncio
async def test_upload_service_delete(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_module, "UPLOAD_DIR", tmp_path)
    target = tmp_path / "abc.png"
    target.write_bytes(b"x")

    await UploadService().delete("abc.png")

    assert not target.exists()


# ---------- 허용 형식 ----------

def test_allowed_types_are_images_only():
    """실행 가능한 형식이 섞여 들어가면 안 된다"""
    assert set(ALLOWED_TYPES) == {"image/jpeg", "image/png", "image/gif", "image/webp"}
    for extension in ALLOWED_TYPES.values():
        assert extension.startswith(".")


# ---------- 썸네일 추출 ----------

def test_extract_first_image():
    assert extract_first_image("![](/img/a.png)") == "/img/a.png"
    assert extract_first_image("앞\n![alt](/img/a.png)\n뒤\n![](/img/b.png)") == "/img/a.png"


def test_extract_first_image_none():
    assert extract_first_image("이미지 없는 본문") is None
    assert extract_first_image("") is None


def test_extract_first_image_ignores_link():
    """일반 링크 [text](url) 은 이미지가 아니다"""
    assert extract_first_image("[링크](/page/1)") is None
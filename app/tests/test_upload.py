#app/tests/test_upload.py

'''
2026-07-24
파일 업로드 API / 마크다운 추출 테스트
업로드는 관리자만
'''

from app.service.markdown import extract_first_image
from app.service.upload import ALLOWED_TYPES


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


def test_upload_as_member(auth_client, mock_upload_service, mock_upload_repo):
    """이미지는 글 본문에만 쓰이므로 일반 회원은 올릴 수 없다"""
    response = auth_client.post("/upload", files={"file": ("a.png", b"x", "image/png")})

    assert response.status_code == 403
    assert response.json()["detail"] == "admin only"
    mock_upload_repo.save.assert_not_called()


def test_upload_without_token(client, mock_upload_service, mock_upload_repo):
    response = client.post("/upload", files={"file": ("a.png", b"x", "image/png")})

    assert response.status_code == 401
    mock_upload_repo.save.assert_not_called()


def test_upload_unverified(unverified_client, mock_upload_service, mock_upload_repo):
    """이메일 인증 전에는 업로드할 수 없다 (등급보다 먼저 걸린다)"""
    response = unverified_client.post(
        "/upload", files={"file": ("a.png", b"x", "image/png")}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "email not verified"
    mock_upload_repo.save.assert_not_called()


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
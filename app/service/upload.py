#app/service/upload.py

'''
2026-07-24
파일 업로드 서비스 (검증 / 저장)

2026-07-28
실제 이미지 검증 / 픽셀 제한 / 비동기 파일 저장·삭제
아바타 교체 시 애플리케이션이 관리하는 기존 파일 식별 지원
'''

import asyncio
import re
import uuid
import warnings
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from ..database.connection import settings


# 확장자는 파일명이 아니라 이 표에서 정한다.
# 파일명을 믿으면 ../../ 같은 경로 탈출이나 위장 확장자가 들어온다
ALLOWED_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

# 요청의 Content-Type과 실제 이미지 포맷이 일치하는지 확인한다.
PIL_FORMATS: dict[str, str] = {
    "image/jpeg": "JPEG",
    "image/png": "PNG",
    "image/gif": "GIF",
    "image/webp": "WEBP",
}

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "img"
_MANAGED_FILENAME = re.compile(r"^[0-9a-f]{32}\.(?:jpg|png|gif|webp)$")


class UploadService:
    async def save(self, file: UploadFile) -> tuple[str, int]:
        """검증된 이미지를 저장하고 저장 파일명과 바이트 크기를 반환한다."""
        content_type = file.content_type or ""
        extension = ALLOWED_TYPES.get(content_type)
        if extension is None:
            raise HTTPException(status_code=415, detail="unsupported file type")

        # 전부 읽어 크기를 재고 나서 쓴다.
        # 스트리밍으로 쓰면서 검사하면 초과분이 이미 디스크에 남는다.
        data = await file.read()
        if len(data) > settings.upload_max_bytes:
            limit_mb = settings.upload_max_bytes // (1024 * 1024)
            raise HTTPException(status_code=413, detail=f"file too large (max {limit_mb}MB)")
        if len(data) == 0:
            raise HTTPException(status_code=400, detail="empty file")

        self._validate_image(data=data, content_type=content_type)

        # 이름은 UUID로 새로 짓는다 → 충돌·덮어쓰기·경로 탈출이 원천 차단된다.
        filename = f"{uuid.uuid4().hex}{extension}"
        target = UPLOAD_DIR / filename
        await asyncio.to_thread(self._write_file, target, data)

        return filename, len(data)

    async def delete(self, filename: str) -> None:
        """DB 저장 실패나 이미지 교체 시 이미 저장된 파일을 안전하게 삭제한다."""
        root = UPLOAD_DIR.resolve()
        target = (UPLOAD_DIR / filename).resolve()
        if target.parent != root:
            raise ValueError("invalid upload filename")
        await asyncio.to_thread(target.unlink, missing_ok=True)

    @staticmethod
    def managed_filename_from_url(url: str | None) -> str | None:
        """로컬 `/img/<uuid>.<ext>` URL이면 관리 대상 파일명만 반환한다.

        외부 URL, 쿼리 문자열이 붙은 URL, 경로 탈출 형태, 사용자가 직접 지정한
        일반 파일명은 삭제 대상으로 인정하지 않는다.
        """
        if not url:
            return None
        parsed = urlsplit(url)
        if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment:
            return None
        path = PurePosixPath(parsed.path)
        if path.parent != PurePosixPath("/img"):
            return None
        filename = path.name
        return filename if _MANAGED_FILENAME.fullmatch(filename) else None

    @staticmethod
    def _write_file(target: Path, data: bytes) -> None:
        """이벤트 루프 밖에서 임시 파일에 쓴 뒤 원자적으로 교체한다."""
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(f".{target.name}.tmp")
        try:
            temporary.write_bytes(data)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _validate_image(data: bytes, content_type: str) -> None:
        """Pillow로 실제 이미지 포맷·무결성·크기를 확인한다."""
        expected_format = PIL_FORMATS[content_type]

        try:
            with warnings.catch_warnings():
                # Pillow가 압축 폭탄 의심 경고를 내면 업로드를 거부한다.
                warnings.simplefilter("error", Image.DecompressionBombWarning)

                with Image.open(BytesIO(data)) as image:
                    detected_format = image.format
                    width, height = image.size

                    if detected_format != expected_format:
                        raise HTTPException(
                            status_code=415,
                            detail="file type does not match content",
                        )

                    if (
                        width > settings.upload_max_width
                        or height > settings.upload_max_height
                        or width * height > settings.upload_max_pixels
                    ):
                        raise HTTPException(
                            status_code=413,
                            detail="image dimensions too large",
                        )

                    # 파일 구조가 손상됐는지 검사한다.
                    image.verify()

                # verify()는 픽셀을 완전히 디코딩하지 않으므로 다시 열어 첫 프레임을 읽는다.
                with Image.open(BytesIO(data)) as image:
                    image.load()

        except HTTPException:
            raise
        except (Image.DecompressionBombWarning, Image.DecompressionBombError) as exc:
            raise HTTPException(status_code=413, detail="image dimensions too large") from exc
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            raise HTTPException(status_code=415, detail="invalid image file") from exc

#app/service/upload.py

'''
2026-07-24
파일 업로드 서비스 (검증 / 저장)
'''

import uuid
from pathlib import Path
from fastapi import HTTPException, UploadFile
from ..database.connection import settings

# 확장자는 파일명이 아니라 이 표에서 정한다.
# 파일명을 믿으면 ../../ 같은 경로 탈출이나 위장 확장자가 들어온다
ALLOWED_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "img"


class UploadService:
    async def save(self, file: UploadFile) -> tuple[str, int]:
        """저장된 파일명과 크기를 돌려준다"""
        extension = ALLOWED_TYPES.get(file.content_type or "")
        if extension is None:
            raise HTTPException(status_code=415, detail="unsupported file type")

        # 전부 읽어 크기를 재고 나서 쓴다.
        # 스트리밍으로 쓰면서 검사하면 초과분이 이미 디스크에 남는다
        data = await file.read()
        if len(data) > settings.upload_max_bytes:
            limit_mb = settings.upload_max_bytes // (1024 * 1024)
            raise HTTPException(status_code=413, detail=f"file too large (max {limit_mb}MB)")
        if len(data) == 0:
            raise HTTPException(status_code=400, detail="empty file")

        # 이름은 UUID 로 새로 짓는다 → 충돌·덮어쓰기·경로 탈출이 원천 차단된다
        filename = f"{uuid.uuid4().hex}{extension}"
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        (UPLOAD_DIR / filename).write_bytes(data)

        return filename, len(data)
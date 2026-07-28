#app/api/upload.py

'''
2026-07-24
파일 업로드 라우터 (에디터가 이미지를 여기로 보낸다)

2026-07-28
DB 기록 실패 시 저장 파일 정리
'''

from contextlib import suppress

from fastapi import APIRouter, Depends, UploadFile

from ..database.orm import Upload, User
from ..database.repository import UploadRepository
from ..schema.response import UploadSchema
from ..service.upload import UploadService
from .dependency import require_permission

router = APIRouter(tags=["upload"])


@router.post("/upload", status_code=201, response_model=UploadSchema)#파일 업로드
async def upload_handler(
    file: UploadFile,
    # 열어두면 아무나 디스크를 채울 수 있으므로 권한을 따로 둔다
    current_user: User = Depends(require_permission("can_upload")),
    upload_service: UploadService = Depends(),
    upload_repo: UploadRepository = Depends(),
):
    filename, size = await upload_service.save(file)

    try:
        await upload_repo.save(
            Upload.create(
                user_id=current_user.id,
                filename=filename,
                original_name=file.filename or "",
                content_type=file.content_type or "",
                size=size,
            )
        )
    except Exception:
        # 파일 저장 후 DB 기록만 실패하면 고아 파일이 남으므로 정리한다.
        # 삭제 실패가 원래 DB 예외를 가리지 않도록 OSError만 무시한다.
        with suppress(OSError):
            await upload_service.delete(filename)
        raise

    # static 이 "/" 에 마운트돼 있으므로 사이트 기준 상대 경로다.
    # 도메인이나 디스크가 바뀌어도 본문을 고칠 필요가 없다
    return UploadSchema(url=f"/img/{filename}", filename=filename, size=size)
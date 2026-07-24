#app/api/upload.py

'''
2026-07-24
파일 업로드 라우터 (에디터가 이미지를 여기로 보낸다)
'''

from fastapi import APIRouter, Depends, UploadFile
from ..database.orm import Upload, User
from ..database.repository import UploadRepository
from ..schema.response import UploadSchema
from ..service.upload import UploadService
from .dependency import get_admin_user

router = APIRouter(tags=["upload"])


@router.post("/upload", status_code=201, response_model=UploadSchema)#파일 업로드
async def upload_handler(
    file: UploadFile,
    # 이미지는 글 본문에만 쓰이므로 글을 쓸 수 있는 등급만 올릴 수 있다.
    # 열어두면 아무나 디스크를 채울 수 있다
    current_user: User = Depends(get_admin_user),
    upload_service: UploadService = Depends(),
    upload_repo: UploadRepository = Depends(),
):
    filename, size = await upload_service.save(file)

    upload_repo.save(
        Upload.create(
            user_id=current_user.id,
            filename=filename,
            original_name=file.filename or "",
            content_type=file.content_type or "",
            size=size,
        )
    )

    # static 이 "/" 에 마운트돼 있으므로 사이트 기준 상대 경로다.
    # 도메인이나 디스크가 바뀌어도 본문을 고칠 필요가 없다
    return UploadSchema(url=f"/img/{filename}", filename=filename, size=size)
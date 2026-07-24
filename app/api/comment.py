#app/api/comment.py

'''
2026-07-21
댓글 관련 라우터 (생성, 수정, 삭제)
repository 패턴 적용

2026-07-23
인증 연동 + 권한 검사

2026-07-24
댓글 작성에 이메일 인증 요구
대댓글 (1단계)
'''

from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime, timezone
from ..database.repository import PostRepository, CommentRepository
from ..database.orm import Comment, User
from ..schema.request import CommentCreate
from ..schema.response import PostDetailSchema
from ..service.comment import visible_comments
from .dependency import get_current_user, get_verified_user

router = APIRouter(tags=["comment"])


@router.post("/page/{post_id}/comment", status_code=201, response_model=PostDetailSchema)#댓글 쓰기
def create_comment_handler(
    post_id: int,
    request: CommentCreate,
    current_user: User = Depends(get_verified_user),   # 이메일 인증된 회원만
    post_repo: PostRepository = Depends(),
    comment_repo: CommentRepository = Depends(),
):
    post = post_repo.get_post_by_id(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    if request.parent_id is not None:
        parent = comment_repo.get_comment_by_id(request.parent_id)
        if parent is None or parent.post_id != post_id:
            # 다른 글의 댓글에 답글을 달 수 없다
            raise HTTPException(status_code=400, detail="parent comment not found")
        if parent.parent_id is not None:
            # 답글의 답글은 받지 않는다 (깊이 1)
            raise HTTPException(status_code=400, detail="cannot reply to a reply")

    comment = Comment.create(
        request=request, post_id=post_id, user_id=current_user.id
    )
    comment_repo.save(comment)

    # 새 댓글 반영된 글 다시 읽기
    post = post_repo.get_post_by_id(post_id)
    post.comments = visible_comments(post.comments)
    return post


@router.patch("/comment/{id}", status_code=200)#댓글 수정
def update_comment_handler(
    id: int,
    contents: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
    comment_repo: CommentRepository = Depends(),
):
    comment = comment_repo.get_comment_by_id(id)
    if comment is None:
        raise HTTPException(status_code=404, detail="comment not found")
    if comment.user_id != current_user.id:      # 내 댓글만 수정 가능
        raise HTTPException(status_code=403, detail="not your comment")

    comment.contents = contents
    comment.updated_at = datetime.now(timezone.utc)
    comment = comment_repo.update(comment)
    return {"id": comment.id, "contents": comment.contents}


@router.delete("/comment/{id}", status_code=204)#댓글 삭제
def delete_comment_handler(
    id: int,
    current_user: User = Depends(get_current_user),
    comment_repo: CommentRepository = Depends(),
):
    comment = comment_repo.get_comment_by_id(id)
    if comment is None:
        raise HTTPException(status_code=404, detail="comment not found")
    if comment.user_id != current_user.id:      # 내 댓글만 삭제 가능
        raise HTTPException(status_code=403, detail="not your comment")

    # 소프트삭제. 답글이 달려 있으면 자리표시자로 남는다
    comment.is_deleted = True
    comment.updated_at = datetime.now(timezone.utc)
    comment_repo.update(comment)
    return
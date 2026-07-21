#app/main.py

'''
2026-07-15
main.py작성

2026-07-16
get api 전체 조회
get api 단일 조회
post api 생성
patch api 작성
delete api 작성

2026-07-17
404 예외 처리 추가

2026-07-20
get 전체조회 api
orm → http response 스키마
get 단일 조회 api
refactoring

2026-07-21
post/patch/delete api DB 전환
'''

from fastapi import FastAPI, Body, HTTPException, Depends
from datetime import datetime, timezone
from .schema.request import PostCreate, CommentCreate
from .schema.response import ListPostSchema, PostListItemSchema, PostDetailSchema
from typing import Optional
from sqlalchemy.orm import Session
from .database.connection import get_db
from sqlalchemy import select, func
from .database.orm import Post, Comment, Image

app = FastAPI()

@app.get("/", status_code=200)#index
async def index():
    return {"message": "Hello, FastAPI"}


@app.get("/pages", status_code=200, response_model=ListPostSchema)#글 목록 보기
def get_pages_handler(
    order: str = "random",
    session: Session = Depends(get_db),
):
    order = order.lower()

    # 삭제 안 된 글 가져오기 + 정렬을 DB가 함
    stmt = select(Post).where(Post.is_deleted == False)
    if order == "asc":
        stmt = stmt.order_by(Post.created_at.asc())
    elif order == "desc":
        stmt = stmt.order_by(Post.created_at.desc())
    else:
        stmt = stmt.order_by(func.random())

    posts = session.scalars(stmt).all()

    result = []
    for post in posts:
        # 이 글의 삭제 안 된 댓글 수 세기 (COUNT를 DB가 함)
        comment_count = session.scalar(
            select(func.count(Comment.id))
            .where(Comment.post_id == post.id)
            .where(Comment.is_deleted == False)
        )

        result.append(
            PostListItemSchema(
                id=post.id,
                title=post.title,
                nickname=post.nickname,
                created_at=post.created_at,
                comment_count=comment_count,
            )
        )

    return ListPostSchema(posts=result)

@app.get("/page/{id}", status_code=200, response_model=PostDetailSchema)#글 읽기
def get_page_handler(
    id: int,
    session: Session = Depends(get_db),
):
    post = session.scalar(
        select(Post).where(Post.id == id).where(Post.is_deleted == False)
    )
    if post is None:      # 없거나 삭제된 글
        raise HTTPException(status_code=404, detail="post not found")

    # 삭제 안 된 댓글만 남기기 (relationship은 삭제 여부를 안 가리므로 직접 필터)
    post.comments = [c for c in post.comments if not c.is_deleted]

    return post

@app.post("/page", status_code=201, response_model=PostDetailSchema)#본문 쓰기
def create_post_handler(
    request: PostCreate,
    session: Session = Depends(get_db),
):
    post = Post.create(request=request)   # 글 객체 생성 (orm의 create)
    session.add(post)
    session.flush()                       # commit 전에 post.id 확보 (이미지 연결용)

    # 이미지가 있으면 각각 Image 객체 만들어 매달기 (없으면 루프 안 돎)
    for order, url in enumerate(request.image):
        image = Image.create(url=url, post_id=post.id, display_order=order)
        session.add(image)

    session.commit()                      # 글 + 이미지 한 번에 저장 확정
    session.refresh(post)                 # 최신 상태 다시 읽기 (이미지 연결 포함)

    return post

@app.post("/page/{post_id}/comment", status_code=201, response_model=PostDetailSchema)#댓글 쓰기
def create_comment_handler(
    post_id: int,
    request: CommentCreate,
    session: Session = Depends(get_db),
):
    post = session.scalar(
        select(Post).where(Post.id == post_id).where(Post.is_deleted == False)
    )
    if post is None:      # 없는 글엔 댓글 못 담
        raise HTTPException(status_code=404, detail="post not found")

    comment = Comment.create(request=request, post_id=post_id)   # 댓글 객체 생성
    session.add(comment)
    session.commit()
    session.refresh(post)                 # 새 댓글 반영된 글 다시 읽기

    # 삭제 안 된 댓글만 남기기
    post.comments = [c for c in post.comments if not c.is_deleted]

    return post

@app.patch("/page/{id}", status_code=200, response_model=PostDetailSchema)#본문 수정
def update_post_handler(
    id: int,
    title: Optional[str] = Body(None, embed=True),
    contents: Optional[str] = Body(None, embed=True),
    session: Session = Depends(get_db),
):
    post = session.scalar(
        select(Post).where(Post.id == id).where(Post.is_deleted == False)
    )
    if post is None:      # 없거나 삭제된 글
        raise HTTPException(status_code=404, detail="post not found")

    if title is not None:
        post.title = title
    if contents is not None:
        post.contents = contents
    post.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(post)

    # 삭제 안 된 댓글만 남기기
    post.comments = [c for c in post.comments if not c.is_deleted]

    return post

@app.patch("/comment/{id}", status_code=200)#댓글 수정
def update_comment_handler(
    id: int,
    contents: str = Body(..., embed=True),
    session: Session = Depends(get_db),
):
    comment = session.scalar(
        select(Comment).where(Comment.id == id).where(Comment.is_deleted == False)
    )
    if comment is None:      # 없거나 삭제된 댓글
        raise HTTPException(status_code=404, detail="comment not found")

    comment.contents = contents
    comment.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(comment)

    return comment

@app.delete("/page/{id}", status_code=204)#본문 삭제
def delete_post_handler(
    id: int,
    session: Session = Depends(get_db),
):
    post = session.scalar(
        select(Post).where(Post.id == id).where(Post.is_deleted == False)
    )
    if post is None:      # 없거나 이미 삭제된 글
        raise HTTPException(status_code=404, detail="post not found")

    post.is_deleted = True   # 소프트삭제
    post.updated_at = datetime.now(timezone.utc)
    session.commit()
    return

@app.delete("/comment/{id}", status_code=204)#댓글 삭제
def delete_comment_handler(
    id: int,
    session: Session = Depends(get_db),
):
    comment = session.scalar(
        select(Comment).where(Comment.id == id).where(Comment.is_deleted == False)
    )
    if comment is None:      # 없거나 이미 삭제된 댓글
        raise HTTPException(status_code=404, detail="comment not found")

    comment.is_deleted = True   # 소프트삭제
    comment.updated_at = datetime.now(timezone.utc)
    session.commit()
    return
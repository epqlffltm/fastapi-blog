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
'''

from fastapi import FastAPI, Body, HTTPException,Depends
from datetime import datetime, timezone
import random
from .database.fake_posts import fake_posts
from .database.fake_comments import fake_comments
from .schemas import PostCreate, CommentCreate
from typing import Optional
from sqlalchemy.orm import Session
from .database.connection import get_db
from sqlalchemy import select, func
from .database.orm import Post, Comment

app = FastAPI()

@app.get("/", status_code=200)#index
async def index():
    return {"message": "Hello, FastAPI"}


@app.get("/pages", status_code=200)#글 목록 보기
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

        result.append({
            "id": post.id,
            "title": post.title,
            "nickname": post.nickname,
            "created_at": post.created_at,
            "comment_count": comment_count,
        })

    return result

@app.get("/page/{id}", status_code=200)#글 읽기
def get_page_handler(id: int):
    post = fake_posts.get(id)
    if post is None or post["is_deleted"]:      # 없거나 삭제된 글
        raise HTTPException(status_code=404, detail="post not found")

    comments = []
    for c in fake_comments.values():
        if c["post_id"] == id and not c["is_deleted"]:
            comments.append(c)

    return {**post, "comments": comments}

@app.post("/page", status_code=201)#본문 쓰기
def create_post_handler(request: PostCreate):
    new_id = max(fake_posts.keys()) + 1   # 서버가 id 발급
    now = datetime.now(timezone.utc).isoformat()

    fake_posts[new_id] = {
        "id": new_id,
        "created_at": now,
        "updated_at": now,
        "title": request.title,
        "nickname": request.nickname,
        "contents": request.contents,
        "image": request.image,
        "is_deleted": False,# 서버가 강제
    }
    return fake_posts[new_id]

@app.post("/page/{post_id}/comment", status_code=201)#댓글 쓰기
def create_comment_handler(post_id: int, request: CommentCreate):
    post = fake_posts.get(post_id)
    if post is None or post["is_deleted"]:      # 없는 글엔 댓글 못 닮
        raise HTTPException(status_code=404, detail="post not found")

    new_id = max(fake_comments.keys()) + 1   # 댓글 고유 id 발급
    now = datetime.now(timezone.utc).isoformat()

    fake_comments[new_id] = {
        "id": new_id,
        "post_id": post_id,     # URL의 post_id = 어느 글에 다는지
        "created_at": now,
        "updated_at": now,
        "nickname": request.nickname,
        "contents": request.contents,
        "is_deleted": False,
    }
    return fake_comments[new_id]

@app.patch("/page/{id}", status_code=200)#본문 수정
def update_post_handler(
    id: int,
    title: Optional[str] = Body(None, embed=True),
    contents: Optional[str] = Body(None, embed=True),
):
    post = fake_posts.get(id)
    if post is None or post["is_deleted"]:      # 없거나 삭제된 글
        raise HTTPException(status_code=404, detail="post not found")

    if title is not None:
        post["title"] = title
    if contents is not None:
        post["contents"] = contents
    post["updated_at"] = datetime.now(timezone.utc).isoformat()
    return post

@app.patch("/comment/{id}", status_code=200)#댓글 수정
def update_comment_handler(
    id: int,
    contents: str = Body(..., embed=True),
):
    comment = fake_comments.get(id)
    if comment is None or comment["is_deleted"]:    # 없거나 삭제된 댓글
        raise HTTPException(status_code=404, detail="comment not found")

    comment["contents"] = contents
    comment["updated_at"] = datetime.now(timezone.utc).isoformat()
    return comment

@app.delete("/page/{id}", status_code=204)#본문 삭제
def delete_post_handler(id: int):
    post = fake_posts.get(id)
    if post is None or post["is_deleted"]:      # 없거나 이미 삭제된 글
        raise HTTPException(status_code=404, detail="post not found")

    post["is_deleted"] = True
    post["updated_at"] = datetime.now(timezone.utc).isoformat()
    return

@app.delete("/comment/{id}", status_code=204)#댓글 삭제
def delete_comment_handler(id: int):
    comment = fake_comments.get(id)
    if comment is None or comment["is_deleted"]:    # 없거나 이미 삭제된 댓글
        raise HTTPException(status_code=404, detail="comment not found")

    comment["is_deleted"] = True
    comment["updated_at"] = datetime.now(timezone.utc).isoformat()
    return
#app/main.py

'''
2026-07-15
main.py작성

2026-07-16
get api 전체 조회
get api 단일 조회
post api 생성
patch api 작성
'''

from fastapi import FastAPI, Body
from datetime import datetime, timezone
import random
#from pydantic import BaseModel
from .database.fake_posts import fake_posts
from .database.fake_comments import fake_comments
from .schemas import PostCreate, CommentCreate
from typing import Optional

app = FastAPI()

@app.get("/")#index
async def index():
    return {"message": "Hello, FastAPI"}


@app.get("/pages")#글 목록 보기
def get_pages_handler(order: str = "random"):
    order = order.lower()

    result = []
    for post in fake_posts.values():
        if post["is_deleted"]:          # 삭제된 글은 목록에서 제외
            continue

        comment_count = 0
        for c in fake_comments.values():
            if c["post_id"] == post["id"] and not c["is_deleted"]:
                comment_count += 1

        result.append({
            "id": post["id"],
            "title": post["title"],
            "nickname": post["nickname"],
            "created_at": post["created_at"],
            "comment_count": comment_count,
        })

    if order == "asc":
        result.sort(key=lambda x: x["created_at"])
    elif order == "desc":
        result.sort(key=lambda x: x["created_at"], reverse=True)
    else:
        random.shuffle(result)

    return result

@app.get("/page/{id}")#글 읽기
def get_page_handler(id: int):
    post = fake_posts.get(id)
    if post is None or post["is_deleted"]:   # 없거나 삭제된 글
        return None

    comments = []
    for c in fake_comments.values():
        if c["post_id"] == id and not c["is_deleted"]:
            comments.append(c)

    return {**post, "comments": comments}

@app.post("/page")#본문 쓰기
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

@app.post("/page/{id}")#댓글 쓰기
def create_comment_handler(id: int, request: CommentCreate):
    new_id = max(fake_comments.keys()) + 1   # 댓글 고유 id 발급
    now = datetime.now(timezone.utc).isoformat()

    fake_comments[new_id] = {
        "id": new_id,
        "post_id": id,          # URL의 id = 어느 글에 다는지
        "created_at": now,
        "updated_at": now,
        "nickname": request.nickname,
        "contents": request.contents,
        "is_deleted": False,
    }
    return fake_comments[new_id]

@app.patch("/page/{id}")#본문 수정
def update_post_handler(
    id: int,
    title: Optional[str] = Body(None, embed=True),
    contents: Optional[str] = Body(None, embed=True),
):
    post = fake_posts.get(id)
    if post:
        if title is not None:
            post["title"] = title
        if contents is not None:
            post["contents"] = contents
        post["updated_at"] = datetime.now(timezone.utc).isoformat()
        return post
    return {}

@app.patch("/comment/{id}")#댓글 수정
def update_comment_handler(
    id: int,
    contents: str = Body(..., embed=True),
):
    comment = fake_comments.get(id)
    if comment:
        comment["contents"] = contents
        comment["updated_at"] = datetime.now(timezone.utc).isoformat()
        return comment
    return {}
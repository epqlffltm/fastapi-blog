#app/main

'''
2026-07-15
main.py작성

2026-07-16
get api 전체 조회
get api 단일 조회
post api 생성
'''

from fastapi import FastAPI
from pydantic  import BaseModel
from datetime import datetime, timezone
import random
from .database.fake_posts import fake_posts
from .database.fake_comments import fake_comments
from .schemas import PostCreate, CommentCreate

app = FastAPI()

@app.get("/")
async def index():
    return {"message": "Hello, FastAPI"}


@app.get("/pages")
def get_pages_handler(order: str = "random"):
    order = order.lower()

    result = []
    for post in fake_posts.values():
        comment_count = 0
        for c in fake_comments.values():
            if c["post_id"] == post["id"]:
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

@app.get("/page/{id}")
def get_page_handler(id: int):
    post = fake_posts.get(id)

    comments = []
    for c in fake_comments.values():
        if c["post_id"] == id:
            comments.append(c)

    return {**post, "comments": comments}

@app.post("/page")
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

@app.post("/post/{id}")
def create_comment_handler(id: int, request: CommentCreate):
    new_id = max(fake_comments.keys()) + 1   # 댓글 고유 id 발급
    now = datetime.now(timezone.utc).isoformat()

    fake_comments[new_id] = {
        "id": new_id,
        "post_id": id,          # URL의 id = 어느 글에 다는지
        "nickname": request.nickname,
        "contents": request.contents,
        "is_deleted": False,
    }
    return fake_comments[new_id]
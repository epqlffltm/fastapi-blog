#app/main

'''
2026-07-15
main.py작성

2026-07-16
get api 전체조회
'''

from fastapi import FastAPI
import random
from .database.fake_posts import fake_posts
from .database.fake_comments import fake_comments

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
        return result
    elif order == "desc":
        return result[::-1]
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
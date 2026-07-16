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
    result = list(fake_posts.values())
    if order == "asc":
        return result
    elif order == "desc":
        return result[::-1]
    else:  # "random" 포함, 그 외 아무 값
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
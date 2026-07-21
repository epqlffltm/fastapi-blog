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
api 라우터 분리 (post, comment)
'''

from fastapi import FastAPI
from .api import post, comment

app = FastAPI()

app.include_router(post.router)
app.include_router(comment.router)


@app.get("/", status_code=200)#index
async def index():
    return {"message": "Hello, FastAPI"}
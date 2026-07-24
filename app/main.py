#app/main.py

'''
2026-07-15
main.py작성

2026-07-16
get api 전체 조회 / 단일 조회 / post 생성 / patch 수정 / delete 삭제

2026-07-17
404 예외 처리 추가

2026-07-20
DB 전환, response 스키마, refactoring

2026-07-21
api 라우터 분리 (post, comment)

2026-07-23
user 라우터 추가

2026-07-24
정적 파일 서빙 (static)
category / upload 라우터 추가
'''

from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .api import post, comment, user, category, upload

app = FastAPI()

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# API 라우터를 먼저 등록해야 정적 마운트에 경로를 뺏기지 않는다
app.include_router(post.router)
app.include_router(comment.router)
app.include_router(user.router)
app.include_router(category.router)
app.include_router(upload.router)


@app.get("/health", status_code=200)#헬스 체크
async def health_check():
    return {"message": "Hello, FastAPI"}


# 확장자 없는 경로를 각 html에 연결 (StaticFiles는 .html을 자동으로 붙이지 않는다)
PAGES = ["login", "signup", "reset", "write", "edit", "post"]

for _page in PAGES:
    def _make_page_route(name: str):
        async def _serve_page():
            return FileResponse(STATIC_DIR / f"{name}.html")
        return _serve_page

    app.add_api_route(
        f"/{_page}", _make_page_route(_page), methods=["GET"], include_in_schema=False
    )


# html=True → "/" 요청에 index.html을 돌려준다
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
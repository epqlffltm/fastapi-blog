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
관리 페이지

2026-07-30
admin 라우터 추가 (감사 로그 조회)
'''

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from .api import admin, post, comment, user, category, upload
from .database.cache import close_redis_client


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        yield
    finally:
        await close_redis_client()


app = FastAPI(lifespan=lifespan)

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

# API 라우터를 먼저 등록해야 정적 마운트에 경로를 뺏기지 않는다
app.include_router(post.router)
app.include_router(comment.router)
app.include_router(user.router)
app.include_router(category.router)
app.include_router(upload.router)
# /admin 페이지 라우트와 경로가 겹치지 않는다.
# 페이지는 "/admin" 정확히 일치, 이쪽은 "/admin/audit-logs"
app.include_router(admin.router)


@app.get("/health", status_code=200)#헬스 체크
async def health_check():
    return {"message": "Hello, FastAPI"}


# 확장자 없는 경로를 각 html에 연결 (StaticFiles는 .html을 자동으로 붙이지 않는다)
PAGES = ["login", "signup", "reset", "write", "edit", "post", "admin", "profile"]

for _page in PAGES:
    def _make_page_route(name: str):
        async def _serve_page():
            return FileResponse(STATIC_DIR / f"{name}.html")
        return _serve_page

    app.add_api_route(
        f"/{_page}", _make_page_route(_page), methods=["GET"], include_in_schema=False
    )


# 남의 공개 프로필 페이지 (/user/3 처럼 id 가 변하는 동적 경로).
# API(/user/{id}/profile)와 경로가 겹치지 않는다. user.html 이 JS 로 id 를 읽어 데이터를 불러온다
@app.get("/user/{id}", include_in_schema=False)
async def serve_user_page(id: int):
    return FileResponse(STATIC_DIR / "user.html")


# html=True → "/" 요청에 index.html을 돌려준다
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
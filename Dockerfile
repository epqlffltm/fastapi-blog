# syntax=docker/dockerfile:1

# ---------- 빌드 단계 ----------
# uv 공식 이미지에는 uv 와 파이썬이 함께 들어 있다
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# 의존성만 먼저 설치한다.
# 소스가 바뀌어도 uv.lock 이 그대로면 이 레이어를 재사용하므로 재빌드가 빠르다
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

# 그다음 소스를 넣고 프로젝트 자체를 설치한다
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev


# ---------- 실행 단계 ----------
# uv 도 빌드 도구도 필요 없다. 만들어진 .venv 만 가져온다
FROM python:3.13-slim-bookworm AS runtime

# root 로 돌리지 않는다. 컨테이너가 뚫려도 권한을 제한한다
RUN groupadd --system --gid 1001 app \
 && useradd --system --uid 1001 --gid app --create-home app

WORKDIR /app
COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# 업로드 디렉터리. compose 에서 볼륨으로 덮어쓴다
RUN mkdir -p /app/static/img && chown -R app:app /app/static/img

USER app
EXPOSE 8000

# --proxy-headers 를 쓰지 않는다.
# 이 앱은 app/service/client_ip.py 에서 TRUSTED_PROXY_CIDRS 기준으로
# X-Forwarded-For 를 직접 해석한다. uvicorn 이 먼저 request.client 를
# 헤더 값으로 바꿔버리면 그 신뢰 경계가 무너진다
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

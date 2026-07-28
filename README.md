# fastapi-blog

FastAPI + PostgreSQL 로 만든 블로그. 회원·권한·글·댓글·좋아요·이미지 업로드까지 갖춘, 실제로 운영 가능한 수준의 백엔드를 목표로 했습니다.

```
Python 3.13 · FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Redis · Alembic · uv
```

아래는 기능마다 **무엇을 하는지**와 **왜 그렇게 만들었는지**를 같이 적었습니다. 대안이 여럿이던 지점에서 무엇을 골랐고 무엇을 버렸는지가 이 저장소의 본론입니다.

프론트엔드는 빌드 도구 없는 순수 HTML/CSS/JS 입니다. 백엔드가 주제인 프로젝트에 프론트 도구 체인까지 얹으면 읽는 사람의 시선이 분산됩니다.

---

## 인증 — httpOnly 쿠키에 담은 JWT

로그인하면 서버가 JWT 를 발급해 `access_token` 쿠키에 담아 내려줍니다. 유효기간은 24시간이고, 이후 모든 요청은 이 쿠키로 인증됩니다.

**왜 헤더가 아니라 쿠키인가.** `Authorization: Bearer` 방식은 토큰을 JS 가 들고 있어야 하고, 그러려면 `localStorage` 에 둘 수밖에 없습니다. XSS 가 한 번만 터지면 토큰이 통째로 나갑니다. `httpOnly` 쿠키는 JS 가 읽을 수 없어 그 경로가 막힙니다.

대신 대가가 있습니다. **프론트가 자기 로그인 여부를 알 수 없습니다.** 그래서 페이지마다 `GET /user/me` 로 서버에 물어보고 헤더를 그립니다. 요청이 한 번 더 드는 대신 토큰 탈취 경로를 없앤 거래입니다.

```javascript
// 쿠키는 JS가 읽을 수 없으므로, 로그인 여부는 서버에 물어봐야 안다
async function getCurrentUser() {
    try { return await api.get("/user/me"); }
    catch { return null; }      // 401 등 → 비로그인
}
```

비밀번호는 bcrypt 로 해싱합니다. 가입 요청의 비밀번호 길이를 `max_length=72` 로 막아둔 건 bcrypt 가 72바이트를 넘는 입력을 조용히 잘라버리기 때문입니다. 그대로 두면 73자 이상 비밀번호가 앞 72바이트만 같아도 통과합니다.

---

## 이메일 OTP — 발급 제한을 Lua 스크립트로

가입 후 이메일 인증과 비밀번호 재설정에 6자리 코드를 씁니다. 코드는 Redis 에 3분 TTL 로 저장되고, 메일 발송은 `BackgroundTasks` 로 응답 뒤에 처리합니다.

**왜 용도별로 키를 나눴나.** `otp:{purpose}:{email}` 로 저장합니다. 키가 하나면 가입 인증용으로 받은 코드로 비밀번호를 바꿀 수 있습니다.

**왜 Lua 스크립트인가.** 발급 제한이 두 가지입니다 — 1분 쿨다운, 그리고 이메일·용도별 1시간 5회. 이걸 파이썬에서 "쿨다운 확인 → 횟수 확인 → 쿨다운 설정 → 횟수 증가" 로 처리하면 네 번의 왕복 사이에 다른 요청이 끼어듭니다. 동시에 열 번 누르면 열 통이 나갈 수 있습니다.

Redis 는 Lua 스크립트를 원자적으로 실행하므로, 확인과 등록을 한 덩어리로 묶었습니다.

```lua
if redis.call("EXISTS", cooldown_key) == 1 then return 0 end

local current_count = tonumber(redis.call("GET", count_key) or "0")
if current_count >= max_sends then return 0 end

redis.call("SET", cooldown_key, "1", "EX", cooldown_seconds)
local new_count = redis.call("INCR", count_key)
if new_count == 1 then redis.call("EXPIRE", count_key, window_seconds) end
return 1
```

코드 생성은 `random` 이 아니라 `secrets.randbelow` 입니다. `random` 은 시드를 알면 다음 값이 예측되는 의사난수라 인증 코드에 쓰면 안 됩니다.

---

## 권한 — 등급 하나가 아니라 기능별 스위치

회원마다 기능별 권한 6종을 켜고 끕니다. 가입 직후엔 댓글만 가능하고, 나머지는 관리자가 열어줍니다.

```python
PERMISSIONS = (
    ("can_comment",         "댓글"),
    ("can_write_post",      "글쓰기"),
    ("can_upload",          "이미지 업로드"),
    ("can_manage_category", "분류 관리"),
    ("can_manage_post",     "글 관리"),
    ("can_manage_user",     "회원 관리"),
)
```

**왜 등급제를 버렸나.** `admin / member / guest` 는 처음엔 단순하지만, "글은 쓰되 이미지는 못 올리는 사람"이나 "댓글만 막고 싶은 사람"이 생기는 순간 등급표를 다시 짜야 합니다. 등급을 하나 늘리면 기존 등급들과의 관계도 다시 정리해야 하고요. 플래그는 컬럼 하나만 늘리면 되고 조합이 자유롭습니다.

**왜 튜플로 이름을 모아뒀나.** 권한을 하나 추가하면 고칠 곳이 ORM 컬럼, 관리 화면 체크박스, 요청 스키마, 응답 스키마로 흩어집니다. 어딘가 하나 빠뜨리면 화면엔 체크박스가 있는데 저장이 안 되는 식으로 조용히 어긋납니다. `PERMISSION_NAMES` 하나가 관리 UI 렌더링과 `require_permission()` 의 오타 검사를 함께 구동해서, 최소한 이름이 틀리는 사고는 막습니다.

```python
def require_permission(permission: str):
    # 라우터가 데코레이터에서 부르므로, 권한 이름 오타는 서버 기동 시점에 바로 걸린다
    assert permission in PERMISSION_NAMES, f"unknown permission: {permission}"
```

오타가 요청이 들어올 때가 아니라 **서버가 뜰 때** 터지게 한 게 요점입니다.

### 401 과 403 을 구분하는 4단 게이트

권한 검사를 한 덩어리 함수로 만들지 않고 의존성 체인으로 쪼갰습니다.

```
get_current_user  →  get_verified_user  →  get_active_user  →  require_permission("...")
   401 누구인지 모름     403 이메일 미인증      403 정지·강퇴        403 권한 없음
```

**왜 쪼갰나.** 라우터마다 필요한 깊이가 다릅니다. **글 삭제는 `get_active_user` 가 아니라 `get_current_user` 를 씁니다** — 정지 중이라고 자기 글을 못 내리게 할 이유가 없기 때문입니다. 반대로 글 수정은 새 내용을 만드는 일이라 제재 중엔 막습니다. 한 덩어리였다면 이런 구분을 못 합니다.

상태 코드도 의미대로 나눴습니다. 401 은 "누구인지 모르겠으니 로그인해라", 403 은 "누구인지는 알지만 자격이 없다"입니다. 둘을 뭉뚱그리면 클라이언트가 로그인 페이지로 보낼지 안내 문구를 띄울지 판단할 수 없습니다.

---

## 제재 — 정지와 강퇴

기간 정지(`suspended_until`)와 영구 강퇴(`is_banned`)가 있습니다. 정지는 기한이 지나면 저절로 풀리고, 강퇴는 사람이 풀어야 합니다.

**왜 배치 작업이 없나.** 정지 만료를 처리하는 흔한 방법은 cron 으로 주기적으로 훑어 푸는 것입니다. 그런데 그러면 배치가 안 돌았을 때 사람이 계속 묶여 있고, 배치 주기만큼 오차가 생깁니다.

읽는 시점에 계산하면 그런 게 없습니다.

```python
@property
def is_suspended(self) -> bool:
    if self.suspended_until is None:
        return False
    # 컬럼이 timestamptz(시간대 포함)라 DB 에서 읽어도 aware. 그대로 비교하면 된다
    return self.suspended_until > datetime.now(timezone.utc)
```

**왜 제재 상태를 숨기지 않나.** 정지된 사람에게도 헤더에 "정지 ~날짜"를 그대로 보여줍니다. 이유 없이 기능만 안 되면 본인은 버그인 줄 알고, 문의할 근거도 없습니다.

---

## 글 — 소프트 삭제, 마크다운, 목록

작성·수정·삭제·복구, 분류 이동, 페이지네이션, 제목·본문·작성자 검색을 지원합니다.

### 지우지 않는 삭제

`DELETE /page/{id}` 는 `is_deleted` 플래그만 세웁니다.

**왜.** 실제로 지우면 그 글에 달린 댓글이 전부 고아가 됩니다. 그리고 관리자가 실수로 지운 글을 되살릴 방법이 없습니다. 복구(`POST /page/{id}/restore`)를 만들 수 있는 건 데이터가 남아 있기 때문입니다.

삭제된 글은 `can_manage_post` 권한자에게만 목록과 상세에 보입니다. 비로그인도 통과하는 옵셔널 인증으로 보는 사람을 판별합니다.

```python
# 관리자(글 관리 권한)만 삭제된 글도 목록에서 본다
include_deleted = viewer is not None and viewer.can_manage_post
```

### 썸네일을 쓸 때 한 번만 계산

본문에서 첫 이미지 주소를 정규식으로 뽑아 `thumbnail_url` 컬럼에 저장합니다. 목록에서 제목에 마우스를 올리면 그 이미지가 미리보기로 뜹니다.

**왜 컬럼에 저장하나.** 목록을 그릴 때마다 글 20개의 본문을 정규식으로 훑을 이유가 없습니다. 본문이 바뀌는 시점(작성·수정)에 한 번만 계산해 두면 됩니다. 읽기가 쓰기보다 압도적으로 잦은 데이터라 계산을 쓰기 쪽으로 옮기는 게 이득입니다.

### 목록 쿼리 — 집계 서브쿼리

글마다 댓글 수와 좋아요 수를 세면 글 20개에 쿼리 40번이 추가됩니다. 서브쿼리로 한 번에 조인합니다.

```python
comment_counts = (
    select(Comment.post_id, func.count(Comment.id).label("comment_count"))
    .where(Comment.is_deleted.is_(False))
    .group_by(Comment.post_id).subquery()
)
```

관계 로딩 전략도 용도별로 다르게 뒀습니다.

| 관계 | 전략 | 왜 |
|---|---|---|
| `Post.user`, `Post.category` | `joined` | N:1. 글 하나당 하나뿐이라 조인이 싸다 |
| `Post.comments` | `selectin` | 상세에 필요. 단 목록 쿼리는 `noload()` 로 끈다 |
| `User.posts`, `User.comments`, `Category.posts` | `raise` | 코드에서 안 읽는 역방향 |

마지막 줄이 중요합니다. 이 셋은 `back_populates` 짝일 뿐 어디서도 읽지 않는데, `selectin` 으로 두면 **회원을 한 명 조회할 때마다** 그 사람의 글을 본문까지 전부 읽고, 그 글들이 다시 작성자·분류를 물어 연쇄합니다. 옵셔널 인증이 걸린 모든 요청에서 벌어지던 일이었고, `lazy="raise"` 로 바꾸니 `get_user_by_id` 가 6 쿼리에서 1 쿼리가 됐습니다.

`raise` 를 고른 건 실수로 접근했을 때 **조용한 쿼리 폭주 대신 예외**가 나게 하기 위해서입니다. 성능 문제는 조용히 나빠질 때가 제일 위험합니다.

### 검색어 이스케이프

```python
escaped = query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
filters.append(or_(
    Post.title.ilike(f"%{escaped}%", escape="\\"),
    Post.contents.ilike(f"%{escaped}%", escape="\\"),
    Post.user.has(User.nickname.ilike(f"%{escaped}%", escape="\\")),
))
```

**왜.** `%` 와 `_` 는 SQL LIKE 의 와일드카드입니다. 이스케이프하지 않으면 사용자가 `%` 하나만 검색해도 전체 글이 나오고, `_` 는 아무 글자 하나와 매칭됩니다. 사용자 입력은 패턴이 아니라 문자 그대로 다뤄야 합니다.

---

## 댓글 — 1단계 대댓글과 자리표시자

`parent_id` 자기참조 FK 로 답글을 답니다. 깊이는 1단계로 제한합니다 — 답글에 답글은 못 답니다.

**왜 깊이를 제한하나.** 무한 중첩은 화면에서 들여쓰기가 감당이 안 되고, 조회할 때 재귀 쿼리가 필요합니다. 블로그 댓글에서 3단 이상 들어가는 대화는 드물고, 있어도 멘션으로 충분합니다. 제한은 DB 제약이 아니라 핸들러가 지킵니다.

**삭제된 댓글이 남는 경우.** 삭제된 원댓글에 살아 있는 답글이 하나라도 있으면 자리표시자로 남깁니다.

```python
# 삭제된 원댓글은 답글이 하나라도 살아 있으면 자리표시자로 남긴다.
# 지워버리면 답글이 무엇에 대한 답인지 알 수 없게 되기 때문이다.
# 삭제된 답글은 남길 이유가 없으므로 그냥 뺀다.
```

### 가리는 책임을 스키마에 뒀다

자리표시자의 내용과 작성자는 응답에서 지웁니다. 이걸 핸들러가 아니라 **응답 스키마**가 합니다.

```python
@model_validator(mode="after")
def hide_deleted(self):
    if self.is_deleted:
        self.user = None
        self.contents = ""
    return self
```

**왜.** 댓글이 실려 나가는 엔드포인트가 여럿입니다 — 글 상세, 댓글 작성, 댓글 수정, 글 복구, 분류 이동. 핸들러마다 가리면 새 엔드포인트를 만들 때 한 번만 빠뜨려도 삭제된 댓글 내용이 샙니다. 스키마에 두면 어느 경로로 만들어도 새지 않습니다.

---

## 좋아요와 조회수

### 좋아요 — 중복을 DB 제약으로

버튼을 한 번 더 누르면 취소되는 토글입니다. `(user_id, post_id)` 에 유니크 제약을 걸었습니다.

**왜 앱 로직이 아니라 제약인가.** "이미 눌렀는지 확인 → 없으면 추가" 사이에 다른 요청이 끼어들면 중복이 들어갑니다. 애플리케이션 코드로는 이 창을 완전히 닫을 수 없습니다. 제약을 걸고, 삽입은 `ON CONFLICT DO NOTHING` 으로 처리합니다.

```python
stmt = pg_insert(Like).values(...).on_conflict_do_nothing(constraint="uq_likes_user_post")
```

개수는 캐싱하지 않고 매번 셉니다. 이 규모에선 정확하고 단순한 쪽이 이득입니다.

### 조회수 — IP별 중복 방지

새로고침마다 오르면 숫자가 무의미해집니다. IP 마다 Redis 키를 두고, 없을 때만 셉니다.

```python
first_view = await redis.set(f"viewed:{post.id}:{ip}", "1", nx=True, ex=6 * 3600)
if first_view:
    post.view_count = await post_repo.increment_view_count(post.id)
```

**왜 `SET NX EX` 인가.** "키가 있나 확인 → 없으면 쓰기" 를 두 번의 명령으로 하면 그 사이에 다른 요청이 들어옵니다. `SET NX EX` 는 "없을 때만 쓰기 + 만료 설정"을 한 명령으로 처리합니다. 그리고 반환값이 곧 "내가 처음 썼는가" 라서 별도 확인이 필요 없습니다.

**왜 증가도 DB 에서 하나.**

```python
sa_update(Post).where(Post.id == post_id).values(view_count=Post.view_count + 1)
```

파이썬으로 읽어서 +1 해 저장하면(read-modify-write) 동시 요청에서 값이 유실됩니다. `view_count = view_count + 1` 은 DB 가 원자적으로 처리합니다.

삭제된 글은 관리자만 보므로 조회수를 세지 않습니다.

---

## 분류 — 삭제하면 글은 미분류로

생성·이름 변경·삭제와 사이드바 글 수 집계를 지원합니다.

**왜 삭제 시 글을 옮기나.** 글이 있는 분류를 지울 때 선택지는 셋입니다. 글을 같이 지우거나, 삭제를 막거나, 옮기거나. 첫째는 분류 정리하다 글이 날아가는 사고를 부르고, 둘째는 관리자가 아무것도 못 하게 만듭니다. 워드프레스 관례대로 **미분류로 옮기고 빈 분류를 지우는** 쪽을 택했습니다.

```python
async with _write_transaction(self.session):
    await self.session.execute(
        sa_update(Post).where(Post.category_id == category.id).values(category_id=fallback_id)
    )
    await self.session.delete(category)
```

두 작업을 한 트랜잭션으로 묶은 이유는, 중간에 실패하면 글은 옮겨졌는데 분류는 남아 있는 어정쩡한 상태가 되기 때문입니다.

`uncategorized` 분류 자체는 삭제할 수 없습니다 — 사라지면 재배치할 곳이 없어집니다. 이 분류는 관리 화면 청소용이라 **분류 관리 권한자에게만** 사이드바에 보입니다. 일반 방문자에게 "미분류(0)" 가 보일 이유가 없습니다.

사이드바 글 수는 분류마다 COUNT 를 날리지 않고 `GROUP BY` 로 한 번에 셉니다. `outerjoin` 이라 글이 하나도 없는 분류도 목록에 남습니다.

---

## 이미지 업로드 — 파일명도 Content-Type 도 믿지 않는다

에디터에서 이미지를 올리면 검증 후 저장하고 URL 을 돌려줍니다. 프로필 사진도 같은 서비스를 씁니다.

**왜 Pillow 로 실제 디코딩까지 하나.** 확장자와 `Content-Type` 은 클라이언트가 보내는 값이라 얼마든지 위조됩니다. `.jpg` 로 이름 붙인 실행 파일이나 스크립트가 들어올 수 있습니다. 그래서 세 겹으로 확인합니다.

1. `Content-Type` 이 허용 목록에 있는가
2. Pillow 로 실제 디코딩이 되는가, 그리고 그 포맷이 `Content-Type` 과 일치하는가
3. 해상도와 총 픽셀 수가 제한 안인가

3번은 **디컴프레션 폭탄** 방어입니다. 수십 KB 짜리 PNG 가 압축을 풀면 수억 픽셀이 되어 메모리를 터뜨릴 수 있습니다. 바이트 크기 제한만으로는 못 막습니다.

**왜 파일명을 새로 짓나.**

```python
# 이름은 UUID로 새로 짓는다 → 충돌·덮어쓰기·경로 탈출이 원천 차단된다.
filename = f"{uuid.uuid4().hex}{extension}"
```

사용자가 준 파일명을 쓰면 `../../etc/passwd` 같은 경로 탈출과 같은 이름 덮어쓰기가 열립니다. 확장자도 파일명이 아니라 허용 목록 표에서 정합니다.

**왜 다 읽고 나서 쓰나.** 스트리밍으로 쓰면서 크기를 검사하면 한도를 넘긴 시점에 이미 상당량이 디스크에 남습니다. 전부 메모리에 읽어 검사한 뒤 쓰는 쪽을 택했습니다. 5MB 제한이라 메모리 부담이 크지 않습니다.

**왜 임시 파일에 썼다가 교체하나.** `write_bytes` 도중에 프로세스가 죽으면 잘린 파일이 남습니다. 임시 파일에 다 쓰고 `replace` 로 바꾸면 원자적이라, 파일은 완전하거나 아예 없거나 둘 중 하나입니다. 디스크 I/O 는 `asyncio.to_thread` 로 이벤트 루프 밖에서 돌립니다.

---

## 그 밖의 공통 설계

**쓰기 트랜잭션 헬퍼.** 모든 쓰기를 `_write_transaction` 컨텍스트 매니저로 감쌉니다. 실패하면 rollback 하고 원래 예외를 다시 던집니다. 안 하면 세션이 더러운 채로 커넥션 풀에 돌아가 다음 요청이 엉뚱한 곳에서 터집니다.

**경합 대비 이중 방어.** 이메일·닉네임·분류 이름 중복은 먼저 조회해서 막되, 그 사이 다른 요청이 먼저 저장할 수 있으므로 `IntegrityError` 도 잡아 409 로 바꿉니다. 사전 조회는 사용자 경험(명확한 메시지), 제약은 정합성 보장 — 역할이 다릅니다.

**타임존.** 모든 시각 컬럼이 `timestamptz` 입니다. naive datetime 을 저장하면 서버 타임존이 바뀌는 순간 과거 데이터의 의미가 달라집니다.

---

## 실행

### 요구사항

PostgreSQL 16+, Redis 7+, Python 3.13, [uv](https://docs.astral.sh/uv/)

### 설정

```bash
git clone https://github.com/epqlffltm/fastapi-blog.git
cd fastapi-blog
uv sync

cp .env.example .env
```

```dotenv
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/blog
JWT_SECRET_KEY=            # openssl rand -hex 32
JWT_ALGORITHM=HS256
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
SMTP_HOST=smtp.gmail.com   # OTP 메일 발송용
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
COOKIE_SECURE=false        # 배포(HTTPS)에서 true
COOKIE_MAX_AGE=86400
UPLOAD_MAX_BYTES=5242880
```

### 기동

```bash
uv run alembic upgrade head     # 스키마 생성
uv run python -m app.seed       # 초기 분류·계정 (선택)
uv run uvicorn app.main:app --reload
```

`http://localhost:8000` — 화면
`http://localhost:8000/docs` — Swagger

관리자 권한이 필요하면:

```bash
uv run python -m app.promote your@email.com
```

### 테스트

```bash
uv run pytest
```

217개. 레포지토리를 `AsyncMock` 으로 갈아끼워 DB 없이 라우터·권한·검증 로직을 검증합니다. 레포지토리가 `Depends()` 로 주입되기 때문에 가능한 구조입니다.

---

## API

| 메서드 | 경로 | 설명 | 필요 권한 |
|---|---|---|---|
| GET | `/pages` | 글 목록 (`page`, `size`, `q`, `category`, `author`, `order`) | — |
| GET | `/page/{id}` | 글 상세 + 댓글 | — |
| POST | `/page` | 글 작성 | `can_write_post` |
| PATCH | `/page/{id}` | 글 수정 | 작성자 또는 `can_manage_post` |
| DELETE | `/page/{id}` | 소프트 삭제 | 작성자 또는 `can_manage_post` |
| POST | `/page/{id}/restore` | 삭제 복구 | `can_manage_post` |
| PATCH | `/page/{id}/category` | 분류 이동 | `can_manage_post` |
| GET·POST | `/page/{id}/like` | 좋아요 상태 / 토글 | 토글은 로그인 |
| POST | `/page/{post_id}/comment` | 댓글·대댓글 | `can_comment` |
| PATCH·DELETE | `/comment/{id}` | 댓글 수정·삭제 | 작성자 |
| GET·POST | `/categories` | 분류 목록 / 생성 | 생성은 `can_manage_category` |
| PATCH·DELETE | `/categories/{id}` | 이름 변경 / 삭제 | `can_manage_category` |
| POST | `/user/sign-up` · `/user/log-in` · `/user/log-out` | 가입·로그인·로그아웃 | — |
| GET·PATCH | `/user/me` | 내 정보 조회·수정 | 로그인 |
| POST | `/user/email/otp` · `/user/email/otp/verify` | 이메일 인증 | 로그인 |
| POST | `/user/password/reset` · `.../verify` | 비밀번호 재설정 | — |
| GET | `/user/list` | 회원 목록 | `can_manage_user` |
| PATCH | `/user/{id}/permissions` · `/suspend` · `/ban` | 권한·제재 | `can_manage_user` |
| POST | `/upload` | 이미지 업로드 | `can_upload` |

전체 스키마는 `/docs` 에 있습니다.

---

## 구조

```
app/
├── api/            라우터 — HTTP 만 안다
│   └── dependency.py   인증·권한 게이트
├── database/
│   ├── orm.py          모델, 관계 로딩 전략
│   ├── repository.py   DB 접근 계층
│   ├── connection.py   async 엔진, 설정
│   └── cache.py        Redis 클라이언트
├── schema/         요청·응답 (Pydantic)
├── service/        인증, OTP, 메일, 업로드, 마크다운, 댓글 표시 규칙
└── tests/
alembic/versions/   마이그레이션
static/             화면 (빌드 없음)
```

라우터는 HTTP 만, 레포지토리는 쿼리만, 서비스는 도메인 로직만 압니다. 이 경계 덕분에 댓글 표시 규칙 같은 로직을 DB 없이 단위 테스트할 수 있습니다.

---

## 알려진 한계

- **Redis 가 죽으면 글 상세가 500 입니다.** 조회수 중복 방지는 부가 기능인데 읽기를 막고 있습니다. `redis.set` 실패 시 조회수만 포기하도록 고쳐야 합니다.
- **단일 서버 전제.** 업로드 파일을 로컬 디스크에 저장하므로 인스턴스를 늘리려면 S3 같은 외부 스토리지가 필요합니다.
- **HS256 대칭키.** 서비스가 하나라 문제없지만, 인증 서버를 분리하면 RS256 + JWKS 로 바꿔야 합니다. 대칭키를 여러 서비스가 공유하면 검증만 해야 할 쪽이 토큰을 위조할 수 있습니다.
- **리프레시 토큰 없음.** 액세스 토큰 만료가 24시간이라 탈취 시 노출 창이 그만큼 깁니다.
- **검색이 `ILIKE`.** 글이 늘면 풀스캔이 부담됩니다. PostgreSQL 의 `pg_trgm` 인덱스나 전문 검색으로 옮겨야 합니다.
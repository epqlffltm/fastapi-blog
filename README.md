# fastapi-blog

[![CI](https://github.com/epqlffltm/fastapi-blog/actions/workflows/ci.yml/badge.svg)](https://github.com/epqlffltm/fastapi-blog/actions/workflows/ci.yml)

FastAPI + PostgreSQL 로 만든 블로그. 회원·권한·글·댓글·좋아요·이미지 업로드를 갖춘, 실제로 운영 가능한 수준의 백엔드를 목표로 했습니다.

```
Python 3.13 · FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL · Redis · Alembic · uv · Docker
```

Docker 만 있으면 `docker compose up -d` 로 바로 띄울 수 있습니다. 자세한 절차는 [실행](#실행)에 있습니다.

아래는 기능마다 **무엇을 하는지**와 **왜 그렇게 만들었는지**를 같이 적었습니다. 대안이 여럿이던 지점에서 무엇을 골랐고 무엇을 버렸는지가 이 저장소의 본론입니다.

프론트엔드는 빌드 도구 없는 순수 HTML/CSS/JS 입니다. 백엔드가 주제인 프로젝트에 프론트 도구 체인까지 얹으면 읽는 사람의 시선이 분산됩니다.

---

## 인증 — httpOnly 쿠키에 담은 JWT

로그인하면 서버가 JWT 를 발급해 `access_token` 쿠키에 담아 내려줍니다. 이후 모든 요청은 이 쿠키로 인증됩니다.

**왜 헤더가 아니라 쿠키인가.** `Authorization: Bearer` 방식은 토큰을 JS 가 들고 있어야 하고, 그러려면 `localStorage` 에 둘 수밖에 없습니다. XSS 가 한 번만 터지면 토큰이 통째로 나갑니다. `httpOnly` 쿠키는 JS 가 읽을 수 없어 그 경로가 막힙니다. `SameSite=Strict` 를 함께 걸어 크로스 사이트 요청에는 쿠키가 실리지 않게 했고, 그래서 별도 CSRF 토큰을 두지 않았습니다.

대신 대가가 있습니다. **프론트가 자기 로그인 여부를 알 수 없습니다.** 그래서 페이지마다 `GET /user/me` 로 서버에 물어보고 헤더를 그립니다. 요청이 한 번 더 드는 대신 토큰 탈취 경로를 없앤 거래입니다.

### 비밀번호 변경 시 기존 세션 무효화

JWT 는 서버가 상태를 들고 있지 않아 발급한 뒤에는 취소할 수 없습니다. 비밀번호가 털린 걸 알고 바꿔도 공격자의 토큰이 만료까지 살아 있으면 의미가 없습니다.

`users.token_version` 정수 컬럼을 두고 토큰에 `ver` 클레임으로 심습니다. 비밀번호를 바꾸면 이 값이 오르고, 그 전에 발급된 토큰은 전부 무효가 됩니다.

```python
def _session_version_matches(claims: JWTClaims, user: User) -> bool:
    return claims.token_version == int(user.token_version or 0)
```

배포 전에 발급된 토큰에는 `ver` 가 없으므로 0 으로 해석합니다. 상태를 완전히 서버에 두는 세션 방식만큼 강하진 않지만, 정수 컬럼 하나로 가장 필요한 취소 시나리오를 덮습니다.

### bcrypt 의 72바이트 한계

bcrypt 는 UTF-8 인코딩 후 72바이트를 넘는 입력을 처리하지 못합니다. 여기서 함정은 **문자 수와 바이트 수가 다르다**는 점입니다. 한글은 한 글자가 3바이트라, 25자 비밀번호는 75바이트가 되어 한도를 넘습니다.

`max_length=72` 를 문자 수로만 걸어두면 한글 25자 비밀번호가 스키마를 통과한 뒤 bcrypt 에서 예외가 나 회원가입이 500 으로 죽습니다. 그래서 바이트 길이로 검증합니다.

가입과 로그인의 처리도 다릅니다.

- **가입·변경**: 한도를 넘으면 422 로 거절 (정책 위반이므로 명확히 알려야 한다)
- **로그인**: 예외 없이 그냥 인증 실패로 처리 (기존 계정 정책과 무관하게 들어오는 입력이고, 여기서 500 을 내면 그 자체가 정보다)

### bcrypt 를 이벤트 루프 밖에서

bcrypt 는 일부러 느리게 설계된 CPU 작업이라 해시 한 번에 수백 ms 가 걸립니다. async 핸들러에서 그대로 부르면 그동안 이벤트 루프 전체가 멈춰 다른 요청이 밀립니다.

```python
async def verify_password_async(self, plain_password: str, hashed_password: str) -> bool:
    return await run_in_threadpool(self.verify_password, plain_password, hashed_password)
```

느린 게 목적인 연산이므로 없앨 수 없고, 격리하는 것이 답입니다.

---

## 로그인 실패 횟수 제한

계정별 15분에 5회, IP별 15분에 20회를 넘으면 429 로 막습니다.

**왜 두 축을 다 세나.** 계정별만 세면 공격자가 IP 하나로 계정 수천 개를 훑습니다(password spraying). IP별만 세면 봇넷이 IP 를 갈아타며 한 계정을 집중 공략합니다. 한쪽이라도 한도를 넘으면 차단합니다. IP 한도를 넉넉히 잡은 건 회사 NAT 뒤에 여러 사람이 있을 수 있어서입니다.

**왜 비밀번호 검증 '전에' 확인하나.** bcrypt 는 의도적으로 느립니다. 어차피 거절할 요청에 해시를 태우면 레이트리밋 자체가 CPU 고갈 공격 통로가 됩니다.

**응답 시간도 맞춥니다.** 메시지를 "invalid email or password" 로 통일해도, 없는 계정은 bcrypt 를 건너뛰어 응답이 60배 가까이 빨라집니다. 시간 자체가 가입 여부를 알려주는 셈입니다. 계정이 없을 때도 더미 해시로 검증을 한 번 수행해 비용을 맞췄습니다 (측정값 60.7배 → 0.99배).

**왜 성공 시 IP 카운터는 남기나.** 둘 다 지우면 공격자가 자기 계정 하나로 로그인해서 IP 한도를 초기화할 수 있습니다.

**Redis 장애 시 fail-open.** 레이트리밋은 완화 장치이고 1차 방어는 bcrypt 와 비밀번호 정책입니다. 캐시가 죽었다고 전 사용자의 로그인을 막는 쪽이 더 큰 사고라고 판단했고, 대신 로그는 남깁니다.

---

## 이메일 OTP — 발급도 검증도 원자적으로

가입 인증과 비밀번호 재설정에 6자리 코드를 씁니다. Redis 에 3분 TTL 로 저장하고, 메일 발송은 `BackgroundTasks` 로 응답 뒤에 처리합니다.

**왜 용도별로 키를 나눴나.** `otp:{purpose}:{email}` 로 저장합니다. 키가 하나면 가입 인증용으로 받은 코드로 비밀번호를 바꿀 수 있습니다.

### 발급 제한

1분 쿨다운과 이메일·용도별 1시간 5회를 겁니다. 이걸 파이썬에서 "쿨다운 확인 → 횟수 확인 → 쿨다운 설정 → 횟수 증가" 로 처리하면 네 번의 왕복 사이에 다른 요청이 끼어듭니다. 동시에 열 번 누르면 열 통이 나갈 수 있습니다. Redis 는 Lua 스크립트를 원자적으로 실행하므로 확인과 등록을 한 덩어리로 묶었습니다.

### 검증 제한 — 여기가 더 중요하다

발급만 막으면 절반입니다. **6자리는 100만 조합이고 창이 3분인데 검증 시도가 무제한이면** 초당 수백 건만 던져도 확률이 무시할 수 없는 수준이 됩니다. 그리고 이 OTP 는 비밀번호 재설정에 걸려 있어 뚫리면 계정이 넘어갑니다.

코드 하나당 5회로 제한하고, 한도에 닿으면 정답 코드까지 폐기합니다.

```lua
if new_attempts >= max_attempts then
    -- 한도에 도달하면 정답 코드도 폐기한다
    redis.call("DEL", otp_key)
    return -2
end
```

실패 카운터의 만료는 `PTTL` 로 읽은 OTP 의 잔여 시간에 맞춥니다. 별도 TTL 을 주면 코드가 사라진 뒤에도 카운터가 남아 다음 발급에 영향을 줍니다.

### 검증 성공 시 원자적 소비

`GET → 비교 → DELETE` 를 파이썬에서 나누면 같은 코드로 들어온 동시 요청이 **둘 다 성공**할 수 있습니다. 검증과 소비를 한 Lua 실행에 담아 하나만 성공하게 했습니다. 실제 Redis 를 띄운 통합 테스트로 동시 요청 중 정확히 하나만 통과하는지 확인합니다.

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

**왜 등급제를 버렸나.** `admin / member / guest` 는 처음엔 단순하지만, "글은 쓰되 이미지는 못 올리는 사람"이나 "댓글만 막고 싶은 사람"이 생기는 순간 등급표를 다시 짜야 합니다. 플래그는 컬럼 하나만 늘리면 되고 조합이 자유롭습니다.

**왜 튜플로 이름을 모아뒀나.** 권한을 하나 추가하면 고칠 곳이 ORM 컬럼, 관리 화면 체크박스, 요청·응답 스키마로 흩어집니다. 하나 빠뜨리면 화면엔 체크박스가 있는데 저장이 안 되는 식으로 조용히 어긋납니다. `PERMISSION_NAMES` 하나가 관리 UI 와 `require_permission()` 의 오타 검사를 함께 구동합니다.

```python
def require_permission(permission: str):
    # 라우터가 데코레이터에서 부르므로, 오타는 서버 기동 시점에 바로 걸린다
    assert permission in PERMISSION_NAMES, f"unknown permission: {permission}"
```

### 401 과 403 을 구분하는 4단 게이트

```
get_current_user  →  get_verified_user  →  get_active_user  →  require_permission("...")
   401 누구인지 모름     403 이메일 미인증      403 정지·강퇴        403 권한 없음
```

**왜 쪼갰나.** 라우터마다 필요한 깊이가 다릅니다. **글 삭제는 `get_active_user` 가 아니라 `get_current_user` 를 씁니다** — 정지 중이라고 자기 글을 못 내리게 할 이유가 없기 때문입니다. 반대로 글 수정은 새 내용을 만드는 일이라 제재 중엔 막습니다.

401 은 "누구인지 모르겠으니 로그인해라", 403 은 "누구인지는 알지만 자격이 없다"입니다. 둘을 뭉뚱그리면 클라이언트가 로그인 페이지로 보낼지 안내를 띄울지 판단할 수 없습니다.

---

## 시드 — 공개된 비밀번호를 심지 않는다

`python -m app.seed` 는 분류 4개와 **관리자 계정 하나**만 만듭니다.

이전 판본은 `seedpass123` 이라는 고정 비밀번호로 계정 9개를 만들고 그중 셋에 전권을 줬습니다. 로컬 테스트에는 편하지만, 배포한 서버에서 한 번만 돌리면 **비밀번호가 공개된 관리자 계정 셋**이 생깁니다. 시드는 개발용 스크립트가 아니라 배포 절차의 일부가 되기 쉬워서, 그 자체로 백도어가 됩니다.

그래서 계정 정보를 코드에서 빼고 설정에서 읽습니다.

```dotenv
SEED_ADMIN_EMAIL=        # 비우면 SMTP_USER 를 쓴다
SEED_ADMIN_PASSWORD=     # 8자 이상, UTF-8 72바이트 이하
SEED_ADMIN_NICKNAME=     # 비우면 이메일 앞부분
```

가입 폼과 같은 검증기(`is_bcrypt_password_length_valid`)를 씁니다. 시드만 다른 정책을 갖는 건 나중에 로그인이 안 되는 계정을 만드는 길입니다. 비밀번호는 어떤 경우에도 출력하지 않습니다.

**다시 돌려도 안전합니다.** 없는 분류만 추가하고, 계정이 이미 있으면 건드리지 않습니다. 특히 **기존 계정의 비밀번호를 덮어쓰지 않습니다** — 운영 중에 시드를 한 번 더 돌렸다고 관리자 비밀번호가 설정 파일 값으로 되돌아가면 그게 사고입니다.

`Settings` 가 `extra="forbid"` 라서 이 세 값도 정식 필드로 선언되어 있습니다. `.env` 에 모르는 키가 있으면 앱 전체가 기동을 거부하는데, 그건 오타를 잡아주는 장치라 풀지 않고 필드를 늘리는 쪽을 택했습니다.

---

## 제재 — 정지와 강퇴

기간 정지(`suspended_until`)와 영구 강퇴(`is_banned`)가 있습니다.

**왜 배치 작업이 없나.** 정지 만료를 cron 으로 훑어 푸는 방식은 배치가 안 돌면 사람이 계속 묶이고, 주기만큼 오차가 생깁니다. 읽는 시점에 계산하면 그런 게 없습니다.

```python
@property
def is_suspended(self) -> bool:
    if self.suspended_until is None:
        return False
    # timestamptz 라 DB 에서 읽어도 aware. 그대로 비교하면 된다
    return self.suspended_until > datetime.now(timezone.utc)
```

**왜 제재 상태를 숨기지 않나.** 정지된 사람에게도 헤더에 기한을 그대로 보여줍니다. 이유 없이 기능만 안 되면 본인은 버그인 줄 알고, 문의할 근거도 없습니다.

---

## 글 — 소프트 삭제, 마크다운, 목록

### 지우지 않는 삭제

`DELETE /page/{id}` 는 `is_deleted` 플래그만 세웁니다. 실제로 지우면 그 글에 달린 댓글이 고아가 되고, 실수로 지운 글을 되살릴 방법이 없습니다. 복구 기능이 가능한 건 데이터가 남아 있기 때문입니다.

삭제된 글은 `can_manage_post` 권한자에게만 보입니다. 비로그인도 통과하는 옵셔널 인증으로 보는 사람을 판별합니다.

### 썸네일을 쓸 때 한 번만 계산

본문에서 첫 이미지 주소를 뽑아 `thumbnail_url` 컬럼에 저장합니다. 목록을 그릴 때마다 글 20개의 본문을 정규식으로 훑을 이유가 없습니다. 읽기가 쓰기보다 압도적으로 잦은 데이터라 계산을 쓰기 쪽으로 옮기는 게 이득입니다.

### 목록 쿼리 — 집계 서브쿼리와 명시적 로딩 전략

글마다 댓글 수와 좋아요 수를 세면 글 20개에 쿼리 40번이 추가됩니다. 서브쿼리로 한 번에 조인합니다.

| 관계 | 전략 | 왜 |
|---|---|---|
| `Post.user`, `Post.category` | `joined` | N:1. 글 하나당 하나뿐이라 조인이 싸다 |
| `Post.comments` | `selectin` | 상세에 필요. 단 목록 쿼리는 `noload()` 로 끈다 |
| `User.posts`, `User.comments`, `Category.posts` | `raise` | 코드에서 안 읽는 역방향 |

마지막 줄이 중요합니다. 이 셋은 `back_populates` 짝일 뿐 어디서도 읽지 않는데, `selectin` 으로 두면 **회원을 한 명 조회할 때마다** 그 사람의 글을 본문까지 전부 읽고, 그 글들이 다시 작성자·분류를 물어 연쇄합니다. 인증이 걸린 모든 요청에서 벌어지던 일이었고, `lazy="raise"` 로 바꾸니 `get_user_by_id` 가 6 쿼리에서 1 쿼리가 됐습니다.

`raise` 를 고른 건 실수로 접근했을 때 **조용한 쿼리 폭주 대신 예외**가 나게 하기 위해서입니다. 성능 문제는 조용히 나빠질 때가 제일 위험합니다.

### 검색어 이스케이프

`%` 와 `_` 는 SQL LIKE 의 와일드카드입니다. 이스케이프하지 않으면 사용자가 `%` 하나만 검색해도 전체 글이 나옵니다. 사용자 입력은 패턴이 아니라 문자 그대로 다뤄야 합니다.

---

## 댓글 — 1단계 대댓글과 자리표시자

`parent_id` 자기참조 FK 로 답글을 답니다. 깊이는 1단계로 제한합니다.

**왜 제한하나.** 무한 중첩은 화면에서 들여쓰기가 감당이 안 되고 조회에 재귀 쿼리가 필요합니다. 블로그 댓글에서 3단 이상 대화는 드물고, 있어도 멘션으로 충분합니다.

삭제된 원댓글에 살아 있는 답글이 있으면 자리표시자로 남깁니다. 지워버리면 답글이 무엇에 대한 답인지 알 수 없게 되기 때문입니다.

### 가리는 책임을 스키마에 뒀다

```python
@model_validator(mode="after")
def hide_deleted(self):
    # 핸들러가 아니라 스키마가 막아야 어느 경로로 만들어도 새지 않는다
    if self.is_deleted:
        self.user = None
        self.contents = ""
    return self
```

댓글이 실려 나가는 엔드포인트가 여럿입니다 — 글 상세, 댓글 작성·수정, 글 복구, 분류 이동. 핸들러마다 가리면 새 엔드포인트를 만들 때 한 번만 빠뜨려도 내용이 샙니다.

### 삭제된 글의 댓글이 프로필로 새지 않게

프로필의 "작성한 댓글" 은 함정이 하나 있습니다. **댓글 자체는 살아 있어도 그 댓글이 달린 글이 삭제됐을 수 있습니다.** 댓글의 `is_deleted` 만 보면 삭제된 글의 내용이 프로필을 통해 노출됩니다.

그래서 이 조회만 별도 저장소로 분리하고, 두 조건을 함께 겁니다.

```python
if not include_deleted:
    filters.extend((
        Comment.is_deleted.is_(False),
        Post.is_deleted.is_(False),
    ))
```

일반 댓글 조회와 같은 클래스에 두면 다음에 누군가 편한 쪽을 골라 쓰다 조건 하나를 빠뜨립니다. 이름 자체가 용도를 말하도록(`ProfileCommentRepository`) 떼어냈습니다.

---

## 좋아요와 조회수

**좋아요 중복은 DB 제약으로 막습니다.** "이미 눌렀는지 확인 → 없으면 추가" 사이에 다른 요청이 끼어들면 중복이 들어갑니다. 애플리케이션 코드로는 이 창을 닫을 수 없습니다. `(user_id, post_id)` 유니크 제약을 걸고 `ON CONFLICT DO NOTHING` 으로 삽입합니다.

**조회수는 IP 마다 6시간 중복을 막습니다.**

```python
first_view = await redis.set(f"viewed:{post.id}:{ip}", "1", nx=True, ex=VIEW_DEDUP_TTL_SECONDS)
```

`SET NX EX` 는 "없을 때만 쓰기 + 만료"를 한 명령으로 처리하고, 반환값이 곧 "내가 처음 썼는가" 입니다. 증가도 `view_count = view_count + 1` 로 DB 에서 원자적으로 합니다. 파이썬으로 읽어서 +1 해 저장하면 동시 요청에서 값이 유실됩니다.

**Redis 가 죽어도 글은 읽힙니다.** 조회수 중복 방지는 부가 기능인데 이게 실패한다고 글 조회까지 막으면 안 됩니다. 예외를 잡아 로그만 남기고 조회수 증가만 포기합니다.

---

## 신뢰할 수 있는 클라이언트 IP

조회수 중복 방지와 로그인 레이트리밋이 IP 에 의존하는데, 여기엔 두 가지 실패 방식이 있습니다.

- 프록시 뒤에서 `request.client.host` 를 그대로 쓰면 **모든 방문자가 프록시 IP 하나로 묶입니다.**
- 반대로 `X-Forwarded-For` 를 무조건 믿으면 **아무나 헤더를 위조해 레이트리밋을 우회합니다.**

그래서 신뢰 경계를 명시적으로 둡니다. `TRUSTED_PROXY_CIDRS` 에 적힌 대역에서 온 연결만 헤더를 인정하고, 체인을 **오른쪽부터** 벗겨 첫 비신뢰 주소를 실제 클라이언트로 봅니다.

```python
hops = [*chain, peer]
index = len(hops) - 1
while index > 0 and _is_trusted(hops[index], raw_cidrs):
    index -= 1
return str(hops[index])
```

흔한 실수는 헤더의 **맨 왼쪽**을 쓰는 것입니다. 왼쪽은 사용자가 임의로 채워 보낼 수 있어 그대로 믿으면 위조가 통합니다. 설정이 비어 있으면 헤더를 아예 무시하므로, 프록시가 없는 로컬에서도 안전한 쪽이 기본값입니다.

---

## 이미지 업로드 — 파일명도 Content-Type 도 믿지 않는다

**왜 Pillow 로 실제 디코딩까지 하나.** 확장자와 `Content-Type` 은 클라이언트가 보내는 값이라 얼마든지 위조됩니다. 세 겹으로 확인합니다.

1. `Content-Type` 이 허용 목록에 있는가
2. Pillow 로 실제 디코딩이 되는가, 그 포맷이 `Content-Type` 과 일치하는가
3. 해상도와 총 픽셀 수가 제한 안인가

3번은 **디컴프레션 폭탄** 방어입니다. 수십 KB 짜리 PNG 가 압축을 풀면 수억 픽셀이 되어 메모리를 터뜨릴 수 있습니다. 바이트 크기 제한만으로는 못 막습니다.

**파일명은 UUID 로 새로 짓습니다.** 사용자가 준 이름을 쓰면 `../../etc/passwd` 같은 경로 탈출과 덮어쓰기가 열립니다.

**임시 파일에 썼다가 교체합니다.** 쓰는 도중 프로세스가 죽으면 잘린 파일이 남습니다. `replace` 는 원자적이라 파일은 완전하거나 아예 없거나 둘 중 하나입니다.

### 아바타 교체 시 이전 파일 정리

아바타를 바꾸면 이전 파일은 아무도 참조하지 않는 채 디스크에 남습니다. 그래서 **DB 갱신이 성공한 뒤에** 이전 파일을 지웁니다. 순서를 뒤집으면 DB 저장에 실패했을 때 참조는 남았는데 파일이 없는 상태가 됩니다. 반대로 업로드는 됐는데 DB 가 실패하면 새로 올린 파일을 지우고 URL 을 되돌립니다.

지울 대상은 **애플리케이션이 만든 파일만**으로 한정합니다.

```python
_MANAGED_FILENAME = re.compile(r"^[0-9a-f]{32}\.(?:jpg|png|gif|webp)$")
```

외부 URL, 쿼리 문자열이 붙은 주소, 경로 탈출 형태는 삭제 대상으로 인정하지 않습니다. 사용자가 넣은 값을 그대로 `unlink` 에 넘기면 그게 곧 임의 파일 삭제 취약점입니다.

---

## 프로필 — 하나의 화면, 두 개의 주소

| URL | 역할 | 누가 보나 |
|---|---|---|
| `/user/{id}` | 프로필 보기 (아바타·닉네임·소개·작성 글·댓글) | 누구나. **본인이든 남이든 화면이 같다** |
| `/profile` | 설정 (이메일·닉네임·소개·아바타·비밀번호) | 본인만 |

**왜 본인에게도 같은 화면을 보여주나.** 자기 닉네임을 누르면 남에게 보이는 그대로가 나옵니다. "내 프로필이 어떻게 보이는지" 를 따로 확인할 필요가 없습니다. 편집은 그 화면의 설정 버튼으로 한 번 더 들어갑니다.

공개 엔드포인트는 `PublicUserSchema` 만 내보냅니다 — id, 닉네임, 소개, 아바타. 이메일·권한·제재 상태는 **스키마 자체에 없어서** 실수로도 나갈 수 없습니다.

---

## 설정을 기동 시점에 검증한다

잘못된 설정은 조용히 넘어가는 대신 서버가 뜨지 않게 합니다.

- **`JWT_SECRET_KEY` 는 32바이트 이상.** 예제 값이나 짧은 키가 운영에 들어가면 서명을 무차별 대입으로 복원할 수 있습니다.
- **`JWT_ALGORITHM` 은 `Literal["HS256"]`.** 타입으로 고정해 `none` 같은 값이 설정으로 들어올 여지를 없앴습니다.
- **`TRUSTED_PROXY_CIDRS` 는 파싱 검증.** 오타가 나면 조용히 무시되는 게 아니라 기동이 거부됩니다. 무시되면 IP 신뢰 경계가 소리 없이 사라집니다.

런타임에 터지는 것보다 배포가 실패하는 쪽이 낫습니다.

---

## 컨테이너 — 비루트 실행과 볼륨 소유권

이미지는 두 단계로 나눠 만듭니다. 빌드 단계에서 uv 로 `.venv` 를 만들고, 실행 단계는 순수 파이썬 이미지에 그 결과만 가져옵니다. uv 도 빌드 도구도 최종 이미지에 남지 않아 크기와 공격면이 줍니다.

의존성을 소스보다 **먼저** 설치하는 것도 의도적입니다.

```dockerfile
RUN --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-dev

COPY . /app
```

코드 한 줄 고칠 때마다 패키지를 다시 받으면 재빌드가 못 쓸 만큼 느려집니다. `uv.lock` 이 그대로면 이 레이어는 캐시에서 재사용됩니다.

### 엔트리포인트가 필요한 이유

앱은 uid 1001 로 돕니다. 그런데 `Dockerfile` 에서 업로드 디렉터리를 그 유저 소유로 만들어도, compose 가 그 위에 볼륨을 마운트하면 **이미지에서 설정한 소유권이 덮이고 root 소유가 됩니다.** 결과는 업로드마다 `Permission denied` 입니다.

그래서 root 로 시작해 소유자만 맞추고 권한을 버립니다.

```sh
if [ "$(id -u)" = "0" ]; then
    if [ "$(stat -c '%u' "$UPLOAD_DIR")" != "$APP_UID" ]; then
        chown -R "$APP_UID:$APP_GID" "$UPLOAD_DIR"
    fi
    exec setpriv --reuid="$APP_UID" --regid="$APP_GID" --clear-groups "$@"
fi
exec "$@"
```

애플리케이션 프로세스 자체는 root 로 돌지 않습니다. PostgreSQL·Redis 공식 이미지가 쓰는 방식과 같습니다. 소유자가 이미 맞으면 `chown` 을 건너뛰고, 이름 대신 숫자 id 를 써서 이름 해석에 의존하지 않습니다.

### uvicorn 의 `--proxy-headers` 를 쓰지 않는다

보통은 붙이라고 하지만, 이 앱은 `client_ip.py` 에서 신뢰 대역 기준으로 `X-Forwarded-For` 를 직접 해석합니다. uvicorn 이 먼저 `request.client` 를 헤더 값으로 바꿔버리면, 그 코드가 "직접 연결한 상대" 라고 믿는 값이 이미 사용자가 보낸 값이 됩니다. 신뢰 경계가 통째로 무너지므로 둘 중 하나만 씁니다.

### compose

`depends_on` 에 `condition: service_healthy` 를 겁니다. 컨테이너가 **시작된 시점**과 **접속을 받는 시점**은 다릅니다. `pg_isready` 가 통과해야 앱이 뜹니다.

업로드는 볼륨(`uploads`)으로 뺐습니다. 이미지 안에 두면 컨테이너를 갈아끼울 때마다 사라집니다. Redis 는 영속화를 껐습니다 — OTP·레이트리밋 카운터·조회수 중복키는 전부 만료가 있는 임시 데이터입니다.

---

## 그 밖의 공통 설계

**쓰기 트랜잭션 헬퍼.** 모든 쓰기를 `_write_transaction` 으로 감쌉니다. 실패하면 rollback 하고 원래 예외를 다시 던집니다. 안 하면 세션이 더러운 채로 커넥션 풀에 돌아가 다음 요청이 엉뚱한 곳에서 터집니다.

**경합 대비 이중 방어.** 이메일·닉네임 중복은 먼저 조회해 막되, 그 사이 다른 요청이 먼저 저장할 수 있으므로 `IntegrityError` 도 잡아 409 로 바꿉니다. 사전 조회는 사용자 경험, 제약은 정합성 — 역할이 다릅니다.

**타임존.** 모든 시각 컬럼이 `timestamptz` 입니다. naive datetime 을 저장하면 서버 타임존이 바뀌는 순간 과거 데이터의 의미가 달라집니다.

**에디터 자산은 자체 호스팅.** 마크다운 에디터를 CDN 의 `latest` 로 물면 라이브러리가 breaking change 를 낼 때 커밋 하나 없이 사이트가 깨지고, CDN 이 오염되면 임의 JS 가 우리 오리진에서 실행됩니다. 인증이 쿠키라서 그 스크립트는 로그인한 사용자로 행세할 수 있습니다. `scripts/vendor_toastui.py` 로 버전을 고정해 받아 저장소에 커밋합니다.

**실패가 화면에 드러나게.** 프론트에서 `catch` 로 조용히 삼키지 않습니다. 목록이 비어 있는 것과 불러오지 못한 것은 다른 상태이고, 구분되지 않으면 매번 서버 로그부터 뒤지게 됩니다. 마크다운 뷰어를 못 쓰면 원문을 평문으로라도 보여줍니다.

---

## 실행

### 설정

```bash
git clone https://github.com/epqlffltm/fastapi-blog.git
cd fastapi-blog
cp .env.example .env
```

```dotenv
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/blog
JWT_SECRET_KEY=              # openssl rand -hex 32  (32바이트 미만이면 기동 실패)
JWT_ALGORITHM=HS256
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
SMTP_HOST=smtp.gmail.com     # OTP 메일 발송용
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
COOKIE_SECURE=false          # 배포(HTTPS)에서 true
COOKIE_MAX_AGE=86400
UPLOAD_MAX_BYTES=5242880
TRUSTED_PROXY_CIDRS=         # 프록시 뒤에 둘 때만. 예) 10.0.0.0/8
SEED_ADMIN_EMAIL=            # 비우면 SMTP_USER 를 쓴다
SEED_ADMIN_PASSWORD=         # 시드로 만들 관리자 비밀번호 (8자 이상)
SEED_ADMIN_NICKNAME=
```

`DATABASE_URL` 과 `REDIS_HOST` 는 도커로 띄우면 compose 가 덮어쓰므로 그대로 두셔도 됩니다.

### 기동 — 도커 (권장)

PostgreSQL·Redis 를 따로 설치할 필요가 없습니다. Docker 만 있으면 됩니다.

```bash
docker compose build
docker compose run --rm app alembic upgrade head
docker compose run --rm app python -m app.seed
docker compose up -d
```

`http://localhost:8000` — 화면 / `http://localhost:8000/docs` — Swagger

마이그레이션을 컨테이너 엔트리포인트가 아니라 **별도 명령으로** 돌립니다. 엔트리포인트에 넣으면 인스턴스를 둘로 늘리는 순간 동시에 실행됩니다.

평소에 쓰는 명령은 이 정도입니다.

```bash
docker compose up -d              # 시작
docker compose down               # 정지 (-v 를 붙이면 볼륨까지 지워져 글이 날아간다)
docker compose logs -f app        # 로그
docker compose up -d --build app  # 코드를 고친 뒤
```

소스는 이미지에 구워집니다. 호스트 파일만 고치고 재빌드하지 않으면 컨테이너 안은 예전 코드 그대로입니다.

### 기동 — 로컬 직접 실행

PostgreSQL 16+, Redis 7+, Python 3.13, [uv](https://docs.astral.sh/uv/) 가 필요합니다.

```bash
uv sync
uv run python scripts/vendor_toastui.py 3.2.2   # 에디터 자산 (최초 1회)
uv run alembic upgrade head
uv run python -m app.seed
uv run uvicorn app.main:app --reload
```

관리자 권한을 나중에 조정하려면: `uv run python -m app.promote your@email.com` (회수는 뒤에 `revoke`)

### 테스트

```bash
uv run pytest -m "not integration"   # 단위 (DB·Redis 불필요)
uv run pytest -m integration         # 실제 PostgreSQL·Redis 필요
```

단위 테스트는 레포지토리를 `AsyncMock` 으로 갈아끼워 라우터·권한·검증 로직을 검증합니다. 레포지토리가 `Depends()` 로 주입되기 때문에 가능한 구조입니다.

다만 목으로는 **실제 SQL 과 Redis 의 원자성을 확인할 수 없습니다.** 그래서 통합 테스트를 따로 두고, 목으로는 증명이 안 되는 것만 검증합니다.

- 마이그레이션이 실제로 적용되고 삭제된 글의 댓글이 프로필로 새지 않는가
- 같은 OTP 로 들어온 동시 요청 중 정확히 하나만 성공하는가
- 검증 실패 한도가 실제 Redis 에서 동작하고 재발급으로 초기화되는가

### CI

`push` 와 `pull_request` 마다 GitHub Actions 가 PostgreSQL·Redis 컨테이너를 띄우고 다음을 돌립니다.

1. 문법 검사 (`compileall`)
2. Ruff 정확성 규칙 (`E9,F63,F7,F82,F401` — 스타일이 아니라 실제 오류와 미사용 import 만)
3. **마이그레이션 왕복** (`upgrade head` → `downgrade base` → `upgrade head`)
4. **의존성 취약점 검사** (`pip-audit`)
5. 단위 테스트
6. 통합 테스트

3번은 자주 빠지는 검사입니다. `downgrade` 를 안 쓴다고 방치하면 롤백이 필요한 순간에 그게 깨져 있다는 걸 알게 됩니다.

4번을 넣은 이유는, 코드가 멀쩡해도 라이브러리를 통해 들어오는 구멍이 있기 때문입니다. 에디터 자산을 CDN 에서 저장소로 옮긴 것과 같은 맥락입니다.

---

## API

| 메서드 | 경로 | 설명 | 필요 권한 |
|---|---|---|---|
| GET | `/pages` | 글 목록 (`page`, `size`, `q`, `category`, `author`, `order`) | — |
| GET | `/page/{id}` | 글 상세 + 댓글 | — |
| POST | `/page` | 글 작성 | `can_write_post` |
| PATCH·DELETE | `/page/{id}` | 수정 / 소프트 삭제 | 작성자 또는 `can_manage_post` |
| POST | `/page/{id}/restore` | 삭제 복구 | `can_manage_post` |
| PATCH | `/page/{id}/category` | 분류 이동 | `can_manage_post` |
| GET·POST | `/page/{id}/like` | 좋아요 상태 / 토글 | 토글은 로그인 |
| POST | `/page/{post_id}/comment` | 댓글·대댓글 | `can_comment` |
| PATCH·DELETE | `/comment/{id}` | 댓글 수정·삭제 | 작성자 |
| GET·POST | `/categories` | 분류 목록 / 생성 | 생성은 `can_manage_category` |
| PATCH·DELETE | `/categories/{id}` | 이름 변경 / 삭제 | `can_manage_category` |
| POST | `/user/sign-up` · `/user/log-in` · `/user/log-out` | 가입·로그인·로그아웃 | — |
| GET·PATCH | `/user/me` | 내 정보 조회·수정 | 로그인 |
| PATCH | `/user/me/password` | 비밀번호 변경 (기존 세션 무효화) | 로그인 |
| POST | `/user/me/avatar` | 프로필 이미지 | 로그인 |
| GET | `/user/{id}/profile` · `/user/{id}/comments` | 공개 프로필 / 작성 댓글 | — |
| POST | `/user/password/reset` · `.../verify` | 비밀번호 재설정 | — |
| GET | `/user/list` | 회원 목록 | `can_manage_user` |
| PATCH | `/user/{id}/permissions` · `/suspend` · `/ban` | 권한·제재 | `can_manage_user` |
| POST | `/upload` | 이미지 업로드 | `can_upload` |

전체 스키마는 `/docs` 에 있습니다.

---

## 구조

```
app/
├── api/                    라우터 — HTTP 만 안다
│   └── dependency.py           인증·권한 게이트
├── database/
│   ├── orm.py                  모델, 관계 로딩 전략
│   ├── repository.py           DB 접근 계층
│   ├── profile_repository.py   공개 프로필 전용 조회 (삭제 글 필터 포함)
│   ├── connection.py           async 엔진, 설정 검증
│   └── cache.py                Redis 클라이언트
├── schema/                 요청·응답 (Pydantic)
├── service/                인증, OTP, 레이트리밋, 클라이언트 IP, 업로드, 마크다운
└── tests/
    └── integration/            실제 PostgreSQL·Redis 필요
alembic/versions/           마이그레이션
scripts/                    에디터 자산 벤더링
static/                     화면 (빌드 없음)
Dockerfile                  멀티스테이지 빌드 (uv → 런타임)
docker-entrypoint.sh        볼륨 소유권 조정 후 비루트로 강등
docker-compose.yml          app + postgres + redis
```

라우터는 HTTP 만, 레포지토리는 쿼리만, 서비스는 도메인 로직만 압니다.

---

## 알려진 한계

- **본문 이미지의 고아 파일.** 아바타는 정리하지만, 글에 넣은 이미지는 글을 지우거나 바꿔도 디스크에 남습니다.
- **관리자 행위 로그가 없습니다.** 누가 누구를 언제 정지·강퇴했는지, 권한을 누가 열어줬는지 흔적이 없습니다. 마지막 관리자가 자기 권한을 회수하면 아무도 회원 관리를 못 하게 되는 잠김도 막혀 있지 않습니다.
- **글·댓글 작성에 레이트리밋이 없습니다.** 권한 플래그는 "할 수 있나"만 보고 "얼마나 자주"는 보지 않습니다.
- **단일 서버 전제.** 업로드를 로컬 디스크(`static/img/`)에 저장합니다. 도커에서는 볼륨으로 빼 두어 컨테이너를 갈아끼워도 남지만, 인스턴스를 여럿으로 늘리려면 S3 같은 외부 스토리지가 필요합니다. 런타임 데이터라 버전 관리에서는 제외되어 있습니다.
- **업로드 오류 메시지가 불친절합니다.** 확장자와 실제 형식이 다르면 `file type does not match content` 만 나옵니다. 웹에서 받은 이미지가 `.jpg` 이름에 WebP 내용인 경우가 흔한데, 사용자는 무엇을 고쳐야 할지 알 수 없습니다. 감지된 형식을 응답에 담아야 합니다.
- **HS256 대칭키.** 서비스가 하나라 문제없지만, 인증 서버를 분리하면 RS256 + JWKS 로 바꿔야 합니다. 대칭키를 여러 서비스가 공유하면 검증만 해야 할 쪽이 토큰을 위조할 수 있습니다.
- **리프레시 토큰 없음.** 액세스 토큰 만료가 24시간이라 탈취 시 노출 창이 그만큼 깁니다.
- **검색이 `ILIKE`.** 글이 늘면 풀스캔이 부담됩니다. `pg_trgm` 인덱스나 전문 검색으로 옮겨야 합니다.
- **회원 탈퇴가 없습니다.**

---

## 라이선스

MIT. `LICENSE` 파일을 참고하세요.
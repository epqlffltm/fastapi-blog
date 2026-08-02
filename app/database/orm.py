#app/database/orm.py

'''
2026-07-20
orm 모델링 (posts, comments, images)
get 전체조회 api

2026-07-21
create classmethod 추가 (post api)

2026-07-23
회원 테이블
nickname → user_id FK 전환

2026-07-24
분류(categories) 테이블 추가
images → uploads (업로드 파일 기록) 전환, 본문 썸네일
대댓글 (parent_id 자기참조 FK, 1단계)
role → 권한 체크박스 / 정지 · 강퇴

2026-07-26
조회수 컬럼 / 좋아요(likes) 테이블

2026-07-28
비밀번호 변경 시 기존 JWT를 무효화하는 token_version 추가

2026-07-30
관리자 행위 감사 로그(admin_audit_logs) 추가
'''

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

# 변경 전후 값은 키가 고정되지 않은 dict 다.
# PostgreSQL 에서는 JSONB, 그 외(테스트용 SQLite)에서는 JSON 으로 저장한다.
# JSONB 는 파싱된 형태로 보관해 조회와 인덱싱이 가능하다
_JSON_DICT = JSON().with_variant(JSONB(), "postgresql")

from .connection import Base    # connection의 Base 재사용 (새로 만들지 않음)


# 관리 화면의 체크박스와 1:1. 순서가 곧 화면 순서다.
# 새 권한을 추가하려면 여기에 한 줄 넣고, User에 같은 이름의 컬럼을 추가하고,
# request.PermissionUpdateRequest / response.UserSchema 에도 같은 필드를 더한다
PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("can_comment", "댓글"),
    ("can_write_post", "글쓰기"),
    ("can_upload", "이미지 업로드"),
    ("can_manage_category", "분류 관리"),
    ("can_manage_post", "글 관리"),
    ("can_manage_user", "회원 관리"),
)

PERMISSION_NAMES: tuple[str, ...] = tuple(name for name, _ in PERMISSIONS)


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    title: Mapped[str]
    contents: Mapped[str]                              # 마크다운 원문
    thumbnail_url: Mapped[str | None] = mapped_column(String(512), default=None)
    is_deleted: Mapped[bool] = mapped_column(default=False)
    view_count: Mapped[int] = mapped_column(default=0)   # 글 조회수

    # N:1 이라 joined 로딩이 적합 (글 하나당 작성자·분류 하나)
    user: Mapped["User"] = relationship(back_populates="posts", lazy="joined")
    category: Mapped["Category"] = relationship(back_populates="posts", lazy="joined")
    comments: Mapped[list["Comment"]] = relationship(back_populates="post", lazy="selectin")

    def __repr__(self):
        return f"Post(id={self.id}, title={self.title})"

    @classmethod
    def create(cls, request, user_id: int) -> "Post":
        now = datetime.now(timezone.utc)
        return cls(
            title=request.title,
            contents=request.contents,
            user_id=user_id,          # 작성자는 요청이 아니라 토큰에서 온다
            category_id=request.category_id,
            created_at=now,
            updated_at=now,
        )


class Comment(Base):
    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    # 자기 테이블을 가리킨다. None 이면 원댓글, 값이 있으면 그 댓글의 답글.
    # 깊이 1 제한은 DB가 아니라 핸들러가 지킨다 (답글에 답글을 막는다)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id"), index=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    contents: Mapped[str]
    is_deleted: Mapped[bool] = mapped_column(default=False)

    post: Mapped["Post"] = relationship(back_populates="comments")
    user: Mapped["User"] = relationship(back_populates="comments", lazy="joined")

    def __repr__(self):
        return f"Comment(id={self.id}, post_id={self.post_id}, parent_id={self.parent_id})"

    @classmethod
    def create(cls, request, post_id: int, user_id: int) -> "Comment":
        now = datetime.now(timezone.utc)
        return cls(
            post_id=post_id,
            user_id=user_id,
            parent_id=request.parent_id,
            contents=request.contents,
            created_at=now,
            updated_at=now,
        )


class Upload(Base):    # 업로드된 파일 기록 (본문 위치는 마크다운이 갖는다)
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    filename: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    original_name: Mapped[str] = mapped_column(String(256))
    content_type: Mapped[str] = mapped_column(String(64))
    size: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    def __repr__(self):
        return f"Upload(id={self.id}, filename={self.filename})"

    @classmethod
    def create(
        cls, user_id: int, filename: str, original_name: str,
        content_type: str, size: int,
    ) -> "Upload":
        return cls(
            user_id=user_id,
            filename=filename,
            original_name=original_name,
            content_type=content_type,
            size=size,
            created_at=datetime.now(timezone.utc),
        )


class User(Base):    # 회원 테이블
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    password: Mapped[str] = mapped_column(String(256))
    token_version: Mapped[int] = mapped_column(default=0)
    nickname: Mapped[str] = mapped_column(String(64), unique=True)
    is_verified: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    bio: Mapped[str | None] = mapped_column(String(500), default=None)   # 자기소개
    avatar_url: Mapped[str | None] = mapped_column(String(255), default=None)   # 프로필 이미지 URL

    # 권한 — 등급 하나가 아니라 기능별로 켜고 끈다.
    # 새 기능이 생기면 컬럼 하나만 늘리면 되고, 등급표를 다시 짤 필요가 없다
    can_comment: Mapped[bool] = mapped_column(default=True)
    can_write_post: Mapped[bool] = mapped_column(default=False)
    can_upload: Mapped[bool] = mapped_column(default=False)
    can_manage_category: Mapped[bool] = mapped_column(default=False)
    can_manage_user: Mapped[bool] = mapped_column(default=False)
    can_manage_post: Mapped[bool] = mapped_column(default=False)

    # 제재 — 정지는 기한이 지나면 저절로 풀리고, 강퇴는 사람이 풀어야 한다
    suspended_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    is_banned: Mapped[bool] = mapped_column(default=False)

    # back_populates 를 위한 역방향일 뿐, 코드에서 한 번도 읽지 않는다.
    # selectin 이면 User 를 한 명 읽을 때마다 그 사람의 글·댓글을 전부 끌고 오고,
    # 글은 다시 user·category 를 joined 로 물어 연쇄가 된다 (로그인 상태의 모든 요청에서).
    # raise 로 두면 실수로 접근하는 순간 조용한 쿼리 폭주 대신 예외로 드러난다
    posts: Mapped[list["Post"]] = relationship(back_populates="user", lazy="raise")
    comments: Mapped[list["Comment"]] = relationship(back_populates="user", lazy="raise")

    def __repr__(self):
        return f"User(id={self.id}, email={self.email})"

    @property
    def is_suspended(self) -> bool:
        if self.suspended_until is None:
            return False
        # 컬럼이 timestamptz(시간대 포함)라 DB 에서 읽어도 aware. 그대로 비교하면 된다
        return self.suspended_until > datetime.now(timezone.utc)

    @property
    def is_active(self) -> bool:
        return not self.is_banned and not self.is_suspended

    def grant_all(self) -> None:
        for name in PERMISSION_NAMES:
            setattr(self, name, True)

    def revoke_all(self) -> None:
        for name in PERMISSION_NAMES:
            setattr(self, name, False)

    @classmethod
    def create(cls, email: str, hashed_password: str, nickname: str) -> "User":
        # 반드시 해싱된 비번을 받는다 (평문 저장 금지)
        # 가입 직후엔 댓글만. 나머지는 관리자가 켜준다
        return cls(
            email=email,
            password=hashed_password,
            token_version=0,
            nickname=nickname,
            can_comment=True,
            can_write_post=False,
            can_upload=False,
            can_manage_category=False,
            can_manage_post=False,
            can_manage_user=False,
            suspended_until=None,
            is_banned=False,
            created_at=datetime.now(timezone.utc),
        )


class Category(Base):    # 글 분류 (사이드바)
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    slug: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # URL에 쓰는 이름
    name: Mapped[str] = mapped_column(String(32), unique=True)              # 화면에 보이는 이름
    display_order: Mapped[int] = mapped_column(default=0)

    # User 쪽과 같은 이유. 사이드바 글 수는 GROUP BY 로 따로 센다
    posts: Mapped[list["Post"]] = relationship(back_populates="category", lazy="raise")

    def __repr__(self):
        return f"Category(id={self.id}, slug={self.slug})"

    @classmethod
    def create(cls, request) -> "Category":
        return cls(
            slug=request.slug,
            name=request.name,
            display_order=request.display_order,
        )


class Like(Base):    # 글 좋아요
    __tablename__ = "likes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    post_id: Mapped[int] = mapped_column(ForeignKey("posts.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # (user_id, post_id) 조합을 유일하게 — 한 사람이 같은 글에 두 번 좋아요 못 누른다.
    # 중복 방지를 앱 로직이 아니라 DB 제약으로 보장한다
    __table_args__ = (
        UniqueConstraint("user_id", "post_id", name="uq_likes_user_post"),
    )

    def __repr__(self):
        return f"Like(user_id={self.user_id}, post_id={self.post_id})"

    @classmethod
    def create(cls, user_id: int, post_id: int) -> "Like":
        return cls(
            user_id=user_id,
            post_id=post_id,
            created_at=datetime.now(timezone.utc),
        )


class AdminAuditLog(Base):    # 관리자 행위 기록
    """누가 언제 누구에게 무엇을 했는지 남긴다.

    권한을 여닫고 계정을 정지·강퇴하는 기능은 흔적이 없으면 미완성이다.
    이 표는 append-only 로 다룬다 — 수정·삭제 API 를 두지 않는다.
    고칠 수 있는 기록은 기록이 아니다.
    """

    __tablename__ = "admin_audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)

    # 행위자. 계정이 지워져도 기록은 남아야 하므로 FK 만 걸고 관계는 두지 않는다.
    # 안 읽는 관계를 두면 조용한 쿼리 폭주의 씨앗이 된다 (User.posts 와 같은 이유)
    actor_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    # "user.permissions.update" 처럼 점으로 구분한 행위 이름
    action: Mapped[str] = mapped_column(String(64), index=True)

    # 대상. 지금은 user 뿐이지만 나중에 post·category 로 넓힐 수 있게 종류를 같이 둔다
    target_type: Mapped[str] = mapped_column(String(32), default="user")
    target_id: Mapped[int] = mapped_column(index=True)

    # 전체 스냅샷이 아니라 '바뀐 키만' 담는다. 무엇이 달라졌는지가 바로 읽힌다
    before_data: Mapped[dict] = mapped_column(_JSON_DICT, default=dict)
    after_data: Mapped[dict] = mapped_column(_JSON_DICT, default=dict)

    # client_ip 로 해석한 실제 클라이언트 주소 (프록시 뒤에서도 정확).
    # IPv6 최대 45자
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    def __repr__(self):
        return (
            f"AdminAuditLog(id={self.id}, action={self.action}, "
            f"actor={self.actor_user_id}, target={self.target_id})"
        )

    @classmethod
    def create(
        cls,
        *,
        actor_user_id: int,
        action: str,
        target_id: int,
        before_data: dict,
        after_data: dict,
        ip_address: str | None = None,
        target_type: str = "user",
    ) -> "AdminAuditLog":
        return cls(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            before_data=before_data,
            after_data=after_data,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc),
        )
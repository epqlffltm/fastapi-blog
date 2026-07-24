#app/seed.py

'''
2026-07-20
초기 테스트 데이터를 DB에 넣는 시드 스크립트 (최초 1회)

2026-07-23
회원 먼저 생성 후 글/댓글을 user_id로 연결

2026-07-24
시드 계정은 인증됨으로 생성
분류(사이드바) 추가
본문을 마크다운으로 / 대댓글 예시 추가
회원 등급 / dnd 밈 3개
'''

from datetime import datetime
from .database.connection import SessionFactory
from .database.orm import Post, Comment, User, Category, UserRole
from .service.auth import AuthService
from .service.markdown import extract_first_image


# 분류 (slug: URL용 / name: 화면 표시용)
categories_data = [
    {"slug": "dnd", "name": "TRPG", "display_order": 0},
    {"slug": "dev", "name": "개발", "display_order": 1},
    {"slug": "daily", "name": "일상", "display_order": 2},
]

# 시드 계정 (비번은 전부 seedpass123)
# 글쓴이는 관리자, 나머지는 일반 회원
users_data = [
    {"nickname": "hong", "role": UserRole.ADMIN},
    {"nickname": "gil", "role": UserRole.ADMIN},
    {"nickname": "dong", "role": UserRole.ADMIN},
    {"nickname": "kim", "role": UserRole.MEMBER},
    {"nickname": "lee", "role": UserRole.MEMBER},
    {"nickname": "park", "role": UserRole.MEMBER},
    {"nickname": "choi", "role": UserRole.MEMBER},
    {"nickname": "jung", "role": UserRole.MEMBER},
    {"nickname": "yoon", "role": UserRole.MEMBER},
]

# reply_to: 같은 글 안에서 몇 번째 댓글에 달린 답글인지 (0부터). None 이면 원댓글
posts_data = [
    {
        "author": "hong",
        "category": "dnd",
        "created_at": datetime.fromisoformat("2026-07-16T09:00:00+00:00"),
        "updated_at": datetime.fromisoformat("2026-07-16T09:00:00+00:00"),
        "title": "dnd 밈1",
        "contents": "새로온 파티원이 로그일때 로그의 말은 '나로는 부족해?'",
        "comments": [
            {"author": "kim", "reply_to": None,
             "created_at": datetime.fromisoformat("2026-07-16T09:10:00+00:00"),
             "updated_at": datetime.fromisoformat("2026-07-16T09:10:00+00:00"),
             "contents": "응, 로그 실력이 부족해"},
            {"author": "lee", "reply_to": 0,
             "created_at": datetime.fromisoformat("2026-07-16T09:15:00+00:00"),
             "updated_at": datetime.fromisoformat("2026-07-16T09:15:00+00:00"),
             "contents": "그건 좀 심했다"},
            {"author": "park", "reply_to": None,
             "created_at": datetime.fromisoformat("2026-07-16T09:20:00+00:00"),
             "updated_at": datetime.fromisoformat("2026-07-16T09:20:00+00:00"),
             "contents": "로그 수는 부족하진 않아"},
        ],
    },
    {
        "author": "gil",
        "category": "dnd",
        "created_at": datetime.fromisoformat("2026-07-16T10:30:00+00:00"),
        "updated_at": datetime.fromisoformat("2026-07-16T10:30:00+00:00"),
        "title": "dnd 밈2",
        "contents": "새로온 파티원이 바바리안일때 바바리안 왈 '바바리안, 뭉치면 강하다'",
        "comments": [
            {"author": "park", "reply_to": None,
             "created_at": datetime.fromisoformat("2026-07-16T10:40:00+00:00"),
             "updated_at": datetime.fromisoformat("2026-07-16T10:40:00+00:00"),
             "contents": "바바리안, 계획이 있다"},
            {"author": "choi", "reply_to": 0,
             "created_at": datetime.fromisoformat("2026-07-16T10:45:00+00:00"),
             "updated_at": datetime.fromisoformat("2026-07-16T10:45:00+00:00"),
             "contents": "바바리안, 계획은 도끼질이다"},
            {"author": "jung", "reply_to": None,
             "created_at": datetime.fromisoformat("2026-07-16T10:50:00+00:00"),
             "updated_at": datetime.fromisoformat("2026-07-16T10:50:00+00:00"),
             "contents": "바바리안, 찢고 죽인다"},
        ],
    },
    {
        "author": "dong",
        "category": "dnd",
        "created_at": datetime.fromisoformat("2026-07-16T14:15:00+00:00"),
        "updated_at": datetime.fromisoformat("2026-07-16T14:15:00+00:00"),
        "title": "dnd 밈3",
        "contents": "둥그런 선술집을 지으세요",
        "comments": [
            {"author": "yoon", "reply_to": None,
             "created_at": datetime.fromisoformat("2026-07-16T14:25:00+00:00"),
             "updated_at": datetime.fromisoformat("2026-07-16T14:25:00+00:00"),
             "contents": "로그가 구석에서 비릿한 웃음을 짓지 못하도록"},
            {"author": "kim", "reply_to": 0,
             "created_at": datetime.fromisoformat("2026-07-16T14:30:00+00:00"),
             "updated_at": datetime.fromisoformat("2026-07-16T14:30:00+00:00"),
             "contents": "구석이 없으면 웃을 곳도 없다"},
        ],
    },
    {
        "author": "hong",
        "category": "dev",
        "created_at": datetime.fromisoformat("2026-07-17T11:00:00+00:00"),
        "updated_at": datetime.fromisoformat("2026-07-17T11:00:00+00:00"),
        "title": "마크다운 확인용",
        "contents": (
            "## 코드 블록\n\n"
            "```python\n"
            "@router.get('/pages', status_code=200)\n"
            "def get_pages_handler():\n"
            "    ...\n"
            "```\n\n"
            "### 목록\n\n"
            "- 위지윅으로 쓰고\n"
            "- 마크다운으로 저장한다\n\n"
            "> 인용문도 된다\n"
        ),
        "comments": [],
    },
]


def seed():
    session = SessionFactory()
    auth_service = AuthService()
    try:
        # 1) 분류
        slug_to_category = {}
        for cdata in categories_data:
            category = Category(**cdata)
            session.add(category)
            slug_to_category[cdata["slug"]] = category

        # 2) 회원 (글이 user_id 를 참조하므로 먼저)
        hashed = auth_service.hash_password("seedpass123")
        nickname_to_user = {}
        for udata in users_data:
            user = User.create(
                email=f"{udata['nickname']}@example.com",
                hashed_password=hashed,
                nickname=udata["nickname"],
            )
            user.is_verified = True      # 시드 계정은 인증된 것으로
            user.role = udata["role"]
            session.add(user)
            nickname_to_user[udata["nickname"]] = user

        session.flush()   # id 확보

        # 3) 글
        for pdata in posts_data:
            data = dict(pdata)
            comments_data = data.pop("comments")
            author = data.pop("author")
            category_slug = data.pop("category")

            post = Post(
                user_id=nickname_to_user[author].id,
                category_id=slug_to_category[category_slug].id,
                thumbnail_url=extract_first_image(data["contents"]),
                **data,
            )
            session.add(post)
            session.flush()   # post.id 확보

            # 4) 댓글 → 답글 (부모 id 가 필요하므로 원댓글을 먼저 flush)
            created = []
            for cdata in comments_data:
                comment = Comment(
                    post_id=post.id,
                    user_id=nickname_to_user[cdata["author"]].id,
                    parent_id=(
                        None if cdata["reply_to"] is None
                        else created[cdata["reply_to"]].id
                    ),
                    created_at=cdata["created_at"],
                    updated_at=cdata["updated_at"],
                    contents=cdata["contents"],
                )
                session.add(comment)
                session.flush()
                created.append(comment)

        session.commit()
        print("시드 완료 (분류 3개 / 계정 9개, 관리자 hong·gil·dong / 비번 seedpass123)")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
#app/seed.py

'''
2026-07-20
fake 데이터를 DB에 넣는 시드 스크립트 (최초 1회)

2026-07-22
초기 테스트 데이터를 DB에 넣는 시드 스크립트 (최초 1회)

2026-07-23
회원 먼저 생성 후 글/댓글을 user_id로 연결
'''

from datetime import datetime
from .database.connection import SessionFactory
from .database.orm import Post, Comment, Image, User
from .service.auth import AuthService


# 시드 계정 (비번은 전부 seedpass123)
users_data = ["hong", "gil", "dong", "kim", "lee", "park", "choi", "jung", "yoon"]

posts_data = [
    {
        "author": "hong",
        "created_at": datetime.fromisoformat("2026-07-16T09:00:00+00:00"),
        "updated_at": datetime.fromisoformat("2026-07-16T09:00:00+00:00"),
        "title": "dnd 밈1",
        "contents": "새로온 파티원이 로그일때 로그의 말은 '나로는 부족해?'",
        "comments": [
            {"author": "kim",
            "created_at": datetime.fromisoformat("2026-07-16T09:10:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T09:10:00+00:00"),
            "contents": "응, 로그 실력이 부족해"},
            {"author": "lee",
            "created_at": datetime.fromisoformat("2026-07-16T09:20:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T09:20:00+00:00"),
            "contents": "로그 수는 부족하진 않아"},
        ],
        "images": [
            {"url": "https://example.com/dnd1_a.jpg", "display_order": 0},
            {"url": "https://example.com/dnd1_b.jpg", "display_order": 1},
        ],
    },
    {
        "author": "gil",
        "created_at": datetime.fromisoformat("2026-07-16T10:30:00+00:00"),
        "updated_at": datetime.fromisoformat("2026-07-16T10:30:00+00:00"),
        "title": "dnd 밈2",
        "contents": "새로온 파티원이 바바리안일때 바바리안 왈 '바바리안, 뭉치면 강하다'",
        "comments": [
            {"author": "park",
            "created_at": datetime.fromisoformat("2026-07-16T10:40:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T10:40:00+00:00"),
            "contents": "바바리안, 계획이 있다"},
            {"author": "choi",
            "created_at": datetime.fromisoformat("2026-07-16T10:45:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T10:45:00+00:00"),
            "contents": "바바리안, 계획은 도끼질이다"},
            {"author": "jung",
            "created_at": datetime.fromisoformat("2026-07-16T10:50:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T10:50:00+00:00"),
            "contents": "바바리안, 찢고 죽인다"},
        ],
        "images": [
            {"url": "https://example.com/dnd2_a.jpg", "display_order": 0},
        ],
    },
    {
        "author": "dong",
        "created_at": datetime.fromisoformat("2026-07-16T14:15:00+00:00"),
        "updated_at": datetime.fromisoformat("2026-07-16T14:15:00+00:00"),
        "title": "dnd 밈3",
        "contents": "둥그런 선술집을 지으세요",
        "comments": [
            {"author": "yoon",
            "created_at": datetime.fromisoformat("2026-07-16T14:25:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T14:25:00+00:00"),
            "contents": "로그가 구석에서 비릿한 웃음을 짓지 못하도록"},
        ],
        "images": [],
    },
]


def seed():
    session = SessionFactory()
    auth_service = AuthService()
    try:
        # 1) 회원 먼저 생성 (글이 user_id를 참조하므로)
        hashed = auth_service.hash_password("seedpass123")
        nickname_to_user = {}
        for nickname in users_data:
            user = User.create(
                email=f"{nickname}@example.com",
                hashed_password=hashed,
                nickname=nickname,
            )
            session.add(user)
            nickname_to_user[nickname] = user

        session.flush()   # user.id 확보

        # 2) 글/댓글/이미지
        for pdata in posts_data:
            data = dict(pdata)
            comments_data = data.pop("comments")
            images_data = data.pop("images")
            author = data.pop("author")

            post = Post(user_id=nickname_to_user[author].id, **data)
            post.comments = [
                Comment(
                    user_id=nickname_to_user[c["author"]].id,
                    created_at=c["created_at"],
                    updated_at=c["updated_at"],
                    contents=c["contents"],
                )
                for c in comments_data
            ]
            post.images = [Image(**img) for img in images_data]
            session.add(post)

        session.commit()
        print("시드 완료 (계정 9개 / 비번 seedpass123)")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
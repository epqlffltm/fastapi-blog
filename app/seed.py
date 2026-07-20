#app/seed.py

'''
2026-07-20
fake 데이터를 DB에 넣는 시드 스크립트 (최초 1회)
'''

from datetime import datetime
from .database.connection import SessionFactory
from .database.orm import Post, Comment, Image


posts_data = [
    {
        "created_at": datetime.fromisoformat("2026-07-16T09:00:00+00:00"),
        "updated_at": datetime.fromisoformat("2026-07-16T09:00:00+00:00"),
        "title": "dnd 밈1",
        "nickname": "hong",
        "contents": "새로온 파티원이 로그일때 로그의 말은 '나로는 부족해?'",
        "comments": [
            {"created_at": datetime.fromisoformat("2026-07-16T09:10:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T09:10:00+00:00"),
            "nickname": "kim", "contents": "응, 로그 실력이 부족해"},
            {"created_at": datetime.fromisoformat("2026-07-16T09:20:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T09:20:00+00:00"),
            "nickname": "lee", "contents": "로그 수는 부족하진 않아"},
        ],
        "images": [
            {"url": "https://example.com/dnd1_a.jpg", "display_order": 0},
            {"url": "https://example.com/dnd1_b.jpg", "display_order": 1},
        ],
    },
    {
        "created_at": datetime.fromisoformat("2026-07-16T10:30:00+00:00"),
        "updated_at": datetime.fromisoformat("2026-07-16T10:30:00+00:00"),
        "title": "dnd 밈2",
        "nickname": "gil",
        "contents": "새로온 파티원이 바바리안일때 바바리안 왈 '바바리안, 뭉치면 강하다'",
        "comments": [
            {"created_at": datetime.fromisoformat("2026-07-16T10:40:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T10:40:00+00:00"),
            "nickname": "park", "contents": "바바리안, 계획이 있다"},
            {"created_at": datetime.fromisoformat("2026-07-16T10:45:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T10:45:00+00:00"),
            "nickname": "choi", "contents": "바바리안, 계획은 도끼질이다"},
            {"created_at": datetime.fromisoformat("2026-07-16T10:50:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T10:50:00+00:00"),
            "nickname": "jung", "contents": "바바리안, 찢고 죽인다"},
        ],
        "images": [
            {"url": "https://example.com/dnd2_a.jpg", "display_order": 0},
        ],
    },
    {
        "created_at": datetime.fromisoformat("2026-07-16T14:15:00+00:00"),
        "updated_at": datetime.fromisoformat("2026-07-16T14:15:00+00:00"),
        "title": "dnd 밈3",
        "nickname": "dong",
        "contents": "둥그런 선술집을 지으세요",
        "comments": [
            {"created_at": datetime.fromisoformat("2026-07-16T14:25:00+00:00"),
            "updated_at": datetime.fromisoformat("2026-07-16T14:25:00+00:00"),
            "nickname": "yoon", "contents": "로그가 구석에서 비릿한 웃음을 짓지 못하도록"},
        ],
        "images": [],
    },
]


def seed():
    session = SessionFactory()
    try:
        for pdata in posts_data:
            comments_data = pdata.pop("comments")
            images_data = pdata.pop("images")

            post = Post(**pdata)
            post.comments = [Comment(**c) for c in comments_data]
            post.images = [Image(**img) for img in images_data]
            session.add(post)

        session.commit()
        print("시드 완료")
    finally:
        session.close()


if __name__ == "__main__":
    seed()
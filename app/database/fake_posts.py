#app/database/fake_posts.py

'''
2026-07-16
테스트용 posts db
'''

fake_posts = {
    1:{
        "id":1,
        "created_at":"2026-07-16T09:00:00+00:00",
        "updated_at":"2026-07-16T09:00:00+00:00",
        "title":"dnd 밈1",
        "nickname":"hong",
        "contents":"새로온 파티원이 로그일때 로그의 말은 '나로는 부족해?'",
        "image":"",
        "is_deleted":False,
    },
    2:{
        "id":2,
        "created_at":"2026-07-16T10:30:00+00:00",
        "updated_at":"2026-07-16T10:30:00+00:00",
        "title":"dnd 밈2",
        "nickname":"gil",
        "contents":"새로온 파티원이 바바리안일때 바바리안 왈 '바바리안, 뭉치면 강하다'",
        "image":"",
        "is_deleted":False,
    },
    3:{
        "id":3,
        "created_at":"2026-07-16T14:15:00+00:00",
        "updated_at":"2026-07-16T14:15:00+00:00",
        "title":"dnd 밈3",
        "nickname":"dong",
        "contents":"둥그런 선술집을 지으세요",
        "image":"",
        "is_deleted":False,
    }
}
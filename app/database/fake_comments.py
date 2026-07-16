#app/database/fake_comments.py

'''
2026-07-16
테스트용 comments db
'''

fake_comments = {
    1:{
        "id":1,
        "post_id":1,
        "nickname":"kim",
        "contents":"응, 로그 실력이 부족해",
        "is_deleted":False,
    },
    2:{
        "id":2,
        "post_id":1,
        "nickname":"lee",
        "contents":"로그 수는 부족하진 않아",
        "is_deleted":False,
    },
    3:{
        "id":3,
        "post_id":2,
        "nickname":"park",
        "contents":"바바리안, 계획이 있다",
        "is_deleted":False,
    },
    4:{
        "id":4,
        "post_id":2,
        "nickname":"choi",
        "contents":"바바리안, 계획은 도끼질이다",
        "is_deleted":False,
    },
    5:{
        "id":5,
        "post_id":2,
        "nickname":"jung",
        "contents":"바바리안, 찢고 죽인다",
        "is_deleted":False,
    },
    6:{
        "id":6,
        "post_id":3,
        "nickname":"yoon",
        "contents":"로그가 구석에서 비릿한 웃음을 짓지 못하도록",
        "is_deleted":False,
    }
}
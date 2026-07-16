#app/database/fake_db.py

'''
2026-07-16
테스트용 db 작성
'''

fake_db = {
    1:{
        "id":1,
        "title":"dnd 밈1",
        "nickname":"hong",
        "contents":"새로온 파티원이 로그일때 로그의 말은 '나로는 부족해?'",
        "imige":"",
        "comment":["응, 로그 실력이 부족해", "로그 수는 부족하진 않아"],
        "delete":False,
    },
    2:{
        "id":2,
        "title":"dnd 밈2",
        "nickname":"gil",
        "contents":"새로온 파티원이 바바리안일때 바바리안 왈 '바바리안, 뭉치면 강하다'",
        "imige":"",
        "comment":["바바리안, 계획이 있다","바바리안, 계획은 도끼질이다","바바리안, 찢고 죽인다"],
        "delete":False,
    },
    3:{
        "id":3,
        "title":"dnd 밈3",
        "nickname":" dong",
        "contents":"둥그런 선술집을 지으세요",
        "imige":"",
        "comment":["로그가 구석에서 비릿한 웃음을 짓지 못하도록"],
        "delete":False,
    }
}
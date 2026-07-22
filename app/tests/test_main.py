#app/tests/test_main.py

'''
2026-07-22
test_code 코드 작성
'''


def test_health_check(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, FastAPI"}
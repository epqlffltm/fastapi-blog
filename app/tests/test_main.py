#app/tests/test_main.py

'''
testcode코드 작성

2026-07-24
index → /health 로 이동 (/ 는 정적 파일)
'''

def test_health_check(client):
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, FastAPI"}
#app/create_tables.py

'''
2026-07-20
테이블 생성 스크립트 (최초 1회 실행)
'''

from .database.connection import Base, engine   # database → database.connection
from .database import orm   # models → database.orm (모델 등록용)

Base.metadata.create_all(bind=engine)
print("테이블 생성 완료")
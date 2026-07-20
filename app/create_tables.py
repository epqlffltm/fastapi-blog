#app/create_tables.py

'''
2026-07-20
테이블 생성 스크립트 (최초 1회 실행)
'''

from .database import Base, engine
from . import models   # 모델 import 필수 (안 하면 테이블 안 만들어짐)

Base.metadata.create_all(bind=engine)
print("테이블 생성 완료")
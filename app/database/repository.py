#app/database/repository.py

'''
2026-07-20
get 전체조회 api
'''

from sqlalchemy import select
from sqlalchemy.orm import Session
from .orm import Post

def get_pages(session: Session) -> list[Post]:
    return session.scalars(select(Post)).all() 
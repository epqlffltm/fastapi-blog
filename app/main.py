#app/main

'''
2026-07-15
main.py작성

2026-07-16
get api 전체조회
'''

from fastapi import FastAPI
from .database.fake_db import fake_db

app = FastAPI()

@app.get("/")
async def index():
    return {"message": "Hello, FastAPI"}

@app.get("/pages")
def get_pages_handler():
    return list(fake_db.values())

@app.get("/page/{id}")
def get_page_handler(id:int):
    return {"message":"id"}

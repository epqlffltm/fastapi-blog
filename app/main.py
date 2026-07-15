#app/main

'''
2026-07-15
main.py작성
'''

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def index():
    return {"message": "Hello, FastAPI"}

@app.get("/pages")
def get_pages_handler():
    return {"message":"pages"}

@app.get("/page/{id}")
def get_page_handler(id:int):
    return {"message":"id"}

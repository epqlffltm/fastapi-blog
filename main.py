#main

'''
2026-07-15
tast용으로 작성
'''

from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "Hello, FastAPI"}
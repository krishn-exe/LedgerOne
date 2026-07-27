from fastapi import FastAPI
from auth import router as auth_router
from expenses import router as expenses_router
from fetch import router as fetch_router

app = FastAPI()
app.include_router(auth_router)
app.include_router(expenses_router)
app.include_router(fetch_router)

@app.get("/")
def root():
    return {"message": "Online"}
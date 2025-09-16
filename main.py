from typing import Annotated
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")
@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.get("/{short_url}")
async def short_url_handler(short_url: str):
    return {"message": f"Hello {short_url}"}

@app.post("/login/")
async def create_url(longurl: Annotated[str, Form()]):
    return {"username": longurl}

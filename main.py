import string
from random import choice
from typing import Annotated
import os

import aiofiles
import json
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")


@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse(
        request=request, name="mainpage.html")


@app.get("/{short_url}")
async def short_url_handler(short_url: str):
    return {"message": f"{short_url}"}


@app.post("/")
async def create_url(longurl: Annotated[str, Form()]):
    alphabet = string.ascii_letters + string.digits
    short_url = ''.join(choice(alphabet) for _ in range(6))

    async with aiofiles.open("urls.JSON", mode="r") as f:
        urls_data = json.loads(await f.read())

    urls_data[short_url] = longurl

    async with aiofiles.open("urls.JSON", mode="w") as f:
        await f.write(json.dumps(urls_data, indent=4))
    return {"short_url": short_url, "longurl": longurl}

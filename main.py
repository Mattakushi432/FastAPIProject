import string
from random import choice
from typing import Annotated, Optional
import os

import aiofiles
import json
from fastapi import FastAPI, Form, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from starlette.responses import RedirectResponse

app = FastAPI()

templates = Jinja2Templates(directory="templates")

if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


def render_template(template_name: str, request: Request, short_url_code: Optional[str] = None):
    return templates.TemplateResponse(template_name, {"request": request,
                                                      "short_url_code": short_url_code})


@app.get("/", response_class=HTMLResponse, name="root")
async def root(request: Request, short_url: Optional[str] = None):
    return render_template('mainpage.html', request, short_url_code=short_url)


@app.get("/{short_code}", name="redirect_to_url")
async def short_url_handler(short_code: str):
    async with aiofiles.open("urls.JSON", mode="r") as f:
        urls_data = json.loads(await f.read())
    longurl = urls_data.get(short_code)
    if not longurl:
        return RedirectResponse(url="/", status_code=307)
    return RedirectResponse(longurl)


@app.post("/", name="shorten")
async def create_url(request: Request, longurl: Annotated[str, Form()]):
    alphabet = string.ascii_letters + string.digits
    short_url = ''.join(choice(alphabet) for _ in range(6))

    async with aiofiles.open("urls.JSON", mode="r") as f:
        urls_data = json.loads(await f.read())

    urls_data[short_url] = longurl

    async with aiofiles.open("urls.JSON", mode="w") as f:
        await f.write(json.dumps(urls_data, indent=4))

    redirect_url = str(request.url_for("root").include_query_params(short_url=short_url))

    return RedirectResponse(url=redirect_url, status_code=303)

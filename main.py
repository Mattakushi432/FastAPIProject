import string

from random import choice
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated, Optional, Dict

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

import aiofiles
import json
from fastapi import FastAPI, Form, Request, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse


class Settings(BaseSettings):
    MONGO_USER: str = ""
    MONGO_PASSWORD: str = ""
    MONGO_HOST: str = "localhost"
    MONGO_PORT: int = 27017
    MONGO_DB_NAME: str = "test"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def build_mongo_uri(s: "Settings") -> str:
    auth = f"{s.MONGO_USER}:{s.MONGO_PASSWORD}@" if s.MONGO_USER and s.MONGO_PASSWORD else ""
    return f"mongodb://{auth}{s.MONGO_HOST}:{s.MONGO_PORT}"


settings = Settings()
MONGO_URI = build_mongo_uri(settings)

BASE_DIR = Path(__file__).resolve().parent
SHORT_URLS_LENGTH = 6
ALPHABET = string.ascii_letters + string.digits

db_state: Dict[str, AsyncIOMotorClient | AsyncIOMotorDatabase] = {}

def generate_short_code(length: int = SHORT_URLS_LENGTH, alphabet: str = ALPHABET) -> str:
    return ''.join(choice(alphabet) for _ in range(length))


class URLMapping(BaseModel):
    long_url: str
    short_code: str = Field(default_factory=generate_short_code)
    visits: int = 0

@asynccontextmanager
async def lifespan(_app: FastAPI):
    db_state["client"] = AsyncIOMotorClient(MONGO_URI)
    db_state["database"] = db_state["client"][settings.MONGO_DB_NAME]
    yield
    db_state["client"].close()
    print("MongoDB connection closed")

app = FastAPI(title="URL Shorten with MongoDB", lifespan=lifespan)

statick_dir = BASE_DIR / "static"
if statick_dir.is_dir():
    app.mount("/static", StaticFiles(directory="static_dir"), name="static")

templates = Jinja2Templates(directory="templates")

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

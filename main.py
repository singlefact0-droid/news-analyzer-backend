# main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import os
import openai
import json

# -----------------------------
# App initialization
# -----------------------------
app = FastAPI()

# CORS setup
origins = [
    "https://house-of-prompts.web.app",  # your frontend domain
    "http://localhost:5500",             # optional local dev
    "http://127.0.0.1:5500"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# API Keys and Clients
# -----------------------------
OPENROUTER_API_KEY = os.getenv("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")

# Initialize OpenAI (OpenRouter)
client = openai.OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

# -----------------------------
# Models
# -----------------------------
class Article(BaseModel):
    article: str

# -----------------------------
# Exception handler (ensures CORS headers always present)
# -----------------------------
@app.exception_handler(Exception)
async def all_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )

# -----------------------------
# Routes
# -----------------------------
@app.get("/")
async def root():
    return {"message": "News Analyzer API is running"}

from datetime import datetime, timedelta

cache = {"data": None, "timestamp": None}

@app.get("/news")
async def get_news():
    global cache
    if cache["data"] and cache["timestamp"] > datetime.now() - timedelta(minutes=30):
        return cache["data"]  # return cached data if recent

    # otherwise fetch new
    GNEWS_API_KEY = "2bad3eea46a5af8373e977e781fc5547"
    categories = ["general", "world", "science", "nation"]
    all_articles = []

    for cat in categories:
        url = f"https://gnews.io/api/v4/top-headlines?category={cat}&lang=en&country=in&max=5&apikey={GNEWS_API_KEY}"
        res = requests.get(url)
        if res.status_code == 200:
            data = res.json()
            if "articles" in data:
                all_articles.extend(data["articles"])

    cache = {"data": {"articles": all_articles}, "timestamp": datetime.now()}
    return {"articles": all_articles}


@app.get("/wiki")
async def get_wiki():
    """Fetch Wikipedia Current Events summary"""
    try:
        url = "https://en.wikipedia.org/api/rest_v1/page/summary/Portal:Current_events"
        res = requests.get(url)
        data = res.json()
        summary = data.get("extract", "")
        return {"summary": summary}
    except Exception as e:
        return {"error": str(e)}

@app.post("/analyze")
async def analyze(article: Article):
    news_text = article.article

    try:
        # Fetch Wikipedia summary
        wiki_res = requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/Portal:Current_events")
        wiki_summary = wiki_res.json().get("extract", "")

        prompt = f"""
        You are an AI assistant analyzing a news article. Use the following Wikipedia summary as reference:

        Wikipedia summary:
        {wiki_summary}

        News article:
        {news_text}

        Tasks:
        1. Credibility score (0-100)
        2. Short summary
        3. Counterarguments

        Return JSON with keys: credibility_score, summary, counterarguments
        """

        response = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )

        message = response.choices[0].message.content

        # Attempt to parse JSON safely
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            start, end = message.find("{"), message.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(message[start:end + 1])
            else:
                data = {
                    "credibility_score": "N/A",
                    "summary": message,
                    "counterarguments": "Could not parse JSON"
                }

        return data

    except Exception as e:
        return {
            "credibility_score": "Error",
            "summary": "Could not analyze article.",
            "counterarguments": str(e)
        }




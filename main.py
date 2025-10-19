# main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import os
import openai
import json
import re

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
OPENROUTER_API_KEY = "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"
GNEWS_API_KEY = "2bad3eea46a5af8373e977e781fc5547"

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
    """
    Fetch top GNews articles for selected categories.
    Cached for 30 minutes to reduce API usage.
    """
    global cache
    if cache["data"] and cache["timestamp"] > datetime.now() - timedelta(minutes=30):
        return cache["data"]

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




@app.post("/analyze")
async def analyze(article: Article):
    news_text = article.article

    try:
        # DuckDuckGo live data
        duck_res = requests.get(f"https://api.duckduckgo.com/?q={news_text[:80]}&format=json&no_html=1&skip_disambig=1")
        duck_data = duck_res.json()
        related = duck_data.get("RelatedTopics", [])
        duck_summary = " ".join([r.get("Text", "") for r in related[:5]])

        if not duck_summary.strip():
            duck_summary = "No live search data available."

        prompt = f"""
        You are a News Credibility Analyzer.
        Use the live DuckDuckGo results to verify the truthfulness.

    
        DuckDuckGo current data:
        {duck_summary}

        News article:
        {news_text}

        Return JSON in this exact format:
        {{
            "credibility_score": (0-100),
            "summary": "...",
            "counterarguments": "..."
        }}
        """

        response = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400
        )

        raw = response.choices[0].message.content.strip()

        # Try extracting JSON


# Clean markdown code blocks and extract JSON
clean_raw = re.sub(r"```(json)?", "", raw).strip()
match = re.search(r"\{[\s\S]*\}", clean_raw)

if match:
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {
            "credibility_score": "N/A",
            "summary": clean_raw,
            "counterarguments": "JSON formatting issue."
        }
else:
    return {
        "credibility_score": "N/A",
        "summary": clean_raw,
        "counterarguments": "No valid JSON detected."
    }













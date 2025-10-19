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
        # --- Step 1: Get Wikipedia current events summary ---
        wiki_res = requests.get("https://en.wikipedia.org/api/rest_v1/page/summary/Portal:Current_events")
        wiki_summary = wiki_res.json().get("extract", "")

        # --- Step 2: Fetch DuckDuckGo search results ---
        search_url = f"https://api.duckduckgo.com/?q={news_text[:80]}&format=json&no_redirect=1&no_html=1"
        ddg_res = requests.get(search_url)
        ddg_data = ddg_res.json()
        ddg_snippets = []

        # Collect up to 3 relevant snippets
        for topic in ddg_data.get("RelatedTopics", [])[:3]:
            if "Text" in topic:
                ddg_snippets.append(topic["Text"])

        duckduck_summary = " ".join(ddg_snippets)

        # --- Step 3: Combine data sources ---
        prompt = f"""
        You are a real-time news credibility analyst.
        Use the following info for context and verification.

        WIKIPEDIA SUMMARY (recent events):
        {wiki_summary}

        DUCKDUCKGO LIVE RESULTS:
        {duckduck_summary}

        NEWS ARTICLE:
        {news_text}

        TASKS:
        1. Give a credibility score (0-100)
        2. Write a short, unbiased summary
        3. Provide counterarguments or alternative viewpoints

        Output valid JSON with keys: credibility_score, summary, counterarguments.
        """

        # --- Step 4: Ask DeepSeek ---
        response = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
        )

        raw = response.choices[0].message.content.strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            start, end = raw.find("{"), raw.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(raw[start:end + 1])
            else:
                data = {
                    "credibility_score": "N/A",
                    "summary": raw,
                    "counterarguments": "Could not parse structured data."
                }

        return data

    except Exception as e:
        return {
            "credibility_score": "Error",
            "summary": "Could not analyze article.",
            "counterarguments": str(e)
        }







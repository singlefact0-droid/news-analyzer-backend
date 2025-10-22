from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import os
import json
import openai
import aiohttp
import asyncio
from datetime import datetime

# -----------------------------
# FastAPI Initialization
# -----------------------------
app = FastAPI()

# CORS
origins = [
    "https://house-of-prompts.web.app",
    "http://localhost:5500",
    "https://house-of-prompts.firebaseapp.com",
    "https://counter-8d610.web.app",
    "https://counter-8d610.firebaseapp.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# API Keys
# -----------------------------
OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "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"
)

# -----------------------------
# OpenRouter Client (DeepSeek)
# -----------------------------
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
# Exception Handler
# -----------------------------
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc)},
        headers={"Access-Control-Allow-Origin": "*"},
    )

# -----------------------------
# Wikipedia Search Helper
# -----------------------------
async def fetch_wikipedia_summary(query: str) -> str:
    """Fetch summary from Wikipedia"""
    try:
        search_url = (
            f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={query}&utf8=&format=json&origin=*"
        )
        async with aiohttp.ClientSession() as session:
            async with session.get(search_url) as res:
                search_data = await res.json()
                if "query" not in search_data or len(search_data["query"]["search"]) == 0:
                    return "No relevant Wikipedia entry found."

                title = search_data["query"]["search"][0]["title"]

                summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title}"
                async with session.get(summary_url) as summary_res:
                    summary_data = await summary_res.json()
                    return summary_data.get("extract", "No summary available.")
    except Exception as e:
        return f"Error fetching Wikipedia data: {e}"

# -----------------------------
# Routes
# -----------------------------
@app.get("/")
async def home():
    return {"message": "AI News Analyzer with Wikipedia Fact Check is running."}

@app.post("/analyze")
async def analyze(article: Article):
    news_text = article.article

    try:
        # Step 1: Fetch factual reference from Wikipedia
        wiki_summary = await fetch_wikipedia_summary(news_text[:100])

        # Step 2: AI Analysis using DeepSeek (or GPT-4o-mini)
        prompt = f"""
        You are a factual AI news analyzer.
        Below is a claim or article excerpt. Check its factual accuracy using the Wikipedia summary provided.

        Article:
        {news_text}

        Wikipedia summary:
        {wiki_summary}

        Tasks:
        1. Determine if the article's main claim aligns with Wikipedia's information (True / False / Unclear).
        2. Give a credibility score (0–100) based on accuracy.
        3. Provide a concise, neutral summary of the article.
        4. Offer counterarguments or alternative perspectives neutrally.
        """

        response = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400
        )

        analysis = response.choices[0].message.content.strip()

        return {
            "wikipedia_summary": wiki_summary,
            "summary_and_counterarguments": analysis
        }

    except Exception as e:
        return {
            "summary_and_counterarguments": "Could not analyze article.",
            "wikipedia_summary": str(e)
        }

# -----------------------------
# News Fetch Route
# -----------------------------
@app.get("/news")
async def get_news(request: Request):
    """Fetch top headlines asynchronously, with optional search query"""
    GNEWS_API_KEY = "2bad3eea46a5af8373e977e781fc5547"
    base_url = "https://gnews.io/api/v4/top-headlines"
    query = request.query_params.get("q", "")
    categories = ["general", "world", "science", "nation"]
    all_articles = []

    try:
        async with aiohttp.ClientSession() as session:
            tasks = []
            for cat in categories:
                params = {
                    "category": cat,
                    "lang": "en",
                    "country": "in",
                    "max": 5,
                    "apikey": GNEWS_API_KEY
                }
                if query:
                    params["q"] = query
                tasks.append(session.get(base_url, params=params))

            responses = await asyncio.gather(*tasks)

            for res in responses:
                if res.status == 200:
                    data = await res.json()
                    if "articles" in data:
                        for article in data["articles"]:
                            # Format publication date
                            published_date = article.get("publishedAt", "")
                            if published_date:
                                try:
                                    dt = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
                                    formatted_date = dt.strftime("%B %d, %Y")  # Example: "October 22, 2025"
                                except Exception:
                                    formatted_date = published_date
                            else:
                                formatted_date = "Unknown"

                            # Add formatted date to article
                            article["formattedDate"] = formatted_date
                            all_articles.append(article)
                else:
                    print(f"⚠️ GNews API failed with status {res.status}")

        return {"articles": all_articles}

    except Exception as e:
        print("❌ Error in /news:", e)
        return {"error": str(e)}


    except Exception as e:
        print("❌ Error in /news:", e)
        return {"error": str(e)}


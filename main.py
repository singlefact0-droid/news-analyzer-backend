from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiohttp
import asyncio
import os
import json
import urllib.parse
from datetime import datetime
import re

# ---------------------------
# FastAPI setup
# ---------------------------
app = FastAPI()

# CORS (add your frontend domains here)
origins = [
    "https://house-of-prompts.web.app",
    "http://localhost:5500",
    "https://house-of-prompts.firebaseapp.com",
    "https://counter-8d610.web.app/",
    "https://counter-8d610.firebaseapp.com",

]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------
# API keys
# ---------------------------
DEEPSEEK_API_KEY = os.getenv("OPENROUTER_API_KEY")
GNEWS_API_KEY = "2bad3eea46a5af8373e977e781fc5547"

# ---------------------------
# Request model
# ---------------------------
class ArticleRequest(BaseModel):
    article: str


# ---------------------------
# DeepSeek Analysis Route
# ---------------------------
@app.post("/analyze")
async def analyze_article(request: ArticleRequest):
    article = request.article.strip()
    if not article:
        return {"error": "No article text provided."}

    try:
        # ✳️ DeepSeek prompt for summary and emotional bias
        prompt = f"""
        You are an AI specialized in emotional tone and bias detection.
        Analyze the following article and respond in strict JSON format.

        TASKS:
        1. Write a concise, objective summary (no external context or factual checking).
        2. State some counter arguements regarding the view of the articles (do not use real life data just give emotional bias with everything within the article).
        Respond ONLY in JSON format:
        {{
          "summary": "...",
          "emotional_bias": "..."
        }}

        ARTICLE:
        {article}
        """

        # 🔹 Send to DeepSeek
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "deepseek/deepseek-chat",
                    "messages": [
                        {"role": "system", "content": "You are an objective tone and bias detector."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.6,
                },
            ) as deepseek_res:
                result = await deepseek_res.json()
                raw_reply = result["choices"][0]["message"]["content"]

        # 🔹 Parse DeepSeek output safely
        try:
            analysis = json.loads(raw_reply)
        except json.JSONDecodeError:
            summary_match = re.search(r'"summary"\s*:\s*"(.*?)"', raw_reply, re.DOTALL)
            bias_match = re.search(r'"emotional_bias"\s*:\s*"(.*?)"', raw_reply, re.DOTALL)
            analysis = {
                "summary": summary_match.group(1) if summary_match else "No summary available.",
                "emotional_bias": bias_match.group(1) if bias_match else "Neutral",
            }

        # 🔹 Fetch similar articles using DuckDuckGo (with title + URL)
        query = urllib.parse.quote(article[:100])
        duck_url = f"https://html.duckduckgo.com/html/?q={query}"

        similar_articles = []
        async with aiohttp.ClientSession() as session:
            async with session.get(duck_url, headers={"User-Agent": "Mozilla/5.0"}) as duck_res:
                if duck_res.status == 200:
                    html = await duck_res.text()

                    # Extract titles and URLs
                    titles = re.findall(r'<a[^>]+class="result__a"[^>]*>(.*?)</a>', html)
                    links = re.findall(r'<a[^>]+class="result__a"[^>]+href="(https?://[^"]+)"', html)

                    for title, link in zip(titles, links):
                        clean_title = re.sub(r'<.*?>', '', title)  # remove HTML tags
                        if len(similar_articles) < 2:
                            similar_articles.append({
                                "title": clean_title,
                                "url": link
                            })

        return {
            "summary": analysis.get("summary", "No summary found."),
            "emotional_bias": analysis.get("emotional_bias", "Neutral"),
            "similar_articles": similar_articles,
        }

    except Exception as e:
        print("❌ Error in /analyze:", e)
        return {"error": str(e)}


# ---------------------------
# GNews Route
# ---------------------------
@app.get("/news")
async def get_news(request: Request):
    """Fetch top headlines asynchronously, with optional search query"""
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
                            published_date = article.get("publishedAt", "")
                            if published_date:
                                try:
                                    dt = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
                                    formatted_date = dt.strftime("%B %d, %Y")
                                except Exception:
                                    formatted_date = published_date
                            else:
                                formatted_date = "Unknown"

                            article["formattedDate"] = formatted_date
                            all_articles.append(article)
                else:
                    print(f"⚠️ GNews API failed with status {res.status}")

        return {"articles": all_articles}

    except Exception as e:
        print("❌ Error in /news:", e)
        return {"error": str(e)}




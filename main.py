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
from supabase import create_client, Client

SUPABASE_URL = "https://uzfcsexiyckrkgfnvirk.supabase.co"
SUPABASE_KEY = os.getenv("SUPABASE_KEY")  
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------------------
# FastAPI setup
# ---------------------------
app = FastAPI()

# CORS (add your frontend domains here)
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
        2. State some counter arguments regarding the view of the article 
           (do not use real life data, just the data within the article).

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
                    "model": "mistralai/mistral-small-3.2-24b-instruct:free",
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

        # 🔹 Fetch similar articles using DuckDuckGo Lite (more stable)
        try:
            query = urllib.parse.quote(article[:200])
        except Exception as e:
            print("Error encoding query:", e)
            query = ""

        duck_url = f"https://lite.duckduckgo.com/lite/?q={query}"
        similar_articles = []

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(duck_url, headers={"User-Agent": "Mozilla/5.0"}) as duck_res:
                    if duck_res.status == 200:
                        html = await duck_res.text()
                        matches = re.findall(
                            r'<a rel="nofollow" href="(https?://[^"]+)".*?>(.*?)</a>',
                            html,
                            re.DOTALL
                        )
                        for link, title in matches[:3]:
                            clean_title = re.sub(r'<.*?>', '', title).strip()
                            similar_articles.append({
                                "title": clean_title,
                                "url": link
                            })
        except Exception as e:
            print("Error fetching DuckDuckGo results:", e)

        if not similar_articles:
            similar_articles = [{"title": "No similar articles found.", "url": "#"}]

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



@app.post("/upload-article")
async def upload_article(request: Request):
    try:
        data = await request.json()

        # Validate required fields
        required_fields = ["title", "source_url", "published_date"]
        for field in required_fields:
            if not data.get(field):
                return {"error": f"{field} is required."}

        # Insert into Supabase
        res = supabase.table("articles").insert({
            "title": data["title"],
            "description": data["description"],
            "image_url": data.get("image_url", ""),
            "source_url": data["source_url"],
            "published_date": data["published_date"]
        }).execute()

        if res.error:
            return {"error": res.error.message}

        return {"status": "success", "data": res.data}

    except Exception as e:
        return {"error": str(e)}


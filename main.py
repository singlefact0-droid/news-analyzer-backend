from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiohttp
import asyncio
import os
import json
import urllib.parse
from datetime import datetime, timezone
import re
from supabase import create_client, Client
import openai

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
GNEWS_API_KEY = "2bad3eea46a5af8373e977e781fc5547"

# ---------------------------
# Request model
# ---------------------------
class ArticleRequest(BaseModel):
    article: str

# ---------------------------
# AI Analysis Route
# ---------------------------
@app.post("/analyze")
async def analyze_article(request: ArticleRequest):
    article = request.article.strip()
    if not article:
        return {"error": "No article text provided."}

    try:
        prompt = f"""
        You are an AI specialized in emotional tone and bias detection.
        Analyze the following article and respond strictly in JSON format.

        TASKS:
        1. Write a concise, objective summary (no external context or factual checking).
        2. Provide a few counterarguments to the article's claims 
           (use only data mentioned within the article).

        Respond ONLY in JSON format like this:
        {{
          "summary": "...",
          "emotional_bias": "..."
        }}

        ARTICLE:
        {article}
        """

        # Try Mistral first
        reply, model_used = await call_openrouter_model(
            prompt,
            "mistralai/mistral-small-3.2-24b-instruct:free"
        )

        # Fallback to GPT-4o if Mistral fails
        if reply is None:
            print("⚠️ Mistral failed — switching to GPT-4o fallback")
            reply, model_used = await call_openrouter_model(prompt, "openai/gpt-4o-mini")

        if not reply:
            return {"error": "Both models failed to respond."}

        # Parse response JSON
        try:
            analysis = json.loads(reply)
        except json.JSONDecodeError:
            summary_match = re.search(r'"summary"\s*:\s*"(.*?)"', reply, re.DOTALL)
            bias_match = re.search(r'"emotional_bias"\s*:\s*"(.*?)"', reply, re.DOTALL)
            analysis = {
                "summary": summary_match.group(1) if summary_match else "No summary available.",
                "emotional_bias": bias_match.group(1) if bias_match else "Neutral",
            }

        # --- DuckDuckGo similar articles search ---
        query = urllib.parse.quote(article[:200])
        similar_articles = []
        duck_url = f"https://lite.duckduckgo.com/lite/?q={query}"

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
                            similar_articles.append({"title": clean_title, "url": link})
        except Exception as e:
            print("Error fetching DuckDuckGo results:", e)

        if not similar_articles:
            similar_articles = [{"title": "No similar articles found.", "url": "#"}]

        return {
            "model_used": model_used,
            "summary": analysis.get("summary", "No summary found."),
            "emotional_bias": analysis.get("emotional_bias", "Neutral"),
            "similar_articles": similar_articles,
        }

    except Exception as e:
        print("❌ Error in /analyze:", e)
        return {"error": str(e)}



OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

async def call_openrouter_model(prompt: str, model: str):
    """Calls Mistral or GPT-4o via OpenRouter using the same API key"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": "You are an objective tone and bias detector."},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": 0.6,
                },
            ) as res:
                if res.status == 200:
                    data = await res.json()
                    return data["choices"][0]["message"]["content"], model
                else:
                    print(f"❌ OpenRouter {model} failed with status:", res.status)
                    return None, model
    except Exception as e:
        print(f"⚠️ Exception with {model}:", e)
        return None, model



# ---------------------------
# News Route (Supabase + GNews)
# ---------------------------


@app.get("/news")
async def get_news():
    try:
        all_articles = []

        # 1️⃣ Fetch Supabase articles
        res = supabase.table("articles").select("*").execute()
        supabase_articles = res.data or []

        for article in supabase_articles:
            pub_date = article.get("published_date")
            if pub_date:
                try:
                    dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                    # Convert naive datetime to UTC-aware
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    formatted_date = dt.strftime("%B %d, %Y")
                except Exception:
                    dt = datetime.min.replace(tzinfo=timezone.utc)
                    formatted_date = pub_date
            else:
                dt = datetime.min.replace(tzinfo=timezone.utc)
                formatted_date = "Unknown"

            image_url = article.get("image_url") or "https://via.placeholder.com/400x200?text=No+Image"

            all_articles.append({
                "id": article.get("id"),
                "title": article.get("title"),
                "description": article.get("description", ""),
                "source_url": article.get("source_url"),
                "published_date": pub_date,
                "formattedDate": formatted_date,
                "image": image_url,
                "source": "manual",
                "dt_obj": dt
            })

        # 2️⃣ Fetch GNews articles
        base_url = "https://gnews.io/api/v4/top-headlines"
        categories = ["general", "world", "science", "nation"]
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
                tasks.append(session.get(base_url, params=params))

            responses = await asyncio.gather(*tasks)
            for res in responses:
                if res.status == 200:
                    data = await res.json()
                    for article in data.get("articles", []):
                        pub_date = article.get("publishedAt")
                        if pub_date:
                            try:
                                dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                                formatted_date = dt.strftime("%B %d, %Y")
                            except Exception:
                                dt = datetime.min.replace(tzinfo=timezone.utc)
                                formatted_date = pub_date
                        else:
                            dt = datetime.min.replace(tzinfo=timezone.utc)
                            formatted_date = "Unknown"

                        image_url = article.get("image") or "https://via.placeholder.com/400x200?text=No+Image"

                        all_articles.append({
                            "id": None,
                            "title": article.get("title"),
                            "description": article.get("description", ""),
                            "source_url": article.get("url"),
                            "published_date": pub_date,
                            "formattedDate": formatted_date,
                            "image": image_url,
                            "source": "gnews",
                            "dt_obj": dt
                        })

        # 3️⃣ Sort all articles by datetime
        all_articles.sort(key=lambda x: x["dt_obj"], reverse=True)

        # Remove helper dt_obj before returning
        for a in all_articles:
            del a["dt_obj"]

        return {"articles": all_articles}

    except Exception as e:
        return {"error": str(e)}


# ---------------------------
# Upload Article Route
# ---------------------------
from bs4 import BeautifulSoup

@app.post("/upload-article")
async def upload_article(request: Request):
    try:
        data = await request.json()
        required_fields = ["title", "source_url", "published_date"]
        for field in required_fields:
            if not data.get(field):
                return {"error": f"{field} is required."}

        image_url = data.get("image_url", "")

        # 🔹 Scrape image from source page if not provided
        if not image_url:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(data["source_url"], headers={"User-Agent": "Mozilla/5.0"}) as res:
                        if res.status == 200:
                            html = await res.text()
                            soup = BeautifulSoup(html, "html.parser")
                            # Try to get main image from <meta property="og:image">
                            og_image = soup.find("meta", property="og:image")
                            if og_image and og_image.get("content"):
                                image_url = og_image["content"]
                            else:
                                # fallback: first <img> tag on page
                                img_tag = soup.find("img")
                                image_url = img_tag["src"] if img_tag and img_tag.get("src") else ""
            except Exception as e:
                print("Error fetching image from source:", e)

            if not image_url:
                image_url = "https://via.placeholder.com/400x200?text=No+Image"

        # ✅ Insert into Supabase
        res = supabase.table("articles").insert({
            "title": data["title"],
            "description": data.get("description", ""),
            "image_url": image_url,
            "source_url": data["source_url"],
            "published_date": data["published_date"]
        }).execute()

        if getattr(res, "status_code", None) != 201:
            try:
                error_msg = res.json().get("message", "Unknown error")
            except Exception:
                error_msg = str(res)
            return {"error": error_msg}

        return {
            "status": "success",
            "message": "✅ Article uploaded successfully!",
            "article_title": data["title"],
            "image_url": image_url
        }

    except Exception as e:
        return {"error": str(e)}





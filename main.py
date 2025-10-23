from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import aiohttp
import os
import json
import urllib.parse

app = FastAPI()

# ---------------------------
# CORS setup
# ---------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# API keys
# ---------------------------
DEEPSEEK_API_KEY = os.getenv("OPENROUTER_API_KEY")

# ---------------------------
# Request model
# ---------------------------
class ArticleRequest(BaseModel):
    article: str


# ---------------------------
# Routes
# ---------------------------
@app.post("/analyze")
async def analyze_article(request: ArticleRequest):
    article = request.article.strip()
    if not article:
        return {"error": "No article text provided."}

    try:
        # ✳️ DeepSeek prompt for emotional bias and short summary
        prompt = f"""
        You are an advanced AI specializing in emotional tone and bias detection.
        Analyze the following news article and respond in JSON.

        TASKS:
        1. Provide a short, neutral summary of the article (no opinions or external context).
        2. Describe the emotional bias (if any) — such as positivity, fear, outrage, hope, or neutrality.
        3. Avoid fact-checking, real-world accuracy, or referencing future/past events.

        Respond ONLY in JSON format with:
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
                        {"role": "user", "content": prompt}
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
            # Fallback if DeepSeek doesn't return perfect JSON
            summary = raw_reply.split("emotional_bias")[0].strip()
            emotional_bias = raw_reply.split("emotional_bias")[-1].strip()
            analysis = {
                "summary": summary or "No summary available.",
                "emotional_bias": emotional_bias or "Neutral"
            }

        # 🔹 Fetch similar articles from DuckDuckGo (2 results)
        query = urllib.parse.quote(article[:120])
        duck_url = f"https://duckduckgo.com/?q={query}&format=json&no_redirect=1"

        similar_articles = []
        async with aiohttp.ClientSession() as session:
            async with session.get(duck_url, headers={"User-Agent": "Mozilla/5.0"}) as duck_res:
                if duck_res.status == 200:
                    text = await duck_res.text()
                    # DuckDuckGo doesn't provide structured JSON in `format=json` anymore,
                    # so we will use search result links via HTML scrape
                    import re
                    matches = re.findall(r'https://[a-zA-Z0-9./?=_-]+', text)
                    unique_links = []
                    for link in matches:
                        if "duckduckgo" not in link and link not in unique_links:
                            unique_links.append(link)
                        if len(unique_links) >= 2:
                            break
                    for link in unique_links:
                        similar_articles.append({"url": link})

        return {
            "summary": analysis.get("summary", "No summary found."),
            "emotional_bias": analysis.get("emotional_bias", "Neutral"),
            "similar_articles": similar_articles,
        }

    except Exception as e:
        return {"error": str(e)}

import requests

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


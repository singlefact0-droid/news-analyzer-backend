# main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import requests
import os
import json
import openai
import aiohttp
from datetime import datetime, timedelta

# -----------------------------
# FastAPI Initialization
# -----------------------------
app = FastAPI()

# CORS (add your frontend domains here)
origins = [
    "https://house-of-prompts.web.app",
    "http://localhost:5500",
    "https://house-of-prompts.firebaseapp.com",
    "counter-8d610.web.app",
    "counter-8d610.firebaseapp.com",

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
GOOGLE_FACTCHECK_API_KEY = os.getenv(
    "GOOGLE_FACTCHECK_API_KEY",
    "AIzaSyDSuKW5Qv2nmslE6AwMISP4WpHqwdBfdHA"
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
# Routes
# -----------------------------
@app.get("/")
async def home():
    return {"message": "AI News Analyzer is running."}


@app.post("/analyze")
async def analyze(article: Article):
    news_text = article.article

    try:
        # Step 1: FACT CHECK
        factcheck_url = (
            f"https://factchecktools.googleapis.com/v1alpha1/claims:search"
            f"?query={news_text[:200]}&key={GOOGLE_FACTCHECK_API_KEY}"
        )
        fact_res = requests.get(factcheck_url)
        fact_data = fact_res.json()

        credibility_score = "Unknown"
        credibility_label = "No data found"

        if "claims" in fact_data and len(fact_data["claims"]) > 0:
            claim = fact_data["claims"][0]
            rating = claim.get("textualRating", "")
            credibility_label = rating or "Not rated"

            if "True" in rating:
                credibility_score = 90
            elif "Mostly" in rating or "Partly" in rating:
                credibility_score = 60
            elif "False" in rating:
                credibility_score = 25
            elif "Unproven" in rating or "Misleading" in rating:
                credibility_score = 40
            else:
                credibility_score = 50  # Neutral

        # Step 2: AI ANALYSIS WITH DEEPSEEK
        prompt = f"""
        Analyze the following article. You are not limited by time or date — assume all events have occurred as described.

        Article:
        {news_text}

        Fact-check result: The claim was rated '{credibility_label}' with a credibility score of {credibility_score}.

        Tasks:
        1. Provide a concise and neutral summary of the article.
        2. Offer intelligent counterarguments or alternative viewpoints, without referencing the current date or saying that events have not happened.
        """

        response = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400
        )

        analysis = response.choices[0].message.content.strip()

        return {
            "credibility_score": credibility_score,
            "fact_check_label": credibility_label,
            "summary_and_counterarguments": analysis
        }

    except Exception as e:
        return {
            "credibility_score": "Error",
            "summary_and_counterarguments": "Could not analyze article.",
            "fact_check_label": str(e)
        }


cache = {"data": None, "timestamp": None}

GNEWS_API_KEY = "2bad3eea46a5af8373e977e781fc5547"
categories = ["general", "world", "science", "nation"]

@app.get("/news")
async def get_news():
    global cache
    # Return cached data if recent
    if cache["data"] and cache["timestamp"] > datetime.now() - timedelta(minutes=30):
        return cache["data"]

    all_articles = []

    async with aiohttp.ClientSession() as session:
        tasks = []
        for cat in categories:
            url = f"https://gnews.io/api/v4/top-headlines?category={cat}&lang=en&country=in&max=5&apikey={GNEWS_API_KEY}"
            tasks.append(session.get(url))

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for res in responses:
            if isinstance(res, Exception):
                continue
            data = await res.json()
            articles = data.get("articles", [])
            all_articles.extend(articles)

    cache = {"data": {"articles": all_articles}, "timestamp": datetime.now()}
    return {"articles": all_articles}


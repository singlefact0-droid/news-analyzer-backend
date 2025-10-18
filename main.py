from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import os
import json

# ✅ Load key from environment (Render injects it)
OPENROUTER_API_KEY = os.getenv("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")

# ✅ Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

app = FastAPI()

# ✅ Enable CORS (allow your Firebase site)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or ["https://house-of-prompts.web.app"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Article(BaseModel):
    article: str

@app.post("/analyze")
async def analyze(article: Article):
    try:
        # Tell the AI to respond strictly in JSON format
        prompt = f"""
        You are an AI that analyzes the credibility of news articles.

        Return your answer **strictly as a JSON object** with the following keys:
        {{
          "credibility_score": "number out of 100",
          "summary": "short factual summary",
          "counterarguments": "logical counterpoints or fact-checking notes"
        }}

        Article:
        {article.article}
        """

        response = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[
                {"role": "system", "content": "You are a factual news credibility analyzer."},
                {"role": "user", "content": prompt},
            ],
        )

        raw = response.choices[0].message.content.strip()

        # Try to extract valid JSON even if AI adds extra text
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Fallback: attempt to extract JSON substring
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

@app.get("/")
def home():
    return {"message": "✅ News Analyzer API with OpenRouter is running!"}

import requests

@app.get("/news")
async def get_news():
    GNEWS_API_KEY = "2bad3eea46a5af8373e977e781fc5547"
    categories = ["general", "world", "science", "nation"]
    all_articles = []

    try:
        for cat in categories:
            url = f"https://gnews.io/api/v4/top-headlines?category={cat}&lang=en&country=in&max=5&apikey={GNEWS_API_KEY}"
            res = requests.get(url)
            if res.status_code == 200:
                data = res.json()
                if "articles" in data:
                    all_articles.extend(data["articles"])

        return {"articles": all_articles}

    except Exception as e:
        return {"error": str(e)}

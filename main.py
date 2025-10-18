from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import os
import json
import requests
import re

# ✅ Load API key safely
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not OPENROUTER_API_KEY:
    OPENROUTER_API_KEY = "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"

# ✅ Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

app = FastAPI()

# ✅ Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # replace with your domain later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Article(BaseModel):
    article: str

@app.post("/analyze")
async def analyze(article: Article):
    try:
        prompt = f"""
        You are an AI that analyzes the credibility of news articles.

        Return your answer strictly as a JSON object:
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

@app.get("/")
def home():
    return {"message": "✅ News Analyzer API with OpenRouter is running!"}

@app.get("/wiki")
async def get_wiki_articles(q: str = "India"):
    """Fetch top 10 Wikipedia articles related to a query (default: India)."""
    url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={q}&utf8=&format=json&srlimit=10"
    res = requests.get(url)
    data = res.json()

    articles = []
    for item in data.get("query", {}).get("search", []):
        title = item["title"]
        snippet = re.sub(r"<.*?>", "", item["snippet"])
        link = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"
        articles.append({"title": title, "summary": snippet, "link": link})

    return {"articles": articles}

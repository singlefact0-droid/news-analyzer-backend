from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
import os

# -------------------------------
# Replace with your OpenRouter API key
# Get it from https://openrouter.ai/settings/keys
# -------------------------------
OPENROUTER_API_KEY = "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"

# Initialize OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
)

# -------------------------------
# FastAPI app setup
# -------------------------------
app = FastAPI()

# Allow CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to your frontend URL later
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------
# Request model
# -------------------------------
class ArticleRequest(BaseModel):
    article: str

# -------------------------------
# Helper: analyze article using OpenRouter
# -------------------------------
def analyze_article(article_text: str):
    try:
        prompt = f"""
        You are an AI news credibility analyzer.
        Analyze the following article and provide:
        1. A credibility score (0–100, higher = more trustworthy)
        2. A concise AI-generated summary
        3. A list of counterarguments or skeptical viewpoints

        Article:
        {article_text}
        """

        completion = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[
                {"role": "system", "content": "You are a helpful and neutral AI news analyzer."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=500,
            temperature=0.7,
            extra_headers={
                "HTTP-Referer": "https://houseofprompts.com",  # optional
                "X-Title": "News Credibility Analyzer",        # optional
            },
        )

        result = completion.choices[0].message.content.strip()

        # Attempt to parse output
        # (You can later format this with regex if needed)
        return {
            "credibility_score": "Estimated via AI",
            "summary": result,
            "counterarguments": "See analysis text for skeptical points."
        }

    except Exception as e:
        print("Error:", e)
        return {"error": str(e)}


# -------------------------------
# Main route
# -------------------------------
@app.post("/analyze")
async def analyze(request: ArticleRequest):
    result = analyze_article(request.article)
    return result


# -------------------------------
# Root test route
# -------------------------------
@app.get("/")
async def home():
    return {"message": "✅ News Analyzer API is running with OpenRouter!"}

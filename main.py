from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import openai
import os

app = FastAPI()

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://house-of-prompts.web.app",
        "https://house-of-prompts.firebaseapp.com",
        "http://localhost:5500"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Set up API key
openai.api_key = os.getenv("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")

@app.get("/")
def home():
    return {"message": "✅ Backend is running successfully!"}

@app.post("/analyze")
async def analyze_article(request: Request):
    data = await request.json()
    article = data.get("article", "").strip()

    if not article:
        return {
            "score": "-",
            "summary": "⚠️ No article text provided.",
            "counter": "Please paste a valid article."
        }

    try:
        # 🧠 Ask OpenAI to analyze credibility, summarize, and generate counterarguments
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an AI trained to evaluate news credibility. "
                        "Given a news article, respond in JSON with three fields: "
                        "'credibility_score' (0 to 100), "
                        "'summary' (2-3 sentences), "
                        "and 'counterarguments' (short critical reasoning points)."
                    ),
                },
                {"role": "user", "content": article},
            ],
        )

        message = response["choices"][0]["message"]["content"]

        # Return AI response directly
        return {"result": message}

    except Exception as e:
        return {
            "score": "-",
            "summary": "⚠️ Could not analyze this article.",
            "counter": f"Error: {str(e)}"
        }

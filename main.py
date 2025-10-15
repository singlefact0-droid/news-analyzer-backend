from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI
import os

# Get OpenRouter API key
OPENAI_API_KEY = os.getenv("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")

if not OPENAI_API_KEY:
    raise RuntimeError("❌ OPENAI_API_KEY is not set in Render environment variables.")

# Initialize OpenAI client (for OpenRouter)
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENAI_API_KEY
)

# Initialize FastAPI app
app = FastAPI()

# Allow your frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://house-of-prompts.web.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/analyze")
async def analyze(request: Request):
    data = await request.json()
    article = data.get("article", "")
    if not article.strip():
        return {"credibility_score": None, "summary": "Empty input.", "counterarguments": "N/A"}

    prompt = f"""
    Analyze this news article and return ONLY in the following JSON format:

    {{
        "credibility_score": "number out of 100",
        "summary": "short summary",
        "counterarguments": "key counterarguments"
    }}

    Article: {article}
    """

    try:
        completion = client.chat.completions.create(
            model="deepseek/deepseek-r1:free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=500
        )

        content = completion.choices[0].message.content
        return {"result": content}

    except Exception as e:
        return {"error": str(e)}

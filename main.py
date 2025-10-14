from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import os
import openai

# Initialize FastAPI
app = FastAPI()

# CORS setup — allow Firebase site
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://house-of-prompts.web.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load your OpenAI key from Render environment
openai.api_key = os.environ.get("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")

# Root route for testing
@app.get("/")
def home():
    return {"message": "✅ Backend is live and connected!"}

# Analyze news endpoint
@app.post("/analyze")
async def analyze(request: Request):
    try:
        data = await request.json()
        text = data.get("text", "")

        if not text.strip():
            return {"error": "No text provided"}

        # Ask OpenAI for analysis
        prompt = f"""
You are a fake news analyzer. Analyze the following article:
'{text}'

Respond in JSON format with:
- credibility: "High", "Medium", or "Low"
- explanation: short reasoning why
- counterarguments: a few bullet points arguing the opposite viewpoint
"""

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )

        reply = response.choices[0].message["content"]

        return {"result": reply}

    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)


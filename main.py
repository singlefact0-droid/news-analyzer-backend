from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# ✅ Allow frontend domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or restrict to your Firebase URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class Article(BaseModel):
    article: str

@app.get("/")
def home():
    return {"message": "News Analyzer Backend Running ✅"}

@app.post("/analyze")
async def analyze(article: Article):
    text = article.article

    # Dummy analysis logic (you can replace later)
    if not text.strip():
        return {
            "credibility_score": None,
            "summary": "No article text provided.",
            "counterarguments": "N/A"
        }

    # Fake AI output for testing
    return {
        "credibility_score": "85%",
        "summary": "This article discusses recent events and seems partially credible.",
        "counterarguments": "However, the article lacks verified sources and may exaggerate claims."
    }

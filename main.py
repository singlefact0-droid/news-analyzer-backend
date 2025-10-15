from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os

app = Flask(__name__)
CORS(app)

# ✅ Your OpenRouter API setup
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key="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"
)

@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        data = request.get_json()
        article = data.get("article", "")

        if not article:
            return jsonify({"error": "No article text provided"}), 400

        # 🧩 The AI prompt that ensures structured, labeled output
        prompt = f"""
        Analyze the credibility of the following news article.

        Article:
        \"\"\"{article}\"\"\"

        Provide your answer in **strict JSON format** with the following keys:
        - credibility_score: a number between 0 and 100 (higher = more credible)
        - summary: a short, clear summary of the article
        - counterarguments: key weaknesses or missing evidence

        Example format:
        {{
          "credibility_score": 78,
          "summary": "The article discusses...",
          "counterarguments": "Lacks verified data..."
        }}
        """

        response = client.chat.completions.create(
            model="mistralai/mistral-7b:free",  # ✅ fast + good reasoning
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        # ✅ Parse the model’s structured JSON reply
        reply = response.choices[0].message.content.strip()

        # Sometimes the AI adds text around JSON — we handle that safely
        import json, re
        match = re.search(r'\{.*\}', reply, re.DOTALL)
        if match:
            json_data = json.loads(match.group(0))
        else:
            json_data = {
                "credibility_score": "Unavailable",
                "summary": "Could not parse summary.",
                "counterarguments": "Could not parse counterarguments."
            }

        return jsonify(json_data)

    except Exception as e:
        print("❌ Error:", e)
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

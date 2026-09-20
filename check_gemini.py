from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
key = os.getenv("GEMINI_API_KEY", "")
print(f"Gemini key starts with: {key[:15]}...")

try:
    client = genai.Client(api_key=key)
    result = client.models.list()
    for m in result:
        if "flash" in m.name.lower() or "pro" in m.name.lower():
            print(m.name)
except Exception as e:
    print(f"Gemini error: {e}")

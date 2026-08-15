import httpx
from app.config import settings

def main():
    if not settings.groq_api_key or settings.groq_api_key == "your_groq_api_key_here":
        print("Groq API key not set.")
        return
    url = "https://api.groq.com/openai/v1/models"
    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}
    response = httpx.get(url, headers=headers)
    if response.status_code == 200:
        models = response.json().get("data", [])
        print("Available Groq Models:")
        for m in models:
            print(f"- {m['id']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")

if __name__ == "__main__":
    main()

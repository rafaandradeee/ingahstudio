from google import genai
import os
from dotenv import load_dotenv

load_dotenv()
client = genai.Client() # Usa a variável de ambiente GEMINI_API_KEY

print("🔍 Modelos disponíveis para a sua chave:")
for model in client.models.list():
    print(f"👉 {model.name}")
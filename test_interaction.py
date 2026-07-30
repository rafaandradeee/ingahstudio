import os
import base64
from google import genai
from IPython.display import Image, display

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", "dummy"))

# Just to see the types
print(dir(client.interactions))

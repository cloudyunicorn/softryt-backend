import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("NVIDIA_API_KEY")
model = os.getenv("WRITER_MODEL", "moonshotai/kimi-k2.6")

print(f"Testing model: {model}")
print(f"API Key starting with: {api_key[:10] if api_key else 'None'}")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key
)

try:
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "user", "content": "Hello, write a 5 word response."}
        ],
        temperature=0.2,
        max_tokens=50
    )
    print("Success!")
    print(response.choices[0].message.content)
except Exception as e:
    print(f"Failed: {e}")
    if hasattr(e, "response"):
        print(f"Response: {e.response.text if hasattr(e.response, 'text') else e.response}")

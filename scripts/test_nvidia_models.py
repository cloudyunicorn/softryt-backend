import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("NVIDIA_API_KEY")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=api_key
)

models_to_test = [
    "meta/llama-3.3-70b-instruct",
    "meta/llama3-8b-instruct",
    "nvidia/llama-3.1-nemotron-70b-instruct",
    "mistralai/mixtral-8x22b-instruct-v0.1",
    "moonshotai/kimi-k2.6"
]

for model in models_to_test:
    print(f"\nTesting model: {model}")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Hello, write a 5 word response."}
            ],
            temperature=0.2,
            max_tokens=50
        )
        print(f"  Success: {response.choices[0].message.content.strip()}")
    except Exception as e:
        print(f"  Failed: {e}")
        if hasattr(e, "response") and hasattr(e.response, "text"):
            print(f"  Response text: {e.response.text}")

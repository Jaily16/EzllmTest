import openai

testKey = "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"
model = "gpt-3.5-turbo"
messages = [
    {"role": "user", "content": "你好，我吃柠檬"}
]

client = openai.OpenAI(api_key=testKey)
response = client.chat.completions.create(
    model=model,
    messages=messages
)

print(response.choices[0].message.content)

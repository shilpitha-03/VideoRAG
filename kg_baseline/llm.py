from openai import OpenAI
import os

#setup openai client on deepseek as it uses the openai protocol to run inference
client = OpenAI(
    api_key = os.environ["DEEPSEEK_API_KEY"], #the key is in the environment.
    base_url = "https://api.deepseek.com"
)

def complete(prompt, system=None):
    messages =[]
    
    if system:
        messages.append({"role":"system", "content":system})
    messages.append({"role":"user","content":prompt})
    resp = client.chat.completions.create(model = "deepseek-chat", message=messages)
    return resp.choices[0].message.content

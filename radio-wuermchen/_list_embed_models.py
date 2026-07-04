import google.genai as genai
import os

c = genai.Client(api_key=os.environ['GEMINI_API_KEY'])
models = [m for m in c.models.list() if 'embed' in m.name.lower()]
for m in models:
    actions = getattr(m, 'supported_actions', '?')
    print(f'{m.name} -> {actions}')

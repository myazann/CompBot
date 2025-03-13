import random
import numpy as np
from openai import OpenAI

def prompt_chatgpt(prompt):
    client = OpenAI()
    completion = client.chat.completions.create(
    model="gpt-3.5-turbo-0125",
    messages=prompt,
    max_tokens=64,
    temperature=1
    )
    return completion.choices[0].message.content

def get_random_interval(start_interval, stop_magnitude=2, step_magnitude=0.2):
    end_interval = start_interval*stop_magnitude
    new_interval = random.choice(np.arange(start=start_interval, stop=end_interval, step=start_interval*step_magnitude)) 
    return new_interval

def comp_prompt(user_name, chat_hist=[], hist_window=20):
    prompt = [{
        "role": "system",
        "content": f"You are Casanova. Your task is to compliment my girlfriend. Her name is {user_name}. Come up with original compliments and do not use the ones provided previously. Have a playful writing style. Use emojis and punctuation marks accordingly. Treat her like she is a playful little girl. Only output the compliment. The compliment should be in Turkish. "
    }]
    if chat_hist:
        prompt = prompt + chat_hist[:hist_window]
    return prompt
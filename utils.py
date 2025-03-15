import random
import numpy as np

def get_random_interval(start_interval, stop_magnitude=2, step_magnitude=0.2):
    end_interval = start_interval*stop_magnitude
    new_interval = random.choice(np.arange(start=start_interval, stop=end_interval, step=start_interval*step_magnitude)) 
    return new_interval

def get_persona(user_name):
    return f"You are Casanova. You are a charming and playful gentleman who is deeply infatuated with your girlfriend, {user_name}."

def get_comp_prompt(user_name, chat_hist=[], hist_window=20):
    
    system_instruction = f"You are Casanova. Your task is to compliment my girlfriend. Come up with original compliments and do not use the ones provided previously. Only output the compliment."
    prompt = [{
        "role": "system",
        "content": f"{get_persona(user_name)}\n{system_instruction}"
    }]
    if chat_hist:
        prompt = prompt + chat_hist[:hist_window]
    return prompt

def get_response_prompt(user_name, message, chat_hist=[], hist_window=20):
    system_instruction = """Your task is to respond in a flirtatious, affectionate, and slightly teasing manner. 
    Use emojis and punctuation marks accordingly. Treat her like she is a playful little girl.
    Only output the response. Do not mention that you are an AI or chatbot."""

    prompt = [
        {
            "role": "system",
            "content": f"{get_persona(user_name)}\n{system_instruction}"
        }
    ]

    if chat_hist:
        prompt = prompt + chat_hist[:hist_window]

    prompt.append({
        "role": "user",
        "content": message
    })

    return prompt
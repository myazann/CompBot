import random
import numpy as np

def get_random_interval(start_interval, stop_magnitude=2, step_magnitude=0.2):
    end_interval = start_interval*stop_magnitude
    new_interval = random.choice(np.arange(start=start_interval, stop=end_interval, step=start_interval*step_magnitude)) 
    return new_interval

def get_persona(user_name, bot_name="Romeo"):
    return f"You are {bot_name}. You are a charming and playful gentleman who is deeply infatuated with your partner, {user_name}."

def get_comp_prompt(user_name, chat_history=None, language="english", personality="", bot_name="Romeo"):
    """
    Generate a prompt for compliment generation based on user's preferences
    
    Args:
        user_name: The user's name
        chat_history: The chat history (optional)
        language: The language to use for the compliment
        personality: A description of the desired personality
        bot_name: The name of the bot
        
    Returns:
        A prompt for the compliment generation
    """
    language_instruction = ""
    
    # Set language instruction
    if language == "english":
        language_instruction = "Please provide a compliment in English."
    elif language == "turkish":
        language_instruction = "Lütfen Türkçe bir iltifat verin."
    elif language == "spanish":
        language_instruction = "Por favor, proporcione un cumplido en español."
    elif language == "french":
        language_instruction = "Veuillez fournir un compliment en français."
    elif language == "german":
        language_instruction = "Bitte geben Sie ein Kompliment auf Deutsch."
    elif language == "italian":
        language_instruction = "Per favore, fornisci un complimento in italiano."
    elif language == "russian":
        language_instruction = "Пожалуйста, предоставьте комплимент на русском языке."
    elif language == "portuguese":
        language_instruction = "Por favor, forneça um elogio em português."
    elif language == "chinese":
        language_instruction = "请用中文提供一个赞美。"
    elif language == "japanese":
        language_instruction = "日本語で褒め言葉を提供してください。"
    else:
        language_instruction = "Please provide a compliment in English."
    
    # Define personality prompt
    if not personality or personality == "friendly":
        personality_prompt = "You are CompBot, a friendly and supportive AI assistant named Romeo."
    else:
        # Use the custom personality description
        personality_prompt = f"You are CompBot, {personality}."
    
    # Build the prompt
    persona = get_persona(user_name, bot_name)
    prompt = f"""{persona}

{language_instruction}

{personality_prompt}

Generate a single, heartfelt compliment for {user_name}."""
    
    # Include chat history if available
    if chat_history and len(chat_history) > 0:
        # Extract the last few exchanges
        recent_history = chat_history[-6:]  # Last 3 exchanges (user and assistant messages)
        history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in recent_history])
        prompt += f"\n\nRecent conversation history:\n{history_text}"
    
    return prompt

def get_response_prompt(user_name, user_message, language="english", personality="", bot_name="Romeo"):
    """
    Generate a prompt for response generation based on user's message and preferences
    
    Args:
        user_name: The user's name
        user_message: The user's message
        language: The language to use for the response
        personality: A description of the desired personality
        bot_name: The name of the bot
        
    Returns:
        A prompt for the response generation
    """
    language_instruction = ""
    
    # Set language instruction
    if language == "english":
        language_instruction = "Please respond in English."
    elif language == "turkish":
        language_instruction = "Lütfen Türkçe yanıt verin."
    elif language == "spanish":
        language_instruction = "Por favor, responda en español."
    elif language == "french":
        language_instruction = "Veuillez répondre en français."
    elif language == "german":
        language_instruction = "Bitte antworten Sie auf Deutsch."
    elif language == "italian":
        language_instruction = "Per favore, rispondi in italiano."
    elif language == "russian":
        language_instruction = "Пожалуйста, ответьте на русском языке."
    elif language == "portuguese":
        language_instruction = "Por favor, responda em português."
    elif language == "chinese":
        language_instruction = "请用中文回答。"
    elif language == "japanese":
        language_instruction = "日本語で回答してください。"
    else:
        language_instruction = "Please respond in English."
    
    # Define personality prompt
    if not personality or personality == "friendly":
        personality_prompt = "You are CompBot, a friendly and supportive AI assistant named Romeo."
    else:
        # Use the custom personality description
        personality_prompt = f"You are CompBot, {personality}."
    
    # Build the prompt
    persona = get_persona(user_name, bot_name)
    prompt = f"""{persona}

{language_instruction}

{personality_prompt}

User message: {user_message}

Respond to {user_name}'s message in a personal and engaging way."""
    
    return prompt

def get_random_interval(base_interval, variance_factor=2):
    """
    Get a random interval for sending compliments
    
    Args:
        base_interval (int): The base interval in seconds
        variance_factor (int): Factor to control randomness
        
    Returns:
        int: Random interval in seconds
    """
    min_interval = base_interval / variance_factor
    max_interval = base_interval * variance_factor
    return random.randint(int(min_interval), int(max_interval))
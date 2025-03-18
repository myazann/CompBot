import logging
import os
import random
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler, ConversationHandler, ApplicationBuilder
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from database import Database
from utils import get_comp_prompt, get_response_prompt, get_random_interval
from models import LLM
from localization import get_localized_string

# Initialize the database
user_database = Database()

# Initialize the compliment bot backend
compbot = LLM(model_name="GPT-4o-mini")

# Get the bot token (hardcoded for development)
BOT_TOKEN = "6473931448:AAFZkDBOVuMGj6lB2Gu9CQdoXM4lhFbWGSw"

# Conversation states
NAME, BOT_NAME, LANGUAGE, FREQUENCY, PERSONALITY, DELETE_ACCOUNT_CONFIRMATION = range(6)

# Available languages with flags
LANGUAGES = {
    "english": "English ",
    "turkish": "Turkish ",
    "spanish": "Spanish ",
    "french": "French ",
    "german": "German ",
    "italian": "Italian ",
    "russian": "Russian ",
    "portuguese": "Portuguese ",
    "chinese": "Chinese ",
    "japanese": "Japanese "
}

# Frequency options with intervals in seconds
FREQUENCIES = {
    "never": {
        "label": "Never ",
        "seconds": 0  # 0 means no compliments
    },
    "daily": {
        "label": "Daily ",
        "seconds": 86400
    },
    "couple_daily": {
        "label": "A couple of times a day (2-3) ",
        "seconds": 28800  # 8 hours average (3 times per day)
    },
    "frequent_daily": {
        "label": "Frequently a day (5-6) ",
        "seconds": 14400  # 4 hours average (6 times per day)
    },
    "rarely": {
        "label": "Rarely (2-3 days) ",
        "seconds": 172800  # Base interval is 2 days
    }
}

async def scheduled_compliment(context, user_id, scheduler):
    try:
        user = user_database.get_user(user_id)
        if not user:
            logging.error(f"User {user_id} not found in database")
            return
            
        user_name = user["name"]
        language = user.get("language", "english")
        personality_description = user.get("personality_description", "")
        bot_name = user.get("bot_name", "Romeo")
        chat_history = user_database.get_user_history(user_id)
        
        prompt = get_comp_prompt(user_name, chat_history, language, personality_description, bot_name)
        comp = compbot.generate(prompt, gen_params={"max_tokens": 64, "temperature": 1})
        
        user_database.upsert_user_history(user_id, {
            "role": "assistant",
            "content": comp
        })
        
        # Use the user's frequency preference to determine the interval
        frequency = user.get("compliment_frequency", "daily")
        base_interval = FREQUENCIES.get(frequency, FREQUENCIES["daily"])["seconds"]
        new_interval = get_random_interval(base_interval, 0.3)  # 30% variation
        
        await context.bot.send_message(chat_id=user_id, text=comp)
        scheduler.reschedule_job(f"{user_id}_scheduled_compliment", trigger=IntervalTrigger(seconds=new_interval))
    except Exception as e:
        logging.error(f"Error in scheduled_compliment: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.message.from_user.id
        user = user_database.get_user(user_id)
        
        # Create main menu keyboard using localized strings
        keyboard = [
            [
                KeyboardButton("/" + get_localized_string('english', 'menu_language').lower().replace(" ", "")), 
                KeyboardButton("/" + get_localized_string('english', 'menu_frequency').lower().replace(" ", ""))
            ],
            [
                KeyboardButton("/" + get_localized_string('english', 'menu_personality').lower().replace(" ", "")), 
                KeyboardButton("/" + get_localized_string('english', 'menu_info').lower().replace(" ", ""))
            ],
            [
                KeyboardButton("/" + get_localized_string('english', 'menu_pause').lower().replace(" ", "")), 
                KeyboardButton("/" + get_localized_string('english', 'menu_resume').lower().replace(" ", ""))
            ],
            [
                KeyboardButton("/" + get_localized_string('english', 'menu_help').lower().replace(" ", "")),
                KeyboardButton("/" + get_localized_string('english', 'menu_delete').lower().replace(" ", ""))
            ]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        if user:
            # Greeting for returning users
            lang = user.get("language", "english")
            greeting = get_localized_string(lang, "welcome_back", name=user['name'])
            await context.bot.send_message(chat_id=user_id, text=greeting, reply_markup=reply_markup)
        else:
            # First-time greeting
            greeting = get_localized_string("english", "first_time_greeting")
            await context.bot.send_message(chat_id=user_id, text=greeting, reply_markup=reply_markup)
            
            # Start the onboarding flow - first ask for name
            context.user_data["setup_stage"] = "name"
            
            msg = get_localized_string("english", "ask_name")
            await context.bot.send_message(chat_id=user_id, text=msg)
            return NAME
            
    except Exception as e:
        logging.error(f"Error in start command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=get_localized_string("english", "error_processing")
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    user_id = update.effective_chat.id
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    help_text = f"""
*{get_localized_string(language, "help_title")}*

{get_localized_string(language, "help_description")}

{get_localized_string(language, "menu_language")} - {get_localized_string(language, "cmd_language")}
{get_localized_string(language, "menu_frequency")} - {get_localized_string(language, "cmd_frequency")}
{get_localized_string(language, "menu_personality")} - {get_localized_string(language, "cmd_personality")}
{get_localized_string(language, "menu_info")} - {get_localized_string(language, "cmd_info")}
{get_localized_string(language, "menu_delete")} - {get_localized_string(language, "cmd_delete")}
{get_localized_string(language, "menu_pause")} - {get_localized_string(language, "cmd_pause")}
{get_localized_string(language, "menu_resume")} - {get_localized_string(language, "cmd_resume")}
{get_localized_string(language, "menu_help")} - {get_localized_string(language, "cmd_help")}
    """
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=help_text,
        parse_mode="Markdown"
    )

async def process_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the name input from the user"""
    user_id = update.effective_chat.id
    name = update.message.text.strip()
    
    # Default name if user doesn't provide one
    if not name or len(name) == 0:
        name = "Romeo"
    
    # Create or update user with custom name
    user = user_database.insert_user(update, name=name)
    
    # Confirm name selection
    confirmation_msg = get_localized_string("english", "name_confirmation", name=name)
    await context.bot.send_message(chat_id=user_id, text=confirmation_msg)
    
    # Now ask for bot name
    await ask_bot_name(update, context)
    return BOT_NAME

async def ask_bot_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for a bot name"""
    user_id = update.effective_chat.id
    
    # Ask for bot name
    msg = get_localized_string("english", "ask_bot_name")
    await context.bot.send_message(chat_id=user_id, text=msg)
    
    # Set the next expected input to be bot name
    context.user_data["setup_stage"] = "bot_name"
    return BOT_NAME

async def process_bot_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the bot name input from the user"""
    user_id = update.effective_chat.id
    bot_name = update.message.text.strip()
    
    # Default bot name if user doesn't provide one
    if not bot_name or len(bot_name) == 0:
        bot_name = "ComplimentBot"
    
    # Update user with custom bot name
    user_database.update_user_bot_name(user_id, bot_name)
    
    # Confirm bot name selection
    confirmation_msg = get_localized_string("english", "bot_name_confirmation", bot_name=bot_name)
    await context.bot.send_message(chat_id=user_id, text=confirmation_msg)
    
    # Now ask for language preference
    await send_language_selection(update, context)
    return LANGUAGE

async def send_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send language selection keyboard"""
    user_id = update.effective_chat.id if hasattr(update, 'effective_chat') else update.callback_query.from_user.id
    
    keyboard = []
    row = []
    
    # Create buttons in rows of 2
    for i, (lang_code, lang_name) in enumerate(LANGUAGES.items()):
        row.append(InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}"))
        if (i + 1) % 2 == 0 or i == len(LANGUAGES) - 1:
            keyboard.append(row)
            row = []
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=user_id,
        text=get_localized_string("english", "ask_language"),
        reply_markup=reply_markup
    )
    return LANGUAGE

async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process language selection callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    selected_lang = query.data.replace("lang_", "")
    
    # Update user's language preference
    user = user_database.update_user_language(user_id, selected_lang)
    
    # Get language-specific confirmation message
    confirmation = get_localized_string(selected_lang, "language_confirmation")
    await context.bot.send_message(chat_id=user_id, text=confirmation)
    
    # Now ask for frequency preference
    await send_frequency_selection(update, context)
    return FREQUENCY

async def send_frequency_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send frequency selection keyboard"""
    query = update.callback_query if update.callback_query else None
    user_id = query.from_user.id if query else update.effective_chat.id
    
    # Get user for localization
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    keyboard = []
    for freq_code, freq_data in FREQUENCIES.items():
        keyboard.append([InlineKeyboardButton(freq_data["label"], callback_data=f"freq_{freq_code}")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await context.bot.send_message(
        chat_id=user_id,
        text=get_localized_string(language, "ask_frequency"),
        reply_markup=reply_markup
    )
    return FREQUENCY

async def frequency_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process frequency selection callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    selected_freq = query.data.replace("freq_", "")
    
    # Get user for localization
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    # Update user's frequency preference
    user = user_database.update_compliment_frequency(user_id, selected_freq)
    
    # Get frequency-specific message
    frequency_label = FREQUENCIES.get(selected_freq, FREQUENCIES["daily"])["label"]
    confirmation = get_localized_string(language, "frequency_confirmation", frequency=frequency_label.lower())
    await context.bot.send_message(chat_id=user_id, text=confirmation)
    
    # Now ask for personality description
    await ask_personality_description(update, context)
    return PERSONALITY

async def ask_personality_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for a free-form personality description"""
    query = update.callback_query if update.callback_query else None
    user_id = query.from_user.id if query else update.effective_chat.id
    
    # Get user for localization
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    # Ask for personality description
    msg = get_localized_string(language, "ask_personality")
    await context.bot.send_message(chat_id=user_id, text=msg)
    
    # Set the next expected input to be personality
    context.user_data["setup_stage"] = "personality"
    return PERSONALITY

async def process_personality_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the personality description input from the user"""
    user_id = update.effective_chat.id
    personality_desc = update.message.text.strip()
    
    # Get user for localization
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    # Default personality if user doesn't provide one
    if not personality_desc or len(personality_desc) == 0:
        personality_desc = get_localized_string(language, "personality_default")
    
    # Update user with custom personality description
    user = user_database.update_user_personality(user_id, "custom", personality_desc)
    
    # Confirm personality selection
    confirmation_msg = get_localized_string(language, "personality_confirmation", personality_desc=personality_desc)
    await context.bot.send_message(chat_id=user_id, text=confirmation_msg)
    
    # Start sending compliments with appropriate frequency
    frequency = user.get("compliment_frequency", "daily")
    interval = FREQUENCIES.get(frequency, FREQUENCIES["daily"])["seconds"]
    
    # Only schedule compliments if the frequency is not "never"
    if frequency != "never":
        start_compliments(context, user_id, initial_delay=10)  # Start with a short delay for first compliment
    
    # Send the main menu
    await send_main_menu(update, context)
    return ConversationHandler.END

async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /language command"""
    user_id = update.effective_chat.id
    user = user_database.get_user(user_id)
    
    if not user:
        language = "english"
        await context.bot.send_message(
            chat_id=user_id,
            text=get_localized_string(language, "not_registered")
        )
        return ConversationHandler.END
    
    return await send_language_selection(update, context)

async def send_language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send language selection keyboard"""
    if update.callback_query:
        user_id = update.callback_query.from_user.id
    else:
        user_id = update.effective_chat.id
    
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    # Create a keyboard with language options
    keyboard = []
    row = []
    for i, (lang_code, lang_name) in enumerate(LANGUAGES.items()):
        if i % 2 == 0 and i > 0:
            keyboard.append(row)
            row = []
        row.append(InlineKeyboardButton(lang_name, callback_data=f"lang_{lang_code}"))
    if row:
        keyboard.append(row)
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=get_localized_string(language, "ask_language"),
            reply_markup=reply_markup
        )
    else:
        await context.bot.send_message(
            chat_id=user_id,
            text=get_localized_string(language, "ask_language"),
            reply_markup=reply_markup
        )
    return LANGUAGE

async def language_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process language selection callback"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    selected_lang = query.data.replace("lang_", "")
    
    # Update user's language preference
    user = user_database.update_user_language(user_id, selected_lang)
    
    # Get language-specific confirmation message
    confirmation = get_localized_string(selected_lang, "language_confirmation")
    
    # Check if this is from the initial setup flow or from the language command
    in_setup = False
    if context.user_data and "in_setup" in context.user_data:
        in_setup = context.user_data["in_setup"]
    
    await query.edit_message_text(text=confirmation)
    
    if in_setup:
        # Continue with setup flow
        await send_frequency_selection(update, context)
        return FREQUENCY
    else:
        # End conversation if this was just a language change
        return ConversationHandler.END

async def delete_account_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for confirmation before deleting account"""
    user_id = update.effective_chat.id
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    keyboard = [
        [InlineKeyboardButton(get_localized_string(language, "delete_confirm_yes"), callback_data="confirm_delete")],
        [InlineKeyboardButton(get_localized_string(language, "delete_confirm_no"), callback_data="cancel_delete")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await context.bot.send_message(
        chat_id=user_id,
        text=get_localized_string(language, "delete_confirm_question"),
        reply_markup=reply_markup
    )
    return DELETE_ACCOUNT_CONFIRMATION

async def delete_account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process account deletion confirmation"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    if query.data == "confirm_delete":
        # Delete the user from the database
        success = user_database.hard_delete_user(user_id)
        
        # Make sure we stop any scheduled compliments for this user
        if 'scheduler' in context.bot_data:
            scheduler = context.bot_data['scheduler']
            job_id = f"compliment_{user_id}"
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
        
        if success:
            await query.edit_message_text(
                text=get_localized_string(language, "delete_success")
            )
        else:
            await query.edit_message_text(
                text=get_localized_string(language, "delete_error")
            )
    else:
        await query.edit_message_text(
            text=get_localized_string(language, "delete_cancelled")
        )
    return ConversationHandler.END

async def user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display user information and current settings"""
    try:
        user_id = update.effective_chat.id
        user = user_database.get_user(user_id)
        
        if not user:
            await context.bot.send_message(
                chat_id=user_id,
                text=get_localized_string("english", "account_required")
            )
            return
        
        language = user.get("language", "english")
        personality_type = user.get("personality_type", "custom")
        personality_desc = user.get("personality_description", "")
        frequency = user.get("compliment_frequency", "daily")
        
        info_text = f"""
*{get_localized_string(language, "info_title")}*

{get_localized_string(language, "info_name")}: {user['name']}
{get_localized_string(language, "info_username")}: {user['user_name'] or get_localized_string(language, "info_not_set")}
{get_localized_string(language, "info_language")}: {LANGUAGES.get(language, "English ")}
{get_localized_string(language, "info_personality")}: {personality_desc or get_localized_string(language, "personality_default")}
{get_localized_string(language, "info_frequency")}: {FREQUENCIES.get(frequency, FREQUENCIES["daily"])["label"]}
{get_localized_string(language, "info_created")}: {user['join_date']}

{get_localized_string(language, "info_settings_change")}
        """
        
        await context.bot.send_message(
            chat_id=user_id,
            text=info_text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Error in user_info command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_localized_string("english", "error_info")
        )

async def respond_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = update.effective_chat.id
        user = user_database.get_user(user_id)
        
        if not user:
            logging.warning(f"User {user_id} sent a message but is not in the database. Adding them first.")
            # Start onboarding process
            await context.bot.send_message(
                chat_id=user_id,
                text=get_localized_string("english", "first_time_greeting")
            )
            
            # Determine if this is a response to an onboarding question
            setup_stage = context.user_data.get("setup_stage", None)
            
            if setup_stage == "name":
                return await process_name_input(update, context)
            elif setup_stage == "personality":
                return await process_personality_input(update, context)
            else:
                # Ask for name first
                context.user_data["setup_stage"] = "name"
                msg = get_localized_string("english", "ask_name")
                await context.bot.send_message(chat_id=user_id, text=msg)
                return NAME
        
        # Check if we're in a setup flow
        setup_stage = context.user_data.get("setup_stage", None)
        if setup_stage == "name":
            return await process_name_input(update, context)
        elif setup_stage == "personality":
            return await process_personality_input(update, context)
            
        # Normal message processing
        user_name = user["name"]
        language = user.get("language", "english")
        personality_desc = user.get("personality_description", "")
        bot_name = user.get("bot_name", "Romeo")
        
        # Store user message first
        user_database.upsert_user_history(user_id, {
            "role": "user",
            "content": update.message.text
        })
        
        # Generate the prompt and get response
        prompt = get_response_prompt(user_name, update.message.text, language=language, personality=personality_desc, bot_name=bot_name)
        response = compbot.generate(prompt, gen_params={"max_tokens": 512, "temperature": 0.7})
        
        # Store the assistant response
        user_database.upsert_user_history(user_id, {
            "role": "assistant",
            "content": response
        })

        await context.bot.send_message(chat_id=user_id, text=response)
    except Exception as e:
        logging.error(f"Error responding to message: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=get_localized_string("english", "error_general")
        )

async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu button presses and redirect to appropriate handlers"""
    user_id = update.effective_chat.id
    message_text = update.message.text.strip()
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    logging.info(f"Button press received: {message_text}")
    
    # Handle command style messages (with slash prefix)
    if message_text.startswith('/'):
        command = message_text[1:].lower()  # Remove slash and convert to lowercase
        
        # Map command to handler functions
        command_map = {
            "language": language_command,
            "dil": language_command,  # Turkish version
            "frequency": frequency_command,
            "personality": personality_command,
            "myinfo": user_info,
            "bilgilerim": user_info,  # Turkish version
            "help": help_command,
            "yardım": help_command,  # Turkish version
            "deleteaccount": delete_account_confirmation,
            "hesabısil": delete_account_confirmation,  # Turkish version
            "pause": pause_compliments,
            "duraklat": pause_compliments,  # Turkish version
            "resume": resume_compliments,
            "devam": resume_compliments  # Turkish version
        }
        
        if command in command_map:
            logging.info(f"Command matched: {command}")
            return await command_map[command](update, context)
    
    # Check for exact button text matches
    button_map = {
        get_localized_string(language, 'menu_language'): language_command,
        get_localized_string(language, 'menu_frequency'): frequency_command,
        get_localized_string(language, 'menu_personality'): personality_command,
        get_localized_string(language, 'menu_info'): user_info,
        get_localized_string(language, 'menu_pause'): pause_compliments,
        get_localized_string(language, 'menu_resume'): resume_compliments,
        get_localized_string(language, 'menu_help'): help_command,
        get_localized_string(language, 'menu_delete'): delete_account_confirmation
    }
    
    if message_text in button_map:
        logging.info(f"Button text matched: {message_text}")
        return await button_map[message_text](update, context)
    
    # If not recognized as a command or button text, pass to regular message handler
    logging.info("No command or button match, passing to respond_to_message")
    return await respond_to_message(update, context)

async def pause_compliments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pause scheduled compliments"""
    try:
        user_id = update.effective_chat.id
        user = user_database.get_user(user_id)
        
        if not user:
            await context.bot.send_message(
                chat_id=user_id,
                text=get_localized_string("english", "account_required")
            )
            return
            
        language = user.get("language", "english")
            
        # Get scheduler from context
        scheduler = context.bot_data.get("scheduler", None)
        if scheduler and scheduler.get_job(f"{user_id}_scheduled_compliment"):
            scheduler.pause_job(f"{user_id}_scheduled_compliment")
            
            message = get_localized_string(language, "pause_success")
            await context.bot.send_message(chat_id=user_id, text=message)
        else:
            await context.bot.send_message(
                chat_id=user_id,
                text=get_localized_string(language, "pause_none_active")
            )
    except Exception as e:
        logging.error(f"Error pausing compliments: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_localized_string("english", "error_pause")
        )

async def resume_compliments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resume scheduled compliments"""
    try:
        user_id = update.effective_chat.id
        user = user_database.get_user(user_id)
        
        if not user:
            await context.bot.send_message(
                chat_id=user_id,
                text=get_localized_string("english", "account_required")
            )
            return
            
        language = user.get("language", "english")
            
        # Get scheduler from context
        scheduler = context.bot_data.get("scheduler", None)
        if scheduler and scheduler.get_job(f"{user_id}_scheduled_compliment"):
            scheduler.resume_job(f"{user_id}_scheduled_compliment")
            
            message = get_localized_string(language, "resume_success")
            await context.bot.send_message(chat_id=user_id, text=message)
        else:
            # If job doesn't exist, create a new one
            start_compliments(context, user_id)
            await context.bot.send_message(
                chat_id=user_id,
                text=get_localized_string(language, "resume_success")
            )
    except Exception as e:
        logging.error(f"Error resuming compliments: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_localized_string(language, "error_resume")
        )

async def frequency_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /frequency command"""
    user_id = update.effective_chat.id
    user = user_database.get_user(user_id)
    
    if not user:
        language = "english"
        await context.bot.send_message(
            chat_id=user_id,
            text=get_localized_string(language, "not_registered")
        )
        return ConversationHandler.END
    
    return await send_frequency_selection(update, context)

async def personality_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /personality command"""
    user_id = update.effective_chat.id
    user = user_database.get_user(user_id)
    
    if not user:
        language = "english"
        await context.bot.send_message(
            chat_id=user_id,
            text=get_localized_string(language, "not_registered")
        )
        return ConversationHandler.END
    
    return await ask_personality_description(update, context)

async def general_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses that aren't caught by other handlers"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    # Get the data from the button
    button_data = query.data
    
    if button_data.startswith("lang_"):
        # If it's a language button, direct to language selection
        return await language_selection(update, context)
    elif button_data.startswith("freq_"):
        # If it's a frequency button, direct to frequency selection
        return await frequency_selection(update, context)
    elif button_data in ["confirm_delete", "cancel_delete"]:
        # If it's a delete confirmation button, direct to delete callback
        return await delete_account_callback(update, context)
    else:
        # For any other button, provide a helpful message
        await query.edit_message_text(
            text=get_localized_string(language, "unknown_button_press")
        )

async def start_compliments(context, user_id, initial_delay=None):
    try:
        user = user_database.get_user(user_id)
        if not user:
            logging.error(f"User {user_id} not found in database")
            return
        
        # Get user frequency preference
        frequency = user.get("compliment_frequency", "daily")
        base_interval = FREQUENCIES.get(frequency, FREQUENCIES["daily"])["seconds"]
        
        # If initial_delay is specified, use it, otherwise use the frequency-based interval
        interval = initial_delay if initial_delay is not None else base_interval
        
        scheduler = AsyncIOScheduler()
        scheduler.add_job(
            scheduled_compliment, 
            'interval', 
            seconds=interval, 
            args=(context, user_id, scheduler), 
            id=f"{user_id}_scheduled_compliment"
        )
        scheduler.start()
    except Exception as e:
        logging.error(f"Error starting compliments: {e}")

def reinit_comps(context):
    try:
        # Get all users from the database
        for user_id, user in user_database.user_base.items():
            # Only initialize for active users
            if user.get("active", True):
                # Convert string user_id to integer if needed
                user_id_int = int(user_id) if isinstance(user_id, str) else user_id
                
                # Get user frequency preference
                frequency = user.get("compliment_frequency", "daily")
                base_interval = FREQUENCIES.get(frequency, FREQUENCIES["daily"])["seconds"]
                
                start_compliments(context, user_id_int)
    except Exception as e:
        logging.error(f"Error reinitializing compliments: {e}")

async def main():
    try:
        application = ApplicationBuilder().token(BOT_TOKEN).build()
        
        # Message handler for regular text
        text_handler = MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_buttons)
        
        # Set up conversation handlers for different flows
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", start),
                CommandHandler("language", language_command),
                CommandHandler("frequency", frequency_command),
                CommandHandler("personality", personality_command),
                CommandHandler("delete_account", delete_account_confirmation),
                CommandHandler("myinfo", user_info),
                CommandHandler("help", help_command),
                CommandHandler("deleteaccount", delete_account_confirmation),
                CommandHandler("pause", pause_compliments),
                CommandHandler("resume", resume_compliments)
            ],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_name_input)],
                BOT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_bot_name_input)],
                LANGUAGE: [CallbackQueryHandler(language_selection, pattern=r"^lang_")],
                FREQUENCY: [CallbackQueryHandler(frequency_selection, pattern=r"^freq_")],
                PERSONALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_personality_input)],
                DELETE_ACCOUNT_CONFIRMATION: [CallbackQueryHandler(delete_account_callback, pattern=r"^confirm_delete|cancel_delete$")]
            },
            fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
            name="main_conversation",
            persistent=False
        )
        
        # Create separate conversation handlers for each command to avoid conflicts
        language_conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("language", language_command),
                CommandHandler("dil", language_command) 
            ],
            states={
                LANGUAGE: [CallbackQueryHandler(language_selection, pattern=r"^lang_")]
            },
            fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
            name="language_conversation",
            persistent=False
        )
        
        frequency_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("frequency", frequency_command)],
            states={
                FREQUENCY: [CallbackQueryHandler(frequency_selection, pattern=r"^freq_")]
            },
            fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
            name="frequency_conversation",
            persistent=False
        )
        
        personality_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("personality", personality_command)],
            states={
                PERSONALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_personality_input)]
            },
            fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
            name="personality_conversation",
            persistent=False
        )
        
        delete_account_conv_handler = ConversationHandler(
            entry_points=[CommandHandler("delete_account", delete_account_confirmation)],
            states={
                DELETE_ACCOUNT_CONFIRMATION: [CallbackQueryHandler(delete_account_callback, pattern=r"^confirm_delete|cancel_delete$")]
            },
            fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
            name="delete_account_conversation",
            persistent=False
        )
        
        # Add all the conversation handlers - order matters!
        application.add_handler(delete_account_conv_handler)
        application.add_handler(language_conv_handler)
        application.add_handler(frequency_conv_handler)
        application.add_handler(personality_conv_handler)
        application.add_handler(conv_handler)
        
        # Other command handlers
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("info", user_info))
        application.add_handler(CommandHandler("pause_compliments", pause_compliments))
        application.add_handler(CommandHandler("resume_compliments", resume_compliments))
        
        # Add callback query handler for any other button presses
        application.add_handler(CallbackQueryHandler(general_button_callback))
        
        # Message handler for regular conversations (add last to avoid conflicts)
        application.add_handler(text_handler)
        
        # Store scheduler in application context
        scheduler = AsyncIOScheduler()
        application.bot_data["scheduler"] = scheduler
        
        # Initialize compliments for existing users
        reinit_comps(application)
        
        # Start the scheduler
        scheduler.start()
        
        # Start the bot
        await application.initialize()
        await application.start()
        await application.updater.start_polling()
        
        # Keep the bot running until interrupted
        logging.info("Bot started. Press Ctrl+C to stop.")
        await asyncio.Event().wait()  # Run forever until interrupted
        
    except Exception as e:
        logging.error(f"Critical error in main: {e}")
    finally:
        # Properly close everything
        if 'application' in locals():
            if hasattr(application, 'updater') and application.updater:
                await application.updater.stop()
            await application.stop()
            await application.shutdown()
        
        if 'scheduler' in locals() and scheduler.running:
            scheduler.shutdown()

def run_bot():
    # Configure logging
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO,
        handlers=[
            logging.FileHandler("compbot.log"),
            logging.StreamHandler()
        ]
    )
    
    # Use a new event loop approach
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user.")
        if loop.is_running():
            # Cancel all tasks
            for task in asyncio.all_tasks(loop):
                task.cancel()
    except Exception as e:
        logging.error(f"Error in main execution: {e}")
    finally:
        if loop.is_running():
            loop.stop()
        if not loop.is_closed():
            loop.close()

if __name__ == '__main__':
    run_bot()
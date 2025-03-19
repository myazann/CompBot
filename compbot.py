import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.constants import ParseMode
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
NAME, BOT_NAME, LANGUAGE, FREQUENCY, PERSONALITY, PERSONALITY_OPTIONS, DELETE_ACCOUNT_CONFIRMATION = range(7)

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
{get_localized_string(language, "menu_delete")} - {get_localized_string(language, "cmd_delete")}
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
    
    # Set default bot name
    user_database.update_user_bot_name(user_id, "Romeo")
    
    # Confirm name selection
    confirmation_msg = get_localized_string("english", "name_confirmation", name=name)
    await context.bot.send_message(chat_id=user_id, text=confirmation_msg)
    
    # Now ask for language preference
    await send_language_selection(update, context)
    return LANGUAGE

async def ask_bot_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for a bot name"""
    query = update.callback_query if update.callback_query else None
    user_id = query.from_user.id if query else update.effective_chat.id
    
    # Get user for localization
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    # Create keyboard with cancel/back options
    keyboard = [
        [InlineKeyboardButton("Keep default (Romeo)", callback_data="keep_default_name")],
        [InlineKeyboardButton("Cancel", callback_data="cancel_name_change")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Ask for bot name
    msg = get_localized_string(language, "ask_bot_name") + "\n\nOr choose an option below:"
    await context.bot.send_message(chat_id=user_id, text=msg, reply_markup=reply_markup)
    
    # Set the next expected input to be bot name
    context.user_data["setup_stage"] = "bot_name"
    context.user_data["from_personality"] = True
    return BOT_NAME

async def process_bot_name_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the bot name input from the user"""
    user_id = update.effective_chat.id
    bot_name = update.message.text.strip()
    
    # Get user for localization
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    # Default bot name if user doesn't provide one
    if not bot_name or len(bot_name) == 0:
        bot_name = "Romeo"
    
    # Update user with custom bot name
    user_database.update_user_bot_name(user_id, bot_name)
    
    # Confirm bot name selection
    confirmation_msg = get_localized_string(language, "bot_name_confirmation", bot_name=bot_name)
    await context.bot.send_message(chat_id=user_id, text=confirmation_msg)
    
    # Check if we're coming from personality menu or initial setup
    setup_stage = context.user_data.get("setup_stage", "")
    if setup_stage == "bot_name" and "from_personality" in context.user_data:
        # If coming from personality command, just show main menu
        await send_main_menu(update, context)
        return ConversationHandler.END
    
    # Otherwise continue with language selection (initial setup flow)
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

async def language_selection_initial_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process language selection callback during initial setup"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    selected_lang = query.data.replace("lang_", "")
    
    # Update user's language preference
    user = user_database.update_user_language(user_id, selected_lang)
    
    # Get language-specific confirmation message
    confirmation = get_localized_string(selected_lang, "language_confirmation")
    await context.bot.send_message(chat_id=user_id, text=confirmation)
    
    # Now ask for frequency preference - this is the onboarding flow
    await send_frequency_selection(update, context)
    return FREQUENCY

async def language_selection_after_setup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process language selection callback after initial setup"""
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
    
    # Edit the inline keyboard message with the confirmation
    await query.edit_message_text(text=confirmation)
    
    # Add the customization message with a playful tone
    customization_msg = "Oh, and just so you know, darling... you can give me a new name or adjust my personality anytime using the /personality command! 💫"
    await context.bot.send_message(chat_id=user_id, text=customization_msg)
    
    if in_setup:
        # Continue with setup flow
        await send_frequency_selection(update, context)
        return FREQUENCY
    else:
        # Give a flirty goodbye when just changing the language
        await context.bot.send_message(
            chat_id=user_id, 
            text="Your language preferences are saved, sweetheart! Anything else I can help you with? 😘"
        )
        # End conversation if this was just a language change
        return ConversationHandler.END

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
    frequency_code = query.data.replace("freq_", "")
    
    # Get the user's current language
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    # Update frequency in database
    user_database.update_compliment_frequency(user_id, frequency_code)
    
    # Add a flirty message based on frequency selection
    if frequency_code == "never":
        flirty_msg = "Playing hard to get, I see? 😏 I'll respect your space, but I'm here whenever you want to chat!"
    elif frequency_code in ["daily", "rarely"]:
        flirty_msg = "I'll be counting the moments until our next interaction, beautiful! 💖"
    else:
        flirty_msg = "I can't wait to shower you with sweet words! You've made me the happiest bot in the world! 😍"
    
    await context.bot.send_message(chat_id=user_id, text=flirty_msg)
    
    # Add the customization message
    customization_msg = "Oh, and just so you know, darling... you can give me a new name or adjust my personality anytime using the /personality command! 💫"
    await context.bot.send_message(chat_id=user_id, text=customization_msg)
    
    # Complete the setup and send the main menu
    await send_main_menu(update, context)
    
    # Start the compliment scheduling for this user
    await start_compliments(context, user_id)
    
    context.user_data.pop("setup_stage", None)

    # End conversation
    return ConversationHandler.END

async def ask_personality_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for a free-form personality description"""
    query = update.callback_query if update.callback_query else None
    user_id = query.from_user.id if query else update.effective_chat.id
    
    # Get user for localization
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    # Create a message asking for personality description
    msg = "Please describe what kind of personality you'd like me to have (e.g., friendly, flirty, professional, poetic, humorous, or any other style):"
    playful_msg = msg + "\n\nDon't be shy, tell me how you want me to treat you... I'm all yours to customize! 💋"
    
    await context.bot.send_message(
        chat_id=user_id,
        text=playful_msg
    )
    return PERSONALITY

async def process_personality_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process the personality description input from the user"""
    user_id = update.effective_chat.id
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    try:
        # Get the user's input
        personality_desc = update.message.text.strip()
        
        # If no input, use default
        if not personality_desc or len(personality_desc) == 0:
            personality_desc = get_localized_string(language, "personality_default")
        
        # Save to database with the correct parameter signature
        user_database.update_user_personality(user_id, "custom", personality_desc)
        
        # Send confirmation
        confirmation_msg = get_localized_string(language, "personality_confirmation", personality_desc=personality_desc)
        await context.bot.send_message(chat_id=user_id, text=confirmation_msg)
        
        # Add a flirty message based on personality selection
        flirty_confirmation = "I'll be exactly how you want me to be, just for you! 💕 Can't wait to make you smile!"
        await context.bot.send_message(chat_id=user_id, text=flirty_confirmation)
        
        # Complete the setup and send the main menu
        await send_main_menu(update, context)
        
        # Start the compliment scheduling for this user
        await start_compliments(context, user_id)
        
        # End conversation
        return ConversationHandler.END
        
    except Exception as e:
        logging.error(f"Error processing personality input: {e}")
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
        return
        
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
        
        # Create a more playful and personal info display
        info_message = f"""
*{get_localized_string(language, "info_title")}*

{get_localized_string(language, "info_name")}: {user['name']} 💖
{get_localized_string(language, "info_username")}: {user['user_name'] or get_localized_string(language, "info_not_set")}
{get_localized_string(language, "info_language")}: {LANGUAGES.get(language, "English ")}
{get_localized_string(language, "info_personality")}: {personality_desc or get_localized_string(language, "personality_default")}
{get_localized_string(language, "info_frequency")}: {FREQUENCIES.get(frequency, FREQUENCIES["daily"])["label"]}
{get_localized_string(language, "info_created")}: {user['join_date']}

{get_localized_string(language, "info_settings_change")}
        """
        
        await context.bot.send_message(
            chat_id=user_id,
            text=info_message,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Add a flirty message after showing the info
        flirty_msg = "Looking at all your details makes me adore you even more! Is there anything you'd like to change, sweetheart? 💫"
        await context.bot.send_message(chat_id=user_id, text=flirty_msg)
        
    except Exception as e:
        logging.error(f"Error in user_info command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_localized_string("english", "error_info")
        )

async def handle_menu_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle menu button presses and redirect to appropriate handlers"""
    if not update.message or not update.message.text:
        return
        
    # Check if we're in a setup flow
    # This is critical - if we're in the setup flow, process the input accordingly
    setup_stage = context.user_data.get("setup_stage", None)
    if setup_stage == "name":
        return await process_name_input(update, context)
        
    message_text = update.message.text.strip()
    user_id = update.effective_chat.id
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
            "help": help_command,
            "yardım": help_command,  # Turkish version
            "deleteaccount": delete_account_confirmation,
            "hesabısil": delete_account_confirmation  # Turkish version
        }
        
        if command in command_map:
            logging.info(f"Command matched: {command}")
            return await command_map[command](update, context)
    
    # Check for exact button text matches
    button_map = {
        get_localized_string(language, 'menu_language'): language_command,
        get_localized_string(language, 'menu_frequency'): frequency_command,
        get_localized_string(language, 'menu_personality'): personality_command,
        get_localized_string(language, 'menu_help'): help_command,
        get_localized_string(language, 'menu_delete'): delete_account_confirmation
    }
    
    if message_text in button_map:
        logging.info(f"Button text matched: {message_text}")
        return await button_map[message_text](update, context)
    
    # If not recognized as a command or button text, pass to regular message handler
    logging.info("No command or button match, passing to respond_to_message")
    return await respond_to_message(update, context)

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
        return
        
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
        
        # Create a more playful and personal info display
        info_message = f"""
*{get_localized_string(language, "info_title")}*

{get_localized_string(language, "info_name")}: {user['name']} 💖
{get_localized_string(language, "info_username")}: {user['user_name'] or get_localized_string(language, "info_not_set")}
{get_localized_string(language, "info_language")}: {LANGUAGES.get(language, "English ")}
{get_localized_string(language, "info_personality")}: {personality_desc or get_localized_string(language, "personality_default")}
{get_localized_string(language, "info_frequency")}: {FREQUENCIES.get(frequency, FREQUENCIES["daily"])["label"]}
{get_localized_string(language, "info_created")}: {user['join_date']}

{get_localized_string(language, "info_settings_change")}
        """
        
        await context.bot.send_message(
            chat_id=user_id,
            text=info_message,
            parse_mode=ParseMode.MARKDOWN
        )
        
        # Add a flirty message after showing the info
        flirty_msg = "Looking at all your details makes me adore you even more! Is there anything you'd like to change, sweetheart? 💫"
        await context.bot.send_message(chat_id=user_id, text=flirty_msg)
        
    except Exception as e:
        logging.error(f"Error in user_info command: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=get_localized_string("english", "error_info")
        )

async def respond_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process regular text messages from users"""
    try:
        user_id = update.effective_chat.id
        user = user_database.get_user(user_id)
        
        # If user doesn't exist in database, they need to go through setup
        if not user:
            logging.warning(f"User {user_id} sent a message but is not in the database. Starting onboarding.")
            # Start onboarding process
            await context.bot.send_message(
                chat_id=user_id,
                text=get_localized_string("english", "first_time_greeting")
            )
            
            # Ask for name first
            context.user_data["setup_stage"] = "name"
            
            msg = get_localized_string("english", "ask_name")
            await context.bot.send_message(chat_id=user_id, text=msg)
            return NAME
        
        # If we have a valid user, process their message as normal conversation
        user_name = user["name"]
        language = user.get("language", "english")
        personality_desc = user.get("personality_description", "")
        bot_name = user.get("bot_name", "Romeo")
        
        # Store user message in history
        user_database.upsert_user_history(user_id, {
            "role": "user",
            "content": update.message.text
        })
        
        # Generate response using AI
        prompt = get_response_prompt(user_name, update.message.text, language=language, personality=personality_desc, bot_name=bot_name)
        response = compbot.generate(prompt, gen_params={"max_tokens": 512, "temperature": 0.7})
        
        # Store the assistant response
        user_database.upsert_user_history(user_id, {
            "role": "assistant",
            "content": response
        })
        
        # Send the response to the user
        await context.bot.send_message(chat_id=user_id, text=response)
        
        # Return ConversationHandler.END to make sure we're not in any conversation
        return ConversationHandler.END
        
    except Exception as e:
        logging.error(f"Error responding to message: {e}")
        await context.bot.send_message(
            chat_id=update.effective_chat.id, 
            text=get_localized_string("english", "error_general")
        )
        return ConversationHandler.END

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
    
    language = user.get("language", "english")
    current_bot_name = user.get("bot_name", "ComplimentBot")
    
    # Create inline keyboard with options
    keyboard = [
        [InlineKeyboardButton("Change bot name", callback_data="change_bot_name")],
        [InlineKeyboardButton("Change personality", callback_data="change_personality")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send options message
    await context.bot.send_message(
        chat_id=user_id,
        text=f"Current bot name: {current_bot_name}\n\nWhat would you like to change?",
        reply_markup=reply_markup
    )
    
    # Set conversation state to handle personality options selection
    return PERSONALITY_OPTIONS

async def personality_options_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process personality options selection"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    selected_option = query.data
    
    if selected_option == "change_bot_name":
        await ask_bot_name(update, context)
        return BOT_NAME
    elif selected_option == "change_personality":
        await ask_personality_description(update, context)
        return PERSONALITY

async def ask_personality_description(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ask for a free-form personality description"""
    query = update.callback_query if update.callback_query else None
    user_id = query.from_user.id if query else update.effective_chat.id
    
    # Get user for localization
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    # Create a message asking for personality description
    msg = "Please describe what kind of personality you'd like me to have (e.g., friendly, flirty, professional, poetic, humorous, or any other style):"
    playful_msg = msg + "\n\nDon't be shy, tell me how you want me to treat you... I'm all yours to customize! 💋"
    
    await context.bot.send_message(
        chat_id=user_id,
        text=playful_msg
    )
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
    
    # End conversation
    return ConversationHandler.END

async def bot_name_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button presses in the bot name selection dialog"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    button_data = query.data
    
    # Get user for localization
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    if button_data == "keep_default_name":
        # Set default bot name (Romeo)
        user_database.update_user_bot_name(user_id, "Romeo")
        
        # Confirm bot name selection
        confirmation_msg = get_localized_string(language, "bot_name_confirmation", bot_name="Romeo")
        await context.bot.send_message(chat_id=user_id, text=confirmation_msg)
        
    elif button_data == "cancel_name_change":
        # User cancelled the name change process
        await context.bot.send_message(chat_id=user_id, text="Bot name change cancelled.")
    
    # Check if we're in personality flow and return to main menu
    if "from_personality" in context.user_data:
        await send_main_menu(update, context)
        return ConversationHandler.END
    
    # Otherwise, continue with the setup flow
    await send_language_selection(update, context)
    return LANGUAGE

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
        return await language_selection_after_setup(update, context)
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

async def send_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send main menu keyboard to the user"""
    # Determine user_id based on whether we're handling a message or callback query
    if update.callback_query:
        user_id = update.callback_query.from_user.id
    else:
        user_id = update.effective_chat.id
    
    # Get user for localization
    user = user_database.get_user(user_id)
    language = "english" if not user else user.get("language", "english")
    
    # Create main menu keyboard using localized strings
    keyboard = [
        [
            KeyboardButton("/" + get_localized_string(language, 'menu_language').lower().replace(" ", "")), 
            KeyboardButton("/" + get_localized_string(language, 'menu_frequency').lower().replace(" ", ""))
        ],
        [
            KeyboardButton("/" + get_localized_string(language, 'menu_personality').lower().replace(" ", "")), 
        ],
        [
            KeyboardButton("/" + get_localized_string(language, 'menu_help').lower().replace(" ", "")),
            KeyboardButton("/" + get_localized_string(language, 'menu_delete').lower().replace(" ", ""))
        ]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await context.bot.send_message(chat_id=user_id, text="Hey baby, how is your day going?", reply_markup=reply_markup)

async def start_compliments(context, user_id, initial_delay=None):
    """Start the scheduled compliments for a user"""
    try:
        # Cancel any existing jobs for this user
        scheduler = context.bot_data.get("scheduler", None)
        if scheduler and scheduler.get_job(f"{user_id}_scheduled_compliment"):
            scheduler.remove_job(f"{user_id}_scheduled_compliment")
        
        user = user_database.get_user(user_id)
        if not user:
            return
            
        frequency = user.get("compliment_frequency", "daily")
        # If frequency is "never", don't schedule compliments
        if frequency == "never":
            return
            
        base_interval = FREQUENCIES.get(frequency, FREQUENCIES["daily"])["seconds"]
        
        # If initial_delay is specified, use it, otherwise use the frequency-based interval
        interval = initial_delay if initial_delay is not None else base_interval
        
        scheduler = context.bot_data.get("scheduler", None)
        if scheduler:
            scheduler.add_job(
                scheduled_compliment, 
                'interval', 
                seconds=interval, 
                args=(context, user_id, scheduler), 
                id=f"{user_id}_scheduled_compliment"
            )
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
        
        # Set up conversation handlers for different flows
        conv_handler = ConversationHandler(
            entry_points=[
                CommandHandler("start", start),
                CommandHandler("language", language_command),
                CommandHandler("frequency", frequency_command),
                CommandHandler("personality", personality_command),
                CommandHandler("delete_account", delete_account_confirmation),
                CommandHandler("help", help_command),
                CommandHandler("deleteaccount", delete_account_confirmation),
            ],
            states={
                NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_name_input)],
                BOT_NAME: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, process_bot_name_input),
                    CallbackQueryHandler(bot_name_button_callback, pattern=r"^keep_default_name|cancel_name_change$")
                ],
                LANGUAGE: [CallbackQueryHandler(language_selection_initial_setup, pattern=r"^lang_")],
                FREQUENCY: [CallbackQueryHandler(frequency_selection, pattern=r"^freq_")],
                PERSONALITY_OPTIONS: [CallbackQueryHandler(personality_options_selection, pattern=r"^change_bot_name|change_personality$")],
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
                LANGUAGE: [CallbackQueryHandler(language_selection_after_setup, pattern=r"^lang_")]
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
                PERSONALITY_OPTIONS: [CallbackQueryHandler(personality_options_selection, pattern=r"^change_bot_name|change_personality$")],
                PERSONALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_personality_input)],
                BOT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_bot_name_input)]
            },
            fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
            name="personality_conversation",
            persistent=False
        )
        
        bot_name_conv_handler = ConversationHandler(
            entry_points=[CallbackQueryHandler(bot_name_button_callback, pattern=r"^keep_default_name|cancel_name_change$")],
            states={
                BOT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_bot_name_input)]
            },
            fallbacks=[CommandHandler("cancel", lambda u, c: ConversationHandler.END)],
            name="bot_name_conversation",
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
        application.add_handler(bot_name_conv_handler)
        application.add_handler(conv_handler)
        
        # Other command handlers
        application.add_handler(CommandHandler("help", help_command))
        
        # Add callback query handler for any other button presses
        application.add_handler(CallbackQueryHandler(general_button_callback))
        
        # Message handler for regular conversations (add last to avoid conflicts)
        # Use handle_menu_buttons instead of going directly to respond_to_message
        # This ensures proper routing based on message content
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_menu_buttons))
        
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
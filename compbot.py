import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
import nest_asyncio
import asyncio
import os
os.chdir("c:\\Users\\myazan\\OneDrive - HvA\\Desktop\\CompBot")

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
nest_asyncio.apply()

from database import Database
from utils import comp_prompt, get_random_interval, prompt_chatgpt

BOT_TOKEN = "6473931448:AAFZkDBOVuMGj6lB2Gu9CQdoXM4lhFbWGSw"
random_msg_interval = 7200
user_database = Database()

async def scheduled_compliment(context, user_id, scheduler):
    # print(scheduler.get_jobs())
    chat_history = user_database.get_user_history(user_id)
    user_name = user_database.get_user(user_id)["name"]
    comp = prompt_chatgpt(comp_prompt(user_name, chat_history))
    user_database.upsert_user_history(user_id, {
        "role": "assistant",
        "content": comp
    })
    new_interval = get_random_interval(random_msg_interval, 3)
    await context.bot.send_message(chat_id=user_id, text=comp)
    scheduler.reschedule_job(f"{user_id}_scheduled_compliment", trigger=IntervalTrigger(seconds=new_interval))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = user_database.get_user(update.message.from_user.id)
    print(user)
    if user:
        await context.bot.send_message(chat_id=user["user_id"], text=f"Tekrardan hoş geldin {user['name']}, seni çok özlemiştim..")
    else:
        user = user_database.insert_user(update)
        await context.bot.send_message(chat_id=user["user_id"], text=f"Merhaba {user['name']}.. Mert abim beni sana hak ettiğin iltifatları duyman için görevlendirdi. Hazırsan başlayalım..")
        start_compliments(context, user["user_id"])

def start_compliments(context, user_id):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_compliment, 'interval', seconds=2, args=(context, user_id, scheduler), id=f"{user_id}_scheduled_compliment")
    scheduler.start()

def reinit_comps(context):
    for user in user_database.user_base.keys():
        start_compliments(context, user)

async def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    start_handler = CommandHandler("start", start)
    # echo_handler = MessageHandler(filters.TEXT & (~filters.COMMAND), echo)
    application.add_handler(start_handler)
    reinit_comps(application)
    # application.add_handler(echo_handler)

    await application.run_polling()

if __name__ == '__main__':
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    asyncio.run(main())
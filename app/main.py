from modules.model import Model
from dotenv import load_dotenv
import telebot
import os

load_dotenv()

TELEGRAM_TOKEN = "7882340349:AAF0DsxE9YIFSX9Dtx01DsY321n6JQs7EkU"
MISTAL_API = "K4zGEUUJAQbeC8E2j0SDd4mRAVTwe5OT"
OPENAI_API_TOKEN = os.getenv("OPENAI API TOKEN")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
model = Model(MISTAL_API)


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Вы можете задать свой вопрос.")


@bot.message_handler(func=lambda message: True)
def echo_all(message):

    loading_message = bot.send_message(message.chat.id, "Формирую ответ...")

    response = model.process_user_query(message.text)

    bot.delete_message(message.chat.id, loading_message.message_id)

    bot.send_message(message.chat.id, response)


bot.polling()

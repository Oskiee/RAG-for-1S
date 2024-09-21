from modules.model import Model
from dotenv import load_dotenv
import telebot
from telebot import types
import os

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM TOKEN")
MISTAL_API = os.getenv("MISTRAL_API_KEY")
# OPENAI_API_TOKEN = os.getenv("OPENAI API TOKEN")

bot = telebot.TeleBot(TELEGRAM_TOKEN)
model = Model(MISTAL_API)
# chat_history = {'user': [], 'bot': []}
# images = []


# def get_history_string():
#     history = ""
#     for i in range(len(chat_history['user'])):
#         history += f"User: {chat_history['user'][i]}\n"
#         history += f"Bot: {chat_history['bot'][i]}\n"
#     return history


@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Вы можете задать свой вопрос.")


@bot.message_handler(func=lambda message: True)
def echo_all(message):
    response = model.process_user_query(message.text) # add chat history
    bot.send_message(message.chat.id, response)

#
# @bot.callback_query_handler(func=lambda call: True)
# def callback_query(call):
#     if call.data.startswith('show_images'):
#         for img in images:
#             with open(img, 'rb') as photo:
#                 bot.send_photo(call.message.chat.id, photo)


bot.polling()
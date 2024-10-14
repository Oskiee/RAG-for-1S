import csv
from modules.model import Model
from dotenv import load_dotenv
import telebot
from telebot import types
import os
import re  # Для работы с регулярными выражениями
from fuzzywuzzy import fuzz

load_dotenv()

TELEGRAM_TOKEN = "7882340349:AAF0DsxE9YIFSX9Dtx01DsY321n6JQs7EkU"
MISTAL_API = "K4zGEUUJAQbeC8E2j0SDd4mRAVTwe5OT"
OPENAI_API_TOKEN = os.getenv("OPENAI API TOKEN")
CSV_FILE = "user_feedback.csv"
METADATA_FILE = "metadata.csv"

bot = telebot.TeleBot(TELEGRAM_TOKEN)
model = Model(MISTAL_API)

# Переменная для хранения состояния пользователя (ожидание выбора причины)
user_states = {}

# Функция для создания клавиатуры с кнопкой "Проверить доступность"
def create_availability_keyboard():
    keyboard = types.ReplyKeyboardMarkup(row_width=1, resize_keyboard=True)
    check_availability_button = types.KeyboardButton("Проверить доступность")
    keyboard.add(check_availability_button)
    return keyboard

# Функция для создания клавиатуры "палец вверх" и "палец вниз"
def create_feedback_keyboard(selected=None):
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    if selected == "thumbs_up":
        thumbs_up = types.InlineKeyboardButton("👍 Вы выбрали", callback_data="thumbs_up_selected")
        thumbs_down = types.InlineKeyboardButton("👎", callback_data="thumbs_down")
    elif selected == "thumbs_down":
        thumbs_up = types.InlineKeyboardButton("👍", callback_data="thumbs_up")
        thumbs_down = types.InlineKeyboardButton("👎 Вы выбрали", callback_data="thumbs_down_selected")
    else:
        thumbs_up = types.InlineKeyboardButton("👍", callback_data="thumbs_up")
        thumbs_down = types.InlineKeyboardButton("👎", callback_data="thumbs_down")

    keyboard.add(thumbs_up, thumbs_down)
    return keyboard

# Функция для создания клавиатуры причин
def create_reason_keyboard():
    keyboard = types.InlineKeyboardMarkup(row_width=1)
    reason_1 = types.InlineKeyboardButton("Полностью мимо", callback_data="reason_miss")
    reason_2 = types.InlineKeyboardButton("В целом верно, но вопрос был не в этом", callback_data="reason_partial")
    reason_3 = types.InlineKeyboardButton("Некорректный источник", callback_data="reason_incorrect_source")  # Изменено
    reason_4 = types.InlineKeyboardButton("Другое", callback_data="reason_other")
    keyboard.add(reason_1, reason_2, reason_3, reason_4)
    return keyboard


# Функция для сохранения данных в CSV
def save_feedback_to_csv(user_id, user_query, bot_response, rating, reason=None):
    with open(CSV_FILE, mode='a', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow([user_id, user_query, bot_response, rating, reason])

# Функция для очистки текста от знаков препинания и приведения к нижнему регистру
def clean_text(text):
    return re.sub(r'[^\w\s]', '', text.lower())

# Функция для чтения metadata.csv и возврата списка значений из столбцов "Name" и "URL" с очисткой текста
def load_metadata():
    metadata = []
    with open(METADATA_FILE, mode='r', newline='', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            metadata.append({"name": clean_text(row['Name']).strip(), "url": row['URL']})
    return metadata

# Функция для логгирования поиска совпадений в консоли
def log_name_search(user_id, user_query, response, name_found):
    if name_found:
        print(f"User ID: {user_id}, Query: '{user_query}', Response: '{response}', Name Found: '{name_found}'")
    else:
        print(f"User ID: {user_id}, Query: '{user_query}', Response: '{response}', Name Found: None")

# Обработка команды /start и /help
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Вы можете задать свой вопрос или проверить доступность бота.", reply_markup=create_availability_keyboard())

# Обработка нажатия на кнопку "Проверить доступность"
@bot.message_handler(func=lambda message: message.text == "Проверить доступность")
def check_availability(message):
    bot.reply_to(message, "Бот доступен. Можете задавать вопрос.", reply_markup=create_availability_keyboard())

# Функция для извлечения текста после слова "Источник:"
def extract_source_text(response):
    match = re.search(r'Источник: (.+)', response)  # Поиск текста после "Источник:"
    if match:
        return match.group(1).strip()  # Возвращаем текст после "Источник:"
    return None

# Обработка любых других сообщений
@bot.message_handler(func=lambda message: not user_states.get(message.from_user.id, {}).get('waiting_for_availability', False))
def echo_all(message):
    loading_message = bot.send_message(message.chat.id, "Формирую ответ...")
    try:
        # Получаем ответ бота
        response = model.process_user_query(message.text)

        # Извлекаем текст после "Источник:"
        source_text = extract_source_text(response)

        # Если текст после "Источник:" найден, продолжаем поиск по нему
        if source_text:
            # Загружаем имена и ссылки из файла metadata.csv
            metadata = load_metadata()

            # Очищаем текст для поиска
            source_text_cleaned = clean_text(source_text)

            # Проверяем, есть ли совпадение с metadata.csv
            name_found = None
            url_found = None
            print(f"Ищем в строке: '{source_text_cleaned}'")
            for entry in metadata:
                similarity = fuzz.token_set_ratio(entry['name'], source_text_cleaned)
                if similarity >= 80:  # Пороговое значение похожести
                    name_found = entry['name']
                    url_found = entry['url']
                    print(f"Найдено совпадение с похожестью {similarity}%: '{entry['name']}'")
                    break

            # Если найдено совпадение, заменяем текст источника на кликабельную ссылку
            if name_found and url_found:
                response = re.sub(r'Источник: .+', f'Источник: <a href="{url_found}">ссылка</a>', response, flags=re.IGNORECASE)

        # Удаляем сообщение "Формирую ответ..."
        bot.delete_message(message.chat.id, loading_message.message_id)

        # Отправляем ответ пользователю (включаем поддержку HTML для ссылок)
        bot.send_message(message.chat.id, response, reply_markup=create_feedback_keyboard(), parse_mode="HTML")

        # Сохраняем состояние
        user_states[message.from_user.id] = {'query': message.text, 'response': response}

        # Логгируем поиск совпадений в консоли
        log_name_search(message.from_user.id, message.text, response, name_found)

        # Выводим результат проверки в консоль
        if name_found:
            print(f"Найдено имя '{name_found}' из metadata.csv, ссылка: {url_found}")
        else:
            print("Имя из metadata.csv не найдено в источнике.")
    except BaseException as error:
        print(f'An exception occurred: {error}')
        bot.send_message(message.chat.id, 'Извините, возникла ошибка. Измените запрос или попробуйте позже.')

# Обработка нажатий на кнопки "палец вверх" и "палец вниз"
@bot.callback_query_handler(func=lambda call: call.data in ["thumbs_up", "thumbs_down"])
def handle_feedback(call):
    user_id = call.from_user.id
    if call.data == "thumbs_up":
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      reply_markup=create_feedback_keyboard(selected="thumbs_up"))
        bot.answer_callback_query(call.id, "Спасибо за обратную связь! 👍")
        save_feedback_to_csv(user_id, user_states[user_id]['query'], user_states[user_id]['response'], "thumbs_up")
    elif call.data == "thumbs_down":
        bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id,
                                      reply_markup=create_feedback_keyboard(selected="thumbs_down"))
        bot.send_message(call.message.chat.id, "Пожалуйста, выберите причину негативного отзыва:",
                         reply_markup=create_reason_keyboard())
        user_states[user_id]['waiting_for_reason'] = True


# Обработка выбора причины
@bot.callback_query_handler(func=lambda call: call.data.startswith("reason_"))
def handle_reason_selection(call):
    user_id = call.from_user.id
    if 'waiting_for_reason' in user_states[user_id]:
        reason = call.data.split("_")[1]
        reason_mapping = {
            "miss": "Полностью мимо",
            "partial": "В целом верно, но вопрос был не в этом",
            "incorrect_source": "Некорректный источник",
            "other": "Другое"
        }

        reason_text = reason_mapping.get(reason, "Некорректный источник")  # Получаем текст причины
        bot.send_message(call.message.chat.id, f"Вы выбрали причину: {reason_text}. Спасибо, можете продолжать работу.")

        save_feedback_to_csv(user_id, user_states[user_id]['query'], user_states[user_id]['response'], "thumbs_down",
                             reason_text)
        user_states[user_id].pop('waiting_for_reason', None)
        bot.answer_callback_query(call.id)


bot.polling()

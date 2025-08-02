import telebot
from telebot import types
import random
import logging

def get_solo_keyboard():
    """Создает клавиатуру для SOLO-режима."""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton('/truth'), types.KeyboardButton('/dare'))
    markup.add(types.KeyboardButton('/end'))
    return markup

def handle_solo_commands(bot, message, session, themes_data):
    """
    Обрабатывает команды /truth и /dare для одиночного режима.
    
    Аргументы:
    bot: экземпляр telebot
    message: объект сообщения
    session: объект текущей игровой сессии
    themes_data: словарь с темами и заданиями
    """
    chat_id = message.chat.id
    command = message.text.lower()
    
    if command == '/truth' and session.theme:
        task = random.choice(themes_data[session.theme]["truths"])
        logging.info(f"Выбрана правда. Задание: {task}")
        bot.send_message(chat_id, f"Правда: {task}", reply_markup=get_solo_keyboard())
    elif command == '/dare' and session.theme:
        task = random.choice(themes_data[session.theme]["dares"])
        logging.info(f"Выбрано действие. Задание: {task}")
        bot.send_message(chat_id, f"Действие: {task}", reply_markup=get_solo_keyboard())
    elif command == '/end':
        # Команда /end обрабатывается в main.py
        pass
    else:
        bot.send_message(chat_id, "Используйте кнопки для выбора или команду /end для завершения.")

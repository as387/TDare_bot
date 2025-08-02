import telebot
from telebot import types
import random
import logging
import os
from solo_mode import handle_solo_commands, get_solo_keyboard

# --- Настройка логирования ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ВАЖНО: Замените 'YOUR_BOT_TOKEN' на токен, который вам выдал BotFather.
# Токен должен быть полным и содержать двоеточие. Например: '123456789:ABC_DEFGHIJ...'
TOKEN = '8275610340:AAHIC3WAbeppALRJPvT4h3J4x9PL-Few2H0'
bot = telebot.TeleBot(TOKEN)

# --- Динамическая загрузка вопросов и заданий из файлов ---
def load_themes(directory='themes'):
    """
    Динамически загружает темы из файлов в указанной директории.
    Файлы должны иметь формат:
    TRUTHS:
    - Вопрос 1
    - Вопрос 2
    DARES:
    - Задание 1
    - Задание 2
    """
    themes = {}
    if not os.path.exists(directory):
        logging.warning(f"Директория '{directory}' не найдена. Создаю ее...")
        os.makedirs(directory)
        return themes

    for filename in os.listdir(directory):
        if filename.endswith('.txt'):
            theme_name = os.path.splitext(filename)[0]
            file_path = os.path.join(directory, filename)
            current_section = None
            truths = []
            dares = []

            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line == 'TRUTHS:':
                        current_section = 'truths'
                    elif line == 'DARES:':
                        current_section = 'dares'
                    elif line and not line.startswith('#'):
                        if current_section == 'truths':
                            truths.append(line)
                        elif current_section == 'dares':
                            dares.append(line)

            if truths or dares:
                themes[theme_name] = {"truths": truths, "dares": dares}
                logging.info(f"Загружена тема '{theme_name}' из файла '{filename}'.")

    return themes

# Загружаем темы при запуске бота
THEMES = load_themes()

# --- Хранение состояний сессий ---
sessions = {}

# Класс для хранения состояния сессии
class GameSession:
    def __init__(self, mode, players, chat_id):
        self.mode = mode
        self.players = players
        self.chat_id = chat_id
        self.turn = None
        self.last_task = None
        self.game_active = True
        self.theme = None # Добавляем атрибут для темы
        logging.info(f"Создана новая игровая сессия в чате {chat_id} в режиме {mode} с игроками {players}.")

# --- Вспомогательные функции и клавиатуры (общие для всех режимов) ---

def get_session(chat_id):
    """Возвращает текущую игровую сессию для чата."""
    return sessions.get(chat_id)

def get_menu_keyboard():
    """Создает клавиатуру для главного меню."""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Играть одному", callback_data='solo_start'))
    markup.add(types.InlineKeyboardButton("Играть с другом", callback_data='duo_start_invite'))
    return markup

def get_theme_keyboard():
    """Создает Inline-клавиатуру для выбора темы на основе загруженных файлов."""
    markup = types.InlineKeyboardMarkup(row_width=1)
    if not THEMES:
        logging.warning("Нет доступных тем. Проверьте директорию 'themes'.")
        markup.add(types.InlineKeyboardButton("Темы не найдены", callback_data='no_theme'))
        return markup
        
    # Сортировка тем: "Сольный режим" всегда в конце
    theme_names = sorted(THEMES.keys())
    
    # Ищем "сольный режим" в списке тем
    solo_theme_name = None
    for name in theme_names:
        if name.lower() == 'сольный режим':
            solo_theme_name = name
            break
            
    # Если "сольный режим" найден, убираем его из основного списка
    if solo_theme_name:
        theme_names.remove(solo_theme_name)
        theme_names.append(solo_theme_name) # И добавляем в конец

    for theme_name in theme_names:
        # theme_name.title() преобразует имя файла (например, 'party') в заголовок ('Party')
        markup.add(types.InlineKeyboardButton(theme_name.title(), callback_data=f'theme:{theme_name}'))
    return markup

def get_truth_dare_inline_keyboard(user_id):
    """Создает Inline-клавиатуру для выбора 'Правда' или 'Действие'."""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Правда", callback_data=f'truth_self:{user_id}'),
               types.InlineKeyboardButton("Действие", callback_data=f'dare_self:{user_id}'))
    return markup

def get_enough_inline_keyboard(user_id):
    """Создает Inline-клавиатуру 'Достаточно' для игрока, который ждет."""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Достаточно", callback_data=f'enough:{user_id}'))
    return markup

def get_user_name(user_id, chat_id=None):
    """Получает имя пользователя по его ID."""
    try:
        user = bot.get_chat_member(chat_id, user_id).user if chat_id else bot.get_chat(user_id)
        return user.first_name if user.first_name else user.username
    except Exception:
        logging.error(f"Не удалось получить имя пользователя с ID {user_id}.", exc_info=True)
        return "Игрок"

# --- Обработчики команд ---

@bot.message_handler(commands=['start'])
def handle_start(message):
    """Обрабатывает команду /start, показывая главное меню."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    logging.info(f"Получена команда /start от пользователя {user_id} в чате {chat_id}.")
    
    session = get_session(chat_id)
    if session and session.game_active:
        logging.info(f"В чате {chat_id} уже идёт игра.")
        bot.send_message(chat_id, "Уже идёт игра! Завершите её командой /end.", reply_markup=types.ReplyKeyboardRemove())
        return

    bot.send_message(chat_id, "Привет! Выбери режим игры:", reply_markup=get_menu_keyboard())

@bot.message_handler(commands=['duo'])
def handle_duo_command(message):
    """
    Обрабатывает команду /duo, начиная приглашение для DUO-игры.
    """
    chat_id = message.chat.id
    user_id = message.from_user.id
    logging.info(f"Получена команда /duo от пользователя {user_id} в чате {chat_id}.")
    
    # Проверка, что игра начинается в групповом чате
    if message.chat.type not in ['group', 'supergroup']:
        bot.send_message(chat_id, "Чтобы играть с другом, нужно создать групповой чат и добавить меня туда.")
        return
        
    session = get_session(chat_id)
    if session and session.game_active:
        bot.send_message(chat_id, "В этом чате уже идёт игра! Завершите её командой /end.")
        return
    
    # Создаем клавиатуру с кнопкой "Присоединиться"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Присоединиться к игре", callback_data=f'join_duo:{user_id}'))
    
    player_name = get_user_name(user_id, chat_id)
    bot.send_message(chat_id, f"**{player_name}** приглашает в игру «Правда или Действие»! Нажмите кнопку, чтобы присоединиться.",
                     parse_mode="Markdown", reply_markup=markup)
    # Добавляем сообщение, чтобы пользователю было понятно, что делать дальше
    bot.send_message(chat_id, f"Отлично, **{player_name}**! Теперь твой друг должен нажать на кнопку, чтобы начать игру.", parse_mode="Markdown")

@bot.message_handler(commands=['end'])
def handle_end(message):
    """Обрабатывает команду /end, завершая текущую игру."""
    chat_id = message.chat.id
    user_id = message.from_user.id
    session = get_session(chat_id)
    logging.info(f"Получена команда /end от пользователя {user_id} в чате {chat_id}.")
    
    if session and session.game_active:
        session.game_active = False
        sessions.pop(chat_id, None)
        logging.info(f"Игра в чате {chat_id} завершена.")
        bot.send_message(chat_id, "Игра завершена.", reply_markup=types.ReplyKeyboardRemove())
    else:
        logging.info(f"Нет активной игры для завершения в чате {chat_id}.")
        bot.send_message(chat_id, "Нет активной игры. Начните новую с /start.", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(commands=['rule'])
def handle_rule_command(message):
    try:
        with open('rules.txt', 'r', encoding='utf-8') as f:
            bot.send_message(message.chat.id, f.read())
    except Exception as e:
        logging.error(f"Ошибка чтения правил: {e}")
        bot.send_message(message.chat.id, "Правила временно недоступны. Попробуйте позже.")

# --- Обработчик добавления бота в новый чат ---
@bot.message_handler(content_types=['new_chat_members'])
def handle_new_chat_members(message):
    """
    Автоматически запускает DUO-игру, когда бот добавлен в групповой чат.
    """
    chat_id = message.chat.id
    new_members = message.new_chat_members
    
    # Проверяем, что в списке новых участников есть сам бот
    if bot.get_me() in new_members:
        logging.info(f"Бот добавлен в чат {chat_id}. Запускаю автоматическое приглашение.")
        
        session = get_session(chat_id)
        if session and session.game_active:
            bot.send_message(chat_id, "В этом чате уже идёт игра! Завершите её командой /end.")
            return

        # Инициатор игры - тот, кто добавил бота.
        # Если есть несколько новых участников, берем первого.
        initiator_id = message.from_user.id
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Присоединиться к игре", callback_data=f'join_duo:{initiator_id}'))
        
        player_name = get_user_name(initiator_id, chat_id)
        bot.send_message(chat_id, 
                         f"Привет! Спасибо, что добавил меня в чат.\n\n**{player_name}** приглашает в игру «Правда или Действие»! Нажмите кнопку, чтобы присоединиться.",
                         parse_mode="Markdown", 
                         reply_markup=markup)

# --- Обработчики Callback-запросов (для кнопок) ---

@bot.callback_query_handler(func=lambda call: call.data == 'solo_start')
def handle_callback_solo_start(call):
    """Обрабатывает нажатие кнопки 'Играть одному'."""
    if call.message is None:
        logging.error("handle_callback_solo_start: call.message is None")
        bot.answer_callback_query(call.id, "Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        return
        
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    logging.info(f"Получен callback 'solo_start' от пользователя {user_id} в чате {chat_id}.")
    
    session = get_session(chat_id)
    if session and session.game_active:
        logging.info(f"Игра в чате {chat_id} уже идёт.")
        bot.answer_callback_query(call.id, "Уже идёт игра! Завершите её командой /end.")
        return

    sessions[chat_id] = GameSession('SOLO', [user_id], chat_id)
    bot.edit_message_text("Началась игра в режиме SOLO! Выбери тему:", chat_id, call.message.message_id)
    bot.send_message(chat_id, "Выбери тему:", reply_markup=get_theme_keyboard())
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data == 'duo_start_invite')
def handle_callback_duo_start_invite(call):
    """Обрабатывает нажатие кнопки 'Играть с другом' из главного меню."""
    if call.message is None:
        logging.error("handle_callback_duo_start_invite: call.message is None")
        bot.answer_callback_query(call.id, "Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        return
        
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    logging.info(f"Получен callback 'duo_start_invite' от пользователя {user_id} в чате {chat_id}.")
    
    # Проверка, что игра начинается в групповом чате
    if call.message.chat.type not in ['group', 'supergroup']:
        bot.answer_callback_query(call.id, "Чтобы играть с другом, нужно создать групповой чат и добавить меня туда.")
        return

    session = get_session(chat_id)
    if session and session.game_active:
        bot.answer_callback_query(call.id, "В этом чате уже идёт игра! Завершите её командой /end.")
        return

    # Отправляем приглашение с кнопкой "Присоединиться"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Присоединиться к игре", callback_data=f'join_duo:{user_id}'))
    
    player_name = get_user_name(user_id, chat_id)
    bot.edit_message_text(f"**{player_name}** приглашает в игру «Правда или Действие»! Нажмите кнопку, чтобы присоединиться.",
                          chat_id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)
    bot.answer_callback_query(call.id, "Приглашение отправлено!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('join_duo'))
def handle_callback_join_duo(call):
    """Обрабатывает нажатие кнопки 'Присоединиться к игре' в DUO-режиме."""
    if call.message is None:
        logging.error("handle_callback_join_duo: call.message is None. Невозможно обработать.")
        bot.answer_callback_query(call.id, "Произошла ошибка. Пожалуйста, попробуйте еще раз.")
        return
        
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    logging.info(f"Получен callback 'join_duo' от пользователя {user_id} в чате {chat_id}.")

    # Извлекаем ID инициатора из callback_data
    initiator_id = int(call.data.split(':')[1])
    
    session = get_session(chat_id)

    if user_id == initiator_id:
        logging.warning(f"Инициатор {initiator_id} пытается присоединиться сам к себе.")
        bot.answer_callback_query(call.id, "Ты уже начал эту игру! Попроси друга нажать на кнопку, чтобы присоединиться.")
        return
    
    # Создаем новую сессию или добавляем игрока, если игра еще не началась
    if not session or not session.game_active:
        # Проверяем, что второй игрок не является ботом
        if bot.get_me().id == user_id:
            bot.answer_callback_query(call.id, "Я не могу играть с тобой, я бот! Выбери другого игрока.")
            return

        sessions[chat_id] = GameSession('DUO', [initiator_id, user_id], chat_id)
        session = sessions[chat_id]
        logging.info(f"Новая DUO-сессия создана в чате {chat_id} с игроками {initiator_id} и {user_id}.")

    bot.edit_message_text("Отлично! Выбери тему для игры:", chat_id, call.message.message_id, reply_markup=get_theme_keyboard())
    bot.answer_callback_query(call.id, "Вы присоединились к игре!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('theme'))
def handle_callback_theme(call):
    """Обрабатывает выбор темы для игры."""
    if call.message is None:
        bot.answer_callback_query(call.id, "Произошла ошибка.")
        return
        
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    
    session = get_session(chat_id)
    if not session or not session.game_active:
        bot.answer_callback_query(call.id, "Игра не активна.")
        return
    
    selected_theme = call.data.split(':')[1]
    if selected_theme not in THEMES:
        bot.answer_callback_query(call.id, "Выбранная тема не найдена.")
        return

    session.theme = selected_theme
    logging.info(f"В чате {chat_id} выбрана тема: {session.theme}")

    if session.mode == 'SOLO':
        bot.edit_message_text(f"Тема '{session.theme.title()}' выбрана. Выбирай:", chat_id, call.message.message_id)
        bot.send_message(chat_id, "Выбирай:", reply_markup=get_solo_keyboard())
    else:
        # Логика для DUO-режима после выбора темы
        player1_name = get_user_name(session.players[0], chat_id)
        player2_name = get_user_name(session.players[1], chat_id)
        
        # Бросок монетки
        coins = [random.choice(['🔴', '⚫️']) for _ in range(5)]
        heads_count = coins.count('🔴')
        
        if heads_count >= 3:
            session.turn = session.players[0]
            start_player_name = player1_name
        else:
            session.turn = session.players[1]
            start_player_name = player2_name
        
        coin_result = ' '.join(coins)
        logging.info(f"Результат броска монетки: {coin_result}. Начинает {start_player_name}.")
        
        # Объединяем сообщения
        message_text = (f"🎲 Бросаю монетку: {coin_result}\n"
                        f"→ начинает **{start_player_name}**.\n"
                        f"Тема '{session.theme.title()}' выбрана. **{start_player_name}**, правда или действие?")
        
        bot.edit_message_text(message_text, chat_id, call.message.message_id, 
                              reply_markup=get_truth_dare_inline_keyboard(session.turn), 
                              parse_mode="Markdown")

    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith(('truth_self', 'dare_self')))
def handle_callback_truth_dare_self(call):
    """Обрабатывает нажатие кнопок 'Правда' и 'Действие' игроком, чей ход."""
    if call.message is None:
        bot.answer_callback_query(call.id, "Произошла ошибка.")
        return
        
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    command_type, turn_user_id_str = call.data.split(':')
    turn_user_id = int(turn_user_id_str)

    session = get_session(chat_id)

    if not session or not session.game_active or not session.theme:
        bot.answer_callback_query(call.id, "Игра не активна или не выбрана тема.")
        return
    
    if user_id != turn_user_id:
        bot.answer_callback_query(call.id, "Сейчас не твой ход, подожди.")
        return

    task_type = command_type.split('_')[0]
    
    # Получаем вопросы из выбранной темы
    questions = THEMES.get(session.theme)
    if questions:
        if task_type == 'truth':
            task = random.choice(questions["truths"])
            session.last_task = task
            
            other_player_id = [p for p in session.players if p != user_id][0] if session.mode == 'DUO' else None
            
            if session.mode == 'DUO':
                bot.edit_message_text(f"**{get_user_name(user_id, chat_id)}**, ты выбрал правду.\nТвоё задание: {task}",
                                      chat_id, call.message.message_id, parse_mode="Markdown",
                                      reply_markup=get_enough_inline_keyboard(other_player_id))
            else:
                bot.edit_message_text(f"**{get_user_name(user_id, chat_id)}**, ты выбрал правду.\nТвоё задание: {task}",
                                      chat_id, call.message.message_id, parse_mode="Markdown")
        else:
            task = random.choice(questions["dares"])
            session.last_task = task
            
            other_player_id = [p for p in session.players if p != user_id][0] if session.mode == 'DUO' else None

            if session.mode == 'DUO':
                bot.edit_message_text(f"**{get_user_name(user_id, chat_id)}**, ты выбрал действие.\nТвоё задание: {task}",
                                      chat_id, call.message.message_id, parse_mode="Markdown",
                                      reply_markup=get_enough_inline_keyboard(other_player_id))
            else:
                bot.edit_message_text(f"**{get_user_name(user_id, chat_id)}**, ты выбрал действие.\nТвоё задание: {task}",
                                      chat_id, call.message.message_id, parse_mode="Markdown")
        
        logging.info(f"Ход игрока {user_id}. Выбрано {task_type}, задание: {task}.")
    else:
        logging.error(f"Тема '{session.theme}' не найдена.")
        bot.answer_callback_query(call.id, "Произошла ошибка: выбранная тема не найдена.")
        
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('enough'))
def handle_callback_enough(call):
    """Обрабатывает нажатие кнопки 'Достаточно' игроком, который ждет."""
    if call.message is None:
        bot.answer_callback_query(call.id, "Произошла ошибка.")
        return
    
    chat_id = call.message.chat.id
    user_id = call.from_user.id
    turn_user_id_str = call.data.split(':')[1]
    turn_user_id = int(turn_user_id_str)
    
    session = get_session(chat_id)
    
    if not session or not session.game_active:
        bot.answer_callback_query(call.id, "Игра не активна.")
        return
    
    # Проверяем, что кнопку нажал тот, кто ждал, а не тот, кто выполнял задание.
    if user_id == session.turn:
        bot.answer_callback_query(call.id, "Ты не можешь нажимать 'Достаточно' пока не выполнил задание!")
        return
        
    if user_id != turn_user_id:
        bot.answer_callback_query(call.id, "Это кнопка для другого игрока.")
        return
        
    if not session.last_task:
        bot.answer_callback_query(call.id, "Задание еще не было выбрано.")
        return

    # Переключаем ход
    old_turn = session.turn
    session.turn = [p for p in session.players if p != old_turn][0]
    session.last_task = None
    next_player_name = get_user_name(session.turn, chat_id)
    
    logging.info(f"Задание выполнено. Ход переходит к игроку {session.turn}.")
    
    bot.edit_message_text(f"Задание выполнено! Теперь ход игрока: **{next_player_name}**.", 
                          chat_id, call.message.message_id, parse_mode="Markdown")

    bot.send_message(chat_id, f"**{next_player_name}**, правда или действие?",
                     reply_markup=get_truth_dare_inline_keyboard(session.turn), parse_mode="Markdown")
                     
    bot.answer_callback_query(call.id, "Ход переключен!")

# --- Основная игровая логика ---
@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """
    Основной обработчик сообщений, который управляет ходом игры
    и делегирует обработку сообщений в зависимости от режима.
    """
    chat_id = message.chat.id
    user_id = message.from_user.id
    session = get_session(chat_id)
    command = message.text.lower()
    
    if session and session.game_active:
        if session.mode == 'SOLO':
            # Если активен SOLO-режим, делегируем обработку в отдельный файл
            handle_solo_commands(bot, message, session, THEMES)
        elif session.mode == 'DUO':
            if command == '/end':
                handle_end(message)
            elif command in ['/truth', '/dare']:
                bot.send_message(chat_id, "Пожалуйста, используйте кнопки 'Правда' или 'Действие' под сообщением.")
            else:
                bot.send_message(chat_id, "Неизвестная команда. Используйте `/end` для завершения.")
    else:
        # Если нет активной сессии, реагируем на команды /start, /duo и /rule
        if command == '/start':
            handle_start(message)
        elif command == '/duo':
            handle_duo_command(message)
        elif command == '/rule':
            handle_rule_command(message)

# --- Запуск бота ---
if __name__ == '__main__':
    # Определяем и устанавливаем список команд для бота
    commands = [
        types.BotCommand("/start", "Начать новую игру"),
        types.BotCommand("/rule", "Показать правила игры"),
        types.BotCommand("/end", "Завершить текущую игру"),
    ]
    bot.set_my_commands(commands)
    
    logging.info("Бот запущен. Ожидание обновлений...")
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        logging.exception("Произошла критическая ошибка в цикле polling.")

import threading
from datetime import datetime, timedelta
from time import sleep
from urllib import parse

import telebot
from telebot import types

import config
from models import User, Note
from umoney import UMoney

TOKEN = '1498958868:AAEFipA9Oy2qd5GA0qGJv3n9DkmIxKiEK90'
bot = telebot.TeleBot(TOKEN)

MESSAGES = {
    'start': """Здравствуй, дорогой человек!
Если ты здесь, стало быть, тебя что-то тревожит, верно?
Поделись, какая именно из сфер жизни тебя беспокоит.""",
    'got_command': """Отлично! Теперь расскажи голосом о том, что же тебя волнует.
Я внимательно изучу сказанное тобой и постараюсь помочь""",
    'send_problem': """Я скоро отвечу тебе""",
    'after_answer': """Помогло?""",
    'after_answer_yes': """Я рад, что смог помочь!""",
    'after_answer_no': """Напиши, что тебя не устроило, чтобы мне стать лучше""",
    'after_answer_more': """Чтобы записаться на консультацию, воспользуйся командой /note""",
    'send_reply': """Спасибо, я буду стараться стать лучше для тебя"""
}
COMMANDS = {
    'start': ['Личное', 'Работа и деньги', 'Отношения с близкими', 'Поиск идей'],
    'to_start': ['В начало'],
    'after_answer': ['Да', 'Нет', 'Хочу подробностей']
}
KEYBOARDS = {
    'remove': types.ReplyKeyboardRemove()
}


def keyboard(buttons_text: list):
    kb = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    kb.add(*[types.KeyboardButton(text=command) for command in buttons_text])
    return kb


for key, value in COMMANDS.items():
    KEYBOARDS[key] = keyboard(value)


def clear_keyboard(f):
    """
    Декоратор очистки инлайн-клавиатуры у предыдущих сообщений
    """
    def recursion_trying(chat_id, message_id, start_message_id):
        try:
            bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id)
        except telebot.apihelper.ApiTelegramException:
            if start_message_id - message_id < 5:
                recursion_trying(chat_id, message_id - 1, start_message_id)

    def decorator(message):
        chat_id = message.chat.id
        message_id = message.message_id
        recursion_trying(chat_id, message_id, message_id)
        f(message)

    return decorator


def simple_answer(_func=None, *, kb=None, state=None):
    """
    Декоратор простого ответа: смена состояния пользователя на {имя функции}, ответ с клавиатурой
    Может быть чистым (без скобок) - тогда всё по названию функции
    Необязательные именованные аргументы:
     :arg kb - название клавиатуры (строка)
     :arg state - состояние пользователя (строка)
    """

    def _decorator(f):
        def decorator(message, _kb=kb, _state=state):
            if not _state:
                _state = f.__name__
            User(message.from_user).update(state=_state)
            if not _kb:
                _kb = f.__name__
            bot.send_message(message.chat.id, MESSAGES[f.__name__], reply_markup=KEYBOARDS[_kb])
            f(message)

        return decorator

    if _func is None:
        return _decorator
    else:
        return _decorator(_func)


def user_state(func):
    """
    Декоратор для проверкаи состояния пользователя при вводе текста
    Добавляет реакцию бота на шаблоны, доступыне в данном состоянии
    """

    def decorator(message):
        state = User(message.from_user).state
        command = message.text
        if state == 'start' and command in COMMANDS[state]:
            got_command(message)
        elif state == 'to_start' and command in COMMANDS[state]:
            start(message)
        elif state == 'got_command':
            if command in COMMANDS['to_start']:
                start(message)
            elif message.voice or message.text:
                send_problem(message)
            else:
                func(message)
        elif state == 'after_answer':
            if command == 'Да':
                after_answer_yes(message)
            elif command == 'Нет':
                after_answer_no(message)
            elif command == 'Хочу подробностей':
                after_answer_more(message)
            else:
                func(message)
        elif state == 'after_answer_no':
            send_reply(message)
        else:
            func(message)

    return decorator


def admin_function(func):
    """
    Декоратор для команд администратора.
    Если нет прав администратора - ответ "Не понимаю тебя"
    """

    def decorator(message):
        user = User(message.from_user)
        if user.is_admin:
            func(message)
        else:
            any_text(message)

    return decorator


def forward_to_admins(message, text, kb=None):
    """
    Пересылка сообщения админам
    :param message: telebot.message
    :param text: текст действия пользователя "Пользователь такой-то {сделал то-то}"
    :param kb: опционально - клавиатура
    """
    user = User(message.from_user)
    for user_admin in user.get_admins():
        message_text = f"id: {user.id}\n" \
                       f"Пользователь @{user.username}\n" \
                       f"({user.first_name} {user.last_name})"
        if text:
            message_text += "\n" + text
        message_text += ":"
        bot.send_message(user_admin.id, message_text, reply_markup=kb)
        bot.forward_message(user_admin.id, from_chat_id=message.chat.id, message_id=message.message_id)


@bot.message_handler(commands=['set_umoney'])
@admin_function
def set_umoney(message):
    link = UMoney.authorization()
    message_text = f"Подтверди права для UMoney по ссылке: {link}"
    bot.send_message(message.chat.id, message_text)


@bot.message_handler(commands=['get_balance'])
@admin_function
def get_balance(message):
    account = UMoney.get_account()
    if not account:
        link = UMoney.authorization()
        message_text = f"Недоступно.\nПодтверди права для UMoney по ссылке: {link}"
    else:
        message_text = str(account)
    bot.send_message(message.chat.id, message_text)


@bot.message_handler(commands=['get_admins'])
@admin_function
def get_admins(message):
    user = User(message.from_user)
    admins = user.get_admins()
    message_text = '\n\n'.join(str(i) for i in admins)
    bot.send_message(message.chat.id, message_text)


@bot.message_handler(func=lambda message: User(message.from_user).is_answering_to)
def answer(message):
    state = 'after_answer'
    user = User(message.from_user)
    # пересылаем ответ пользователю
    message_text = message.text + "\n\n" + MESSAGES[state]
    bot.send_message(user.is_answering_to, message_text, reply_markup=KEYBOARDS[state])
    User(user.is_answering_to).update(state=state)
    # меняем состояние админа
    bot.edit_message_reply_markup(user.id, user.call_id, reply_markup=None)
    user.update(is_answering_to=0, call_id=0)


@bot.message_handler(commands=['admin'])
def admin(message):
    user = User(message.from_user).update(is_admin=True)
    message_text = str(user)
    bot.send_message(message.chat.id, message_text)


@bot.message_handler(commands=['start'])
@simple_answer
def start(message):
    pass


@simple_answer(kb='to_start')
def got_command(message):
    pass


@simple_answer(kb='to_start', state='to_start')
def after_answer_yes(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(text='Задонатить', url=UMoney.HOST + '/pay'))
    message_text = 'Задонать плиз'
    bot.send_message(message.chat.id, message_text, reply_markup=kb)


@simple_answer(kb='to_start', state='to_start')
def send_reply(message):
    forward_to_admins(message, 'прислал пожелания')


@simple_answer(kb='remove')
def after_answer_no(message):
    pass


@simple_answer(kb='to_start', state='to_start')
def after_answer_more(message):
    # далее - бронь времени для консультации
    pass


@simple_answer(kb='remove')
def send_problem(message):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton('Ответить', callback_data=f'answer={message.chat.id}'))
    forward_to_admins(message, f'записал свою проблему', kb)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    user = User(call.from_user)
    params = dict(parse.parse_qsl(call.data))
    if params.get('answer'):
        answer_id = params['answer']
        message_id = call.message.message_id
        user.update(is_answering_to=int(answer_id), call_id=message_id)
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton('Ответить позже',
                                          callback_data=f'answer_later={answer_id}&call_id={message_id}'))
        bot.edit_message_reply_markup(call.message.chat.id, message_id=message_id, reply_markup=kb)
    elif params.get('answer_later'):
        answer_id = params['answer_later']
        user.update(is_answering_to=0, call_id=0)
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton('Ответить', callback_data=f'answer={answer_id}'))
        bot.edit_message_reply_markup(call.message.chat.id, message_id=call.message.message_id, reply_markup=kb)

    elif params.get('date_>'):
        date = datetime.strptime(params.get('date_>'), '%Y-%m-%d').date() + timedelta(1)
        date, kb = create_times_kb(date)
        try:
            bot.edit_message_text(chat_id=call.message.chat.id,
                                  message_id=call.message.message_id,
                                  text=f"Дата: {date}",
                                  reply_markup=kb)
        except telebot.apihelper.ApiTelegramException:
            print('exception >')
    elif params.get('date_<'):
        date = datetime.strptime(params.get('date_<'), '%Y-%m-%d').date() - timedelta(1)
        date, kb = create_times_kb(date)
        try:
            bot.edit_message_text(chat_id=call.message.chat.id,
                                  message_id=call.message.message_id,
                                  text=f"Дата: {date}",
                                  reply_markup=kb)
        except telebot.apihelper.ApiTelegramException:
            print('exception <')
    elif params.get('datetime'):
        n = Note(user.id, float(params.get('datetime'))).create()
        message_text = f"{n.beauty()}\n" \
                       f"Осталось только оплатить\n" \
                       f"(если оплата не поступит в течение 15 минут, бронь времени будет снята)"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton('Оплатить', url=config.HOST + f'/note?dt={n.datetime}'))
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text=message_text,
                              reply_markup=kb)
        thread = threading.Thread(target=check_pay, args=(n.id, n.datetime))
        thread.start()


def check_pay(_id, _datetime):
    sleep(900)
    notes = [Note(*x) for x in Note().select(id=_id, datetime=_datetime)]
    if notes:
        if notes[0].operation_id:
            return
    n = notes[0]
    n.delete(id=n.id, datetime=n.datetime)


@bot.message_handler(commands=['note'])
def note(message):
    date, kb = create_times_kb()
    bot.send_message(message.chat.id, f"Дата: {date}", reply_markup=kb)


@bot.message_handler(commands=['my_notes'])
def my_notes(message):
    notes = User(message.from_user).get_notes()
    message_text = '\n\n'.join([n.beauty() for n in notes])
    if not message_text:
        message_text = "У тебя нет записей. Запишись с помощью команды /note"
    bot.send_message(message.chat.id, message_text)


def got_transaction(transaction):
    n = Note.get(int(transaction['label']))
    if n.operation_id:
        return
    n.update(operation_id=transaction['operation_id'])
    user = User(n.id)
    bot.send_message(user.id, f'Оплата прошла. Ждём тебя {n.date} в {n.time}')
    for user_admin in user.get_admins():
        message_text = f"id: {user.id}\n" \
                       f"Пользователь @{user.username}\n" \
                       f"({user.first_name} {user.last_name})\n" \
                       f"записался на консультацию:\n" \
                       f"{n.beauty()}\n"
        bot.send_message(user_admin.id, message_text)


def notification(n):
    message_text = f"В {n.time}, ждём тебя на консультации"
    bot.send_message(n.id, message_text)


def create_times_kb(date=None):
    kb = types.InlineKeyboardMarkup(row_width=2)
    now = datetime.now().date() + timedelta(1)
    if not date:
        date = now
    times = Note.TIMES(date)
    date_prev = types.InlineKeyboardButton(text='<', callback_data=f'date_<={str(date)}')
    date_next = types.InlineKeyboardButton(text='>', callback_data=f'date_>={str(date)}')
    if date > now:
        kb.add(date_prev, date_next)
    else:
        kb.add(date_next)
    if times:
        kb.add(*[types.InlineKeyboardButton(text=t[0], callback_data=f'datetime={t[1]}') for t in times])
    return str(date), kb


@bot.message_handler(content_types=['text', 'voice'])
@user_state
def any_text(message):
    message_text = 'Не понимаю тебя. Попробуй ещё раз.'
    bot.send_message(message.chat.id, message_text)

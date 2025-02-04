import random
import time
import threading
import psycopg2
from apscheduler.schedulers.background import BackgroundScheduler
from unicodedata import category
from whatsapp_chatbot_python import GreenAPIBot, Notification
import re


# Инициализация бота
bot = GreenAPIBot(
    "1103184379", "523a7b6c3cb04dfe876a1c3d532316837ed0271eebfc42fa86"
)


def create_db():
    """
    Функция для создания соединения с базой данных и таблицы напоминаний.
    """
    try:
        conn = psycopg2.connect(
            dbname="postgres",
            user="postgres",
            password="MissLisa2803",
            host="localhost",
            port="5432",
            options="-c client_encoding=UTF8"
        )

        c = conn.cursor()

        # Создание типа ENUM для статуса
        c.execute('''CREATE TYPE IF NOT EXISTS status_type AS ENUM('active', 'inactive')''')
        conn.commit()

        # Создание таблицы для хранения напоминаний
        c.execute('''CREATE TABLE IF NOT EXISTS reminders
                     (time VARCHAR(5), message TEXT, sender VARCHAR(11), num_reminder INTEGER, regular TEXT, category TEXT, status status_type)''')
        conn.commit()

        return conn
    except Exception as e:
        print(f"Error: {e}")
        return None


def send_reminder():
    """
    Функция для отправки напоминаний в заданное время.
    """
    current_time = time.strftime('%H:%M')
    c = conn.cursor()
    c.execute("SELECT * FROM reminders WHERE time = %s", (current_time,))
    reminders = c.fetchall()

    if reminders:
        for notice in reminders:
            _, time_notice, message, sender, regular = notice
            message = f'Отправляю напоминание: {message}'
            send_whatsapp_message(sender, message)
            if regular.lower() == 'once':
                c.execute("DELETE FROM reminders WHERE time = %s", (time_notice,))
                conn.commit()


@bot.router.message(command="create")
def create(notification: Notification) -> None:
    """
    Создает напоминание в базе данных.

    Параметры:
    - time_notice (VARCHAR(5)): Время отправки напоминания.
    - text_notice (TEXT): Текст напоминания.
    - sender (VARCHAR(11)): Отправитель напоминания.
    - next_num (INTEGER): Порядковый номер напоминания.
    - type_regular (TEXT): Регулярность напоминания (например, day, week, month, year).

    Пример команды: /create 15:30 Текст_сообщения day
    """
    message_data = notification.get_message_data()
    sender = notification.get_sender()[:-5]
    message_text = message_data['textMessageData']['textMessage']
    type_regular = message_text[message_text.rfind(' ') + 1:]
    main_data = message_text[message_text.find(' ') + 1: message_text.rfind(' ')]
    time_notice = main_data[:main_data.find(' ')]
    text_notice = main_data[main_data.find(' ') + 1:]
    c = conn.cursor()
    c.execute(
        "SELECT MAX(num_reminder) FROM reminders WHERE sender = %s", (sender,)
    )
    rows = c.fetchone()
    if rows and rows[0] is not None:
        max_num_reminder = rows[0]
        next_num = max_num_reminder + 1
        print(f"Максимальное значение num_reminder для sender {sender}: {max_num_reminder}")
    else:
        next_num = 1
    insert_query = "INSERT INTO reminders (time, message, sender, num_reminder, regular) VALUES (%s, %s, %s, %s, %s)"
    c.execute(insert_query, (time_notice, text_notice, sender, next_num, type_regular))
    conn.commit()
    notification.answer(f'Ваше напоминание с номером {next_num} было успешно сохранено')


@bot.router.message(command="list")
def get_notice(notification: Notification) -> None:
    """
    Возвращает список напоминаний пользователя.

    Параметры:
    - [category] - фильтр по заданной категории

    Пример команды:
    /list job
    """

    message_data = notification.get_message_data()
    sender = notification.get_sender()[:-5]
    message_text = message_data['textMessageData']['textMessage']
    parts = message_text.split()

    if len(parts) < 2:
        c = conn.cursor()
        c.execute("SELECT * FROM reminders WHERE sender = %s", (sender,))
        rows = c.fetchall()

        if rows:
            answer = 'Ваши напоминания:\n'
            for notice in rows:
                answer += f'{notice[3]}. Текст: {notice[1]}. Время отправления: {notice[0]}. Регулярность: {notice[4]}\n'
        else:
            answer = 'У вас пока нет сохраненных напоминаний'
    else:
        category = parts[1]
        c = conn.cursor()
        c.execute("SELECT * FROM reminders WHERE sender = %s and category = %s", (sender, category))
        rows = c.fetchall()
        if rows:
            answer = f'Ваши напоминания по категории: {category}\n'
            for notice in rows:
                answer += f'{notice[3]}. Текст: {notice[1]}. Время отправления: {notice[0]}. Регулярность: {notice[4]}\n'
        else:
            answer = 'У вас пока нет сохраненных напоминаний'
    notification.answer(answer)


@bot.router.message(command="cancel")
def cancel_notion(notification: Notification) -> None:
    """
    Отменяет указанное напоминание.

    Параметры:
    - num_reminder (INTEGER): Номер упоминания, сохраненного пользователем

    Пример команды:
    /cancel 1
    """
    sender = notification.get_sender()[:-5]
    parts = notification.get_message_data()['textMessageData']['textMessage'].split()

    num_reminder = parts[1] if len(parts) > 1 else None

    c = conn.cursor()
    if num_reminder is None:
        c.execute("SELECT MAX(num_reminder) FROM reminders WHERE sender = %s", (sender,))
        num_reminder = c.fetchone()[0]

    if num_reminder:
        c.execute("DELETE FROM reminders WHERE sender = %s AND num_reminder = %s", (sender, num_reminder))
        conn.commit()
        notification.answer(f'Вы успешно отменили напоминание с номером {num_reminder}')


@bot.router.message(command="edit")
def edit(notification: Notification) -> None:
    """
        Обновляет напоминание в базе данных.

        Параметры:
        - time_notice (VARCHAR(5)): Время отправки напоминания.
        - text_notice (TEXT): Текст напоминания.
        - sender (VARCHAR(11)): Отправитель напоминания.
        - group (TEXT): Категория напоминания.
        - type_regular (TEXT): Регулярность напоминания (например, day, week, month, year).

        Пример команды: /edit text=Текст сообщения time=15:30 group=job regular=day
        """
    message_data = notification.get_message_data()
    sender = notification.get_sender()[:-5]
    match = re.match(r'/edit\s+(\d+)\s+(?:text=(.*?)\s+)?(?:time=(\d{2}:\d{2})\s+)?(?:group=(\w+)\s+)?(?:regular=(once|day|week|month)\s+)?', message_data)

    if match:
        set_components = []
        params = []
        reminder_id = match.group(1)
        text_notice = match.group(2) or ""
        time_notice = match.group(3) or ""
        group = match.group(4) or ""
        regular = match.group(5) or ""
        if text_notice != "":
            set_components.append("message = %s")
            params.append(text_notice)
        if time_notice != "":
            set_components.append("time = %s")
            params.append(time_notice)
        if group != "":
            set_components.append("category = %s")
            params.append(group)
        if regular != "":
            set_components.append("regular = %s")
            params.append(regular)
        c = conn.cursor()

        update_query = f"UPDATE reminders SET {', '.join(set_components)} WHERE num_reminder = %s and sender = %s"
        params.append(reminder_id)
        params.append(sender)
        c.execute(update_query, tuple(params))
        c.commit()
        notification.answer('Напоминание успешно обновлено')
    else:
        notification.answer('Неверный формат команды')


@bot.router.message(command="help")
def command_help(notification: Notification) -> None:
    """
    Выводит список доступных команд.
    """
    notification.answer(
        'Доступные команды:\n'
        '/help - Список доступных команд\n'
        '/create [Время] [Текст] [Регулярность] - Создает напоминание\n'
        '/list - Список созданных напоминаний\n'
        '/cancel [Номер напоминания] - Отмена напоминания\n'
    )


def send_whatsapp_message(to_number, message):
    """
    Отправляет сообщение в WhatsApp.
    """
    try:
        response = bot.api.sending.sendMessage(f"{to_number}@c.us", message)
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")


def start_scheduler():
    """
    Запускает планировщик задач.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_reminder, 'interval', minutes=1)
    scheduler.start()


def run_bot():
    """
    Запускает бота.
    """
    bot.run_forever()


# Инициализация базы данных
conn = create_db()

if conn:
    #Запуск планировщика и бота в отдельных потоках
    scheduler_thread = threading.Thread(target=start_scheduler)
    scheduler_thread.start()
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    bot_thread.join()
    scheduler_thread.join()
else:
    print("Не удалось подключиться к базе данных.")

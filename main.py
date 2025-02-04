import configparser
import time
import threading
import datetime

import psycopg2
from apscheduler.schedulers.background import BackgroundScheduler
from whatsapp_chatbot_python import GreenAPIBot, Notification
import re

# Инициализация бота
bot = GreenAPIBot(
    "1103184379", "523a7b6c3cb04dfe876a1c3d532316837ed0271eebfc42fa86"
)


def create_db():
    """
    Функция для создания соединения с базой данных и создания таблицы напоминаний.
    """
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        SQL_DB_USER = config['database']['user']
        SQL_DB_PASSWORD = config['database']['password']
        SQL_DB_HOST = config['database']['host']
        SQL_DB_PORT = config['database']['port']
        SQL_DB_NAME = config['database']['database']
        conn = psycopg2.connect(
            dbname=SQL_DB_NAME,
            user=SQL_DB_USER,
            password=SQL_DB_PASSWORD,
            host=SQL_DB_HOST,
            port=SQL_DB_PORT,
            options="-c client_encoding=UTF8"
        )

        c = conn.cursor()

        # Создание типа ENUM для статуса
        c.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'status_type') THEN
                    CREATE TYPE status_type AS ENUM ('active', 'inactive');
                END IF;
            END $$;
        """)
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
    Функция для отправки напоминаний в заданное время. Если указана регулярность, то функция обновит
    следующее время отправки напоминания
    """
    current_time = time.strftime('%H:%M')
    c = conn.cursor()
    c.execute("SELECT * FROM reminders WHERE time = %s and status = \'active\'", (current_time,))
    reminders = c.fetchall()

    if reminders:
        for notice in reminders:
            time_notice, message, sender, num_reminder, regular, category_notice, status = notice
            message = f'Отправляю напоминание: {message}'
            send_whatsapp_message(sender, message)
            if regular.lower() == 'once':
                c.execute("DELETE FROM reminders WHERE time = %s", (time_notice,))
                conn.commit()
            elif regular.lower() == 'day':
                next_time = (datetime.datetime.now() + datetime.timedelta(days=1)).strftime('%H:%M')
                c.execute("""
                                UPDATE reminders 
                                SET time = %s 
                                WHERE time = %s
                            """, (next_time, time_notice))
                conn.commit()

            elif regular.lower() == 'week':
                next_time = (datetime.datetime.now() + datetime.timedelta(weeks=1)).strftime('%H:%M')
                c.execute("""
                                UPDATE reminders 
                                SET time = %s 
                                WHERE time = %s
                            """, (next_time, time_notice))
                conn.commit()

            elif regular.lower() == 'month':
                next_time = (datetime.datetime.now() + datetime.timedelta(weeks=4)).strftime('%H:%M')
                c.execute("""
                                UPDATE reminders 
                                SET time = %s 
                                WHERE time = %s
                            """, (next_time, time_notice))
                conn.commit()


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


@bot.router.message(command="info")
def get_info(notification: Notification) -> None:
    """
    Возвращает подробную информацию о выбранном напоминании либо о последнем добавленном.

    Параметры:
    - [num_reminder] - номер напоминания

    Пример команды:
    /info 1
    """

    message_data = notification.get_message_data()
    sender = notification.get_sender()[:-5]
    message_text = message_data['textMessageData']['textMessage']
    parts = message_text.split()

    if len(parts) < 2:
        c = conn.cursor()
        c.execute(
            'select Max(num_reminder) FROM reminders WHERE sender = %s', (sender,)
        )
        rows = c.fetchone()
        if rows and rows[0] is not None:
            c.execute("SELECT * FROM reminders WHERE sender = %s and num_reminder = %s", (sender, rows[0]))
            result = c.fetchome()
            answer = 'Детали напоминания:\n'
            notice = result[0]
            time_notice = f'Время напоминания: {notice[0]}\n'
            text_notice = f'Текст напоминания: {notice[1]}\n'
            regular_notice = f'Регулярность напоминания: {notice[4]}\n'
            category_notice = f'Категория напоминания: {notice[5]}\n'
            status_notice = f'Статус напоминания: {notice[6]}\n'
            answer = answer + time_notice + text_notice + regular_notice + category_notice + status_notice

        else:
            answer = 'У вас пока нет сохраненных напоминаний'
    else:
        num_reminder = parts[1]
        c = conn.cursor()
        c.execute("SELECT * FROM reminders WHERE sender = %s and num_reminder = %s", (sender, num_reminder))
        rows = c.fetchall()
        if rows:
            answer = 'Детали напоминания:\n'
            notice = rows[0]
            time_notice = f'Время напоминания: {notice[0]}\n'
            text_notice = f'Текст напоминания: {notice[1]}\n'
            regular_notice = f'Регулярность напоминания: {notice[4]}\n'
            category_notice = f'Категория напоминания: {notice[5]}\n'
            status_notice = f'Статус напоминания: {notice[6]}\n'
            answer = answer + time_notice + text_notice + regular_notice + category_notice + status_notice
        else:
            answer = 'У вас пока нет сохраненных напоминаний'
    notification.answer(answer)


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
    match = re.match(
        r'/edit\s+(\d+)\s+(?:text=(.*?)\s+)?(?:time=(\d{2}:\d{2})\s+)?(?:group=(\w+)\s+)?(?:regular=(once|day|week|month)\s+)?',
        message_data)

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


@bot.router.message(command="cancel")
def cancel_notion(notification: Notification) -> None:
    """
    Отменяет (заглушает) указанное напоминание.

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
        notification.answer('Вы не ввели номер напоминания')
    else:
        c.execute(
            'select status from reminders where sender = %s and num_reminder = %s', (sender, num_reminder)
        )
        result = c.fetchone()
        if result is not None:
            if result[0] == 'active':
                c.execute("update reminders set status = 'inactive' WHERE sender = %s AND num_reminder = %s",
                          (sender, num_reminder))
                conn.commit()
                notification.answer(f'Вы успешно отключили напоминание с номером {num_reminder}')
            else:
                notification.answer('Данное напоминание уже отключено')
        else:
            notification.answer(f'Напоминания с таким номером не существует')


@bot.router.message(command="delete")
def cancel_notion(notification: Notification) -> None:
    """
    Удаляет указанное напоминание.

    Параметры:
    - num_reminder (INTEGER): Номер упоминания, сохраненного пользователем

    Пример команды:
    /delete 1
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
        notification.answer(f'Вы успешно удалили напоминание с номером {num_reminder}')


@bot.router.message(command="turn")
def turn_on_notion(notification: Notification) -> None:
    """
    Включает указанное напоминание.

    Параметры:
    - num_reminder (INTEGER): Номер упоминания, сохраненного пользователем

    Пример команды:
    /turn 1
    """
    sender = notification.get_sender()[:-5]
    parts = notification.get_message_data()['textMessageData']['textMessage'].split()

    num_reminder = parts[1] if len(parts) > 1 else None

    c = conn.cursor()
    if num_reminder is None:
        notification.answer('Вы не ввели номер напоминания')
    else:
        c.execute(
            'select status from reminders where sender = %s and num_reminder = %s', (sender, num_reminder)
        )
        result = c.fetchone()
        if result is not None:
            if result[0] == 'inactive':
                c.execute("update reminders set status = 'active' WHERE sender = %s AND num_reminder = %s",
                          (sender, num_reminder))
                conn.commit()
                notification.answer(f'Вы успешно включили напоминание с номером {num_reminder}')
            else:
                notification.answer('Данное напоминание уже включено')
        else:
            notification.answer(f'Напоминания с таким номером не существует')


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


@bot.router.message(command="help")
def command_help(notification: Notification) -> None:
    """
    Выводит список доступных команд.
    """
    notification.answer(
        'Доступные команды:\n'
        '/help - Список доступных команд\n'
        '/create <Время, в которое нужно отправить напоминание> <Текст напоминания> <Регулярность напоминания> - Создание напоминание\n'
        '/edit <Номер напоминания> [time = [Новое время напоминания]] [text = [Новый текст напоминания]] [group = [Новая категория напоминания]] [regular = [Новая регулярность напоминания]] - Редактирование напоминания\n'
        '/turn <Номер напоминания> - Включение напоминания\n'
        '/cancel <Номер напоминания> - Выключение напоминания\n'
        '/delete <Номер напоминания> - Удаление напоминания\n'
        '/list [категория напоминания]- Список созданных напоминаний (или напоминаний выбранной категории)\n'
    )


@bot.router.message(command="start")
def start_command(notification: Notification) -> None:
    notification.answer(
        'Привет. Я - бот для твоих напоминаний. Со мной ты никогда ничего не забудешь! Очень рад знакомству)\n'
        'Используй /help для получения списка команд. Удачи!'
    )


# Инициализация базы данных
conn = create_db()

if conn:
    # Запуск планировщика и бота в отдельных потоках
    scheduler_thread = threading.Thread(target=start_scheduler)
    scheduler_thread.start()
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    bot_thread.join()
    scheduler_thread.join()
else:
    print("Не удалось подключиться к базе данных.")

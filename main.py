import random
import time
import threading
import psycopg2
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from whatsapp_chatbot_python import GreenAPIBot, Notification

bot = GreenAPIBot(
    "1103184379", "523a7b6c3cb04dfe876a1c3d532316837ed0271eebfc42fa86"
)

answers = ['Hello', 'Sorry, I dont understand u']


def create_db():
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
        c.execute('''CREATE TABLE IF NOT EXISTS reminders
                             (id SERIAL PRIMARY KEY, time TEXT, message TEXT, phone_number TEXT, num_reminder INTEGER, regular TEXT)''')

        conn.commit()
        print("Table created successfully!")
        return conn

    except Exception as e:
        print(f"Error: {e}")
        return None


def send_reminder():
    current_time = time.strftime('%H:%M')
    c = conn.cursor()
    c.execute("SELECT * FROM reminders WHERE time = %s", (current_time,))
    reminders = c.fetchall()
    if reminders:
        for notice in reminders:
            time_notice, message, sender, num_reminder, regular = notice
            send_whatsapp_message(sender, message)


@bot.router.message(command="create")
def create(notification: Notification) -> None:
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
    sender = notification.get_sender()[:-5]
    c = conn.cursor()
    c.execute(
        "SELECT * FROM reminders WHERE sender = %s", (sender,)
    )
    rows = c.fetchall()

    if rows:
        answer = 'Ваши напоминания:\n'
        for notice in rows:
            text = notice[1]
            time_notice = notice[0]
            num_notice = notice[3]
            regular = notice[4]
            line = f'{num_notice}. Текст: {text}. Время отправления: {time_notice}. Регулярность: {regular}\n'
            answer += line
    else:
        answer = 'У вас пока нет сохраненных напоминаний'

    notification.answer(answer)


@bot.router.message(command="cancel")
def cancel_notion(notification: Notification) -> None:
    message_data = notification.get_message_data()
    message_text = message_data['textMessageData']['textMessage']



@bot.router.message(command="help")
def command_help(notification: Notification) -> None:
    notification.answer(
        'Доступные команды:\n'
        '/help  - Список доступных команд\n'
        '/create [Время отправки напоминания] [Текст напоминания] [Регулярность: (day, week, month, year)] - Создает напоминание\n'
        '/list - Список созданных напоминаний\n'
        '/delete / /cancel [Опционально номер напоминания] - Отмена соответствующего(либо последнего) '
        'напоминания (В разработке)\n'
        '/edit [Номер напоминания] [Опционально: изменённое время отправки напоминания] '
        '[Опционально: изменённый текст напоминания] - Изменение параметров напоминания\n'
    )


@bot.router.message(command="start")
def start_command(notification: Notification) -> None:
    notification.answer(
        'Привет. Я - бот для твоих напоминаний. Со мной ты никогда ничего не забудешь! Очень рад знакомству)\n'
        'Используй /help для получения списка команд. Удачи!'
    )


def send_whatsapp_message(to_number, message):
    try:
        response = bot.api.sending.sendMessage(f"{to_number}@c.us", message)
        print(f"Сообщение отправлено: {response}")
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")


@bot.router.message()
def message_handler(notification: Notification) -> None:
    print('Заход в функцию')
    answer = random.choice(answers)
    notification.answer(answer)


# Функция для запуска бота

def start_scheduler():
    scheduler = BackgroundScheduler()

    # Запуск задачи каждую минуту для проверки напоминаний
    scheduler.add_job(send_reminder, 'interval', minutes=1)

    # Запуск планировщика
    scheduler.start()





def run_bot():
    bot.run_forever()


# Создаем соединение с базой данных
conn = create_db()

if conn:  # Если соединение установлено
    # Запуск бота в отдельном потоке
    scheduler_thread = threading.Thread(target=start_scheduler)
    scheduler_thread.start()
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()
    bot_thread.join()
    scheduler_thread.join()
else:
    print("Не удалось подключиться к базе данных.")

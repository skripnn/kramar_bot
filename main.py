from bot import bot
from models import DB
from server import Server, hour_notification, day_notification
import threading

if __name__ == '__main__':
    DB()
    server = Server()

    thread_server = threading.Thread(target=server.start)
    thread_server.start()

    thread_hour_notification = threading.Thread(target=hour_notification)
    thread_hour_notification.start()

    thread_day_notification = threading.Thread(target=day_notification)
    thread_day_notification.start()

    bot.infinity_polling()

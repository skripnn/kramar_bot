from datetime import datetime
from time import sleep

from flask import Flask, redirect, request, render_template, Response

from bot import got_transaction, notification
import config
from models import Note
from umoney import UMoney


class Server:
    def __init__(self):
        self.app = Flask(__name__)

        @self.app.route('/notification/', methods=['POST'])
        def notification():
            x = dict(request.values)
            # следующая строчка - замена значения datetime в пришедшем уведомлении - для отладки
            # x['label'] = 1606982400
            got_transaction(x)
            return Response(status=200)

        @self.app.route('/pay')
        def pay():
            return render_template('pay.html', account=config.ACCOUNT)

        @self.app.route('/note')
        def note():
            dt = request.args.get('dt')
            from_stamp = datetime.fromtimestamp(int(dt))
            d = from_stamp.date().strftime('%Y-%m-%d')
            t = from_stamp.time().strftime('%H:%M')
            return render_template('note.html', datetime=dt, date=d, time=t, account=config.ACCOUNT)

        @self.app.route('/get_token')
        def get_token():
            print('try to get token')
            UMoney.set_access_token(request.url)
            # Server.stop()  # - если сервер не нужен в дальнейшем
            return redirect(config.BOT_URL, code=302)

    def start(self):
        """Запуск сервера"""
        print('start server')
        self.app.run(host='localhost', port=80)
        return self

    @staticmethod
    def stop():
        """Остановка сервера"""
        func = request.environ.get('werkzeug.server.shutdown')
        if func is None:
            print('Not running with the Werkzeug Server')
            # raise RuntimeError('Not running with the Werkzeug Server')
        else:
            print('shutdown server')
            func()


def hour_notification():
    while True:
        now = datetime.now()
        offset = 60 - (now.second + (now.microsecond / 1000000))
        dt = int(now.timestamp() + offset)
        sleep(offset)
        [notification(Note(*note)) for note in Note().select(f'datetime={dt + 3600}')]


def day_notification(time='09:00'):
    notification_time = datetime.strptime(time, '%H:%M').time()
    while True:
        now = datetime.now()
        notification_dt = int(datetime.combine(now.date(), notification_time).timestamp())
        if now.time() > notification_time:
            notification_dt += 86400
        now_dt = int(now.timestamp())
        sleep(notification_dt - now_dt)
        [notification(Note(*note)) for note in Note().select(f'datetime BETWEEN {now_dt} AND {now_dt + 86400}')]

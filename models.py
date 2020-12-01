import abc
import sqlite3
from datetime import datetime, timedelta

from telebot import types


class DBConnect(abc.ABC):
    """Абстрактный класс для коннекта с базой данных"""

    @abc.abstractmethod
    def __init__(self):
        self.conn = sqlite3.connect("database.db")
        self.cursor = self.conn.cursor()


class Model(DBConnect):
    """
    Абстрактный класс модели БД
    TABLENAME - назвение таблицы (str)
    FIELDS - поля {название: (sql-тип)}
    """
    TABLE_NAME = ...
    FIELDS = ...

    @abc.abstractmethod
    def __init__(self):
        super().__init__()

    @property
    def kwargs(self):
        """все аргументы объекта - в словарь"""
        kwargs = {}
        for key in self.FIELDS.keys():
            exec(f"kwargs['{key}'] = self.{key}")
        return kwargs

    def apply(self, sql):
        """отправить изменения в БД"""
        self.cursor.execute(sql)
        self.conn.commit()

    def default(self):
        """применение значенией по умолчанию"""
        for key, value in self.FIELDS.items():
            if len(value) == 2:
                v = value[1]
                if isinstance(v, str):
                    v = f"'{v}'"
                exec(f"self.{key} = {v}")

    def create(self):
        """создание записи в таблице БД"""
        values = self.convert_to_sql(*self.kwargs.values())
        sql = f"""
            INSERT INTO {self.TABLE_NAME}
            VALUES ({', '.join(values)})
            """
        self.apply(sql)
        return self

    def update(self, where="", *args, **kwargs):
        """обновление записи в таблице БД"""
        for key, value in kwargs.items():
            if isinstance(value, str):
                value = f"'{value}'"
            exec(f"self.{key} = {value}")

        values = self.convert_to_sql(*args, **kwargs)
        sql = f"""
            UPDATE {self.TABLE_NAME} 
            SET {', '.join(values)}
            """
        if where:
            sql += f"WHERE {where}"
        self.apply(sql)
        return self

    def select(self, where=None, **kwargs):
        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
        """
        if not where:
            where = ' AND '.join(self.convert_to_sql(**kwargs))
        if where:
            sql += f"WHERE {where}"
        return self.conn.execute(sql).fetchall()

    def delete(self, **kwargs):
        """удаление записи из таблицы БД"""
        if not kwargs:
            kwargs = self.kwargs
        values = self.convert_to_sql(**kwargs)
        sql = f"""
            DELETE FROM {self.TABLE_NAME}
            WHERE {' AND '.join(values)}
            """
        self.apply(sql)

    @staticmethod
    def convert_value_to_sql(value):
        """value from python to sql"""
        v = value
        if value is None:
            v = 'NULL'
        elif isinstance(value, str):
            v = f"'{value}'"
        elif isinstance(value, int):
            v = str(value)
        elif isinstance(value, bool):
            if value:
                v = 'TRUE'
            else:
                v = 'FALSE'
        return v

    def convert_to_sql(self, *args, **kwargs):
        """args или kwargs from python to sql"""
        if args:
            return [self.convert_value_to_sql(arg) for arg in args]

        if kwargs:
            result = {}
            for key, value in kwargs.items():
                result[key] = self.convert_value_to_sql(value)
            return [f"{key} = {value}" for key, value in result.items()]


class Config(Model):
    """
    Настройки
    Каждый параметр - новая запись (key: value)
    """
    TABLE_NAME = 'config'
    FIELDS = {
        'key': 'CHAR',
        'value': 'CHAR'
    }

    def __init__(self):
        super().__init__()
        self.all = self.get()

    def get(self):
        sql = f"""
            SELECT * FROM {self.TABLE_NAME}
        """
        result = self.cursor.execute(sql)
        return dict(result.fetchall())

    def new_param(self, key, value):
        self.all[key] = value
        values = self.convert_to_sql(key, value)
        sql = f"""
            INSERT INTO {self.TABLE_NAME}
            VALUES ({', '.join(values)})
        """
        self.apply(sql)


class User(Model):
    """
    Модель пользователя
    """
    TABLE_NAME = 'user'
    FIELDS = {
        'id': 'INT',
        'is_bot': 'BOOL',
        'first_name': 'CHAR',
        'username': 'CHAR',
        'last_name': 'CHAR',
        'is_admin': 'BOOL',
        'is_answering_to': 'INT',
        'call_id': 'INT',
        'state': 'CHAR'
    }

    def __init__(self, from_user):
        super().__init__()
        self.id = ...
        self.is_bot = ...
        self.first_name = ...
        self.username = ...
        self.last_name = ...
        self.is_admin = ...
        self.is_answering_to = ...
        self.call_id = ...
        self.state = ...
        if isinstance(from_user, types.User):
            args = (from_user.id, from_user.is_bot, from_user.first_name,
                    from_user.username, from_user.last_name, False, 0, 0, "OK", None)
            self.set_all(*args)
            self.exist()
        elif isinstance(from_user, tuple):
            self.set_all(*from_user)
        elif isinstance(from_user, int):
            result = self.select(id=from_user)
            if result:
                self.set_all(*result[0])

    def __str__(self):
        return '\n'.join([f'{key}: {value}' for key, value in self.kwargs.items()])

    def set_all(self, *args):
        for i, key in enumerate(self.FIELDS.keys()):
            exec(f"self.{key} = args[{i}]")

    def exist(self):
        result = self.select(id=self.id)
        if result:
            result = result[0]
            self.is_admin = bool(result[-4])
            self.is_answering_to = int(result[-3])
            self.call_id = int(result[-2])
            self.state = result[-1]
            values = tuple(self.kwargs.values())
            for i in range(5):
                if values[i] != result[i]:
                    self.update(**self.kwargs)
                    break
        else:
            self.create()

    def get_admins(self):
        result = self.select(is_admin=True)
        return [User(db_user) for db_user in result]

    def update(self, *args, **kwargs):
        if 'state' in kwargs.keys():
            print(f"User {self.username} updated to {kwargs['state']}")
        where = f"id = {self.id}"
        return super(User, self).update(where, *args, **kwargs)

    def get_notes(self):
        return [Note(*x) for x in Note().select(id=self.id)]


class Note(Model):
    """
    Модель записи
    """
    TABLE_NAME = 'note'
    FIELDS = {
        'id': 'INT',
        'datetime': 'INT',
        'operation_id': 'CHAR'
    }

    def __init__(self, _id=None, _datetime=None, operation_id=None):
        super(Note, self).__init__()
        self.id = _id
        self.datetime = _datetime
        self.operation_id = operation_id
        if self.datetime:
            self.datetime = int(self.datetime)

    @property
    def date(self):
        return datetime.fromtimestamp(float(self.datetime)).date().strftime('%Y-%m-%d')

    @property
    def time(self):
        return datetime.fromtimestamp(float(self.datetime)).time().strftime('%H:%M')

    def beauty(self):
        """Красивый вид для печати"""
        text = f"Дата: {self.date}\n" \
               f"Время: {self.time}"
        if not self.operation_id:
            text += "\nТребуется оплата"
        return text

    @staticmethod
    def get(dt):
        return Note(*Note().select(datetime=int(dt))[0])


    @staticmethod
    def busy(dts):
        """пересечения слотов с БД"""
        sql = f"""
                SELECT datetime FROM note
                WHERE datetime IN({str(dts)[1:-1]})
                """
        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        result = cursor.execute(sql)
        return [i[0] for i in result.fetchall()]

    @classmethod
    def TIMES(cls, d):
        """получить все слоты в день"""
        start = '10:00'
        end = '18:00'
        period = 60

        times = []
        now = datetime.now().timestamp()
        t = datetime.strptime(start, '%H:%M')
        dt = datetime.timestamp(datetime.combine(d, t.time()))
        _end = datetime.timestamp(datetime.combine(d, datetime.strptime(end, '%H:%M').time()))
        while dt < _end:
            if dt > now:
                times.append(dt)
            t += timedelta(minutes=period)
            dt = datetime.timestamp(datetime.combine(d, t.time()))
        times = [x for x in times if x not in cls.busy(times)]
        times = [(datetime.fromtimestamp(time).time().strftime('%H:%M'), time) for time in times]
        return times


class DB(DBConnect):
    """
    База данных
    TABLES - список с Моделями
    """
    TABLES = [User, Note]

    def __init__(self):
        super().__init__()
        self.create()

    def create(self):
        """Создание таблиц, если они не созданы"""
        for table in self.TABLES:
            try:
                params = ', '.join([f"{key} {value[0]}" for key, value in table.FIELDS.items()])
                sql = f"CREATE TABLE {table.TABLE_NAME} ({params})"
                self.cursor.execute(sql)
            except sqlite3.OperationalError:
                pass

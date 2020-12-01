import datetime
import json
from time import sleep
import config

import requests
from urllib.parse import urlparse


def data_to_string(data):
    if not data:
        return {}
    return '&'.join([f'{key}={value}' for key, value in data.items()])


class UMoneyAccount:
    def __init__(self, model, umoney):
        self.umoney = umoney

        self.account = model.get('account')
        self.balance = model.get('balance')
        self.currency = model.get('currency')
        self.account_type = model.get('account_type')
        self.identified = model.get('identified')
        self.account_status = model.get('account_status')
        self.balance_details = model.get('balance_details')

    def __str__(self):
        return f"Номер счета: {self.account}\n" \
               f"Баланс: {self.balance}"

    def check_balance(self):
        balance = self.umoney.get_account().balance
        print(datetime.datetime.now().strftime('%Y-%d-%m %H:%M:%S'))
        print(f"Баланс: {balance}")
        if balance == self.balance:
            print("Баланс не изменился")
        else:
            print(f"Предыдущий баланс: {self.balance}")
            self.balance = balance
        print('\n')


class UMoney:
    URL = 'https://money.yandex.ru'
    HEADERS = {
        'Host': 'money.yandex.ru',
        'Content-Type': 'application/x-www-form-urlencoded',
    }
    HOST = config.HOST
    REDIRECT_URI = HOST + '/get_token'
    ACCESS_TOKEN = ""
    CLIENT_ID = config.CLIENT_ID
    
    @classmethod
    def authorization(cls):
        data = {
            'client_id': cls.CLIENT_ID,
            'response_type': 'code',
            'redirect_uri': cls.REDIRECT_URI,
            'scope': 'account-info'
        }
        headers = cls.HEADERS
        url = cls.URL + '/oauth/authorize'

        r = requests.post(url, headers=headers, data=data_to_string(data), allow_redirects=False)

        return r.next.url

    @classmethod
    def set_access_token(cls, url):
        params = {}
        for param in urlparse(url).query.split('&'):
            param = param.split('=')
            if len(param) == 2:
                params[param[0]] = param[1]
        code = params.get('code')
        error = params.get('error')
        if code:
            cls.ACCESS_TOKEN = cls.get_token(code)
            if cls.ACCESS_TOKEN:
                print('TOKEN IS OK')
            else:
                print('EMPTY TOKEN')
        elif error:
            print(f'GET TOKEN ERROR: {error}')
        else:
            print('error of url')

    @classmethod
    def get_token(cls, temp_token):
        data = {
            'code': temp_token,
            'client_id': cls.CLIENT_ID,
            'grant_type': 'authorization_code',
            'redirect_uri': cls.REDIRECT_URI,
        }
        headers = cls.HEADERS
        url = cls.URL + '/oauth/token'

        r = requests.post(url, headers=headers, data=data_to_string(data), allow_redirects=False)
        result = json.loads(r.text)
        return result['access_token']

    @classmethod
    def get_account(cls):
        headers = cls.HEADERS.copy()
        headers['Authorization'] = 'Bearer ' + cls.ACCESS_TOKEN
        url = cls.URL + '/api/account-info'

        r = requests.post(url, headers=headers)
        if r.status_code == 200:
            return UMoneyAccount(json.loads(r.text), cls)
        return None


def infinity_check_balance(account, sec):
    while True:
        account.check_balance()
        sleep(sec)

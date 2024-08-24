import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telebot import TeleBot, apihelper

from exceptions import APIError, TokenError

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Доступность всех переменных окружения, необходимых для работы бота."""
    missing_tokens = []
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for token_name, token_value in tokens.items():
        if not token_value:
            missing_tokens.append(token_name)
            logging.critical(f'Отсутствует переменная окружения: {token_name}')

    if missing_tokens:
        raise TokenError(
            f'Отсутствуют переменные окружения: {", ".join(missing_tokens)}')

    logging.debug('Все переменные окружения в наличии.')


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug(f'Начинается отправка сообщения: {message}')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Успешная отправка сообщения: {message}')
    except (apihelper.ApiException, requests.RequestException) as e:
        logging.error(f'Ошибка при отправке сообщения: {e}')


def get_api_answer(timestamp):
    """Делает запрос к API и возвращает ответ в Python-формате."""
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException as e:
        raise APIError(f'Ошибка при запросе к API: {e}')

    if response.status_code != HTTPStatus.OK:
        raise APIError(f'Ошибка API: код ответа {response.status_code}')

    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие ожидаемой структуре."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Ответ API имеет некорректный тип: {type(response)}, '
            'ожидался словарь')

    homeworks = response.get('homeworks')
    if homeworks is None:
        raise KeyError('Ключ "homeworks" отсутствует в ответе API')

    if not isinstance(homeworks, list):
        raise TypeError(
            f'Тип данных "homeworks" некорректен: {type(homeworks)}, '
            'ожидался список')

    logging.debug('Ответ API соответствует ожиданиям.')
    return homeworks


def parse_status(homework):
    """Извлекает статус домашки и возвращает строку для отправки в Telegram."""
    if 'homework_name' not in homework:
        raise KeyError(
            'Ключ "homework_name" отсутствует в информации о домашней работе')
    if 'status' not in homework:
        raise KeyError(
            'Ключ "status" отсутствует в информации о домашней работе')
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Неизвестный статус работы: {status}')
    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = TeleBot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_error_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
                if send_message(bot, message):
                    timestamp = response.get('current_date', timestamp)
                    last_error_message = ''
                else:
                    logging.error('Не удалось отправить сообщение в Telegram.')
            else:
                logging.debug('Новых статусов нет.')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_error_message:
                if send_message(bot, message):
                    last_error_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    main()

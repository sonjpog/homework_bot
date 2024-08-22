import os
import sys
import time
import logging
import requests

from dotenv import load_dotenv
from telebot import TeleBot
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

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)


def check_tokens():
    """Доступность переменных окружения, необходимых для работы бота."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for token_name, token_value in tokens.items():
        if not token_value:
            logging.critical(f'Отсутствует переменная окружения: {token_name}')
            raise TokenError(f'Отсутствует переменная окружения: {token_name}')
    logging.debug('Все переменные окружения в наличии.')


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.debug(f'Успешная отправка сообщения: {message}')
    except Exception as e:
        logging.error(f'Ошибка при отправке сообщения: {e}')


def get_api_answer(timestamp):
    """
    Делает запрос к API и возвращает ответ, преобразованный в Python-формат.
    """
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != 200:
            raise APIError(f'Ошибка API: код ответа {response.status_code}')
        return response.json()
    except requests.RequestException as e:
        logging.error(f'Ошибка при запросе к API: {e}')
        raise APIError(f'Ошибка при запросе к API: {e}')


def check_response(response):
    """Проверяет ответ API на соответствие ожидаемой структуре."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response:
        raise KeyError('Ключ "homeworks" отсутствует в ответе API')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Тип данных "homeworks" не является списком')
    logging.debug('Ответ API соответствует ожиданиям.')
    return response['homeworks']


def parse_status(homework):
    """
    Извлекает статус домашки и возвращает строку для отправки в Telegram.
    """
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
                send_message(bot, message)
            else:
                logging.debug('Новых статусов нет.')
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_error_message:
                send_message(bot, message)
                last_error_message = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

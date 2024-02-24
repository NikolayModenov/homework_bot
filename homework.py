import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='a',
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}
PAYLOAD = {'from_date': 0}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Check that the required variables have been received."""
    try:
        assert PRACTICUM_TOKEN, 'Токен прктикума отсутствует'
        assert TELEGRAM_TOKEN, 'Токен телеграмма отсутствует'
        assert TELEGRAM_CHAT_ID, 'ID чата телеграмма отсутствует'
    except Exception as error:
        logging.critical('!! ОТСУТСТВУЕТ ОБЯЗАТЕЛЬНАЯ ПЕРЕМЕННАЯ !!')
        logging.critical(f'Ошибка: {error}')
        raise error


def send_message(bot, message):
    """Send a message to telegram."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logging.debug('сообщение отправлено')


def get_api_answer(timestamp):
    """Get an API response."""
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=timestamp
        )
    except requests.RequestException:
        logging.error(
            'При получении ответа API возникла ошибка RequestException.'
        )
    if homework_statuses.status_code == HTTPStatus.OK:
        return homework_statuses.json()
    else:
        logging.critical('Некорректный Status code ответа API.')
        raise ConnectionError


def check_response(response):
    """Check the API response."""
    assert response['current_date']
    if 'homeworks' not in response:
        logging.critical('В ответе API отсутствует ключ homeworks.')
        raise KeyError
    if not isinstance(response['homeworks'], list):
        logging.critical(
            'Не корректный формат данных в ответе API под ключом homeworks.'
        )
        raise TypeError


def parse_status(homework):
    """Collect a message to send in a telegram."""
    if 'homework_name' in homework:
        homework_name = homework['homework_name']
    else:
        logging.critical('В ответе API отсутствует ключ homework_name.')
        raise KeyError
    if homework['status'] in HOMEWORK_VERDICTS:
        verdict = HOMEWORK_VERDICTS[homework['status']]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    else:
        logging.critical(
            'В ответе API некорректное значение под ключом status.'
        )
        raise ValueError


def main():
    """The basic logic of the bot's operation."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)

    while True:
        response = get_api_answer(PAYLOAD)
        check_response(response)
        try:
            message = parse_status(response['homeworks'][-1])
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
        try:
            send_message(bot, message)
        except Exception as error:
            logging.error('бот не смог отправить сообщение.')
            logging.error(f'ошибка: {error}')
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()

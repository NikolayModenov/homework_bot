import logging
import os
import time
from datetime import datetime
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

file_log = logging.FileHandler(f'{__name__}.log')
console_out = logging.StreamHandler()


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

PRACTICUM_TOKEN_ERROR_MESSAGE = 'Токен прктикума отсутствует'
TELEGRAM_TOKEN_ERROR_MESSAGE = 'Токен телеграмма отсутствует'
TELEGRAM_CHAT_ID_ERROR_MESSAGE = 'ID чата телеграмма отсутствует'
CHECK_TOKENS_CRITICAL_MESSAGE = (
    '!! ОТСУТСТВУЕТ ОБЯЗАТЕЛЬНАЯ ПЕРЕМЕННАЯ !! Ошибка: {error}'
)
SEND_MESSAGE_FOR_LOG = 'сообщение отправлено: {message}'
GET_API_REQUEST_EXCEPTION = (
    'При получении ответа API с параметрами url={ENDPOINT}, '
    'headers={HEADERS}, params={timestamp} '
    'возникла ошибка RequestException.'
)
GET_API_STATUS_CODE_EXCEPTIONS = (
    'Некорректный Status code ответа API. '
    'Ожидается status_code = 200. '
    'Полученный status_code: {status_code}'
)
GET_API_ERROR_IN_JSON = (
    'Вернулся некорректный ответ API, содержащий ключ "error", '
    'со значением: {error_value}.'
)
GET_API_CODE_IN_JSON = (
    'Вернулся некорректный ответ API, содержащий ключ "code", '
    'со значением: {code_value}.'
)
CHECK_RESPONSE_ISITANSE_DICTIONARY = (
    'Не корректный формат данных в ответе API, '
    'ожидается формат dict; полученный формат: {type_of_response}.'
)
HOMEWORKS_KEY_ERROR = 'В ответе API отсутствует ключ homeworks.'
CHECK_RESPONSE_LISTS_ISITANSE = (
    'Не корректный формат данных в ответе API под ключом homeworks, '
    'ожидается формат list; полученный формат: {incorrect_type}.'
)
HOMEWORK_NAME_KEY_ERROR = 'В ответе API отсутствует ключ homework_name.'
STATUS_VALUE_ERROR = (
    'В ответе API некорректное значение под ключом status. '
    'Полученное значение: {status}'
)
PARSE_STATUS_RESULT = (
    'Изменился статус проверки работы "{homework_name}". {verdict}'
)
MAIN_MESSAGE_ERROR = (
    'Бот не смог отправить сообщение. Возникла ошибка: {error}'
)


def check_tokens():
    """Check that the required variables have been received."""
    variables = (
        (PRACTICUM_TOKEN, PRACTICUM_TOKEN_ERROR_MESSAGE),
        (TELEGRAM_TOKEN, TELEGRAM_TOKEN_ERROR_MESSAGE),
        (TELEGRAM_CHAT_ID, TELEGRAM_CHAT_ID_ERROR_MESSAGE)
    )
    for variable, error_message in variables:
        try:
            assert variable, error_message
        except Exception as error:
            logging.critical(CHECK_TOKENS_CRITICAL_MESSAGE.format(error=error))
            raise ValueError


def send_message(bot, message):
    """Send a message to telegram."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logging.debug(SEND_MESSAGE_FOR_LOG.format(message=message))


def get_api_answer(timestamp):
    """Get an API response."""
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=timestamp
        )
    except requests.RequestException:
        raise GET_API_REQUEST_EXCEPTION.format(
            ENDPOINT=ENDPOINT, HEADERS=HEADERS, timestamp=timestamp
        )
    if homework_statuses.status_code != HTTPStatus.OK:
        raise ValueError(GET_API_STATUS_CODE_EXCEPTIONS.format(
            status_code=homework_statuses.status_code
        ))
    if 'error' in homework_statuses.json():
        raise ValueError(GET_API_ERROR_IN_JSON.format(
            error_value=homework_statuses.json()['error']
        ))
    if 'code' in homework_statuses.json():
        raise ValueError(GET_API_CODE_IN_JSON.format(
            code_value=homework_statuses.json()['code']
        ))
    return homework_statuses.json()


def check_response(response):
    """Check the API response."""
    if not isinstance(response, dict):
        raise TypeError(CHECK_RESPONSE_ISITANSE_DICTIONARY.format(
            type_of_response=type(response)
        ))
    if 'homeworks' not in response:
        raise KeyError(HOMEWORKS_KEY_ERROR)
    if not isinstance(response['homeworks'], list):
        raise TypeError(CHECK_RESPONSE_LISTS_ISITANSE.format(
            incorrect_type=type(response['homeworks'])
        ))


def parse_status(homework):
    """Collect a message to send in a telegram."""
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_KEY_ERROR)
    if homework['status'] not in HOMEWORK_VERDICTS:
        raise ValueError(STATUS_VALUE_ERROR.format(status=homework['status']))
    return PARSE_STATUS_RESULT.format(
        homework_name=homework['homework_name'],
        verdict=HOMEWORK_VERDICTS[homework['status']]
    )


def main():
    """The basic logic of the bot's operation."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    old_message = ''

    while True:
        response = get_api_answer({'from_date': timestamp})
        check_response(response)
        if response['homeworks']:
            message = parse_status(response['homeworks'][0])
        else:
            message = old_message
        if message != old_message:
            try:
                send_message(bot, message)
                timestamp = int(time.mktime(datetime.fromisoformat(
                    response['homeworks'][0]['date_updated']
                    .replace("Z", "+00:00")
                ).timetuple()))
            except Exception as error:
                logging.error(MAIN_MESSAGE_ERROR.format(error=error))
            old_message = message
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=(file_log, console_out),
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
    )

    main()

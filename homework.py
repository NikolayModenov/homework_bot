import logging
import os
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

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
CHECK_TOKENS_CRITICAL_MESSAGE = (
    '!! ОТСУТСТВУЕТ ОБЯЗАТЕЛЬНАЯ ПЕРЕМЕННАЯ {name} !!'
)
SEND_MESSAGE_FOR_LOG = 'сообщение отправлено: {message}'
GET_API_REQUEST_EXCEPTION = (
    'При получении ответа API с параметрами endpoint = {endpoint}, '
    'headers = {headers}, params = {timestamp}. '
    'Возникла ошибка: {exception}.'
)
GET_API_STATUS_CODE_EXCEPTIONS = (
    'Некорректный Status code ответа API. '
    'с параметрами: enpoint = {endpoint}, '
    'headers = {headers}, timestamp = {timestamp}. '
    'Ожидается status_code = 200. '
    'Полученный status_code: {status_code}'
)
GET_API_ERROR_IN_JSON = (
    'Вернулся некорректный ответ API, содержащий ключ {name_error}, '
    'со значением: {error_value}.'
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
MAIN_API_ERROR = (
    'Не получилось сформировать ответ API c Unix time = {timestamp}. '
    'Полученная ошибка: {error}'
)


def check_tokens():
    """Check that the required variables have been received."""
    variables = (
        (PRACTICUM_TOKEN, 'practicum_token'),
        (TELEGRAM_TOKEN, 'telegram_token'),
        (TELEGRAM_CHAT_ID, 'telegram_chat_id')
    )
    empty_variables = list()
    for variable, name in variables:
        if not variable:
            empty_variables.append(name)
    if empty_variables:
        logging.critical(
            CHECK_TOKENS_CRITICAL_MESSAGE.format(name=empty_variables)
        )
        raise ValueError


def send_message(bot, message):
    """Send a message to telegram."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logging.debug(SEND_MESSAGE_FOR_LOG.format(message=message))


def get_api_answer(date):
    """Get an API response."""
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params={'from_date': date}
        )
    except requests.RequestException:
        raise BlockingIOError(GET_API_REQUEST_EXCEPTION.format(
            endpoint=ENDPOINT, headers=HEADERS, timestamp=date,
            exception=requests.RequestException
        ))
    if homework_statuses.status_code != HTTPStatus.OK:
        raise ValueError(GET_API_STATUS_CODE_EXCEPTIONS.format(
            enpoint=ENDPOINT, headers=HEADERS, timestamp=date,
            status_code=homework_statuses.status_code
        ))
    api_response = homework_statuses.json()
    error_keys = ('error', 'code')
    for error_key in error_keys:
        if error_key in api_response:
            raise ValueError(GET_API_ERROR_IN_JSON.format(
                name_error=error_key,
                error_value=api_response[error_key]
            ))
    return api_response


def check_response(response):
    """Check the API response."""
    if not isinstance(response, dict):
        raise TypeError(CHECK_RESPONSE_ISITANSE_DICTIONARY.format(
            type_of_response=type(response)
        ))
    if 'homeworks' not in response:
        raise KeyError(HOMEWORKS_KEY_ERROR)
    homeworks = response['homeworks']
    if not isinstance(homeworks, list):
        raise TypeError(CHECK_RESPONSE_LISTS_ISITANSE.format(
            incorrect_type=type(homeworks)
        ))


def parse_status(homework):
    """Collect a message to send in a telegram."""
    if 'homework_name' not in homework:
        raise KeyError(HOMEWORK_NAME_KEY_ERROR)
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(STATUS_VALUE_ERROR.format(status=homework_status))
    return PARSE_STATUS_RESULT.format(
        homework_name=homework['homework_name'],
        verdict=HOMEWORK_VERDICTS[homework_status]
    )


def main():
    """The basic logic of the bot's operation."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    old_message = ''
    old_response = ''

    while True:
        try:
            response = get_api_answer(timestamp)
        except Exception as error:
            logging.error(MAIN_API_ERROR.format(
                timestamp=timestamp, error=error
            ))
            response = old_response
        check_response(response)
        homeworks = response['homeworks']
        if homeworks:
            message = parse_status(homeworks[0])
        else:
            message = old_message
        if message != old_message:
            try:
                send_message(bot, message)
                timestamp = response['current_date']
            except Exception as error:
                logging.error(MAIN_MESSAGE_ERROR.format(error=error))
            old_message = message
            old_response = response
        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        handlers=(
            logging.FileHandler(f'{__name__}.log'), logging.StreamHandler()
        ),
        format='%(asctime)s, %(levelname)s, %(message)s'
    )

    main()

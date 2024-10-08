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

VARIABLES = ('PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}
CHECK_TOKENS_CRITICAL_MESSAGE = (
    '!! Отсутствуют обязательные переменные {names} !!'
)
SEND_MESSAGE_FOR_LOG = 'сообщение отправлено: {message}'
GET_API_REQUEST_EXCEPTION = (
    'При получении ответа API с параметрами endpoint = {url}, '
    'headers = {headers}, params = {params}. '
    'Возникла ошибка: {exception}.'
)
GET_API_STATUS_CODE_EXCEPTIONS = (
    'Некорректный Status code ответа API. '
    'С параметрами: enpoint = {url}, '
    'headers = {headers}, params = {params}. '
    'Ожидается status_code = 200. '
    'Полученный status_code: {status_code}'
)
GET_API_ERROR_IN_JSON = (
    'Вернулся некорректный ответ API, содержащий ключ {name_error}, '
    'со значением: {error_value}. Параметры ответа API: '
    'enpoint = {url}, headers = {headers}, timestamp = {params}. '
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
    'Не получилось сформировать ответ API. '
    'Полученная ошибка: {error}.'
)


def check_tokens():
    """Check that the required variables have been received."""
    empty_variables = [name for name in VARIABLES if not globals()[name]]
    if empty_variables:
        logging.critical(
            CHECK_TOKENS_CRITICAL_MESSAGE.format(names=empty_variables)
        )
        raise ValueError(
            CHECK_TOKENS_CRITICAL_MESSAGE.format(names=empty_variables)
        )


def send_message(bot, message):
    """Send a message to telegram."""
    bot.send_message(TELEGRAM_CHAT_ID, message)
    logging.debug(SEND_MESSAGE_FOR_LOG.format(message=message))


def get_api_answer(timestamp):
    """Get an API response."""
    response_api_parameters = dict(
        url=ENDPOINT, headers=HEADERS, params={'from_date': timestamp}
    )
    try:
        homework_statuses = requests.get(**response_api_parameters)
    except requests.RequestException as error:
        raise ConnectionError(GET_API_REQUEST_EXCEPTION.format(
            exception=error, **response_api_parameters
        ))
    if homework_statuses.status_code != HTTPStatus.OK:
        raise ValueError(GET_API_STATUS_CODE_EXCEPTIONS.format(
            status_code=homework_statuses.status_code,
            **response_api_parameters
        ))
    api_response = homework_statuses.json()
    for error_key in ('error', 'code'):
        if error_key in api_response:
            raise ValueError(GET_API_ERROR_IN_JSON.format(
                name_error=error_key,
                error_value=api_response[error_key], **response_api_parameters
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
    status = homework['status']
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(STATUS_VALUE_ERROR.format(status=status))
    return PARSE_STATUS_RESULT.format(
        homework_name=homework['homework_name'],
        verdict=HOMEWORK_VERDICTS[status]
    )


def main():
    """The basic logic of the bot's operation."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    old_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homeworks = response['homeworks']
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = old_message
            if message != old_message:
                send_message(bot, message)
                timestamp = response.get('current_date', timestamp)
                old_message = message
        except Exception as error:
            error_message = MAIN_API_ERROR.format(error=error)
            logging.error(error_message)
            if error_message != old_message:
                try:
                    send_message(bot, error_message)
                    old_message = error_message
                except Exception as error:
                    logging.error(MAIN_MESSAGE_ERROR.format(error=error))
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

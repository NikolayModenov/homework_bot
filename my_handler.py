import logging
from logging.handlers import RotatingFileHandler


class MyLogsHandler(RotatingFileHandler):

    # def emit(self, record):
    #     log_entry = self.format(record)
    #     # тут ваша логика
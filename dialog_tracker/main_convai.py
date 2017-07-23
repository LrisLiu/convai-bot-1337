import logging
import telegram
import json
import convai_api
import requests
import os
import subprocess

from random import sample
from time import sleep
from fsm import FSM
from sys import argv
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler


logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    level=logging.INFO)
logger = logging.getLogger(__name__)

logger_bot = logging.getLogger('bot')
bot_file_handler = logging.FileHandler("bot.log")
bot_log_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
bot_file_handler.setFormatter(bot_log_formatter)
if not logger_bot.handlers:
    logger_bot.addHandler(bot_file_handler)

version = "5 (23.07.2017)"


class DialogTracker:
    def __init__(self):
        self._bot = convai_api.ConvApiBot()

        self._chat_fsm = {}
        self._users = {}

    def start(self):
        while True:
            try:
                res = requests.get(os.path.join(convai_api.BOT_URL, 'getUpdates'))
                if res.status_code != 200:
                    logger.warn(res.text)

                for m in res.json():
                    logger.info(m)
                    update = convai_api.ConvUpdate(m)
                    if m['message']['text'].startswith('/start '):
                        self._log_user('_start_or_begin_or_test_cmd', update)
                        self._text = m['message']['text'][len('/start '):]
                        self._get_qas()
                        self._add_fsm_and_user(update)
                        fsm = self._chat_fsm[update.effective_chat.id]

                        fsm.return_to_start()
                        fsm.ask_question()
                    elif m['message']['text'] == '/end':
                        self._log_user('_end_cmd', update)
                        self._add_fsm_and_user(update)
                        fsm = self._chat_fsm[update.effective_chat.id]
                        fsm.return_to_init()
                    elif m['message']['text'].startswith('version'):
                        self._add_fsm_and_user(update)
                        fsm = self._chat_fsm[update.effective_chat.id]
                        fsm._send_message("Version is {}".format(version))
                    else:
                        self._log_user('_echo_cmd', update)

                        self._add_fsm_and_user(update)

                        fsm = self._chat_fsm[update.effective_chat.id]
                        fsm._last_user_message = update.message.text
                        if not fsm._text:
                            fsm._send_message('Text is not given. Please try to type /end and /test to reset the state and get text.')
                            continue

                        if fsm.is_asked():
                            fsm.check_user_answer_on_asked()
                        else:
                            fsm.classify()
            except Exception as e:
                logger.exception(str(e))
            sleep(1)

    def _log_user(self, cmd, update):
        logger_bot.info("USER[{}]: {}".format(cmd, update.message.text))

    def _add_fsm_and_user(self, update, hard=False):
        if update.effective_chat.id not in self._chat_fsm:
            fsm = FSM(self._bot, update.effective_user, update.effective_chat, self._text_and_qa())
            self._chat_fsm[update.effective_chat.id] = fsm
            self._users[update.effective_user.id] = update.effective_user
        elif update.effective_user.id in self._chat_fsm and hard:
            self._chat_fsm[update.effective_chat.id].set_text_and_qa(self._text_and_qa())
            self._chat_fsm[update.effective_chat.id].clear_all()

    def _get_qas(self):
        out = subprocess.check_output(["from_question_generation/get_qnas", self._text])
        questions = [line.split('\t') for line in str(out, "utf-8").split("\n")]
        self._factoid_qas = [{'question': e[0], 'answer': e[1], 'score': e[2]} for e in questions if len(e) == 3]

    def _text_and_qa(self):
        return {'text': self._text, 'qas': self._factoid_qas}


if __name__ == '__main__':
    dt = DialogTracker()
    dt.start()
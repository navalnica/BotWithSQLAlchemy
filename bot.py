import logging
import os
from functools import wraps

from telegram import (Update, ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import (Updater, CallbackContext, CommandHandler, ConversationHandler, MessageHandler, Filters)

import crud as crud
from models import Person

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


# -------------- decorators --------------

def reject_edit_update(func):
    """
    Reject updates that contain information about edited message.
    `message` field of such updates is None
    """

    @wraps(func)
    def wrapper(*args, **kwargs):
        update = args[1] if len(args) > 1 else kwargs['update']
        chat_id = update.effective_user.id
        if update.message is None:
            logger.info(f'{func.__name__}. ignoring edit update. chat_id: {chat_id}')
            return
        return func(*args, **kwargs)

    return wrapper


class TestBot:

    @staticmethod
    def validate_variable(var):
        if var is None:
            raise ValueError(f'variable must be not None')
        return var

    def __init__(self, token, contact_chat_id):
        self.token = TestBot.validate_variable(token)
        self.contact_chat_id = TestBot.validate_variable(contact_chat_id)

        self.conversation_context = dict()
        self.K_PERSONS_LIST = 'persons_list'
        self.K_CHOSEN_PERSON_ID = 'chosen_person_id'

        self.updater = Updater(token, use_context=True)
        self.dp = self.updater.dispatcher

        # conversation states
        self.PARSE_NAME, self.PARSE_AGE, self.PARSE_INDEX = range(3)

        # inline keyboard callback data
        self.CB_DATA_ADD, self.CB_DATA_EDIT = map(str, range(2))

        self.init_handlers()

    def init_handlers(self):
        conversation_add_person = ConversationHandler(
            entry_points=[CommandHandler('add', self.add_new_person)],
            states={
                self.PARSE_NAME: [
                    MessageHandler(Filters.text, self.parse_name)
                ],
                self.PARSE_AGE: [
                    MessageHandler(Filters.text, self.conv_add_parse_age)
                ]
            },
            fallbacks=[
                MessageHandler(Filters.regex(r'^(\/start|\/get|\/edit|\/delete)$'), self.ignore_update),
                CommandHandler('cancel', self.cancel),
                MessageHandler(Filters.all, self.not_recognized)
            ],
            allow_reentry=True
        )
        conversation_edit_person = ConversationHandler(
            entry_points=[CommandHandler('edit', self.edit_person)],
            states={
                self.PARSE_INDEX: [
                    MessageHandler(Filters.regex(r'^\d+$'), self.conv_edit_parse_index)
                ],
                self.PARSE_NAME: [MessageHandler(Filters.text, self.parse_name)],
                self.PARSE_AGE: [MessageHandler(Filters.text, self.conv_edit_parse_age)],
            },
            fallbacks=[
                MessageHandler(Filters.regex(r'^(\/start|\/get|\/add|\/delete)$'), self.ignore_update),
                CommandHandler('cancel', self.cancel),
                MessageHandler(Filters.all, self.not_recognized)
            ],
            allow_reentry=True
        )
        conversation_delete_person = ConversationHandler(
            entry_points=[CommandHandler('delete', self.delete_person)],
            states={
                self.PARSE_INDEX: [
                    MessageHandler(Filters.regex(r'^\d+$'), self.conv_delete_parse_index)
                ]
            },
            fallbacks=[
                MessageHandler(Filters.regex(r'^(\/start|\/get|\/add|\/edit)$'), self.ignore_update),
                CommandHandler('cancel', self.cancel),
                MessageHandler(Filters.all, self.not_recognized)
            ],
            allow_reentry=True
        )

        self.dp.add_handler(CommandHandler('start', self.start), group=1)
        self.dp.add_handler(CommandHandler('get', self.get), group=1)
        self.dp.add_handler(MessageHandler(Filters.regex(r'^(\/add|\/edit|\/delete)$'), self.ignore_update), group=1)
        self.dp.add_handler(conversation_add_person, group=3)
        self.dp.add_handler(conversation_edit_person, group=4)
        self.dp.add_handler(conversation_delete_person, group=5)

        self.dp.add_error_handler(self.error_handler)

    def run(self):
        self.updater.start_polling()
        self.updater.idle()

    @staticmethod
    def error_handler(update: Update, context: CallbackContext):
        logger.error(f'Update:\n{update}')
        logger.exception(context.error)

    @staticmethod
    def not_recognized(update, context):
        update.message.reply_text('your response not recognized')

    @staticmethod
    def ignore_update(update, context):
        return ConversationHandler.END

    @reject_edit_update
    def start(self, update: Update, context: CallbackContext):
        update.message.reply_text(f'Добры дзень!', reply_markup=ReplyKeyboardRemove())

    @reject_edit_update
    def add_new_person(self, update, context):
        update.message.reply_text('Please, enter the name', reply_markup=ReplyKeyboardRemove())
        return self.PARSE_NAME

    @reject_edit_update
    def parse_name(self, update, context: CallbackContext):
        name = update.message.text
        context.user_data['name'] = name
        logger.info(f'name: {name}')
        update.message.reply_text('Please, enter the age')
        return self.PARSE_AGE

    @reject_edit_update
    def conv_add_parse_age(self, update, context):
        age = update.message.text
        name = context.user_data['name']
        logger.info(f'age: {age}')
        p = Person(name=name, age=age)
        logger.info(f'adding new person: {p}')
        crud.add_person(p)
        update.message.reply_text(f'Added new person! name: {name}. age: {age}')

        return ConversationHandler.END

    @staticmethod
    def format_persons_as_text(persons):
        if len(persons) == 0:
            return 'no persons'
        text = '\n'.join([f'{i}. {p}' for (i, p) in enumerate(persons, start=1)])
        return text

    @reject_edit_update
    def get(self, update, context):
        persons = crud.get_all_persons()
        text = self.format_persons_as_text(persons)
        update.message.reply_text(f'persons list:\n\n{text}', reply_markup=ReplyKeyboardRemove())

    @reject_edit_update
    def cancel(self, update, context):
        update.message.reply_text('Conversation canceled', reply_markup=ReplyKeyboardRemove())
        return ConversationHandler.END

    def request_user_to_choose_person(self, update, action):
        chat_id = update.effective_user.id
        if chat_id not in self.conversation_context:
            self.conversation_context[chat_id] = dict()

        persons = crud.get_all_persons()
        self.conversation_context[chat_id][self.K_PERSONS_LIST] = persons
        if len(persons) == 0:
            update.message.reply_text(f'No persons to {action}', reply_markup=ReplyKeyboardRemove())
            return False

        persons_text = self.format_persons_as_text(persons)
        buttons = list(map(str, range(1, len(persons) + 1)))
        rows = 3
        keyboard = [list(map(str, buttons[i:i + rows])) for i in range(0, len(buttons), rows)]
        markup = ReplyKeyboardMarkup(
            keyboard, resize_keyboard=True, one_time_keyboard=True
        )
        update.message.reply_text(
            f'Please choose index of person to {action}:\n\n{persons_text}',
            reply_markup=markup
        )
        return True

    @reject_edit_update
    def delete_person(self, update, context):
        status = self.request_user_to_choose_person(update, 'delete')
        next_state = self.PARSE_INDEX if status else ConversationHandler.END
        return next_state

    def get_person_by_chosen_index(self, update):
        chat_id = update.effective_user.id
        ix_str = update.message.text
        ix = int(ix_str) - 1
        persons = self.conversation_context[chat_id][self.K_PERSONS_LIST]
        if ix < 0 or ix >= len(persons):
            persons_text = self.format_persons_as_text(persons)
            update.message.reply_text(f'Index out of range. Choose again:\n\n{persons_text}')
            return None
        return persons[ix]

    @reject_edit_update
    def conv_delete_parse_index(self, update: Update, context):
        person_to_delete = self.get_person_by_chosen_index(update)
        if person_to_delete is None:
            return
        num_deleted = crud.delete_person(person_to_delete)
        update.message.reply_text(
            f'deleted {num_deleted} items',
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

    @reject_edit_update
    def edit_person(self, update, context):
        status = self.request_user_to_choose_person(update, 'edit')
        next_state = self.PARSE_INDEX if status else ConversationHandler.END
        return next_state

    @reject_edit_update
    def conv_edit_parse_index(self, update, context):
        person_to_edit = self.get_person_by_chosen_index(update)
        if person_to_edit is None:
            return
        chat_id = update.effective_user.id
        self.conversation_context[chat_id][self.K_CHOSEN_PERSON_ID] = person_to_edit.id
        update.message.reply_text('Please, enter new name', reply_markup=ReplyKeyboardRemove())
        return self.PARSE_NAME

    @reject_edit_update
    def conv_edit_parse_age(self, update, context):
        chat_id = update.effective_user.id
        age = update.message.text
        name = context.user_data['name']
        logger.info(f'age: {age}')
        new_p = Person(name=name, age=age)
        old_person_id = self.conversation_context[chat_id][self.K_CHOSEN_PERSON_ID]
        crud.edit_person(old_person_id, new_p)
        update.message.reply_text('Edit succeeded')
        logger.info(f'Edit succeeded')
        return ConversationHandler.END


def main():
    token = os.environ.get('BOT_TOKEN_TEST')
    contact_chat_id = os.environ.get('CONTACT_CHAT_ID')

    bot = TestBot(token, contact_chat_id)
    bot.run()


if __name__ == '__main__':
    main()

from aiogram.types import ReplyKeyboardRemove
import typing
from dataclasses import dataclass

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


@dataclass
class ListOfButtons:
    text: typing.List
    callback: typing.List = None
    align: typing.List[int] = None

    @property
    def inline_keyboard(self):
        return generate_inline_keyboard(self)

    @property
    def reply_keyboard(self):
        return generate_reply_keyboard(self)


def generate_inline_keyboard(args: ListOfButtons) -> InlineKeyboardMarkup:
    keyboard = InlineKeyboardMarkup()
    if args.text and args.callback and not (len(args.text) == len(args.callback)):
        raise IndexError("Все списки должны быть одной длины!")

    if not args.align:
        for num, button in enumerate(args.text):
            keyboard.add(InlineKeyboardButton(text=str(button),
                                              callback_data=str(args.callback[num])))
    else:
        count = 0
        for row_size in args.align:
            keyboard.row(*[InlineKeyboardButton(text=str(text), callback_data=str(callback_data))
                           for text, callback_data in
                           tuple(zip(args.text, args.callback))[count:count + row_size]])
            count += row_size
    return keyboard


def generate_reply_keyboard(args: ListOfButtons) -> ReplyKeyboardMarkup:
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)

    if not args.align:
        for num, button in enumerate(args.text):
            keyboard.add(KeyboardButton(text=str(button)))
    else:
        count = 0
        for row_size in args.align:
            keyboard.row(*[KeyboardButton(text=str(text)) for text in args.text[count:count + row_size]])
            count += row_size
    return keyboard


hide_markup = ReplyKeyboardRemove()


def admin_keyboard():
    k = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    k.insert(KeyboardButton('Create a lot'))
    k.insert(KeyboardButton('Active lots'))
    k.insert(KeyboardButton('Closed lots'))
    k.insert(KeyboardButton('Update from google sheet'))
    return k


def client_keyboard():
    k = ReplyKeyboardMarkup(resize_keyboard=True)
    k.insert(KeyboardButton('Active lots'))
    return k


def next_back_lots(current_page, total_pages):
    k = ListOfButtons(text=["Back", "Next"],
                      callback=[f"change_page back {current_page} {total_pages}",
                                f"change_page next {current_page} {total_pages}"],
                      align=[2]).inline_keyboard
    return k


def next_lots(current_page, total_pages):
    k = ListOfButtons(text=["Next"],
                      callback=[f"change_page next {current_page} {total_pages}"]).inline_keyboard
    return k


def back_lots(current_page, total_pages):
    k = ListOfButtons(text=["Back"],
                      callback=[f"change_page back {current_page} {total_pages}"]).inline_keyboard
    return k


def send_hidden_lot(lot_uid):
    k = ListOfButtons(text=["Show more"],
                      callback=[f"look {lot_uid}"]).inline_keyboard
    return k


def send_active_lot(lot_uid):
    k = ListOfButtons(text=["Place your bid", "Bid history", "Who looked", "Close"],
                      callback=[f"update {lot_uid}",
                                f"history {lot_uid}",
                                f"get_looked {lot_uid}",
                                f"close {lot_uid}"],
                      align=[1, 2, 1]).inline_keyboard
    return k


def send_close_lot(lot_uid):
    k = ListOfButtons(text=["Bid history", "Who looked", "Open lot"],
                      callback=[f"old_history {lot_uid}",
                                f"get_archive_looked {lot_uid}",
                                f"open {lot_uid}"]).inline_keyboard
    return k


def send_lot(lot_uid):
    k = ListOfButtons(text=["Place your bid"], callback=[f"update {lot_uid}"]).inline_keyboard
    return k


def phone_number_keyboard():
    k = ReplyKeyboardMarkup(resize_keyboard=True)
    k.insert(KeyboardButton('📱Send phone number', request_contact=True))
    return k


def cancel():
    k = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    k.insert(KeyboardButton('cancel'))
    return k


def pr():
    k = ReplyKeyboardMarkup(resize_keyboard=True)
    k.insert(KeyboardButton('back'))
    k.insert(KeyboardButton('skip'))
    k.insert(KeyboardButton('cancel'))
    return k


def currency():
    k = ListOfButtons(text=['UAH', 'USD', 'EUR'],
                      align=[3]).reply_keyboard
    return k


def choose_crop(list_crops: list):
    k = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    list_buttons = list_crops.copy()
    list_buttons.extend(['skip', 'cancel'])
    for button in list_buttons:
        k.insert(KeyboardButton(button))
    return k


def choose_basis(list_basis: list):
    k = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    list_buttons = list_basis.copy()
    list_buttons.extend(['back', 'skip', 'cancel'])
    for button in list_buttons:
        k.insert(KeyboardButton(button))
    return k


def choose_month():
    k = ListOfButtons(text=['January', 'February', 'March',
                            'April', 'May', 'June', 'July',
                            'August', 'September', 'October',
                            'November', 'December',
                            'back', 'skip', 'cancel'], align=[4, 4, 4, 3]).reply_keyboard
    return k

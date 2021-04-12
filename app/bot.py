import asyncio
import logging
import time
import datetime
import gspread
import threading
import json
import os

import database
import states
import keyboards
import filters

from aiogram import Bot, types
from aiogram.dispatcher import Dispatcher
from aiogram.contrib.fsm_storage.mongo import MongoStorage
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor, exceptions
from aiogram.types import ContentTypes
from aiogram.types import CallbackQuery

from bson.objectid import ObjectId
from oauth2client.service_account import ServiceAccountCredentials

with open('./app/config.json', 'r') as f:
    config = json.load(f)

config['db_name'] = os.environ['MONGODB_DATABASE']
config['db_host'] = os.environ['MONGODB_HOSTNAME']
config['db_username'] = os.environ['MONGODB_USERNAME']
config['db_password'] = os.environ['MONGODB_PASSWORD']
scope = ['https://spreadsheets.google.com/feeds']
credentials = ServiceAccountCredentials.from_json_keyfile_name(config["credentials"], scope)
gc = gspread.authorize(credentials)
archive = gc.open_by_url(config["archive"])
settings = archive.worksheet(title='settings')
loop = asyncio.get_event_loop()
logging.basicConfig(filename='./app/bot.log', filemode='a', format='%(asctime)s - %(name)s  - %(message)s',
                    level=logging.INFO)

bot = Bot(token=config["token"])
storage = MongoStorage(host=config['db_host'], port=config['db_port'], db_name=config["db_name"], username=config["db_username"],
                       password=config["db_password"])
dp = Dispatcher(bot, storage=storage)


async def shutdown(dp: Dispatcher):
    await dp.storage.close()
    await dp.storage.wait_closed()


def get_total_pages(all_items, items_per_page=10):
    if len(all_items) % items_per_page == 0:
        total_pages = int(len(all_items)) // items_per_page
    else:
        total_pages = (int(len(all_items)) // items_per_page) + 1
    return total_pages


def get_offset_and_items_per_page(current_page, items_per_page=10):
    offset = (current_page - 1) * items_per_page
    return offset, items_per_page


def add_lot_to_sheet_archive(lot_id):
    gc.login()
    logging.info(f'start add to sheet archive lot[{lot_id}]')
    try:
        lot = database.Archive.objects(_id=lot_id).first()
        ws = archive.add_worksheet(title=f"{lot.create_name_worksheet()}", rows="1000", cols="20")

        cell_list = ws.range('A1:K2')
        val_list = lot.lot_info_to_sheet()
        i = 0
        for cell in cell_list:
            cell.value = str(val_list[i])
            i += 1
        ws.update_cells(cell_list)
        n = len(lot.history)
        n = n + 3
        cell_list = ws.range(f'A3:E{n}')
        val_list = lot.history_to_sheet()
        i = 0
        for cell in cell_list:
            cell.value = str(val_list[i])
            i += 1
        ws.update_cells(cell_list)
        n1 = len(lot.looked_info)
        cell_list = ws.range(f'A{n + 1}:D{n + n1 + 1}')
        val_list = lot.lookedinfo_to_sheet()
        i = 0
        for cell in cell_list:
            cell.value = str(val_list[i])
            i += 1
        ws.update_cells(cell_list)
        logging.info(f'end add to sheet archive lot[{lot_id}]')
    except Exception as e:
        logging.error(f'{e}')


def sheet_settings_to_db():
    gc.login()
    admin_phone_list = settings.col_values(1)[1:]
    crops_list = settings.col_values(2)[1:]
    basis_list = settings.col_values(3)[1:]
    white_list = settings.col_values(4)[1:]
    stngs = database.Settings.objects(_id='1').first()
    stngs.admin_phone_numbers = admin_phone_list
    stngs.crops = crops_list
    stngs.basis = basis_list
    stngs.white_list = white_list
    # add crop character
    crops = stngs.crops
    dict_crops = {}
    for crop in crops:
        try:
            characteristics = zip(list(archive.worksheet(title=f'{crop}').row_values(1)),
                                  list(archive.worksheet(title=f'{crop}').row_values(2)))
            dict_crops[f'{crop}'] = dict(characteristics)
        except Exception as e:
            print(e)
    stngs.crops_characteristics = dict_crops
    stngs.save()
    number_list = stngs.admin_phone_numbers
    users = database.User.objects()
    for user in users:
        try:
            if user.phone_number in number_list:
                user.status = 'admin'
                user.save()
            elif user.phone_number in stngs.white_list:
                user.status = 'client'
                user.save()
            else:
                user.status = 'Block'
        except Exception as e:
            print(e)

    try:
        numbers = settings.col_values(4)
        names = settings.col_values(7)
        if len(numbers) == len(names):
            company_names = dict(zip(numbers, names))
        else:
            n = len(numbers) - len(names)
            for i in range(n):
                names.append('None')
            company_names = dict(zip(numbers, names))
        for user in users:
            try:
                company = company_names[f"{user.phone_number}"]
                if len(company) < 1:
                    user.company = 'None'
                    user.save()
                else:
                    user.company = company
                    user.save()
            except Exception as e:
                print(e)
    except Exception as e:
        print(e)


@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message):
    try:
        user = database.User.objects(_id=f'{message.chat.id}')[0]
        if user.status == 'admin':
            await states.Menu.admin_menu.set()
            await bot.send_message(message.chat.id, '👇', reply_markup=keyboards.admin_keyboard())
        else:
            stngs = database.Settings.objects(_id='1').first()
            if user.phone_number in stngs.white_list:
                await states.Menu.main_menu.set()
                lots = database.Lot.objects()
                for lot in lots:
                    msg = await bot.send_message(message.chat.id, text=lot.create_message(),
                                                 reply_markup=keyboards.send_hidden_lot(lot._id))
                    lot.add_message_id(msg.chat.id, msg.message_id)
                    lot.save()
    except IndexError:
        await states.User.phone_number.set()
        # await bot.send_message(message.chat.id, 'Hello👋\n'
        #                                         'Цей бот для проведення торгів зерном компанією Агро-Регіон')
        await bot.send_message(message.chat.id, "Press the button👇", reply_markup=keyboards.phone_number_keyboard())


@dp.message_handler(filters.Button('cancel'), state=states.Menu.update_price)
async def cmd_cancel(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if database.User.objects(_id=str(message.chat.id)).first().status == 'admin':
            await bot.send_message(message.chat.id, 'cancel', reply_markup=keyboards.admin_keyboard())
            await bot.delete_message(message.chat.id, data['message_id'])
            await states.Menu.admin_menu.set()
            await bot.delete_message(message.chat.id, message.message_id)
        else:
            nmsg = await bot.send_message(message.chat.id, 'cancel', reply_markup=keyboards.hide_markup)
            await bot.delete_message(message.chat.id, data['message_id'])
            await states.Menu.main_menu.set()
            await bot.delete_message(message.chat.id, message.message_id)
            await bot.delete_message(nmsg.chat.id, nmsg.message_id)


@dp.message_handler(content_types='contact', state=states.User.phone_number)
async def cmd_contact(message: types.Message):
    if message.from_user.id == message.contact.user_id:
        phone_number = message.contact.phone_number.replace('+', '')
        list_admins = database.Settings.objects(_id='1').first().admin_phone_numbers
        if phone_number in list_admins:
            status = 'admin'
        else:
            status = 'client'
        user = database.User(_id=str(message.chat.id), username=message.from_user.username,
                             name=message.from_user.full_name,
                             phone_number=phone_number, status=status).save()
        await states.Menu.main_menu.set()
        msgs = await bot.send_message(message.chat.id, 'done ', reply_markup=keyboards.hide_markup)
        await bot.delete_message(msgs.chat.id, msgs.message_id)
        if user.status == 'client':
            lots = database.Lot.objects()
            for lot in lots:
                msg = await bot.send_message(message.chat.id, text=lot.create_message(),
                                             reply_markup=keyboards.send_hidden_lot(lot._id))
                lot.add_message_id(msg.chat.id, msg.message_id)
                lot.save()
        elif user.status == 'admin':
            await states.Menu.admin_menu.set()
            await bot.send_message(message.chat.id, '👇', reply_markup=keyboards.admin_keyboard())
    else:
        await bot.send_message(message.chat.id, 'Do not cheat', reply_markup=keyboards.hide_markup)
        await bot.send_message(message.chat.id, 'Send your number👇🏻',
                               reply_markup=keyboards.phone_number_keyboard())


@dp.message_handler(filters.Button('Create a lot'), state=states.Menu.admin_menu)
async def cmd_add_lot(message: types.Message):
    list_crops = database.Settings.objects(_id='1').first().crops
    await bot.send_message(message.chat.id, '🌾Crop:', reply_markup=keyboards.choose_crop(list_crops))
    await states.AddLot.crop.set()


@dp.message_handler(filters.Button('cancel'), state=states.AddLot)
async def cmd_cancel(message: types.Message):
    await bot.send_message(message.chat.id, 'cancel', reply_markup=keyboards.admin_keyboard())
    await states.Menu.admin_menu.set()


@dp.message_handler(filters.Button('Active lots'), state=states.Menu.admin_menu)
async def cmd_active_lots(message: types.Message):
    lots = database.Lot.objects()
    if len(lots) == 0:
        await bot.send_message(message.chat.id, text='Empty',
                               reply_markup=keyboards.admin_keyboard())
    else:
        for lot in lots:
            msg = await bot.send_message(message.chat.id, text=lot.create_full_message(),
                                         reply_markup=keyboards.send_active_lot(lot._id))
            lot.add_message_id(msg.chat.id, msg.message_id)
            lot.save()


@dp.callback_query_handler(filters.Button("old_history", contains=True), state=states.Menu.admin_menu)
async def cmd_old_history(call: CallbackQuery, ):
    lot_id = call.data.split('old_history ')[1]
    text = database.Archive.objects(_id=lot_id)[0].get_history()
    try:
        await call.message.reply(text=text)
    except exceptions.MessageTextIsEmpty:
        await call.message.reply(text='History is empty')


@dp.callback_query_handler(filters.Button("history", contains=True), state=states.Menu.admin_menu)
async def cmd_history(call: CallbackQuery, ):
    lot_id = call.data.split('history ')[1]
    text = database.Lot.objects(_id=lot_id)[0].get_history()
    try:
        await call.message.reply(text=text)
    except exceptions.MessageTextIsEmpty:
        await call.message.reply(text='History is empty')


@dp.callback_query_handler(filters.Button("close", contains=True), state=states.Menu.admin_menu)
async def cmd_close(call: CallbackQuery):
    lot_id = call.data.split('close ')[1]
    lot = database.Lot.objects(_id=lot_id)[0]
    all_msg = lot.dict_message_ids.items()
    for msg in all_msg:
        try:
            await bot.delete_message(msg[0], msg[1])
        except Exception as e:
            print(e)
    database.Archive(_id=lot._id, number=lot.number, author=lot.author, crop=lot.crop, weight=lot.weight,
                     delivery_basis=lot.delivery_basis,
                     delivery_month=lot.delivery_month, currency=lot.currency, start_price=lot.start_price,
                     step_price=lot.step_price,
                     comment=lot.comment, current_price=lot.current_price, history=lot.history,
                     date_creation=lot.date_creation, looked_info=lot.looked_info).save()
    lot.save()
    lot.delete()
    threading.Thread(target=add_lot_to_sheet_archive, args=(lot_id,)).start()
    await bot.send_message(call.message.chat.id, text='Lot closed')


@dp.callback_query_handler(filters.Button("open", contains=True), state=states.Menu.admin_menu)
async def cmd_open(call: CallbackQuery):
    lot_id = call.data.split('open ')[1]
    lot = database.Archive.objects(_id=lot_id)[0]
    open_lot = database.Lot(_id=lot._id, number=lot.number, author=lot.author, crop=lot.crop, weight=lot.weight,
                            delivery_basis=lot.delivery_basis,
                            delivery_month=lot.delivery_month, currency=lot.currency, start_price=lot.start_price,
                            step_price=lot.step_price,
                            comment=lot.comment, current_price=lot.current_price, history=lot.history,
                            date_creation=lot.date_creation).save()
    lot.delete()
    gc.login()
    archive.del_worksheet(archive.worksheet(f'{open_lot.create_name_worksheet()}'))
    users = database.User.objects()
    text = open_lot.create_message()
    for user in users:
        if user.status == 'admin':
            try:
                msg = await bot.send_message(user._id, text)
                open_lot.add_message_id(msg.chat.id, msg.message_id)
                open_lot.save()
            except exceptions.BotBlocked:
                logging.info('block')
            except exceptions.ChatIdIsEmpty:
                logging.info('empty')
            except exceptions.ChatNotFound as e:
                logging.info(f'{e}')
        else:
            stngs = database.Settings.objects(_id='1').first()
            if user.phone_number in stngs.white_list:
                try:
                    msg = await bot.send_message(user._id, text, reply_markup=keyboards.send_hidden_lot(open_lot._id))
                    open_lot.add_message_id(msg.chat.id, msg.message_id)
                    open_lot.save()
                except exceptions.BotBlocked:
                    logging.info('block')
                except exceptions.ChatIdIsEmpty:
                    logging.info('empty')
                except exceptions.ChatNotFound as e:
                    logging.info(f'{e}')
    await bot.send_message(call.message.chat.id, text='Lot open')
    await bot.delete_message(call.message.chat.id, call.message.message_id)


@dp.message_handler(filters.Button('Closed lots'), state=states.Menu.admin_menu)
async def cmd_close_lots(message: types.Message, state: FSMContext):
    all_items = database.Archive.objects()
    current_page = 1
    total_pages = get_total_pages(all_items)
    offset, items_per_page = get_offset_and_items_per_page(current_page)
    if len(all_items) == 0:
        await bot.send_message(message.chat.id, text='Empty',
                               reply_markup=keyboards.admin_keyboard())
    items = database.Archive.objects.order_by('-number').skip(offset).limit(items_per_page)
    if total_pages - current_page == 0:
        for lot in items:
            await bot.send_message(message.chat.id, text=lot.create_message(),
                                   reply_markup=keyboards.send_close_lot(lot._id))
    else:
        for lot in items:
            await bot.send_message(message.chat.id, text=lot.create_message(),
                                   reply_markup=keyboards.send_close_lot(lot._id))
        await bot.send_message(message.chat.id, f'Page {current_page} of {total_pages}',
                               reply_markup=keyboards.next_lots(current_page, total_pages))


@dp.callback_query_handler(filters.Button("change_page", contains=True), state='*')
async def cmd_update(call: CallbackQuery):
    _, action, current_page, total_pages = call.data.split(' ')
    if str(action) == 'back':
        if int(current_page) == 1:
            await bot.answer_callback_query(call.id, 'Wrong request')
        else:
            current_page = int(current_page) - 1
            offset, items_per_page = get_offset_and_items_per_page(current_page)
            items = database.Archive.objects.order_by('-number').skip(offset).limit(items_per_page)
            for lot in items:
                await bot.send_message(call.message.chat.id, text=lot.create_message(),
                                       reply_markup=keyboards.send_close_lot(lot._id))
            if current_page == 1:
                await bot.send_message(call.message.chat.id, f'Page {current_page} of {total_pages}',
                                       reply_markup=keyboards.next_lots(current_page, total_pages))
            else:
                await bot.send_message(call.message.chat.id, f'Page {current_page} of {total_pages}',
                                       reply_markup=keyboards.next_back_lots(current_page, total_pages))
    if str(action) == 'next':
        if int(current_page) == int(total_pages):
            await bot.answer_callback_query(call.id, 'Wrong request')
        else:
            current_page = int(current_page) + 1
            offset, items_per_page = get_offset_and_items_per_page(current_page)
            items = database.Archive.objects.order_by('-number').skip(offset).limit(items_per_page)
            for lot in items:
                await bot.send_message(call.message.chat.id, text=lot.create_message(),
                                       reply_markup=keyboards.send_close_lot(lot._id))
            if int(current_page) == int(total_pages):
                await bot.send_message(call.message.chat.id, f'Page {current_page} of {total_pages}',
                                       reply_markup=keyboards.back_lots(current_page, total_pages))
            else:
                await bot.send_message(call.message.chat.id, f'Page {current_page} of {total_pages}',
                                       reply_markup=keyboards.next_back_lots(current_page, total_pages))


@dp.message_handler(filters.Button('Update from google sheet'), state=states.Menu.admin_menu)
async def cmd_next(message: types.Message):
    try:
        sheet_settings_to_db()
        await bot.send_message(message.chat.id, 'done', reply_markup=keyboards.admin_keyboard())
    except Exception as e:
        await bot.send_message(message.chat.id, f'{e}', reply_markup=keyboards.admin_keyboard())


@dp.callback_query_handler(filters.Button("update", contains=True), state='*')
async def cmd_update(call: CallbackQuery, state: FSMContext):
    async with state.proxy() as data:
        try:
            await bot.delete_message(data['chat_id'], data['message_id'])
        except exceptions.MessageToDeleteNotFound:
            pass
        except exceptions.MessageCantBeDeleted:
            pass
        except Exception as e:
            print(e)
        except KeyError:
            pass
        data['lot_id'] = call.data.split('update ')[1]
        try:
            lot = database.Lot.objects(_id=data['lot_id'])[0]
            msg = await call.message.reply(f'💵Current bid: {lot.current_price} {lot.currency}\n'
                                           f'👟Bid step: {lot.step_price} {lot.currency}\n'
                                           f'💵Place your bid:', reply_markup=keyboards.cancel())
            data['message_id'] = msg.message_id
            data['chat_id'] = msg.chat.id
            data['call_id'] = call.id
            lot.save()
            await states.Menu.update_price.set()
        except IndexError:
            await bot.delete_message(call.message.chat.id, call.message.message_id)
            await bot.answer_callback_query(call.id, 'Lot closed')
            if database.User.objects(_id=str(call.message.chat.id)).first().status == 'admin':
                await states.Menu.admin_menu.set()
            else:
                await states.Menu.main_menu.set()


@dp.callback_query_handler(filters.Button("get_looked", contains=True), state='*')
async def cmd_update(call: CallbackQuery):
    lot_id = call.data.split('get_looked ')[1]
    lot = database.Lot.objects(_id=lot_id).first()
    text = lot.get_looked_info()
    try:
        await call.message.reply(text=text)
    except Exception as e:
        logging.info(e)
        await call.message.reply("Empty")


@dp.callback_query_handler(filters.Button("get_archive_looked", contains=True), state='*')
async def cmd_update(call: CallbackQuery):
    lot_id = call.data.split('get_archive_looked ')[1]
    lot = database.Archive.objects(_id=lot_id).first()
    text = lot.get_looked_info()
    try:
        await call.message.reply(text=text)
    except Exception as e:
        logging.info(e)
        await call.message.reply("Empty")


@dp.callback_query_handler(filters.Button("look", contains=True), state='*')
async def cmd_update(call: CallbackQuery):
    chat_id = str(call.message.chat.id)
    lot_id = call.data.split('look ')[1]
    lot = database.Lot.objects(_id=lot_id).first()
    try:
        lot.add_looked(chat_id, call.message.message_id)
        now_time, now_date = str(datetime.datetime.strftime(datetime.datetime.now(), '%H:%M:%S|%d.%m.%Y')).split('|')
        lot.add_looked_info(database.User.objects(_id=chat_id).first().phone_number, now_time, now_date)
        lot.save()
        await bot.edit_message_text(chat_id=f'{chat_id}',
                                    message_id=call.message.message_id,
                                    text=lot.create_full_message(),
                                    reply_markup=keyboards.send_lot(lot._id))
    except Exception:
        await bot.delete_message(call.message.chat.id, call.message.message_id)
        await bot.answer_callback_query(call.id, 'Lot closed')


@dp.message_handler(content_types=ContentTypes.TEXT, state=states.Menu.main_menu)
async def cmd_clear(message: types.Message):
    await bot.delete_message(message.chat.id, message.message_id)


@dp.message_handler(content_types=ContentTypes.TEXT, state=states.Menu.update_price)
async def cmd_update_price(message: types.Message, state: FSMContext):
    await bot.delete_message(message.chat.id, message.message_id)
    async with state.proxy() as data:

        try:
            lot = database.Lot.objects(_id=data['lot_id'])[0]
            new_price = float(f'{message.text}'.replace(',', '.'))
            try:
                await bot.delete_message(message.chat.id, data['message_id'])
            except exceptions.MessageToDeleteNotFound:
                pass
            now_time, now_date = str(datetime.datetime.strftime(datetime.datetime.now(), '%H:%M:%S|%d.%m.%Y')).split(
                '|')
            chat_id = str(message.chat.id)
            user = database.User.objects(_id=chat_id)[0]
            lot.update_price(user.phone_number, new_price, now_time, now_date)
            lot.save()
            all_msgs = lot.is_looked.items()
            text = lot.create_full_message()
            for msg in all_msgs:
                try:
                    usr = database.User.objects(_id=msg[0]).first()
                    if usr.status == 'admin':
                        await bot.edit_message_text(chat_id=f'{msg[0]}', message_id=msg[1], text=text,
                                                    reply_markup=keyboards.send_active_lot(lot._id))
                    elif usr.status == 'client':
                        await bot.edit_message_text(chat_id=f'{msg[0]}', message_id=msg[1], text=text,
                                                    reply_markup=keyboards.send_lot(lot._id))
                except Exception as e:
                    logging.info(e)
            if user.status == 'admin':
                await states.Menu.admin_menu.set()
                await bot.send_message(message.chat.id, 'Price updated', reply_markup=keyboards.admin_keyboard())
            else:
                try:
                    await bot.answer_callback_query(data['call_id'], text='Price updated')
                except exceptions.BadRequest:
                    pass
                await states.Menu.main_menu.set()
        except ValueError:
            try:
                await bot.delete_message(message.chat.id, data['message_id'])
            except exceptions.MessageToDeleteNotFound:
                pass
            msg = await bot.send_message(message.chat.id, f'⛔This is not a number. Enter a number, please.\n'
                                                          f'💵Current bid: {lot.current_price} {lot.currency}\n'
                                                          f'👟Bid step: {lot.step_price} {lot.currency}\n'
                                                          f'💵Place your bid:')
            data['message_id'] = msg.message_id
            await states.Menu.update_price.set()
        except ArithmeticError:
            try:
                await bot.delete_message(message.chat.id, data['message_id'])
            except exceptions.MessageToDeleteNotFound:
                pass
            msg = await bot.send_message(message.chat.id,
                                         f'⛔The difference between yours and current price must be greater or equal to the bid step.\n'
                                         f'💵Current bid: {lot.current_price} {lot.currency}\n'
                                         f'👟Bid step: {lot.step_price} {lot.currency}\n'
                                         f'💵Place your bid:')
            data['message_id'] = msg.message_id
            await states.Menu.update_price.set()
        except IndexError:
            try:
                await bot.delete_message(message.chat.id, data['message_id'])
                await bot.delete_message(message.chat.id, message.message_id)
            except exceptions.MessageToDeleteNotFound:
                pass
            if database.User.objects(_id=str(message.chat.id)).first().status == 'admin':
                await states.Menu.admin_menu.set()
            else:
                await states.Menu.main_menu.set()


@dp.message_handler(filters.Button('back'), state=states.AddLot)
async def cmd_back(message: types.Message, state: FSMContext):
    await states.AddLot.previous()
    current_state = await state.get_state()
    if current_state == 'AddLot:crop':
        list_crops = database.Settings.objects(_id='1').first().crops
        await bot.send_message(message.chat.id, '🌾Crop:', reply_markup=keyboards.choose_crop(list_crops))
    elif current_state == 'AddLot:weight':
        await bot.send_message(message.chat.id, '⚖Weight, t:', reply_markup=keyboards.pr())
    elif current_state == 'AddLot:delivery_basis':
        list_basis = database.Settings.objects(_id='1').first().basis
        await bot.send_message(message.chat.id, '🏭Delivery Basis:', reply_markup=keyboards.choose_basis(list_basis))
    elif current_state == 'AddLot:delivery_month':
        await bot.send_message(message.chat.id, '📆Delivery month:', reply_markup=keyboards.choose_month())
    elif current_state == 'AddLot:currency':
        await bot.send_message(message.chat.id, '💱Currency:', reply_markup=keyboards.currency())
    elif current_state == 'AddLot:start_price':
        await bot.send_message(message.chat.id, '💰Starting bid:', reply_markup=keyboards.pr())
    elif current_state == 'AddLot:step_price':
        await bot.send_message(message.chat.id, '👟Bid step:', reply_markup=keyboards.pr())
    elif current_state == 'AddLot:comment':
        await bot.send_message(message.chat.id, '📝Comments:', reply_markup=keyboards.pr())


@dp.message_handler(filters.Button('skip'), state=states.AddLot)
async def cmd_next(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        current_state = await state.get_state()
        if current_state == 'AddLot:comment':
            await states.Menu.admin_menu.set()
        else:
            await states.AddLot.next()
        if current_state == 'AddLot:crop':
            data['crop'] = '-'
            await bot.send_message(message.chat.id, '⚖Weight, t:', reply_markup=keyboards.pr())
        elif current_state == 'AddLot:weight':
            data['weight'] = '0'
            list_basis = database.Settings.objects(_id='1').first().basis
            await bot.send_message(message.chat.id, '🏭Delivery Basis:',
                                   reply_markup=keyboards.choose_basis(list_basis))
        elif current_state == 'AddLot:delivery_basis':
            data['delivery_basis'] = '-'
            await bot.send_message(message.chat.id, '📆Delivery month:', reply_markup=keyboards.choose_month())
        elif current_state == 'AddLot:delivery_month':
            data['delivery_month'] = '-'
            await bot.send_message(message.chat.id, '💱Currency:', reply_markup=keyboards.currency())
        elif current_state == 'AddLot:start_price':
            data['start_price'] = '0'
            await bot.send_message(message.chat.id, '👟Bid step:', reply_markup=keyboards.pr())
        elif current_state == 'AddLot:step_price':
            data['step_price'] = '1'
            await bot.send_message(message.chat.id, '📝Comments:', reply_markup=keyboards.pr())
        elif current_state == 'AddLot:comment':
            try:
                await states.Menu.admin_menu.set()
                data['comment'] = '-'
                data['author'] = message.chat.id
                number = database.Settings.objects().first().give_new_number()
                lot = database.Lot(_id=str(ObjectId()), number=int(number), author=str(data['author']),
                                   crop=data['crop'],
                                   weight=float(data['weight']),
                                   delivery_basis=data['delivery_basis'],
                                   delivery_month=data['delivery_month'], currency=data['currency'],
                                   start_price=float(data['start_price']),
                                   step_price=float(data['step_price']),
                                   comment=str(data['comment']), current_price=float(data['start_price']))
                lot.save()
                text = lot.create_message()
                users = database.User.objects()
                stngs = database.Settings.objects(_id='1').first()
                for user in users:
                    if user.status == 'client' and user.phone_number in stngs.white_list:
                        try:
                            msg = await bot.send_message(user._id, text,
                                                         reply_markup=keyboards.send_hidden_lot(lot._id))
                            lot.add_message_id(msg.chat.id, msg.message_id)
                            lot.save()
                        except exceptions.BotBlocked:
                            logging.info('block')
                        except exceptions.ChatIdIsEmpty:
                            logging.info('empty')
                        except exceptions.ChatNotFound:
                            logging.info('chatnotfound')
                    elif user.status == 'admin':
                        try:
                            msg = await bot.send_message(user._id, text)
                            lot.add_message_id(msg.chat.id, msg.message_id)
                            lot.save()
                        except exceptions.BotBlocked:
                            logging.info('block')
                        except exceptions.ChatIdIsEmpty:
                            logging.info('empty')
                        except exceptions.ChatNotFound:
                            logging.info('chatnotfound')
                await bot.send_message(message.chat.id, 'done', reply_markup=keyboards.admin_keyboard())
            except Exception as e:
                await bot.send_message(message.chat.id, f'{e}', reply_markup=keyboards.admin_keyboard())


@dp.message_handler(content_types=ContentTypes.TEXT, state=states.AddLot.crop)
async def cmd_crop(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        try:
            data['crop'] = str(message.text)
            await states.AddLot.next()
            await bot.send_message(message.chat.id, '⚖Weight, t:', reply_markup=keyboards.pr())
        except ValueError:
            await states.AddLot.crop.set()
            await bot.send_message(message.chat.id, 'Invalid data')
            list_crops = database.Settings.objects(_id='1').first().crop
            await bot.send_message(message.chat.id, '🌾Crop:',
                                   reply_markup=keyboards.choose_basis(list_crops))


@dp.message_handler(content_types=ContentTypes.TEXT, state=states.AddLot.weight)
async def cmd_weight(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        try:
            data['weight'] = float(f'{message.text}'.replace(',', '.'))
            await states.AddLot.next()
            list_basis = database.Settings.objects(_id='1').first().basis
            await bot.send_message(message.chat.id, '🏭Delivery Basis:',
                                   reply_markup=keyboards.choose_basis(list_basis))
        except ValueError:
            await states.AddLot.weight.set()
            await bot.send_message(message.chat.id, 'Invalid data')
            await bot.send_message(message.chat.id, '⚖Weight, t:', reply_markup=keyboards.pr())


@dp.message_handler(content_types=ContentTypes.TEXT, state=states.AddLot.delivery_basis)
async def cmd_delivery_basis(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        try:
            data['delivery_basis'] = str(message.text)
            await bot.send_message(message.chat.id, '📆Delivery month:', reply_markup=keyboards.choose_month())
            await states.AddLot.next()
        except ValueError:
            await states.AddLot.delivery_basis.set()
            await bot.send_message(message.chat.id, 'Invalid data')
            list_basis = database.Settings.objects(_id='1').first().basis
            await bot.send_message(message.chat.id, '🏭Delivery Basis:',
                                   reply_markup=keyboards.choose_basis(list_basis))


@dp.message_handler(content_types=ContentTypes.TEXT, state=states.AddLot.delivery_month)
async def cmd_delivery_month(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if message.text in ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September',
                            'October', 'November', 'December']:
            data['delivery_month'] = message.text
            await states.AddLot.next()
            await bot.send_message(message.chat.id, '💱Currency:', reply_markup=keyboards.currency())
        else:
            await states.AddLot.delivery_month.set()
            await bot.send_message(message.chat.id, 'Invalid data')
            await bot.send_message(message.chat.id, '📆Delivery month:', reply_markup=keyboards.choose_month())


@dp.message_handler(content_types=ContentTypes.TEXT, state=states.AddLot.currency)
async def cmd_currency(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        if message.text in ['UAH', 'USD', 'EUR']:
            data['currency'] = message.text
            await states.AddLot.next()
            await bot.send_message(message.chat.id, '💰Starting bid:', reply_markup=keyboards.pr())
        else:
            await states.AddLot.delivery_month.set()
            await bot.send_message(message.chat.id, 'Invalid data')
            await bot.send_message(message.chat.id, '💱Currency:', reply_markup=keyboards.currency())


@dp.message_handler(content_types=ContentTypes.TEXT, state=states.AddLot.start_price)
async def cmd_start_price(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        try:
            data['start_price'] = float(f'{message.text}'.replace(',', '.'))
            await states.AddLot.next()
            await bot.send_message(message.chat.id, '👟Bid step:', reply_markup=keyboards.pr())
        except ValueError:
            await states.AddLot.start_price.set()
            await bot.send_message(message.chat.id, 'Invalid data')
            await bot.send_message(message.chat.id, '💰Starting bid:', reply_markup=keyboards.pr())


@dp.message_handler(content_types=ContentTypes.TEXT, state=states.AddLot.step_price)
async def cmd_step_price(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        try:
            data['step_price'] = float(f'{message.text}'.replace(',', '.'))
            await states.AddLot.next()
            await bot.send_message(message.chat.id, '📝Comments:', reply_markup=keyboards.pr())
        except ValueError:
            await states.AddLot.step_price.set()
            await bot.send_message(message.chat.id, 'Invalid data')
            await bot.send_message(message.chat.id, '👟Bid step:', reply_markup=keyboards.pr())


@dp.message_handler(content_types=ContentTypes.TEXT, state=states.AddLot.comment)
async def cmd_comment(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        try:
            data['comment'] = str(message.text)
            data['author'] = message.chat.id
            number = database.Settings.objects().first().give_new_number()
            lot = database.Lot(_id=str(ObjectId()), number=int(number), author=str(data['author']), crop=data['crop'],
                               weight=float(data['weight']),
                               delivery_basis=data['delivery_basis'], delivery_month=data['delivery_month'],
                               currency=data['currency'],
                               start_price=float(data['start_price']),
                               step_price=float(data['step_price']), comment=str(data['comment']),
                               current_price=float(data['start_price']))
            lot.save()
            text = lot.create_message()
            users = database.User.objects()
            stngs = database.Settings.objects(_id='1').first()
            for user in users:
                if user.status == 'client' and user.phone_number in stngs.white_list:
                    try:
                        msg = await bot.send_message(user._id, text, reply_markup=keyboards.send_hidden_lot(lot._id))
                        lot.add_message_id(msg.chat.id, msg.message_id)
                        lot.save()
                    except exceptions.BotBlocked:
                        logging.info('block')
                    except exceptions.ChatIdIsEmpty:
                        logging.info('empty')
                elif user.status == 'admin':
                    try:
                        msg = await bot.send_message(user._id, text)
                        lot.add_message_id(msg.chat.id, msg.message_id)
                        lot.save()
                    except exceptions.BotBlocked:
                        logging.info('block')
                    except exceptions.ChatIdIsEmpty:
                        logging.info('empty')
            await bot.send_message(message.chat.id, 'done', reply_markup=keyboards.admin_keyboard())
            data.clear()
        except Exception as e:
            await bot.send_message(message.chat.id, f'{e}', reply_markup=keyboards.admin_keyboard())
    await states.Menu.admin_menu.set()


if __name__ == '__main__':
    executor.start_polling(dp, loop=loop, skip_updates=True, on_shutdown=shutdown)

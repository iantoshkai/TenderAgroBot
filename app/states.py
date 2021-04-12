from aiogram.dispatcher.filters.state import State, StatesGroup


class User(StatesGroup):
    phone_number = State()


class Menu(StatesGroup):
    admin_menu = State()
    main_menu = State()
    update_price = State()


class AddLot(StatesGroup):
    crop = State()
    weight = State()
    delivery_basis = State()
    delivery_month = State()
    currency = State()
    start_price = State()
    step_price = State()
    comment = State()
    confirm = State()

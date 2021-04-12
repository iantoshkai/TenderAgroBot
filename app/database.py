import mongoengine
import datetime
import json
import os


mongoengine.connect(
    os.environ['MONGODB_DATABASE'],
    host=os.environ['MONGODB_HOSTNAME'],
    username=os.environ['MONGODB_USERNAME'],
    password=os.environ['MONGODB_PASSWORD'],
    port=27017,
    authentication_source='admin')


class User(mongoengine.Document):
    _id = mongoengine.StringField(required=True, primary_key=True)
    username = mongoengine.StringField(default='None')
    name = mongoengine.StringField(required=True)
    phone_number = mongoengine.StringField(required=True)
    status = mongoengine.StringField(required=True)
    company = mongoengine.StringField()


class Lot(mongoengine.Document):
    _id = mongoengine.StringField(required=True, primary_key=True)
    number = mongoengine.IntField(required=True)
    author = mongoengine.StringField(required=True)
    crop = mongoengine.StringField(required=True)
    weight = mongoengine.FloatField(required=True)
    delivery_basis = mongoengine.StringField(required=True)
    delivery_month = mongoengine.StringField(required=True)
    currency = mongoengine.StringField(required=True)
    start_price = mongoengine.FloatField(required=True)
    step_price = mongoengine.FloatField(required=True)
    comment = mongoengine.StringField(required=True)
    current_price = mongoengine.FloatField(required=True)
    history: list = mongoengine.ListField()
    dict_message_ids: dict = mongoengine.DictField()
    date_creation = mongoengine.DateTimeField(default=datetime.datetime.now)
    isdelete = mongoengine.StringField(default='false')
    is_looked: dict = mongoengine.DictField()
    looked_info: list = mongoengine.ListField()

    def lot_info_to_sheet(self):
        default_list = ['Культура', 'Вага', 'Базис доставки', 'Місяць поставки',
                        'Валюта', 'Стартова ціна', 'Крок', 'Поточна ціна', 'Коментар',
                        'Автор лоту', 'Дата створення']
        l = [self.crop, self.weight, self.delivery_basis, self.delivery_month, self.currency,
             self.start_price, self.step_price, self.current_price, self.comment, self.author, self.date_creation]
        default_list.extend(l)
        return default_list

    def history_to_sheet(self):
        default_list = ['Компанія', 'Телефон', 'Ціна', 'Час', 'Дата']
        for h in self.history:
            user = User.objects(phone_number=h[0]).first()
            full_history = [user.company] + h
            default_list.extend(full_history)
        return default_list

    def lookedinfo_to_sheet(self):
        default_list = ['Компанія', 'Телефон', 'Час', 'Дата']
        for h in self.looked_info:
            user = User.objects(phone_number=h[0]).first()
            full_looked_info = [user.company] + h
            default_list.extend(full_looked_info)

        return default_list

    def get_author(self):
        return self.author

    def add_message_id(self, chat_id, msg_id):
        self.dict_message_ids.update({f'{chat_id}': f'{msg_id}'})

    def add_looked_info(self, phone_number, now_time, now_date):
        self.looked_info.append([str(phone_number), str(now_time), str(now_date)])

    def get_looked_info(self):
        try:
            message = []
            for info in self.looked_info:
                user = User.objects(phone_number=info[0]).first()
                if user.company == None or user.company == "None":
                    pass
                else:
                    info[0] = user.company
                message.append("|".join(info))
            return "\n".join(message)
        except TypeError as e:
            print(e)
            return ""

    def add_looked(self, chat_id, msg_id):
        self.is_looked.update({f'{chat_id}': f'{msg_id}'})

    def get_lot_info(self):
        return self._id, self.crop, self.weight, self.delivery_basis, self.delivery_month, \
               self.start_price, self.step_price, self.comment, self.current_price

    def get_history(self):
        try:
            message = []
            for info in self.history:
                user = User.objects(phone_number=info[0]).first()
                if user.company == None or user.company == "None":
                    pass
                else:
                    info[0] = user.company
                message.append("|".join(info))
            return "\n".join(message)
        except TypeError:
            return ""

    def update_price(self, phone_number, new_price, now_time, now_date):
        if float(new_price) - self.current_price >= self.step_price:
            self.current_price = new_price
            self.history.append([str(phone_number), str(new_price), str(now_time), str(now_date)])
        else:
            raise ValueError

    def create_message(self):
        text = f'№{self.create_name_worksheet()}\n'
        return text

    def get_crop_characteristics(self):
        try:
            settings = Settings.objects(_id='1').first()
            characteristics: dict = settings.crops_characteristics[f"{self.crop}"]
            crop_characterictics = "\n ▪️️".join([": ".join(i) for i in characteristics.items()])
            return crop_characterictics
        except:
            return None

    def create_full_message(self):

        text = f'№{self.create_name_worksheet()}\n' \
               f'🌾Crop: {self.crop}\n'
        if self.get_crop_characteristics():
            text += f'📋Crop characteristics:\n ▪️️{self.get_crop_characteristics()}\n'
        text += f'⚖Weight: {self.weight} t\n' \
                f'🏭Delivery Basis: {self.delivery_basis}\n' \
                f'📆Delivery month: {self.delivery_month}\n' \
                f'💰Starting bid: {self.start_price} {self.currency}/t\n' \
                f'👟Bid step: {self.step_price} {self.currency}\n' \
                f'📝Comments: {self.comment}\n' \
                f'💵Current bid: {self.current_price} {self.currency}'
        return text

    # def create_full_message(self):
    #     text = f'№{self.create_name_worksheet()}\n' \
    #         f'🌾Crop: {self.crop}\n' \
    #         f'⚖Weight: {self.weight} t\n' \
    #         f'🏭Delivery Basis: {self.delivery_basis}\n' \
    #         f'📆Delivery month: {self.delivery_month}\n' \
    #         f'💰Starting bid: {self.start_price} {self.currency}/t\n' \
    #         f'👟Bid step: {self.step_price} {self.currency}\n' \
    #         f'📝Comments: {self.comment}\n' \
    #         f'💵Current bid: {self.current_price} {self.currency}'
    #     return text

    def create_name_worksheet(self):
        date = datetime.datetime.strftime(self.date_creation, '%d.%m.%Y')
        return f'{self.number} / {date}'


class Archive(mongoengine.Document):
    _id = mongoengine.StringField(required=True, primary_key=True)
    number = mongoengine.IntField(required=True)
    author = mongoengine.StringField(required=True)
    crop = mongoengine.StringField(required=True)
    weight = mongoengine.FloatField(required=True)
    delivery_basis = mongoengine.StringField(required=True)
    delivery_month = mongoengine.StringField(required=True)
    currency = mongoengine.StringField(required=True)
    start_price = mongoengine.FloatField(required=True)
    step_price = mongoengine.FloatField(required=True)
    comment = mongoengine.StringField(required=True)
    current_price = mongoengine.FloatField(required=True)
    history: list = mongoengine.ListField()
    dict_message_ids: dict = mongoengine.DictField()
    date_creation = mongoengine.DateTimeField(default=datetime.datetime.utcnow)
    looked_info: list = mongoengine.ListField()

    def lot_info_to_sheet(self):
        default_list = ['Культура', 'Вага', 'Базис доставки', 'Місяць поставки',
                        'Валюта', 'Стартова ціна', 'Крок', 'Поточна ціна', 'Коментар',
                        'Автор лоту', 'Дата створення']
        l = [self.crop, self.weight, self.delivery_basis, self.delivery_month, self.currency,
             self.start_price, self.step_price, self.current_price, self.comment, self.author, self.date_creation]
        default_list.extend(l)
        return default_list

    def history_to_sheet(self):
        default_list = ['Компанія', 'Телефон', 'Ціна', 'Час', 'Дата']
        for h in self.history:
            user = User.objects(phone_number=h[0]).first()
            full_history = [str(user.company)] + h
            default_list.extend(full_history)
        return default_list

    def lookedinfo_to_sheet(self):
        default_list = ['Компанія', 'Телефон', 'Час', 'Дата']
        for h in self.looked_info:
            user = User.objects(phone_number=h[0]).first()
            full_looked_info = [str(user.company)] + h
            default_list.extend(full_looked_info)

        return default_list

    def get_author(self):
        return self.author

    def get_looked_info(self):
        try:
            message = []
            for info in self.looked_info:
                user = User.objects(phone_number=info[0]).first()
                if user.company == None or user.company == "None":
                    pass
                else:
                    info[0] = user.company
                message.append("|".join(info))
            return "\n".join(message)
        except TypeError as e:
            print(e)
            return ""

    def add_message_id(self, chat_id, msg_id):
        self.dict_message_ids.update({f'{chat_id}': f'{msg_id}'})

    def get_lot_info(self):
        return self._id, self.crop, self.weight, self.delivery_basis, self.delivery_month, \
               self.start_price, self.step_price, self.comment, self.current_price

    def get_history(self):
        try:
            message = []
            for info in self.history:
                user = User.objects(phone_number=info[0]).first()
                if user.company == None or user.company == "None":
                    pass
                else:
                    info[0] = user.company
                message.append("|".join(info))
            return "\n".join(message)
        except TypeError:
            return ""

    def update_price(self, phone_number, new_price, now_time, now_date):
        if int(new_price) - self.current_price >= self.step_price:
            self.current_price = new_price
            self.history.append([str(phone_number), str(new_price), str(now_time), str(now_date)])
        else:
            raise ValueError

    def get_crop_characteristics(self):
        try:
            settings = Settings.objects(_id='1').first()
            characteristics: dict = settings.crops_characteristics[f"{self.crop}"]
            crop_characterictics = "\n ▪️️".join([": ".join(i) for i in characteristics.items()])
            return crop_characterictics
        except:
            return None

    def create_message(self):
        text = f'№{self.create_name_worksheet()}\n' \
               f'🌾Crop: {self.crop}\n'
        if self.get_crop_characteristics():
            text += f'📋Crop characteristics:\n ▪️️{self.get_crop_characteristics()}\n'
        text += f'⚖Weight: {self.weight} t\n' \
                f'🏭Delivery Basis: {self.delivery_basis}\n' \
                f'📆Delivery month: {self.delivery_month}\n' \
                f'💰Starting bid: {self.start_price} {self.currency}/t\n' \
                f'👟Bid step: {self.step_price} {self.currency}\n' \
                f'📝Comments: {self.comment}\n' \
                f'💵Current bid: {self.current_price} {self.currency}'
        return text

    def create_name_worksheet(self):
        date = datetime.datetime.strftime(self.date_creation, '%d.%m.%Y')
        return f'{self.number} / {date}'


class Settings(mongoengine.Document):
    _id = mongoengine.StringField(required=True, primary_key=True)
    admin_phone_numbers: list = mongoengine.ListField(required=True)
    crops: list = mongoengine.ListField(required=True)
    basis: list = mongoengine.ListField(required=True)
    block_list: list = mongoengine.ListField()
    white_list: list = mongoengine.ListField(mongoengine.StringField())
    number = mongoengine.IntField()
    crops_characteristics: dict = mongoengine.DictField()

    def give_new_number(self):
        self.number = self.number + 1
        self.save()
        return self.number

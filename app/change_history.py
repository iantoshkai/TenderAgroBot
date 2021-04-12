from Agro_bot import database


lots = database.Archive.objects()

for lot in lots:
    try:
        history = lot.history
        new_history = []
        for h in history:
            phone_number, new_price, now_time, now_date = h.split('|')
            new_history.append([phone_number, new_price, now_time, now_date])
        lot.history = new_history
        lot.save()
    except AttributeError as e:
        print(e)

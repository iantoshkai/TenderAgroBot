from Agro_bot import database


lots = database.Archive.objects()

for lot in lots:
    try:
        looked_info = lot.looked_info
        new_looked_info = []
        for h in looked_info:
            phone_number, now_time, now_date = h.split('|')
            new_looked_info.append([phone_number, now_time, now_date])
        lot.looked_info = new_looked_info
        lot.save()
    except AttributeError as e:
        print(e)


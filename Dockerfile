FROM python:3.7.2-slim

WORKDIR /Agro_bot

COPY requirements.txt /Agro_bot/
RUN pip install --no-cache-dir --upgrade pip 
RUN pip install --no-cache-dir -r /Agro_bot/requirements.txt
COPY . /Agro_bot/

CMD export PYTHONPATH=/Agro_bot/ && python3 ./app/bot.py

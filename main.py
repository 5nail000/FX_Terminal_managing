from fastapi import FastAPI, Depends, HTTPException, Form, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from sqlalchemy import desc
from sqlalchemy.orm import Session
from typing import List

import os
import json
import base64
from io import BytesIO
from datetime import datetime
from read_history import get_history, get_current_account, generate_plot
from cryptography.fernet import Fernet
import matplotlib.pyplot as plt
import pandas as pd
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor()


import logging
# Настройка логирования
# logging.basicConfig(filename='app.log', level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

import models
import schemas
import crud
from models import SessionLocal, engine

# from models import KEY
# FERNET = Fernet(KEY)

import pprint
pp = pprint.PrettyPrinter(indent=4)


class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)
    
# Пользовательская функция для преобразования строк с датой в объекты datetime
def date_decoder(obj):
    date_keys = ['time_in', 'time_out']
    for key in date_keys:
        if key in obj and isinstance(obj[key], str):
            try:
                obj[key] = datetime.fromisoformat(obj[key])
            except ValueError as _err:
                print(_err)
                pass
    return obj


# Инициализация базы данных
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Разрешить запросы с любых источников
    allow_credentials=True,
    allow_methods=["*"],  # Разрешить любые методы
    allow_headers=["*"],  # Разрешить заголовки любого типа
)

# Dependency для получения объекта сессии базы данных
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()



## ---------------------- Accounts ----------------------
## ======================================================

'''
@app.get("/accounts/{account_id}", response_model=schemas.Account)
def read_account(account_id: int, db: Session = Depends(get_db)):
    db_account = crud.get_account(db, account_id=account_id)
    if db_account is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return db_account

@app.post("/accounts/{account_id}/trade_history/", response_model=schemas.TradeHistory)
def create_trade_history_for_account(
    account_id: int, trade_history: schemas.TradeHistoryCreate, db: Session = Depends(get_db)
):
    return crud.create_trade_history(db=db, trade_history=trade_history, account_id=account_id)
'''
@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/account_chart/{account_login}", response_class=HTMLResponse)
def show_account(account_login: int, request: Request, db: Session = Depends(get_db)):
    
    # Получаем текущую дату
    current_date = datetime.now()
    # Находим первый и последний день текущего месяца
    first_day_of_month = current_date.replace(day=1)
    
    # Получаем данные из базы данных для конкретного аккаунта
    account_data = db.query(models.Account).filter(models.Account.login == account_login).first()
    # Фильтруем записи по параметру time_out
    trade_history = (
        db.query(models.TradeHistory)
        .filter(models.TradeHistory.account_id == account_data.id)
        .filter(models.TradeHistory.time_out >= first_day_of_month)
        .order_by(models.TradeHistory.time_out)
        .all()
    )

    if not account_data:
        raise HTTPException(status_code=404, detail="Account not found")

    # Создание будущего результата (image_base64 result) для выполнения в основном потоке
    image_base64 = executor.submit(generate_plot, account_login, trade_history).result()

    titles = [(acc.title, acc.login) for acc in db.query(models.Account).filter(models.Account.active == True).all()]

    balance_in_str = f'$ {round(trade_history[0].balance_end):,.0f}'.replace(',', ' ')
    balance_out_str = f'$ {round(trade_history[-1].balance_end):,.0f}'.replace(',', ' ')
    result_str = f'$ {round(trade_history[-1].balance_end - trade_history[0].balance_end):,.0f}'.replace(',', ' ')
    percent_str = f'{round((trade_history[-1].balance_end - trade_history[0].balance_end)/(trade_history[0].balance_end /100))} %'
    topup_sum = f'$ {round(sum([trade.profit for trade in trade_history if trade.type_in == 2 and trade.profit > 0])):,.0f}'.replace(',', ' ')   # Подсчёт суммы всех пополнений
    withdrawal_sum = f'$ {round(sum([trade.profit for trade in trade_history if trade.type_in == 2 and trade.profit < 0])):,.0f}'.replace(',', ' ')  # Подсчёт суммы всех снятий
    
    account = {
        'login': account_login,
        'title': account_data.title,
        'balance_in': balance_in_str,
        'balance_out': balance_out_str,
        'topup_sum': topup_sum,
        'withdrawal_sum': withdrawal_sum,
        'result': result_str,
        'percent': percent_str,
               }

    return templates.TemplateResponse("account_chart.html", {"request": request, "image_base64": image_base64, "account": account, "titles": titles})


@app.get("/accounts", response_class=HTMLResponse)
async def view_accounts(request: Request, db: Session = Depends(get_db)):
    accounts = db.query(models.Account).all()
    return templates.TemplateResponse("accounts.html", {"request": request, "accounts": accounts})

@app.post("/update_account_status")
async def update_account_status(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    account_id = data['id']
    new_status = data['active']
    try:
        # Ваш код для обновления статуса аккаунта в базе данных
        # Далее следует пример использования SQLAlchemy
        account = db.query(models.Account).filter(models.Account.id == account_id).first()
        account.active = new_status
        db.commit()

        return JSONResponse(content={"message": "Статус аккаунта успешно обновлен"})
    except Exception as e:
        return JSONResponse(content={"message": "Ошибка при обновлении статуса", "error": str(e)}, status_code=500)

@app.post("/update_account")
async def update_account(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    account_id = data['id']
    account_title = data['title']
    account_login = data['login']
    account_password = data['password']
    account_server = data['server']
    account_description = data['description']
    account_active = data['active']
    try:
        # Обновление аккаунта в базе данных
        await crud.update_account_in_db(db, account_id, account_title, account_login, account_password, account_server, account_description, account_active)
        return JSONResponse(content={"message": "Аккаунт успешно обновлен", 'title': 'Данные аккаунта', 'text': 'успешно обновленны'})
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Ошибка при обновлении аккаунта: {str(e)}")

@app.post("/delete_account")
async def delete_account(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    account_id = data['id']
    try:
        # Удаление аккаунта из базы данных
        await crud.delete_account_from_db(db, account_id)
        return JSONResponse(content={"message": "Аккаунт успешно удален"})
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail=f"Ошибка при удалении аккаунта: {str(e)}")

@app.post("/create_new_account")
async def create_new_account(request: Request, db: Session = Depends(get_db)):    
    data = await request.json()
    account_data = {
        'title': data['title'],
        'login': data['login'],
        'password': data['password'],
        'server': data['server'],
        'description': data['description'],
        'active': data['active'],
        'is_online': False
    }
    await crud.create_account(db, account=schemas.AccountCreate(**account_data))
    return JSONResponse(content={"message": "Новый аккаунт добавлен", 'title': 'Новый аккаунт', 'text': 'успешно добавлен'})


## --------------------- GET HISTORY ---------------------
## =======================================================

@app.get("/get-history", response_class=HTMLResponse)
async def upload_data(request: Request, db: Session = Depends(get_db)):
    accounts = db.query(models.Account).all()
    return templates.TemplateResponse("get_history.html", {"request": request, "accounts": accounts})

@app.post("/show-history", response_class=HTMLResponse)
async def post_history(request: Request, history_option: str = Form(...), selected_account: str = Form(None), db: Session = Depends(get_db)):
    account = None
    account_data = get_current_account()
    if history_option == "current":
        # Используйте данные текущего аккаунта
        account = None
    else:
        selected_account = await crud.get_account_by_login(db, selected_account)
        account = {
            'login': selected_account.login,
            'password': selected_account.password,
            'server': selected_account.server
        }

    trade_history = get_history(account)
    trade_history_json = json.dumps(trade_history, cls=DateTimeEncoder)
    trade_history_data = json.loads(trade_history_json)
    return templates.TemplateResponse("show_history.html", {
                                          'request': request,
                                          'trade_history': trade_history_data,
                                          'login': account_data['login'],
                                          'server': account_data['server']
                                          })

@app.post("/submit_history_data")
async def submit_history_data(request: Request, db: Session = Depends(get_db)):
    # logging.info(await request.json())
    data = await request.json()

    login = data['login']
    server = data['server']
    trade_history_json = data['trade_history']

    # Заменяем одинарные кавычки на двойные
    trade_history_json_corrected = trade_history_json.replace("'", '"')
    # Преобразование строки в список словарей
    trade_history_data = json.loads(trade_history_json_corrected, object_hook=date_decoder)

    # Получаем аккаунт или создаем новый
    account = await crud.get_account_by_login(db, login=login)

    if not account:
        # Если аккаунта нет, создаем его
        account_data = {
            'login': login,
            'password': 'unset',
            'server': server,
            'title': 'New Account',
            'description': 'Automatically created account',
            'active': False,
            'is_online': False
        }
        account = await crud.create_account(db, account=schemas.AccountCreate(**account_data))

    # Ищем в базе последнюю дату закрытия сделки для аккаунта
    last_trade = db.query(models.TradeHistory)\
                   .filter(models.TradeHistory.account_id == account.id)\
                   .order_by(desc(models.TradeHistory.time_out))\
                   .first()
    
    # Если сделок еще нет, устанавливаем дату на очень старую
    last_time_out = last_trade.time_out if last_trade else datetime(1980, 1, 1)
    
    # Фильтруем новые сделки которые закрыты после последней даты закрытия
    new_trades = [trade for trade in trade_history_data if trade['time_out'] > last_time_out]
    
    if not new_trades:
        # Если новых сделок нет, возвращаем сообщение
        return JSONResponse(content={"title": "Новых данных", "message": "для обновления нет"})
    
    # Добавляем новые сделки в базу данных
    for trade_data in new_trades:
        trade_data['account_id'] = account.id  # Устанавливаем связь с аккаунтом
        trade_data.setdefault('ticket_in', 0)
        trade_data.setdefault('order_in', 0)
        trade_data.setdefault('type_in', trade_data['type_out'])
        trade_data.setdefault('entry_in', 0)
        trade_data.setdefault('reason_in', 0)
        trade_data.setdefault('volume_in', 0)
        trade_data.setdefault('price_in', 0)
        trade_data.setdefault('comment_in', trade_data['comment_out'])
        trade_data.setdefault('external_id_in', "")
        trade_data.setdefault('time_in', trade_data['time_out'])
        trade_data.setdefault('time_duration', 0)
        trade_data.setdefault('margin', 0)
        trade_data.setdefault('margin_load', 0)
        trade_data.setdefault('draw_down', 0)
        trade_data.setdefault('draw_down_level', 0)
        trade_data.setdefault('draw_down_max_high', 0)
        trade_data.setdefault('draw_down_min_low', 0)
        await crud.create_trade_history(db, trade_history=schemas.TradeHistoryCreate(**trade_data))
    return JSONResponse(content={"title": "Новые данные", "message": "успешно добавлены"})


from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy.orm import Session
import models, schemas

'''
def get_account(db: Session, account_id: int):
    return db.query(models.Account).filter(models.Account.id == account_id).first()

def get_accounts(db: Session, skip: int = 0, limit: int = 10):
    return db.query(models.Account).offset(skip).limit(limit).all()

def get_trade_history(db: Session, account_id: int, skip: int = 0, limit: int = 10):
    return db.query(models.TradeHistory).filter(models.TradeHistory.account_id == account_id).offset(skip).limit(limit).all()
'''

async def create_account(db: Session, account: schemas.AccountCreate):
    db_account = models.Account(**account.model_dump())
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account

async def get_account_by_login(db: Session, login: int):
    return db.query(models.Account).filter(models.Account.login == login).first()

async def update_account_in_db(db: Session, account_id, title, login, password, server, description, active):
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise JSONResponse(content={"message": "Account not found in base"})

    # Обновление полей аккаунта
    account.title = title
    account.login = login
    if password != "password_placeholder":  # Проверьте, был ли изменен пароль
        account.password = password
    account.server = server
    account.description = description
    account.active = active

    db.commit()
    db.refresh(account)

async def delete_account_from_db(db: Session, account_id):
    account = db.query(models.Account).filter(models.Account.id == account_id).first()
    if not account:
        raise JSONResponse(content={"message": "Account not found in base"})
    
    # Удаление всех записей в TradeHistory, связанных с аккаунтом
    db.query(models.TradeHistory).filter(models.TradeHistory.account_id == account_id).delete(synchronize_session=False)
    
    db.delete(account)
    db.commit()


async def create_trade_history(db: Session, trade_history: schemas.TradeHistoryCreate):
    db_trade_history = models.TradeHistory(**trade_history.model_dump())
    db.add(db_trade_history)
    db.commit()
    db.refresh(db_trade_history)
    return db_trade_history
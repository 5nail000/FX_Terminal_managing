from sqlalchemy.orm import sessionmaker
from models import engine
from models import Account, TradeHistory

def delete_all_accounts():
    # Создайте сессию
    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        # Запрос на выбор всех объектов Account
        accounts = session.query(Account).all()

        # Удаление всех объектов
        for account in accounts:
            session.delete(account)
        
        # Зафиксируйте изменения
        session.commit()
        print("All accounts have been deleted.")
    except Exception as e:
        print(f"An error occurred: {e}")
        session.rollback()
    finally:
        # Закрытие сессии
        session.close()

if __name__ == "__main__":
    # delete_all_accounts()
    Session = sessionmaker(bind=engine)
    session = Session()
    trade_history = (
    session.query(TradeHistory)
    .filter(TradeHistory.id == 603)
    .first()
)

if trade_history:
    session.delete(trade_history)
    session.commit()

from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from cryptography.fernet import Fernet

DATABASE_URL = "sqlite:///./test.db"
KEY = b'5-PJKtIKggNY5g_EQq2kAhlz53E2qwqOOAHWuKv9Pys='
# key = base64.urlsafe_b64encode(os.urandom(32))

Base = declarative_base()
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    login = Column(Integer, unique=True, index=True)
    # password = Column(String)
    _password = Column('password', String, nullable=False)
    server = Column(String, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    is_online = Column(Boolean, default=False)
    is_draw = Column(Boolean, default=True)
    trade_history = relationship("TradeHistory", back_populates="account")

    @property
    def password(self):
        # Расшифровать пароль перед его возвратом
        fernet = Fernet(KEY)
        decrypted_password = fernet.decrypt(self._password.encode())
        return decrypted_password.decode()

    @password.setter
    def password(self, raw_password):
        # Зашифровать пароль перед сохранением
        fernet = Fernet(KEY)
        encrypted_password = fernet.encrypt(raw_password.encode())
        self._password = encrypted_password.decode()


class TradeHistory(Base):
    __tablename__ = "trade_history"
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey('accounts.id'))
    position_id = Column(Integer)
    magic = Column(Integer)
    symbol = Column(String)
    balance_start = Column(Float)
    balance_end = Column(Float)
    profit = Column(Float)
    profit_percents = Column(Float)
    ticket_in = Column(Integer, nullable=True)
    ticket_out = Column(Integer, nullable=True)
    order_in = Column(Integer, nullable=True)
    order_out = Column(Integer, nullable=True)
    type_in = Column(Integer, nullable=True)
    type_out = Column(Integer, nullable=True)
    entry_in = Column(Integer, nullable=True)
    entry_out = Column(Integer, nullable=True)
    reason_in = Column(Integer, nullable=True)
    reason_out = Column(Integer, nullable=True)
    volume_in = Column(Float, nullable=True)
    volume_out = Column(Float, nullable=True)
    price_in = Column(Float, nullable=True)
    price_out = Column(Float, nullable=True)
    comment_in = Column(String, nullable=True)
    comment_out = Column(String, nullable=True)
    external_id_in = Column(String, nullable=True)
    external_id_out = Column(String, nullable=True)
    time_in = Column(DateTime, nullable=True)
    time_out = Column(DateTime, nullable=True)
    time_duration = Column(Float, nullable=True)
    margin = Column(Float, nullable=True)
    margin_load = Column(Float, nullable=True)
    draw_down = Column(Float, nullable=True)
    draw_down_level = Column(Float, nullable=True)
    draw_down_max_high = Column(Float, nullable=True)
    draw_down_min_low = Column(Float, nullable=True)
    account = relationship("Account", back_populates="trade_history")

# Создаем таблицы в базе данных
Base.metadata.create_all(bind=engine)

import MetaTrader5 as mt5
from io import BytesIO
import base64
from datetime import datetime, timedelta
import psutil
import pprint

import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
matplotlib.use('Agg')  # Используем бэкэнд 'Agg' для предотвращения использования tkinter

LOCAL_TIMESHIFT = 3
pp = pprint.PrettyPrinter(indent=4)


def check_mt5_process():
    mt5_processes = [proc for proc in psutil.process_iter() if 'terminal64.exe' in proc.name()]
    return mt5_processes


def get_current_account():

    mt5_processes = check_mt5_process()
    all_terminal_exes = False
    if mt5_processes:
        all_terminal_exes = [process.exe() for process in mt5_processes]

    if all_terminal_exes and not mt5.initialize(all_terminal_exes[0]):
        print("Failed to initialize MetaTrader5! ", all_terminal_exes[0])
        mt5.initialize()

    if not all_terminal_exes:
        mt5.initialize()

    # Получение информации о текущем подключенном счёте
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to get account info, error code =", mt5.last_error())
        mt5.shutdown()
        quit()
    
    data = {
        'login': account_info.login,
        'server': account_info.server,
        }

    return data


def get_history(account=None):

    mt5_processes = check_mt5_process()
    all_terminal_exes = False
    if mt5_processes:
        all_terminal_exes = [process.exe() for process in mt5_processes]


    if all_terminal_exes and not mt5.initialize(all_terminal_exes[0]):
        print("Failed to initialize MetaTrader5! ", all_terminal_exes[0])
        mt5.initialize()

    if not all_terminal_exes:
        mt5.initialize()

    if account:
        authorized = mt5.login(account['login'], account['password'], account['server'])
        if not authorized:
            print("Failed to connect to account, error code =", mt5.last_error())
            mt5.shutdown()
            quit()

    # Получение информации о текущем подключенном счёте
    account_info = mt5.account_info()
    if account_info is None:
        print("Failed to get account info, error code =", mt5.last_error())
        mt5.shutdown()
        quit()
    
    # print(f"Connected to account: {account_info.login}")

    # Задать период для получения истории торгов
    from_date = datetime(2000, 1, 1)  # начальная дата
    to_date = datetime.now() + timedelta(hours=LOCAL_TIMESHIFT)  # конечная дата (текущее время)

    # Получение истории торговых операций за указанный период
    deals = mt5.history_deals_get(from_date, to_date)

    trade_history = construct_trade_history(mt5, deals)
    
    # Завершение работы с MetaTrader 5
    mt5.shutdown()

    return trade_history


def construct_trade_history(mt5, deals):
    account_leverage = mt5.account_info().leverage
    positions = []

    if deals is None:
        print("No deals found, error code =", mt5.last_error())
    else:
        # Получаем текущий баланс, который является балансом на конец периода
        balance = mt5.account_info().balance + 0.01
        # print(f"Total deals found: {len(deals)}")
        # print(f"Current balance (at the end of history period): {balance:.2f}")
        # print("-" * 30)

        # Проходим через сделки в обратном порядке
        for deal in reversed(deals):
            # Игнорируем сделки открытия позиций
            position = {}
            if deal.entry != 0 or deal.type == 2:
                # Баланс до закрытия позиции
                exit_balance = balance
                # Обновляем баланс после закрытия позиции
                profit = deal.profit + deal.commission*2 + deal.swap + deal.fee
                balance -= profit  # вычитаем прибыль, чтобы получить баланс до сделки
                entry_balance = balance

                profit_percentage = (profit / entry_balance) * 100 if entry_balance != 0 else 0
                
                position['profit_percents'] = profit_percentage if deal.type != 2 else 0

                position.update({'position_id': deal.position_id})
                position.update({'magic': deal.magic})
                position.update({'symbol': deal.symbol})
                position.update({'balance_start': entry_balance})
                position.update({'balance_end': exit_balance})
                position.update({'profit': profit})

                position.update({'ticket_out': deal.ticket})
                position.update({'order_out': deal.order})
                position.update({'type_out': deal.type})
                position.update({'entry_out': deal.entry})
                position.update({'reason_out': deal.reason})
                position.update({'volume_out': deal.volume})
                position.update({'price_out': deal.price})
                position.update({'comment_out': deal.comment})
                position.update({'external_id_out': deal.external_id})
                position.update({"time_out": datetime.fromtimestamp(deal.time)})

                for start_deal in reversed(deals):
                    if deal.position_id == start_deal.position_id and start_deal.entry == 0 and deal.type != 2:
                        position.update({'ticket_in': start_deal.ticket})
                        position.update({'order_in': start_deal.order})
                        position.update({'type_in': start_deal.type})
                        position.update({'entry_in': start_deal.entry})
                        position.update({'reason_in': start_deal.reason})
                        position.update({'volume_in': start_deal.volume})
                        position.update({'price_in': start_deal.price})
                        position.update({'comment_in': start_deal.comment})
                        position.update({'external_id_in': start_deal.external_id})
                        position.update({"time_in": datetime.fromtimestamp(start_deal.time)})
                        position.update({"time_duration": (position['time_out'] - position['time_in']).total_seconds()})

                ## Calculate margin load
                # Получение информации о символе
                if deal.type != 2:
                    symbol_info = mt5.symbol_info(position['symbol'])
                    currency_base = symbol_info.currency_base
                    base_symbol = deal.symbol[:3] + "USD"
                    contract_size = 100000
                    if symbol_info is None:
                        print(f"Failed to get symbol info for {position['symbol']}, error code =", mt5.last_error())
                    else:
                        # Получение размера контракта
                        contract_size = symbol_info.trade_contract_size

                    if deal.symbol.startswith("USD"):
                        margin = contract_size * position['volume_in'] * (1/account_leverage)
                    else:
                        margin = position['price_in'] * contract_size * position['volume_in'] * (1/account_leverage)
                    
                    if "USD" not in deal.symbol:
                        if currency_base == "USD":
                            margin = position['price_in'] * contract_size * position['volume_in'] * (1/account_leverage)
                        else:
                            margin = contract_size * position['volume_in'] * (1/account_leverage) * mt5.symbol_info(base_symbol).ask
                    
                    margin_load = (margin / entry_balance) * 100

                    position.update({'margin': margin})
                    position.update({'margin_load': margin_load})

                    ## Calculate DrawDown
                    timeframe = mt5.TIMEFRAME_M1
                    # Получение данных о барах за заданный период
                    rates = mt5.copy_rates_range(position['symbol'], timeframe, position['time_in'], position['time_out'])
                    if rates is None or len(rates) < 1:
                        print(f"Failed to get rates for {position['symbol']}, error code =", mt5.last_error())
                        draw_down = 0
                    else:
                        highest_high = max(rates, key=lambda x: x['high'])['high']
                        lowest_low = min(rates, key=lambda x: x['low'])['low']
                        if position['type_in'] == 1: # If Sell in
                            if deal.symbol.startswith("USD"):
                                draw_down = (highest_high - position['price_in']) * contract_size * position['volume_in'] / highest_high
                            else:
                                draw_down = (highest_high - position['price_in']) * contract_size * position['volume_in']
                        if position['type_in'] == 0: # If Buy in
                            if deal.symbol.startswith("USD"):
                                draw_down = (position['price_in'] - lowest_low) * contract_size * position['volume_in'] / lowest_low
                            else:
                                draw_down = (position['price_in'] - lowest_low) * contract_size * position['volume_in']
                        
                        draw_down_level = (draw_down / entry_balance) * 100
                        position.update({'draw_down': draw_down})
                        position.update({'draw_down_level': draw_down_level})
                        
                        position.update({'draw_down_max_high': highest_high})
                        position.update({'draw_down_min_low': lowest_low})

                positions.append(position)

    return positions


def generate_plot(account_id, trade_history):
    # Преобразуем данные в DataFrame
    data = {
        'date': [acc.time_out for acc in trade_history],  # Убедитесь, что используете корректное поле даты
        'balance': [round(acc.balance_end) for acc in trade_history],
        'drawdown': [acc.balance_end - acc.draw_down for acc in trade_history],
        'max_drawdown': [acc.draw_down_level + acc.margin_load for acc in trade_history],
    }

    # Отключение интерактивного режима Matplotlib
    plt.ioff()
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    
    # Получаем начальную и конечную даты из DataFrame
    start_date = df['date'].min().normalize()
    end_date = df['date'].max().normalize()
    # Формируем список всех понедельников между начальной и конечной датами
    mondays = pd.date_range(start=start_date, end=end_date, freq='W-MON').date

    # Минимальное значение для масштабирования баланса
    min_balance = df['drawdown'].min()
    balance_offset = min_balance * 0.95  # 5% ниже минимального значения

    # Построение графика
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10), gridspec_kw={'height_ratios': [3, 1]}, sharex=True)

    # Линия баланса с масштабированием от минимального значения
    ax1.plot(df['date'], df['balance'], label='Balance, $', color='blue')
    ax1.plot(df['date'], df['drawdown'], label='Drawdown', color='green', alpha=0.5)
    ax1.set_ylabel('Balance', color='blue')
    ax1.set_ylim([balance_offset, df['balance'].max() * 1.15])  # Масштабирование от минимального значения + немного запаса
    ax1.tick_params(axis='y', labelcolor='blue')
    ax1.grid(True)
    ax1.legend(loc='upper left')
    # ax1.set_title('Balance Over Time')

    # Добавление вертикальных линий на каждый понедельник
    for monday in mondays:
        saturday = monday - pd.DateOffset(days=2)
        # ax1.axvline(monday, color='purple', linestyle='--', label=None, alpha=0.65)
        ax1.axvspan(saturday, monday, color='red', alpha=0.1875)

    draw_plots(df, ax1)    

    # Линии max_drawdown и margin_load на отдельной оси
    ax2.plot(df['date'], df['max_drawdown'], label='Deposit Load, %', color='red', alpha=0.4)
    ax2.set_ylabel('Deposit Load', color='black')
    ax2.set_ylim([0, df['max_drawdown'].max() * 1.5])  # Масштабирование от 0 до макс
    ax2.tick_params(axis='y', labelcolor='black')
    ax2.legend(loc='upper left')
    ax2.grid(True)

    # Общий заголовок для всего графика
    # fig.suptitle(f'Account Balance Chart for Account ID: {account_id}')


    # Сохранение графика в формате base64
    buffer = BytesIO()
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])  # Для более плотного расположения элементов и оставления места для общего заголовка
    plt.savefig(buffer, format='png')
    buffer.seek(0)
    image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
    plt.close()  # Закрываем, чтобы освободить память

    html_content = f'''
    <html>
    <head><title>Account Balance Chart</title></head>
    <body>
        <h1>Account Balance Chart for Account ID: {account_id}</h1>
        <img src="data:image/png;base64,{image_base64}" />
    </body>
    </html>
    '''

    plt.ion()
    return image_base64


def draw_plots(df, ax1):
    # Получение первого значения
    first_date = df['date'].iloc[0]
    first_balance = df['balance'].iloc[0]

    # Добавление аннотации для первого значения
    formatted_number = f'{first_balance:,.0f}'.replace(',', ' ')
    ax1.annotate(f"${formatted_number}",
                 xy=(first_date, first_balance), 
                 xytext=(first_date, first_balance * 1.06),
                 horizontalalignment='center',
                 color='darkblue',
                 fontweight='bold',
                 verticalalignment='top')

    # Добавление выделенной точки на первое значение
    ax1.scatter([first_date], [first_balance], color='darkblue')
    ax1.plot(first_date, first_balance, 'ko', markersize=10, fillstyle='none')

    # Получение последнего значения
    first_date = df['date'].iloc[-1]
    first_balance = df['balance'].iloc[-1]

    # Добавление аннотации для первого значения
    formatted_number = f'{first_balance:,.0f}'.replace(',', ' ')
    ax1.annotate(f"${formatted_number}",
                 xy=(first_date, first_balance), 
                 xytext=(first_date, first_balance * 0.94),
                 horizontalalignment='center',
                 color='darkblue',
                 fontweight='bold',
                 verticalalignment='top')
    
    # Добавление выделенной точки на первое значение
    ax1.scatter([first_date], [first_balance], color='darkblue')
    ax1.plot(first_date, first_balance, 'ko', markersize=10, fillstyle='none')


if __name__ == "__main__":
    account = {
        'login': 67120008,
        'password': 'tntTNT000!',
        'server': 'RoboForex-ECN',
    }
    # trade_history = get_history(account)
    # pp.pprint(trade_history)
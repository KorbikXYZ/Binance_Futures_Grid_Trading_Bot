import time
import sys
from random import randrange
from datetime import datetime
import requests

SPINNER = ['|', '/', '-', '\\']


def get_liquidation_price_from_api(client, symbol):
    """
    get current liquidation price for symbol from binance futures account.
    works only if position is open.
    """
    try:
        positions = client.futures_account()['positions']   # get all account positions
        for pos in positions:
            if pos['symbol'] == symbol:         # find target symbol position
                return f"[BOT] aktualna likvidacna cena je: {float(pos['liquidationPrice'])}"
        return None  
    except:
        return ("[BOT] nie je otvorena ziadna pozicia, neda sa nacitat likvidacna cena..")


def calculate_liquidation_price(entry_price, total_qty, leverage, direction):
    """
    rough estimation for liquidation price based on entry, leverage and side (long/short).
    do not use for actual trading, just crude formula.
    real liquidation math works differently.
    """
    mmr = 0.004  # maintenance margin rate ~0.4%

    if direction.upper() == "LONG":
        liq_price = entry_price * (1 - (1 / leverage) + mmr)    # long calculation
    else:
        liq_price = entry_price * (1 + (1 / leverage) - mmr)    # short calculation

    return liq_price

def calculate_net_naklady_vsetky_urovne(levels, leverage, direction):

    if direction.upper() == "LONG":
        
        margin = sum(lvl["margin"] for lvl in levels)
        
        negative_margin = 0.0


        for i in range(len(levels)):
            # subtracting everything from last level...
            negative_margin += (float(levels[i]["price"])-float(levels[-1]["price"]))*float(levels[i]["qty"])
    
    return round ((margin+negative_margin),2)

def max_percentualna_zmena(levels):
    return round(abs((float(levels[0]["price"])-float(levels[-1]["price"]))/float(levels[0]["price"]/100)),2)
    

def place_limit_order(client, symbol, side, quantity, price):
    """
    place limit order on futures with symbol, side and price.
    """
    try:
        order = client.futures_create_order(        # create limit order via binance API
            side=side,
            type="LIMIT",
            timeInForce="GTC",                      # good till cancelled
            quantity=str(quantity),
            price=str(price)
        )
        return order["orderId"]                     # return order id
    except Exception as e:
        print(f"[CHYBA {datetime.now().strftime('%x')} {datetime.now().strftime('%X')}] Objednávka zlyhala: {e}")
        return None
    
   
def get_position_information(client,symbol):
    """
    get details for futures position on symbol.
    prints currently configured leverage.
    """
    try:
        # [{'symbol': 'BTCUSDC', 'positionSide': 'BOTH', 'positionAmt': '0.000', 'entryPrice': '0.0', 'breakEvenPrice': '0.0', 'markPrice': '108598.00000000', 'unRealizedProfit': '0.00000000', 'liquidationPrice': '0', 'isolatedMargin': '0', 'notional': '0', 'marginAsset': 'BNFCR', 'isolatedWallet': '0', 'initialMargin': '13.63636500', 'maintMargin': '0', 'positionInitialMargin': '0', 'openOrderInitialMargin': '13.63636500', 'adl': 0, 'bidNotional': '100', 'askNotional': '150', 'updateTime': 0}]
        position_info = client.futures_position_information(symbol=symbol)
        print (position_info)
        print ("paka", int(position_info[0]["leverage"]))
        return int(position_info[0]["leverage"])                # return current leverage
    except Exception as e:
        print(f"[CHYBA] Nepodarilo sa zistiť aktuálnu páku: {e}")
        return None


def get_current_leverage(client,symbol):
    """
    get active leverage for symbol.
    """
    try:
        account_info = client.futures_account()
        # print(account_info)
        for asset in account_info["positions"]:
            if asset["symbol"] == symbol:
                print (asset)
                print (asset["leverage"])
                return int(asset["leverage"])           # return active leverage
        print("[CHYBA] Symbol nebol nájdený v pozíciách.")
        return None
    except Exception as e:
        print(f"[CHYBA] Nepodarilo sa získať leverage: {e}")
        return None


def set_leverage(config, client,symbol):
    """
    set leverage for symbol based on config.
    """
    leverage = config.get("leverage")       # fetch required leverage from config
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage) # set leverage on binance
    except Exception as e:
        print(f"[CHYBA] Nastavenie páky zlyhalo: {e}")


def get_futures_orderbook(client,symbol):
    """
    get orderbook limit 5 depth.
    """
    return client.futures_order_book(symbol=symbol, limit=5)


def get_current_price(client, symbol):
    """
    get current spot price for symbol.
    """
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker["price"])   


def get_current_future_price(client, symbol):
    """
    mid price calculated from best bid/ask in futures orderbook.
    """
    book = get_futures_orderbook(client,symbol)
    return (float(book["bids"][0][0])+float(book["asks"][0][0]))/2   


def get_futures_balance(client, asset, bot_print = True):
    """
    get balance for given asset on futures account.
    """
    try:
        balances = client.futures_account_balance()
        if bot_print:
            print(balances)
        for b in balances:
            if b['asset'] == asset:
                return float(b['balance'])      # return balance value
        return 0.0
    except Exception as e:
        print(f"[BINANCE ERROR] Nepodarilo sa získať futures zostatok: {e}")
        return 0.0


def pauznut_cyklus(trading_paused):
    """
    if paused, delays 1s showing spinner and returns true.
    used in main loop.
    """
    if trading_paused:
        print(f"\r[BOT] Pauza... {SPINNER[randrange(5) % len(SPINNER)]}", end="", flush=True)
        time.sleep(1)

        return True
    return False




def get_open_orders(client,symbol):
    """
    get and print all open orders for symbol.
    """
    orders = client.futures_get_open_orders()
    print (orders)
    tmp_str=""
    for order in orders:
        if order["symbol"] == symbol:
            tmp_str += (f"Order ID: {order['orderId']}, Side: {order['side']}, Price: {order['price']}, Qty: {order['origQty']}\n")
    return tmp_str

def return_date_time_formated(timestamp):
    """
    convert timestamp ms to formatted string.
    """
    return f"{datetime.fromtimestamp(float(timestamp) / 1e3).strftime('%x')} {datetime.fromtimestamp(float(timestamp) / 1e3).strftime('%X')}"

def send_notification(CHAT_ID, TOKEN, message: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {
        "chat_id": CHAT_ID,
        "text": message
    }
    response = requests.post(url, data=data)
    return response.json()
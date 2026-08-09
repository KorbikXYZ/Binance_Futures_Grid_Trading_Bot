import os
import sys
import json
import threading
import time
import platform
from client_handler import *
from utils import *
import math
from random import randrange
from datetime import datetime



STATE_DIR = "state"  # state directory path
CONFIG_DIR = "config"  # config directory path
TIMEOUT_VYPLNENIE_ORDERU = 60  # order fill timeout in seconds



class GridBot:
    def __init__(self, symbol):
        """
        init gridbot object, set core vars and load config.
        """
        self.symbol = symbol  # set traded symbol
        self.config = {}     # init config
        self.trading_active = False     # flag for active trading
        self.trading_paused = False     # flag for paused trading
        self.trading_stop_at_end = False   # flag to stop trading after cycle
        self.num_of_cycles = 10**6    # set high cycle limit
        self.client = get_binance_client()  # get binance api client
        self.active_trades = {"config":{},"trades":[], "cycle":1}   # init trade records
        self.state_file = os.path.join(STATE_DIR, f"{self.symbol}_active.json")    # state file path
        self.TG_ID, self.TG_Token = get_ID_Token()
        
        # load config on bot init
        self.load_config()
        
    def load_config(self):
        """
        load config from file based on symbol.
        set cycle count from config if available.
        """
        config_path = os.path.join(CONFIG_DIR, f"{self.symbol}.json")       # path to config file
        with open(config_path, "r") as f:
            self.config = json.load(f)          # load config json
            # print (self.config)
            try: 
                self.num_of_cycles = self.config.get("num_of_cycles")     # read cycles from config
            except:
                print ("Nepodarilo sa nacitat max pocet cyklov... pokracujem s 10**6")
            
            
    def save_active_state(self, dopl_info = ""):
        """
        save active state to json file.
        """
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.active_trades, f, ensure_ascii=False, indent=4)   # dump state to file
            print(f"Úspešne uložené do súboru: {self.state_file}")
        except Exception as e:
            print(f"Chyba pri ukladaní: {e}")
            
            


    def main_get_active_state(self):
        """
        return active trading state.
        """
        return self.active_trades

    def archive_cycle(self):
        """
        archive active cycle, save to file, remove active state and prepare new cycle.
        """
        now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")       # get utc timestamp
        archive_file = os.path.join(STATE_DIR, f"cyklus_{now}.json") # archive path
        with open(archive_file, "w") as f:
            json.dump(self.active_trades, f, indent=2)  # dump state to archive
        if os.path.exists(self.state_file):
            os.remove(self.state_file)          # remove state file
            self.active_trades["trades"] = []         # clear trades
            self.active_trades["cycle"] = self.active_trades["cycle"]+1    # increment cycle count                      
        return archive_file   
            
    # return active price from exchange
    def main_get_current_price(self):
        return get_current_price(self.client, self.symbol)
    
    # return futures balance for given stablecoin (usdc)
    def main_get_futures_balance(self):
        return get_futures_balance(self.client, "USDC")
    
    # run buy/sell level simulation if levels are needed before launching
    def main_simulate_levels(self):
        return self.simulate_levels()

    # set leverage specified in config file
    def main_set_leverage(self):
        set_leverage(self.config, self.client, self.symbol)
        return self.config.get("leverage")
    
    # get active leverage from exchange
    def main_get_leverage(self):
        return get_current_leverage(self.client, self.symbol)
    
    # test method to fetch position info    
    def main_test(self):
        return get_position_information(self.client,self.symbol)
    
    # return list of open orders    
    def main_get_open_orders(self):
        return get_open_orders(self.client,self.symbol)
    
    # return position liquidation price
    def main_get_likvidation_price (self):
        return get_liquidation_price_from_api(self.client,self.symbol)
    

    def simulate_levels(self):
        """
        calculate simulated order levels for current config.
        uses market price and sets levels based on config gap.
        returns summary of margin, fees and liq price.
        
        just raw calculations, does not execute anything / levels wont be used for actual orders, just terminal check
        """
        
        # load config
        direction = self.config.get("direction", "LONG")        # get trading side
        gap = self.config.get("step_down", 1) / 100             # get percentage gap between levels
        order_count = self.config.get("order_count")            # get total orders count
        leverage = self.config.get("leverage")                  # get leverage
        step_amount = self.config.get("order_amount_stable")    # get step amount in stable
        min_qty = float(self.config.get("min_qty", 0.001))      # get min qty
        fee_rate = 0.001                                        # fixed fee rate 0.1% but inaccurate... needs fix
    
        base_price = get_current_future_price(self.client, self.symbol)     # get current futures price
    
        levels = []             # list for simulated levels
        total_margin = 0.0      # init total margin
        total_fee = 0.0         # init total fees (flawed math)
        total_qty = 0.0         # init total qty
        
        
        price = base_price
        for i in range(order_count):
            # calculate price for level based on direction
            if direction == "LONG":
                if i == 0:
                    price = round(price , 1)
                else:
                    price = round(price * (1 - gap), 1)
            else:
                if i == 0:
                    price = round(price , 1)
                else:
                    price = round(price * (1 + gap), 1)
    
            qty = round(step_amount / price, 6)         # calculate quantity for step amount
            qty = self.vypocitaj_quantity(price)        # adjust qty based on min size, config or notional (qty * price must be >= 100)
            notional = qty * price                      # calculate order value
            margin = notional / leverage                # calculate required margin
            fee = notional * fee_rate                   # calculate fee
    
            # add level to simulated list
            levels.append({
                "price": price,
                "qty": qty,
                "notional": round(notional, 2), 
                "margin": round(margin, 2),
                "fee": round(fee, 4)
            })
            
            # accumulate totals
            total_margin += margin
            total_fee += fee
            total_qty += qty
    
        # calculate weighted entry price by quantity
        entry_price = sum(lvl["price"] * lvl["qty"] for lvl in levels) / total_qty
        
        # estimate liq price from entry and leverage (inaccurate, real formula is different)
        liq_price = calculate_liquidation_price(entry_price, total_qty, leverage, direction)
        
        # calculate total buy cost for all levels
        naklady_nakup = calculate_net_naklady_vsetky_urovne(levels,leverage,direction)
        
        # get stablecoin balance on futures account
        stable_balance = get_futures_balance(self.client, self.symbol[3:], bot_print=False)
        
        # dict containing levels and metadata
        return {
            "levels": levels,
            "needed_margin": round(total_margin, 2),
            "estimated_fees": round(total_fee, 2),
            "liq_price": round(liq_price, 2),
            "available_stable": stable_balance,
            "leverage": leverage,
            "direction": direction,
            "entry_price": entry_price,
            "price_now": base_price,
            "nakup_all": naklady_nakup,
            "max_percent_zmena": max_percentualna_zmena(levels)
        }
    
    
    # return current orderbook bids/asks
    def main_get_order_book(self):
        return get_futures_orderbook(self.client,self.symbol)

    
    def vypocitaj_quantity(self,price):
        min_qty = float(self.config.get("min_qty", 0.001))
        step_amount = self.config.get("order_amount_stable")
        qty = round(step_amount / price, 3)
        qty_notional = math.ceil((100 / price)*1000)
        return max(qty, min_qty,qty_notional/1000)
    
    
    def vytvor_limit_buy_order(self, _id, side, price):
        """
        create buy limit order, append to active trades and save state.
        buy price calculated lower based on step_up percentage in config...
        """
        price = round(price * (1 - self.config.get("step_up") / 100), 1)    # calculate buy price
        qtyty = self.vypocitaj_quantity(price)                              # calculate qty for price
        
        print (price, qtyty)    # debug log for price/qty
        
        buy_order_id = place_limit_order(self.client, self.symbol, side, qtyty, price)      # place limit buy order
        if not buy_order_id:
            return   # return if order placement failed
        
        
        # {'config': {}, 'trades': [{'id': 1, 'buy': [19055626740, 98800.0, 0.002, 1751539057720], 'sell': [19055626750, 101200.0, 0.002], 'filled': False, 'margin': 17.96, 'leverage': 11, 'profit': 0, 'active': True}, {'id': 2, 'buy': [19055663689, 95800.0, 0.002, 1751539058987], 'sell': [19055665689, 97800.0, 0.002, 1751539058899], 'filled': True, 'margin': 18.56, 'leverage': 11, 'profit': 0.12, 'active': False}, {'id': 3, 'buy': [19055796664, 93800.0, 0.002], 'sell': None, 'filled': False, 'margin': 18.96, 'leverage': 11, 'profit': 0, 'active': True}, {'id': 4, 'buy': [19055896888, 90800.0, 0.002], 'sell': None, 'filled': False, 'margin': 19.96, 'leverage': 11, 'profit': 0, 'active': False}]}
        # create record for status file
        trade_record = {
            "id":_id,
            "buy": [buy_order_id, price, qtyty],
            "sell": None,
            "filled": False,
            "margin": round((price * qtyty) / self.config.get("leverage"), 2),
            "leverage": self.config.get("leverage"),
            "profit": 0,
            "active":True
        }
        
        _id +=1         # increment trade id for next order
        self.active_trades["trades"].append(trade_record)       # append trade record
        self.save_active_state(dopl_info = "initial buy order filled placed sell order a tento buy order nizsie")                                # save state
        print(f"[INFO] Zadana {side} objednavka {buy_order_id} na cene {price}")  # terminal output
        print (_id)     # debug id output
        return _id, price   # return id and buy price for further processing


    def load_active_trades(self):
        """
        load active trades from state file. used to restore state on restart.
        """
        try:
            with open(self.state_file, "r", encoding='utf-8') as f:
                self.active_trades = json.load(f)           # load state json
            print(f"[BOT] Uspesne nacitane zo suboru: {self.state_file}")           # log confirmation
            return True             # return true if successfully loaded
        except Exception as e:
            print(f"Chyba pri nacitani: {e}")           # log load error
            return False            # return false on failure

    def monitor_and_chain_orders(self, initial_level_idx=0,_id = 1):
        """
        track initial order, wait for fill and automatically trigger sell order and lower buy order.
        """  

        # set leverage and side from config before running
        set_leverage(self.config, self.client, self.symbol)
        side = "BUY" if self.config.get("direction", "LONG") == "LONG" else "SELL"

        
        # start trading - retry loop to place initial order
        while self.trading_active:
            
            # skip iteration if trading is paused via cli
            if pauznut_cyklus(self.trading_paused):
                continue
            
            # fetch orderbook to determine entry price
            depth = get_futures_orderbook(self.client,self.symbol)
            
            # initial offer price pulled from binance, overwritten later for sell order price
            # pick second closest orderbook level
            price = float(depth["bids"][1][0]) if side == "BUY" else float(depth["asks"][1][0])  
            print("cena pri ktorej otvaramp", price)
            
            # calculate qty for current price
            qtyty = self.vypocitaj_quantity(price)
            
            # place limit initial order
            initial_order_id = place_limit_order(self.client, self.symbol, side, qtyty, price)
            if not initial_order_id:
                return          # exit if placement fails

            print(f"[INFO] Zadana uvodna {side} objednavka {initial_order_id} na cene {price}, čakám na vyplnenie...")
            
            # set timer start for fill timeout
            start_time = time.time()
            print(f"cakam na vyplnenie orderu {TIMEOUT_VYPLNENIE_ORDERU}")
            
            # wait for order fill until timeout
            while self.trading_active and (time.time() - start_time < TIMEOUT_VYPLNENIE_ORDERU):
                try:
                    # try block in case loop runs faster than market order processing
                    # prevents crashes if order id is not indexed instantly on market execution
 
                    if pauznut_cyklus(self.trading_paused):
                        continue        # skip if paused via cli
                    
                    # fetch order status
                    order = self.client.futures_get_order(symbol=self.symbol, orderId=initial_order_id)
                    
                    # order status payload example
                    # {'orderId': 18937513920, 'symbol': 'BTCUSDC', 'status': 'NEW', 'clientOrderId': 'x-Cb7ytekJ3926d3a801092c720e2381', 'price': '100000.0', 'avgPrice': '0.00', 'origQty': '0.001', 'executedQty': '0.000', 'cumQuote': '0.0000', 'timeInForce': 'GTC', 'type': 'LIMIT', 'reduceOnly': False, 'closePosition': False, 'side': 'BUY', 'positionSide': 'BOTH', 'stopPrice': '0.0', 'workingType': 'CONTRACT_PRICE', 'priceProtect': False, 'origType': 'LIMIT', 'priceMatch': 'NONE', 'selfTradePreventionMode': 'EXPIRE_MAKER', 'goodTillDate': 0, 'time': 1751442535271, 'updateTime': 1751442535271}

                    # log progress
                    print(f"\r[BOT] cakam na vyplnenie {int(time.time() - start_time)}/{TIMEOUT_VYPLNENIE_ORDERU} sek.", end="", flush=True)
                    
                    # on order fill create trade record
                    if order["status"] == "FILLED":
                        print(f"[INFO] Prvá BUY objednávka {initial_order_id} vyplnená.")
                        
                        try:
                            send_notification(CHAT_ID = self.TG_ID, TOKEN=self.TG_Token, message = f"Prvá BUY objednávka {initial_order_id} vyplnená na cene {order['avgPrice']}.")
                        except:
                            print(f"pri odosielani na TG bota sa nieco posralo INITIAL BUY....")
                            
                        trade_record = {
                            "id":_id,
                            "buy": [initial_order_id, order["avgPrice"],order["executedQty"],return_date_time_formated(order["time"])],
                            "sell": None,
                            "filled": False,
                            "margin": round(float(order["avgPrice"]) * float(order["executedQty"]) / self.config.get("leverage"), 2),
                            "leverage": self.config.get("leverage"),
                            "profit": 0,
                            "active":True
                        }
                        _id +=1
                        self.active_trades["config"] = self.config
                        self.active_trades["trades"].append(trade_record)       # append record to active state
                        self.save_active_state(dopl_info = "initial buy order")                                # dump active state
                        price = float(order["avgPrice"])                        # log fill price
    
                        break
                    time.sleep(2)               # polling interval
                    
                except Exception as e:
                    print (f"[BOT CHYBA riadok 268] {e}")
                    time.sleep(5)           # delay on error and retry loop without breaking
                                            # handles market order shift edge cases where order object isn't instantly available
                    
            else:
                # order wasn't filled within 60s timeout, cancel and retry
                print(order)
                self.client.futures_cancel_order(symbol=self.symbol, orderId=initial_order_id)
                print(f"[INFO] Order nevyplneny do {TIMEOUT_VYPLNENIE_ORDERU} sekund, order canceled skusam znova...")
                continue            # restart main placement loop
            break  # exit loop on successful initial fill
        
        # proceed if trading hasn't been halted via stop command
        if self.trading_active:
        
            
            # initial filled, creating corresponding sell + buy pair
            # calculate sell target price
            sell_price = round(price * (1 + self.config.get("step_up") / 100), 1)
            qtyty = self.vypocitaj_quantity(price)
            
            
            # place sell order
            sell_order_id = place_limit_order(self.client, self.symbol,"SELL" if side == "BUY" else "BUY", qtyty, sell_price)        
            
            if not sell_order_id:
                return
            
            # attach sell order to filled initial buy
            self.active_trades["trades"][0]["sell"] = [sell_order_id, sell_price,qtyty]         
            print(f"[INFO] Zadana prisluchajuca {'SELL' if side == 'BUY' else 'BUY'} objednavka {sell_order_id} na cene {sell_price}")
            self.save_active_state(dopl_info = "initial buy order filled a placed sell order")
            
    
            # place secondary buy order step lower than initial
            _id, price = self.vytvor_limit_buy_order(_id, side, price)
            
            # secondary buy dropped to avoid managing multiple ladder resets on sell fills
            # _id, price = self.vytvor_limit_buy_order(_id, side, price)
            
        else:
            # no active trading, skip adding orders
            print("[BOT] Neotvoreny ziaden obchod.... ")
    
    
    @staticmethod
    def is_trade_complete(trade):
        """
        trade is finished if filled = true or active = false (e.g. replaced buy).
        """
        return trade.get("filled") is True or trade.get("active") is False  
    
    @staticmethod
    def is_trade_active(trade):
        """
        trade is active if active = true and has a sell order associated.
        """
        if trade.get("active") and trade.get("sell") != None:
            return True
    
    def new_buy_order(self, trade, uzavrety_sell = False):
        """
        create new buy order linked to previous trade.
        if uzavrety_sell is true, open buy at the same entry price. if false, place order step lower.
        """

        if uzavrety_sell:
            # if sell was filled, set buy to same entry price
            price = round(float(trade["buy"][1]), 1)
        else:
            # if sell is open, place buy step_down lower
            gap = self.config.get("step_down") / 100
            price = round(float(trade["buy"][1]) * (1 - gap), 1)
        
        # calculate quantity for price
        qty = self.vypocitaj_quantity(price)
        
        while True:
            # place limit buy on exchange
            buy_order_id= place_limit_order(self.client, self.symbol,"BUY" if self.config.get("direction", "LONG") == "LONG" else "SELL", qty, price)
            # append record if order succeeded
            if buy_order_id:
                new_trade = {
                    "id": max(t["id"] for t in self.active_trades["trades"]) + 1,
                    "buy": [buy_order_id, price, qty],
                    "sell": None,
                    "filled": False,
                    "margin": round(price * qty / trade["leverage"], 2),
                    "leverage": trade["leverage"],
                    "profit": 0,
                    "active": True
                }
                self.active_trades["trades"].append(new_trade)   # append to active trades
                print(f"[BOT] Pridany novy BUY order {buy_order_id} na cene {price}.")
            
                # save updated state    
                self.save_active_state(dopl_info = f"new BUY order uzavrety_Sell: {uzavrety_sell}") 
                return 0
            else:
                time.sleep(5)
        

        
            


    def run_trading(self):
        """
        main execution loop.
        tracks buy/sell orders, handles state changes and chains subsequent trades.
        runs until grid cycle resolves or external exit flag is set.
        """
            
        self.trading_active = True      # set flag to activate loops
        current_price = get_current_future_price(self.client, self.symbol)  # fetch market price
        
        # run loop if conditions met: cycle limit, active flag, no stop_at_end, price below max threshold
        while self.active_trades["cycle"] <= self.num_of_cycles and self.trading_active and not self.trading_stop_at_end and current_price < float(self.config.get("max_open_rice", 150000)):
            
            try:
                # attempt to load active trades, otherwise trigger initial order chain
                if not self.load_active_trades():                
                    print("[BOT] Spúšťam obchodovanie...")
                    self.monitor_and_chain_orders(0) # place initial buy order and follow up orders
                
                # verify state file existence
                if os.path.exists(self.state_file): 
                    tem_i=0
                        
                    # inner monitoring loop
                    while self.trading_active:
                        
                        # break inner loop if no active trades left
                        if not self.active_trades["trades"]:
                            print("[BOT 498] Žiadne aktívne obchody, ukončujem vnútorný cyklus.")
                            break
                        
                        # terminal stats output
                        aktivne_obchody = 0
                        tmp_str  = (f"[BOT cyk {self.active_trades['cycle']} {get_current_future_price(self.client, self.symbol):.1f} {datetime.now().strftime('%x')} {datetime.now().strftime('%X')}]" )
                        tmp_list_pre_string = []
                        
                        # skip iteration if loop is paused
                        if pauznut_cyklus(self.trading_paused):
                            continue
                        
                        # iterate over active trade count
                        for trade in self.active_trades["trades"]:
                           
                           # count active trades
                           if GridBot.is_trade_active(trade):
                               aktivne_obchody +=1

                               
                               
                        # iterate through trade loop
                        for trade in self.active_trades["trades"]:
                           
                           # ignore finished trades
                           if GridBot.is_trade_complete(trade):
                               continue

                           
                           # === TRACK BUY ===
                           if len(trade["buy"]) == 3:
                               order_id = trade["buy"][0] 
                               buy_status = self.client.futures_get_order(symbol=self.symbol, orderId=order_id)
                               tmp_str += f" B: {float(buy_status['price']):.1f}"
                               
                               # handle filled buy order
                               if buy_status["status"] == "FILLED":
                                   print(f"\n[INFO] BUY order {order_id} vyplnený.")
                                   
                                   # increment active trades count to enforce max open order limit
                                   aktivne_obchody +=1
                                   
                                   try:
                                       send_notification(CHAT_ID = self.TG_ID, TOKEN=self.TG_Token, message = f"BUY order {order_id} vyplnený na cene {buy_status['avgPrice']} poradie {aktivne_obchody-1}/{self.config.get('order_count')}.")
                                   except:
                                       print(f"pri odosielani na TG bota sa nieco posralo prvy TRACK BUY....")
                                   
                                   # update filled buy order data
                                   trade["buy"] = [order_id, buy_status["avgPrice"],buy_status["executedQty"],return_date_time_formated(buy_status["updateTime"])]
                           
                                   # calculate sell price percentage higher than fill
                                   gap = self.config.get("step_up") / 100
                                   sell_price = round(float(trade["buy"][1]) * (1 + gap), 1)
                                   qty = float(buy_status["executedQty"])
                                   
                                   # place sell order loop until successful
                                   while True:
                                       
                                       sell_order_id = place_limit_order(self.client, self.symbol,"SELL" if self.config.get("direction", "LONG") == "LONG" else "BUY", qty, sell_price)
                                       
                                       # log active sell order data once created
                                       if sell_order_id:
                                           trade["sell"] = [sell_order_id, sell_price, qty]
                                           self.save_active_state(dopl_info = "track BUY a vytvoreny novy SELL")
                                           print(f"[BOT] Otvorený SELL order {sell_order_id} za cenu {sell_price}.")
                                           break
                                       else:
                                           time.sleep(5)
                                   
                                   # check max order limit before adding next buy
                                   if aktivne_obchody < self.config.get('order_count'):
                                       # open new buy order step lower on grid                     
                                       self.new_buy_order(trade, False)
                                   else:
                                       print(f"[BOT] neotvaram BUY lebo pocet aktivnych obchodov je {aktivne_obchody}/{self.config.get('order_count')}.")
                                  
                                       
                                                
                           
                           # === TRACK SELL ===
                           elif trade["sell"] and len(trade["sell"]) == 3:
                               sell_id = trade["sell"][0]
                               sell_status = self.client.futures_get_order(symbol=self.symbol, orderId=sell_id)
                               tmp_list_pre_string.append(float(sell_status['price']))
                               
                               # handle filled sell order
                               if sell_status["status"] == "FILLED":
                                   print(f"\n[INFO] SELL order {sell_id} vyplnený.")
                                   
                                   try:
                                       send_notification(CHAT_ID = self.TG_ID, TOKEN=self.TG_Token, message = f"SELL order {sell_id} vyplnený na cene {sell_status['avgPrice']}.")
                                   except:
                                       print(f"pri odosielani na TG bota sa nieco posralo, TRACK SELL...")
                                   
                                   # update filled sell record
                                   trade["sell"]=[sell_id, sell_status["avgPrice"],sell_status["executedQty"],return_date_time_formated(sell_status["updateTime"])]
                                   trade["filled"] = True
                                   trade["active"] = False
                                   trade["profit"] = round(((float(trade["sell"][1]) - float(trade["buy"][1])) * float(trade["buy"][2])), 4)
                                   self.save_active_state(dopl_info = "track SELL a vyplneny SELL")
    
    
                                   # cancel pending unlinked buy orders
                                   for t in reversed(self.active_trades["trades"]):
                                       # t["sell"] = None evaluates to false, handled by not t["sell"] 
                                       if t["buy"] and not t["sell"] and t["active"]:
                                           self.client.futures_cancel_order(symbol=self.symbol, orderId=t["buy"][0])
                                           print(f"[INFO] Buy order {t['buy'][0]} canceled kvoli vyplneniu sell orderu pre vyssi buy")
                                           t["active"] = False
                                           print(f"[BOT] Posledný neuzatvorený BUY order ID {t['id']} deaktivovaný.")
                                           self.save_active_state(dopl_info = "track SELL deaktivovany neuzavrety BUY")
                                           break  
                                   
                                   # if closing initial trade, log cycle completion instead of lowering buy price
                                   if not self.active_trades["trades"][0]["filled"]:
                                        # reopen buy at original entry price of filled sell
                                       self.new_buy_order(trade, True)
                                       
                                   else:
                                       # cycle complete, archive state
                                       nazov_archivu = self.archive_cycle()
                                       print (f"[BOT] Cyklus cislo {self.active_trades['cycle']-1} kompletne uzavrety a archivovany do {nazov_archivu}")
                                       break
    
    
                        # break inner loop if trades array cleared
                        if not self.active_trades["trades"]:
                            print("[BOT 618] archivovany cyklus, teraz by som chcel vyskocit z vnutorneho loopu")
                            break
          
                        # terminal progress logger
                        print(f"\r{tmp_str}  S: {min(tmp_list_pre_string):.1f} {aktivne_obchody}/{self.config.get('order_count')} {SPINNER[tem_i % len(SPINNER)]}", end="", flush=True)
                        time.sleep(2)
                        tem_i+=1
    
                    else: 
                        # inner loop interrupted manually (exit/stop commands)
                        print (f"\n[BOT] Cyklus cislo {self.active_trades['cycle']} obchodovania bol ukonceny inak ako kompletne uzavretie")
                        
                     
                else:
                    # active trades file missing
                    print(f"[BOT] obchodovanie uzavrete pred vytvorenim {self.state_file}")  
                    return
            except Exception as e:
                # catch network errors/timeouts and retry loop
                print(f"\n[BOT 637 Excetion] chyba v hlavnom loope: {e}")
                time.sleep(5)
        
    
    
    def pause(self):
        """
        pause execution if active.
        """
        if self.trading_active:
            self.trading_paused = True
            print("\n[BOT\\pause()] Obchodovanie pozastavene.")
            return "[BOT] Obchodovanie pozastavene."
        else:
            print("[BOT\\pause()] Obchodovanie nie je pozastavene.")
            return "[BOT] Obchodovanie nie je pozastavene."

    def resume(self):
        """
        resume execution if paused.
        """
        if self.trading_paused:
            self.trading_paused = False
            print("\n[BOT\\resume()] Obchodovanie obnovene.")
            return "[BOT] Obchodovanie obnovene."
        else:
            print("\n[BOT\\resume()] Obchodovanie nie je obnovene.")
            return "[BOT] Obchodovanie nie je obnovene."
            
    def stop(self):
        """
        stop execution completely (overrides pause).
        """
        self.trading_active = False
        self.trading_paused = False
        print("\n[BOT\\stop()] Obchodovanie bolo vypnute.")
        return "[BOT] Obchodovanie bolo vypnute."

    def stop_at_end(self):
        """
        toggle stop flag after finishing current cycle.
        """
        if self.trading_stop_at_end:
            self.trading_stop_at_end = False
        else:
            self.trading_stop_at_end = True

        print(f"\n[BOT\\stop_at_end()] aktualny stav je: {self.trading_stop_at_end}")
        return f"\n[BOT\\stop_at_end()] aktualny stav je: {self.trading_stop_at_end}"
        
    def get_active_state(self):
        """
        get current active state object.
        """
        return self.active_trades
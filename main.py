import socket
import threading
import json
import os
import sys
import platform
from bot import GridBot  # import main GridBot class
import evaluation


# check whether to use unix socket (linux/mac) or tcp socket (win)
USE_UNIX = platform.system() != "Windows"  
SOCKET_DIR = "/tmp"   # path for unix sockets
STATE_DIR = "state"   # folder for bot state
TCP_PORT = 5000       # tcp port for windows


# load trading pair from arg or use default
pair = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDC"

# path to socket for given pair
SOCKET_PATH = f"{SOCKET_DIR}/gridbot_{pair}.sock"


def start_server():
    trading_thread = None  # hold trading thread reference
    bot = GridBot(pair)    # create bot instance for pair
    

    # if bot has saved active trades -> auto start trading on startup
    if bot.load_active_trades():
        if trading_thread and trading_thread.is_alive():
            print("[main] Obchodovanie uz bezi.")
        else:
            bot.trading_active = True
            trading_thread = threading.Thread(target=bot.run_trading, daemon=True)
            trading_thread.start()
            print("[main] Obchodovanie spustene na pozadi.")
   
    # create socket server
    if USE_UNIX:
        # remove old socket if exists
        if os.path.exists(SOCKET_PATH):
            os.remove(SOCKET_PATH)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(SOCKET_PATH)
        listen_info = SOCKET_PATH
    else:
        # use tcp socket on windows
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("localhost", TCP_PORT))
        listen_info = f"localhost:{TCP_PORT}"

    server.listen(1)
    print(f"[BOT {pair}] Pocuvam na {listen_info}")
    
    # main loop for processing cli commands
    while True:
        conn, _ = server.accept()  # wait for client connection
        data = conn.recv(1024).decode().strip()  # receive command
        doplnkovy_text = None
        try:
            tmp_data, doplnkovy_text = data.split("XXX")[0],data.split("XXX")[1]
            data = tmp_data
        except:
            # print(f"[MAIN] nie je doplnkova informacia oddelena cez \'XXX\' {data}")
            pass
        
        # process commands
        if data == "simulate":
            res = bot.main_simulate_levels()    # calculate levels
            conn.send(json.dumps(res).encode())
            
        elif data == "run":
            # start trading if not running
            if trading_thread and trading_thread.is_alive():
                conn.send(b"Obchodovanie uz bezi.")
                
            else:
                bot.trading_active = True
                trading_thread = threading.Thread(target=bot.run_trading, daemon=True)
                trading_thread.start()
                conn.send(b"Obchodovanie spustene na pozadi.")
                
        elif data == "orderbook":
            res = bot.main_get_order_book()
            conn.send(json.dumps(res).encode())
            
        elif data == "open_orders":
            res = bot.main_get_open_orders()
            conn.send(res.encode())
            
        elif data == "balance":
            res = bot.main_get_futures_balance()
            conn.send(json.dumps(res).encode())
            
        elif data == "state":
            res = bot.main_get_active_state()
            conn.send(json.dumps(res).encode())
            
        elif data == "stop_at_end":
            res = bot.stop_at_end()     # set flag to stop after cycle ends
            conn.send(res.encode())
            
        elif data == "stop":
            res = bot.stop()    # stop trading immediately
            conn.send(res.encode())
            
        elif data == "set_l":
            res = bot.main_set_leverage()
            conn.send(json.dumps(res).encode())
            
        elif data == "get_l":
            res = bot.main_get_leverage()
            conn.send(json.dumps(res).encode())
            
        elif data == "likvidacna_cena":
            res = bot.main_get_likvidation_price()
            conn.send(res.encode())    
            
        elif data == "test":
            res = bot.main_test()
            conn.send(json.dumps(res).encode())
            
        elif data == "pause":
            res = bot.pause()
            conn.send(res.encode())           
            
        elif data == "resume":
            res = bot.resume()
            conn.send(res.encode())
        
        elif data == "status":
            if doplnkovy_text == None:
                res = evaluation.vrat_prehlad_zisk_feecka()
                conn.send(res.encode())
            else:
                res = evaluation.vrat_prehlad_zisk_feecka(doplnkovy_text)
                conn.send(res.encode())
        
        # exit main loop
        elif data == "exit":
            conn.send(b"Ukoncujem bota...")
            conn.close()
            break
        
        else:
            # show help for unknown command
            conn.send(b"Neznamy prikaz skus: set_l, get_l, simulate, status, run, open_orders, orderbook, likvidacna_cena, balance, state, exit, test, pause, resume, stop, stop_at_end, quit")
            
        conn.close()

    # close server and clean up socket
    server.close()
    if USE_UNIX:
        os.remove(SOCKET_PATH)

if __name__ == "__main__":
    start_server()
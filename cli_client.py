import socket
import sys
import os
import json
import platform


# check whether to use unix or tcp socket depending on os
USE_UNIX = platform.system() != "Windows"  # true for linux/mac, false for win
SOCKET_DIR = "/tmp"  # path for unix sockets
TCP_PORT = 5000      # tcp port for windows

print("CLI pripraveny. Zadajte prikaz:")

# originally empty pair var, defaulted to BTCUSDC
# pair = ""
pair = "BTCUSDC"


# main cli loop
while True:
    try:
        # wait for user input
        cmd = input("> ").strip()
        if not cmd:
            continue  # skip if empty input

        # split command into parts
        parts = cmd.split()
        # if less than 2 parts and pair is empty -> print help
        if len(parts) < 2 and pair == "":
            print("Pouzitie: <prikaz> <symbol>")
            continue
        
        # set pair from command if empty
        if pair == "":
            action, pair = parts[0], parts[1]
        else:
            action = parts[0]
        
        # path to socket for target pair
        socket_path = f"{SOCKET_DIR}/gridbot_{pair}.sock"

        # connect to server
        if USE_UNIX:
            # check if socket exists
            if not os.path.exists(socket_path):
                print(f"[ERROR] Bot pre {pair} nebezi.")
                continue
            client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            client.connect(socket_path)
        else:
            # use tcp on windows
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.connect(("localhost", TCP_PORT))
        
        # handle quit command
        if cmd == "quit":
            client.send("exit".encode())        # send exit signal
            print(client.recv(4096).decode())   # print response
            break                               # exit cli
            
        # send command
        client.send(action.encode())
        # receive response
        response = client.recv(4096)

        try:
            decoded = response.decode()
            # parse if JSON response
            if decoded.strip().startswith('{'):
                data = json.loads(decoded)
                levels_str = ""
                for num, level in enumerate(data['levels']):
                    levels_str +=str(num)+": "+str(level)+"\n"  
                
                # print simulation details
                print(f"[INFO] Simulovane levely:\n{levels_str}")
                print(f"Direction: {data['direction']}")
                print(f"Aktualna cena: {data['price_now']}")
                print(f"Entry price cez vsetky levely: {data['entry_price']:.1f} USDC")
                # print(f"Likvidacna cena: {data['liq_price']}")
                print(f"Leverage: {data['leverage']}")
                print(f"Zostatok Futures ucet: {data['available_stable']} USDC")
                print(f"Poplatky: {data['estimated_fees']} USDC")
                print(f"Iba nakup (margin): {data['needed_margin']} USDC")
                print(f"Nakup vsetkych levelov: {data['nakup_all']} USDC")
                print(f"Percentualny rozsah cez vsetky levely: {data['max_percent_zmena']} %")
            else:
                # print raw response if not json
                print(decoded)
        except:
            # fallback on decode error
            print("ina struktura !!!!!, vraciam celu strukturu")
            print(response)
        client.close()

    except KeyboardInterrupt:
        # exit cli on ctrl+c
        break
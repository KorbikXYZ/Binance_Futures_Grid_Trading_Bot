# py -m pip install python-binance 
from binance.client import Client
from binance.exceptions import BinanceAPIException


# API keys  

def get_binance_client ():

    keys = {"API_Key": "", "Secret_Key":""}

    with open ("API/API_keys.env") as f:
        for line in f:
            keys[line.split("=")[0].strip()]=line.split("=")[1].strip()
    
    return Client(api_key=keys["API_Key"],api_secret=keys["Secret_Key"])


def get_ID_Token ():

    ID_TG = {"CHAT_ID": "", "TOKEN":""}    

    with open ("API/telegram.env") as f:
        for line in f:
            ID_TG[line.split("=")[0].strip()]=line.split("=")[1].strip()
    
    return ID_TG["CHAT_ID"], ID_TG["TOKEN"]



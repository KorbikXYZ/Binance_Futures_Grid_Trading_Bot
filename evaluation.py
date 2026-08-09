import os
import json
from bot import GridBot
from datetime import datetime


FEE_PLATENIE_DENNE = 3  # fee paid 3 times a day
FEE_VYSKA_POPLATKU = 0.0001 # 0.01% of total leveraged position

def return_pocet_dni (t_zaciatok, t_koniec):

    t1date = datetime.strptime(t_zaciatok, '%m/%d/%y %H:%M:%S')
    t2date = datetime.strptime(t_koniec, '%m/%d/%y %H:%M:%S')

    return((t2date-t1date).days+1)

def vrat_prehlad_zisk_feecka (file = "cyklus_20250813_224137.json"):
    if len (file.split(".")) == 2:
        file = file.split(".")[0]
    try:
        with open("state/"+file+".json", "r") as f:
            loaded_file = json.load(f)

        trades = loaded_file["trades"]
        
        now = datetime.utcnow().strftime('%m/%d/%y %H:%M:%S')       # get current utc time

        zisk = 0
        feecka = 0
        otvorenych_pozicii = 0
        realizovanych_obchodov = 0
        for trade in trades:
            otvorenych_pozicii +=1
            if trade.get("filled") == True:
                zisk += (float(trade.get("sell")[1])*float(trade.get("sell")[2]) - float(trade.get("buy")[1])*float(trade.get("buy")[2])) 
                # print (return_pocet_dni(trade.get("buy")[3],trade.get("sell")[3])*FEE_PLATENIE_DENNE*float(trade.get("buy")[1])*float(trade.get("buy")[2])*FEE_VYSKA_POPLATKU)
                feecka += return_pocet_dni(trade.get("buy")[3],trade.get("sell")[3])*FEE_PLATENIE_DENNE*float(trade.get("buy")[1])*float(trade.get("buy")[2])*FEE_VYSKA_POPLATKU
                realizovanych_obchodov +=1
            if trade.get("active")== True and len(trade.get("buy")) == 4 :
                feecka += return_pocet_dni(trade.get("buy")[3],now)*FEE_PLATENIE_DENNE*float(trade.get("buy")[1])*float(trade.get("buy")[2])*FEE_VYSKA_POPLATKU
                
        
        return (f"Zrealizovanych obchodov: {realizovanych_obchodov} z otvorenych_pozicii: {otvorenych_pozicii} , cisty zisk: {(zisk-feecka):.2f}, zisk s feeckami = {zisk:.2f}, feecka  = {feecka:.2f}")
    except:
        return("nejaka chyba")
    
    

print (vrat_prehlad_zisk_feecka())
# price_utils.py
import json
import os
import requests
import time
import yfinance as yf
from datetime import datetime, timedelta
from config import SOL_PRICE_CACHE_FILE, PUMP_FUN_API_URL, JUPITER_API_URL, API_TIMEOUT, MAX_RETRIES
from file_utils import round_to_nearest_hour

def load_sol_price_cache(logger):
    # Fonction pour charger le cache des prix du SOL à partir d'un fichier JSON
    # input: logger (pour enregistrer les messages de log)
    # output: dictionnaire contenant les prix du SOL en cache
    if os.path.exists(SOL_PRICE_CACHE_FILE):
        with open(SOL_PRICE_CACHE_FILE, 'r') as f:
            cache = json.load(f)
        logger.info(f"Loaded SOL price cache with {len(cache)} entries")
        return cache
    logger.info("No existing SOL price cache found. Starting with empty cache.")
    return {}

def save_sol_price_cache(cache, logger):
    # Fonction pour sauvegarder le cache des prix du SOL dans un fichier JSON
    # input: cache (dictionnaire de prix), logger (pour enregistrer les messages de log)
    # output: aucun
    with open(SOL_PRICE_CACHE_FILE, 'w') as f:
        json.dump(cache, f)
    logger.debug(f"Saved SOL price cache with {len(cache)} entries")

def get_sol_price_at_time(dt, price_cache, logger, retries=MAX_RETRIES):
    # Fonction pour obtenir le prix du SOL à un moment donné en vérifiant le cache ou en récupérant via yfinance
    # input: dt (datetime pour lequel on veut le prix), price_cache (dictionnaire des prix en cache), logger (pour les logs), retries (nombre de tentatives)
    # output: prix du SOL pour le moment donné arondie à l'heure près ou lève une erreur après plusieurs tentatives
    dt_str = dt.isoformat()
    if dt_str in price_cache:
        logger.debug(f"SOL price for {dt_str} found in cache")
        return price_cache[dt_str]
    
    logger.debug(f"Fetching SOL price for {dt_str}")
    sol_data = yf.download('SOL-USD', start=dt, end=dt + timedelta(hours=1), interval='1h', progress=False)
    if not sol_data.empty:
        price = sol_data.iloc[0]['Close']
        price_cache[dt_str] = price
        save_sol_price_cache(price_cache, logger)  # Save the updated cache
        logger.debug(f"Added new SOL price for {dt_str}: ${price}")
        return price
    elif retries > 0:
        logger.warning(f"No data found for {dt}, retrying with {retries - 1} retries left...")
        return get_sol_price_at_time(dt - timedelta(hours=1), price_cache, logger, retries - 1)
    else:
        logger.error(f"Failed to retrieve SOL price for {dt} after multiple attempts.")
        raise ValueError(f"Failed to retrieve SOL price for {dt} after multiple attempts.")

def get_token_prices(tokens, price_cache, logger):
    # Fonction pour récupérer les prix de plusieurs tokens en utilisant l'API Pump Fun puis celle de Jupiter
    # input: tokens (liste des tokens), price_cache (dictionnaire des prix en cache), logger (pour enregistrer les logs)
    # output: dictionnaire avec les prix des tokens
    recovered = 0
    prices = {}
    sol_price = get_sol_price_at_time(round_to_nearest_hour(time.time()), price_cache, logger)

    for token in tokens:
        # Essayer d'abord de récupérer le prix via l'API Pump Fun
        try:
            response = requests.get(PUMP_FUN_API_URL.format(token=token), timeout = API_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if data and len(data) > 0:
                close_price = data[0].get('close', 0)
                prices[token] = close_price * sol_price
                recovered += 1
                continue  # Passer au token suivant si réussi
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"Error requesting price for token {token} from Pump Fun: {e}")

        # Si l'API Pump Fun échoue, essayer de récupérer le prix via l'API Jupiter
        try:
            response = requests.get(JUPITER_API_URL.format(token=token), timeout = API_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            if 'data' in data and token in data['data']:
                price = float(data['data'][token]['price'])
                prices[token] = price
                recovered += 1
            else:
                logger.warning(f"No price data found for token {token} from Jupiter")
        except (requests.RequestException, ValueError) as e:
            logger.warning(f"Error requesting price for token {token} from Jupiter: {e}")

    logger.info(f"Tokens price recovered: {recovered} / {len(tokens)}")
    return prices

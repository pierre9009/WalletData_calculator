# price_service.py
import json
import os
import requests
import yfinance as yf
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional, Union
from decimal import Decimal

class PriceService:
    def __init__(self, logger, config):
        """
        Initialise le service de prix avec la configuration nécessaire
        """
        self.logger = logger
        self.config = config
        self.price_cache = {
            'token_sol': {},
            'token_usd': {},
            'sol_price': {}
        }
        self._load_cache()

    def _load_cache(self) -> Dict[str, float]:
        """
        Charge le cache des prix à partir du fichier
        """
        if os.path.exists(self.config.SOL_PRICE_CACHE_FILE):
            try:
                with open(self.config.SOL_PRICE_CACHE_FILE, 'r') as f:
                    loaded_cache = json.load(f)
                    # Assurez-vous que toutes les clés existent
                    self.price_cache.update(loaded_cache)
                self.logger.info(f"Loaded price cache with {len(self.price_cache['sol_price'])} entries")
            except Exception as e:
                self.logger.error(f"Error loading cache: {e}")
        self.logger.info("Cache initialized")
        return self.price_cache

    def _save_cache(self) -> None:
        """
        Sauvegarde le cache des prix dans le fichier
        """
        try:
            with open(self.config.SOL_PRICE_CACHE_FILE, 'w') as f:
                json.dump(self.price_cache, f)
            self.logger.debug(f"Saved price cache with {len(self.price_cache)} entries")
        except Exception as e:
            self.logger.error(f"Error saving cache: {e}")

    def get_sol_price(self, timestamp: int) -> Optional[Decimal]:
        """
        Obtient le prix du SOL pour un timestamp donné
        """
        dt = datetime.fromtimestamp(timestamp)
        dt_str = dt.isoformat()

        # Vérifier le cache
        if dt_str in self.price_cache:
            return Decimal(str(self.price_cache[dt_str]))

        try:
            # Récupérer le prix via yfinance
            sol_data = yf.download(
                'SOL-USD',
                start=dt,
                end=dt + timedelta(hours=1),
                interval='1h',
                progress=False
            )

            if not sol_data.empty:
                price = float(sol_data.iloc[0]['Close'])
                self.price_cache[dt_str] = price
                self._save_cache()
                return Decimal(str(price))

            # Si pas de données, essayer l'heure précédente
            for i in range(1, self.config.MAX_RETRIES):
                prev_dt = dt - timedelta(hours=i)
                sol_data = yf.download(
                    'SOL-USD',
                    start=prev_dt,
                    end=prev_dt + timedelta(hours=1),
                    interval='1h',
                    progress=False
                )
                if not sol_data.empty:
                    price = float(sol_data.iloc[0]['Close'])
                    self.price_cache[dt_str] = price
                    self._save_cache()
                    return Decimal(str(price))

            self.logger.error(f"Failed to get SOL price for {dt}")
            return None

        except Exception as e:
            self.logger.error(f"Error fetching SOL price: {e}")
            return None
    def get_token_price_in_sol(self, token: str, timestamp: int) -> Optional[Decimal]:
        """
        Obtient le prix d'un token en SOL
        """
        cache_key = f"{token}_{timestamp}"
        
        # Vérifier le cache
        if cache_key in self.price_cache['token_sol']:
            return self.price_cache['token_sol'][cache_key]
            
        try:
            # Essayer d'abord avec Pump Fun qui donne les prix en SOL
            price = self._get_token_price_pump_fun(token, timestamp)
            if price is not None:
                self.price_cache['token_sol'][cache_key] = price
                return price
                
            # Si pas de succès, essayer de convertir le prix Jupiter
            jupiter_price = self._get_token_price_jupiter(token)
            if jupiter_price is not None:
                sol_price = self.get_sol_price(timestamp)
                if sol_price:
                    price = jupiter_price / sol_price
                    self.price_cache['token_sol'][cache_key] = price
                    return price
                    
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting SOL price for {token}: {e}")
            return None

    def get_token_price_in_usd(self, token: str, timestamp: int) -> Optional[Decimal]:
        """
        Obtient le prix d'un token en USD directement
        """
        cache_key = f"{token}_{timestamp}"
        
        # Vérifier le cache
        if cache_key in self.price_cache['token_usd']:
            return self.price_cache['token_usd'][cache_key]
            
        try:
            # Essayer d'obtenir le prix via Jupiter (qui donne les prix en USD)
            price = self._get_token_price_jupiter(token)
            if price is not None:
                self.price_cache['token_usd'][cache_key] = price
                return price
                
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting USD price for {token}: {e}")
            return None

    def _get_token_price_pump_fun(self, token: str, timestamp: int) -> Optional[Decimal]:
        """
        Obtient le prix d'un token via Pump Fun API (en SOL)
        """
        try:
            response = requests.get(
                self.config.PUMP_FUN_API_URL.format(token=token),
                timeout=self.config.API_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            if data and len(data) > 0:
                return Decimal(str(data[0].get('close', 0)))
                
            return None
            
        except Exception as e:
            self.logger.debug(f"Pump Fun API error for {token}: {e}")
            return None

    def _get_token_price_jupiter(self, token: str) -> Optional[Decimal]:
        """
        Obtient le prix d'un token via Jupiter API (en USD)
        """
        try:
            response = requests.get(
                self.config.JUPITER_API_URL.format(token=token),
                timeout=self.config.API_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            
            if 'data' in data and token in data['data']:
                return Decimal(str(data['data'][token]['price']))
                
            return None
            
        except Exception as e:
            self.logger.debug(f"Jupiter API error for {token}: {e}")
            return None

    def update_cache(self, timestamps: List[int]) -> None:
        """
        Met à jour le cache pour une liste de timestamps
        """
        for ts in timestamps:
            self.get_sol_price(ts)

class TokenPriceManager:
    """
    Gestionnaire de prix pour les tokens avec mise en cache
    """
    def __init__(self, price_service: PriceService):
        self.price_service = price_service
        self.current_prices: Dict[str, Decimal] = {}
        self.last_update = 0
        self.update_interval = 300  # 5 minutes

    def get_current_prices(self, tokens: List[str]) -> Dict[str, Decimal]:
        """
        Obtient les prix actuels pour une liste de tokens avec mise en cache
        """
        current_time = time.time()
        
        # Mise à jour si nécessaire
        if current_time - self.last_update > self.update_interval:
            self.current_prices = self.price_service.get_token_prices(tokens)
            self.last_update = current_time
            
        return self.current_prices
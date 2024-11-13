# config.py

from datetime import datetime, timedelta

class Config:
    def __init__(self):
        # Chemins des dossiers
        self.INPUT_FOLDER = './toProcess/'
        self.OUTPUT_FOLDER = './processed/'


        # Configurations des tokens
        self.EXCLUDED_TOKENS = {
            'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',  # USDC
            'Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB',  # USDT
            '7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs'   # WETH
        }

        self.SOLANA_ADDRESSES = {
            'So11111111111111111111111111111111111111112', # WSOL
            'So11111111111111111111111111111111111111111' # SOL
        }

        # Fichier de cache
        self.SOL_PRICE_CACHE_FILE = 'sol_price_cache.json'

        # Paramètres de calcul
        self.START_DATE = datetime.now() - timedelta(days=30)

        # URLs des API
        self.PUMP_FUN_API_URL = "https://frontend-api.pump.fun/candlesticks/{token}?offset=0&limit=1&timeframe=1"
        self.JUPITER_API_URL = "https://price.jup.ag/v6/price?ids={token}&vsToken=USDC"
        self.SOLSCAN_API_URL = "https://api-v2.solscan.io/v2/account/activity/dextrading?address={address}&page={{page}}&page_size=100"

        # Autres paramètres solscan ou yfinance
        self.REQUEST_TIMEOUT = 5
        self.MAX_RETRIES = 3

        #Time out de pump fun ou jupiter pour recuperer le prix des tokens (seconde)
        self.API_TIMEOUT = 1

        #get_transactions
        self.RATE_LIMIT = {
            'requests_per_10s': 100000,
            'min_interval': 0.05
        }

        self.SWAP_PROGRAMS = {
            "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4": "Jupiter",
            "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca",
            "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP": "Raydium",
            "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium V4",
            "SwaPpA9LAaLfeLi3a68M4DjnLqgtticKg6CnyNwgAC8": "Raydium Legacy",
            "DjVE6JNiYqPL2QXyCUUh8rNjHrbz9hXHNYt99MQ59qw1": "Orca Whirlpool",
        }

        self.BOT_THRESHOLD = 0.75
        self.HIGH_PROBABILITY_BOT_THRESHOLD = 0.95
        self.EARLY_DETECTION_COUNT = 80
        self.MODEL_PATH = 'models/wallet_classifier_pipeline.joblib'
        self.DEFAULT_NBR_TRANSACTIONS = 500
        self.ANALYSIS_CACHE_HOURS = 24
        self.ARCHIVE_AFTER_DAYS = 30
        self.CLEANUP_INTERVAL = 3600  # 1 heure
        self.ANALYSIS_OUTPUT_DIR = "./processed"
        self.CACHE_DIR = "./cache"
        self.TEMP_DIR = "./temp"
        self.ARCHIVE_DIR = "archived_analyses"
        self.SOLANA_RPC_URL = "https://mainnet.helius-rpc.com/?api-key=0a4595b2-fcac-4086-a894-d4df21dcd82c"
        self.RPC_TIMEOUT = 2
        self.TRANSACTION_PROCESSING_DELAY = 0.2
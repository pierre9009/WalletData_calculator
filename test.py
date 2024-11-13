from get_parsed_transactions import SolanaSwapAnalyzer
from logger import setup_logger
# Initialiser l'analyseur
logger = setup_logger()
analyzer = SolanaSwapAnalyzer(logger, "https://mainnet.helius-rpc.com/?api-key=0a4595b2-fcac-4086-a894-d4df21dcd82c")

# Les logs seront maintenant colorés et formatés selon votre configuration
results = analyzer.analyze_wallet(logger, "CuvaikSrjiwvsBs8W51oRomA3vgjQdgSVxFgXLyhnKq5")
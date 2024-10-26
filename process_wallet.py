from config import INPUT_FOLDER, OUTPUT_FOLDER, START_DATE, SOLSCAN_API_URL
from logger import setup_logger
from price_utils import load_sol_price_cache, save_sol_price_cache, get_sol_price_at_time, get_token_prices
from pnl_calculation import process_transaction, calculate_unrealized_pnl, calculate_pnl_and_generate_summary
from file_utils import clear_input_folder
from get_trans import run_scraper
from toDatabase import toDatabase, connection_to_db, close_sql_connection
from multiprocessing import Queue
from dotenv import load_dotenv
import os
import time
import redis

load_dotenv()

# Initialiser la connexion Redis
r = redis.Redis(host=os.getenv('REDIS_HOST'), port=os.getenv('REDIS_PORT'), db=0, password = os.getenv('PASSWORD_REDIS_SERVER'))

def process_address(address, logger, connection, cursor):
    file_path = os.path.join(INPUT_FOLDER, f"{address}.csv")
    
    # Lancer le scraper pour récupérer les données
    logger.info(f"Starting scraper for address: {address}")
    run_scraper([address], logger)  # Appel à run_scraper pour chaque adresse

    if os.path.exists(file_path):
        logger.info(f"Processing file for address: {address}")
        metrics = calculate_pnl_and_generate_summary(logger, file_path, OUTPUT_FOLDER, START_DATE)

        # Afficher les métriques de trading
        logger.info(f"Trading metrics for {address}:")
        logger.info(f"Gross Profit: ${metrics['gross_profit']:.2f}")
        logger.info(f"Win Rate: {metrics['win_rate']:.2f}%")
        logger.info(f"Total ROI: {metrics['total_roi']:.2f}%")
        logger.info(f"Volume: ${metrics['total_volume']:.2f}")
        logger.info(f"Total Trades: {metrics['total_trades']}")
        logger.info(f"Total Token traded: {metrics['total_token_traded']}")

        toDatabase(logger, connection, cursor, address, metrics['gross_profit'], metrics['win_rate'], metrics['total_roi'], metrics['total_volume'], metrics['total_trades'], metrics['total_token_traded'])
        logger.info("--------------------------------------------------------------------------------------")
    else:
        logger.warning(f"File not found for address: {address}")
        logger.info("--------------------------------------------------------------------------------------")

def main():
    logger = setup_logger()
    logger.info("Starting continuous PnL calculation process")
    os.makedirs(INPUT_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    logger.info(f"Using start date: {START_DATE}")

    connection, cursor = connection_to_db(logger)

    while True:
            # Récupérer une adresse depuis la queue Redis (bloquant si la queue est vide)
            address_to_process = r.blpop(os.getenv('REDIS_QUEUE_NAME'))[1].decode('utf-8')
            logger.info(f"Processing address: {address_to_process}")
            process_address(address_to_process, logger, connection, cursor)

            # Si aucun traitement n'est nécessaire, attendre un moment
            if not address_to_process:
                time.sleep(5)


    clear_input_folder(INPUT_FOLDER)
    close_sql_connection(logger, connection, cursor)
    logger.info("PnL calculation process completed")

if __name__ == "__main__":
    main()

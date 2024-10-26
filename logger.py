# logger.py
import logging
from colorama import Fore, Style, init

# Initialisation de colorama pour Windows
init(autoreset=True)

class ColoredLogger(logging.Logger):
    COLOR_MAP = {
        'DEBUG': Fore.BLUE,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT
    }

    def __init__(self, name):
        super().__init__(name)

    def _log(self, level, msg, args, exc_info=None, extra=None):
        color = self.COLOR_MAP.get(logging.getLevelName(level), '')
        msg = f"{color}{msg}{Style.RESET_ALL}"
        super()._log(level, msg, args, exc_info, extra)

def setup_logger():
    logging.setLoggerClass(ColoredLogger)
    
    # Create the root logger and set the basic configuration
    logging.basicConfig(
        level=logging.INFO,  # Niveau par défaut pour afficher les logs
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',  # Format du message de log
        datefmt='%Y-%m-%d %H:%M:%S',  # Format de la date
        handlers=[
            logging.StreamHandler()  # Envoyer les logs à la console (stdout)
        ]
    )
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.setLevel(logging.INFO)
    logging.getLogger('scrapy').setLevel(logging.WARNING)
    logging.getLogger('scrapy').propagate = False

    # Configure other loggers if necessary
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    logging.getLogger("peewee").setLevel(logging.ERROR)
    logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    return logging.getLogger(__name__)
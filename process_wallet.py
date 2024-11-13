# process_wallet.py
from typing import Dict, Any, Optional
import redis
from dotenv import load_dotenv
import os
import time
from config import Config
from logger import setup_logger
from database_manager import DatabaseManager
from get_parsed_transactions import SolanaSwapAnalyzer
from metrics_calculator import MetricsCalculator
from price_service import PriceService
from file_service import FileService, AnalysisFileManager

load_dotenv()

class WalletProcessor:
    def __init__(self, logger):
        """
        Initialise le processeur de wallet avec tous les services nécessaires
        """
        self.logger = logger
        self.config = Config()  # Assumé que vous avez une classe Config
        
        # Initialisation des services
        self.file_service = FileService(logger, self.config)
        self.analysis_manager = AnalysisFileManager(self.file_service)
        self.price_service = PriceService(logger, self.config)
        
        # Initialisation des composants principaux
        self.analyzer = SolanaSwapAnalyzer(logger, self.config)
        self.metrics_calculator = MetricsCalculator(
            logger=logger,
            config=self.config,
            price_service=self.price_service,
            file_service=self.file_service
        )

        # Connexion Redis
        self.redis_client = redis.Redis(
            host=os.getenv('REDIS_HOST'),
            port=os.getenv('REDIS_PORT'),
            db=0,
            password=os.getenv('PASSWORD_REDIS_SERVER'),
            decode_responses=True
        )

    def analyze_behavior(self, analysis: Dict) -> Dict[str, Any]:
        """
        Analyse le comportement du wallet
        """
        return {
            'is_bot': analysis['bot_probability'] >= self.config.BOT_THRESHOLD,
            'bot_probability': analysis['bot_probability'],
            'total_swaps': len(analysis['swaps']),
            'analysis_time': analysis['execution_time'],
            'transactions_analyzed': analysis['total_transactions'],
            'early_detection': analysis.get('early_detection', {}).get('triggered', False)
        }

    def should_skip_detailed_analysis(self, behavior_metrics: Dict[str, Any]) -> bool:
        """
        Détermine si l'analyse détaillée doit être sautée
        """
        return (behavior_metrics['is_bot'] and 
                behavior_metrics['bot_probability'] > self.config.HIGH_PROBABILITY_BOT_THRESHOLD)

    def process_address(self, address: str) -> None:
        """
        Traite une adresse avec analyse complète
        """
        try:
            self.logger.info(f"Starting analysis for address: {address}")
            
            # Vérifier si une analyse récente existe
            recent_analysis = self.analysis_manager.get_latest_analysis(
                address, 
                max_age_hours=self.config.ANALYSIS_CACHE_HOURS
            )
            
            if recent_analysis:
                self.logger.info(f"Using cached analysis for {address}")
                complete_analysis = recent_analysis
            else:
                # Récupérer et analyser les transactions
                analysis = self.analyzer.analyze_wallet(address)
                if "error" in analysis:
                    self.logger.error(f"Analysis failed for {address}: {analysis['error']}")
                    return

                # Extraire les métriques comportementales
                behavior_metrics = self.analyze_behavior(analysis)
                
                # Vérifier si on doit sauter l'analyse détaillée
                if self.should_skip_detailed_analysis(behavior_metrics):
                    self.logger.warning(
                        f"High probability bot detected ({behavior_metrics['bot_probability']:.2%}), "
                        "skipping detailed analysis"
                    )
                    self.save_results_to_db(address, behavior_metrics, None)
                    complete_analysis = {
                        'address': address,
                        'behavior_metrics': behavior_metrics,
                        'trade_metrics': None,
                        'token_summary': None,
                        'timestamp': int(time.time())
                    }
                else:
                    # Calculer les métriques de trading
                    trade_metrics = self.metrics_calculator.calculate_metrics(analysis['swaps'])
                    token_summary = self.metrics_calculator.generate_token_summary()
                    
                    complete_analysis = {
                        'address': address,
                        'behavior_metrics': behavior_metrics,
                        'trade_metrics': trade_metrics,
                        'token_summary': token_summary,
                        'swaps_count': len(analysis['swaps']),
                        'timestamp': int(time.time())
                    }
                    
                    # Sauvegarder dans la base de données
                    self.save_results_to_db(address, behavior_metrics, trade_metrics)

                # Sauvegarder l'analyse complète
                self.analysis_manager.save_wallet_analysis(address, complete_analysis)

            # Logger les résultats
            self.log_analysis_results(complete_analysis)

        except Exception as e:
            self.logger.error(f"Error processing address {address}: {e}")
            raise

    def save_results_to_db(self, 
                          address: str, 
                          behavior_metrics: Dict[str, Any],
                          trade_metrics: Optional[Dict[str, Any]]) -> None:
        """
        Sauvegarde les résultats dans la base de données
        """
        try:
            with DatabaseManager(self.logger) as db:
                db.update_behavior_metrics(address, behavior_metrics)
                if trade_metrics:
                    db.update_wallet_stats(address, trade_metrics)
        except Exception as e:
            self.logger.error(f"Database update failed for {address}: {e}")
            raise

    def log_analysis_results(self, results: Dict[str, Any]) -> None:
        """
        Affiche les résultats de l'analyse dans les logs
        """
        address = results['address']
        behavior = results['behavior_metrics']
        trading = results.get('trade_metrics')
        
        self.logger.info(f"\nAnalysis Results for {address}")
        self.logger.info("="*50)
        
        # Métriques comportementales
        self.logger.info("\nBehavioral Analysis:")
        self.logger.info(f"Bot Probability: {behavior['bot_probability']:.2%}")
        self.logger.info(f"Total Swaps Analyzed: {behavior['total_swaps']}")
        self.logger.info(f"Analysis Time: {behavior['analysis_time']:.2f}s")
        
        # Métriques de trading
        if trading:
            self.logger.info("\nTrading Metrics:")
            metrics_to_log = [
                ("Gross Profit", 'gross_profit', '$'),
                ("Total ROI", 'total_roi', '%'),
                ("Win Rate", 'win_rate', '%'),
                ("Total Volume", 'total_volume', '$'),
                ("Total Trades", 'total_trades', ''),
                ("Total Tokens Traded", 'total_token_traded', ''),
                ("Realized PnL", 'total_realized_pnl', '$'),
                ("Unrealized PnL", 'total_unrealized_pnl', '$')
            ]
            
            for label, key, unit in metrics_to_log:
                value = trading.get(key)
                if value is not None:
                    if unit in ['$', '%']:
                        self.logger.info(f"{label}: {unit}{value:.2f}")
                    else:
                        self.logger.info(f"{label}: {value}")
        
        self.logger.info("="*50)

    def cleanup_old_data(self) -> None:
        try:
            self.file_service.cleanup_temp_files()
            self.analysis_manager.archive_old_analyses(
                days=self.config.ARCHIVE_AFTER_DAYS
            )
            self.logger.info("Cleanup completed successfully")
        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")

    def run(self) -> None:
        """
        Boucle principale de traitement
        """
        self.logger.info("Starting wallet processing service")
        last_cleanup = time.time()
        
        while True:
            try:
                # Nettoyage périodique
                current_time = time.time()
                if current_time - last_cleanup > self.config.CLEANUP_INTERVAL:
                    self.cleanup_old_data()
                    last_cleanup = current_time

                # Traitement des adresses
                redis_data = self.redis_client.blpop(
                    os.getenv('REDIS_QUEUE_NAME'),
                    timeout=5
                )
                
                if redis_data:
                    _, address = redis_data
                    self.process_address(address)
                
            except KeyboardInterrupt:
                self.logger.info("Shutting down gracefully...")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in main loop: {e}")
                time.sleep(5)
        
        # Nettoyage final avant de quitter
        try:
            self.cleanup_old_data()
        except Exception as e:
            self.logger.error(f"Error during final cleanup: {e}")

def main():
    logger = setup_logger()
    processor = WalletProcessor(logger)
    processor.run()

if __name__ == "__main__":
    main()
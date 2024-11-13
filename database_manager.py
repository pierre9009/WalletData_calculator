import psycopg2
from dotenv import load_dotenv
from datetime import datetime
import numpy as np
from typing import Dict, Any, Optional, Tuple
import os

load_dotenv()

class DatabaseManager:
    def __init__(self, logger):
        """Initialize database connection"""
        self.logger = logger
        self.connection = None
        self.cursor = None
        self._connect()

    def _connect(self) -> None:
        """Establish connection to database"""
        try:
            self.connection = psycopg2.connect(
                host=os.getenv('IP_WALLET_DB'),
                database=os.getenv('DB_WALLET'),
                user=os.getenv('USER_WALLET_DB'),
                password=os.getenv('PASSWORD_WALLET_DB')
            )
            self.cursor = self.connection.cursor()
            self.logger.info("Database connection established successfully")
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {e}")
            raise ConnectionError(f"Database connection failed: {e}")

    def _convert_numpy_types(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert numpy types to Python native types"""
        return {
            key: float(value) if isinstance(value, np.generic) else value
            for key, value in data.items()
        }

    def update_wallet_stats(self, address: str, stats: Dict[str, Any]) -> None:
        """
        Update wallet statistics in database
        
        Args:
            address: Wallet address
            stats: Dictionary containing wallet statistics
        """
        try:
            # Convert numpy types to Python native types
            converted_stats = self._convert_numpy_types(stats)
            
            # Prepare the query
            fields = list(converted_stats.keys())
            placeholders = ', '.join(['%s' for _ in fields])
            update_set = ', '.join([f"{field} = EXCLUDED.{field}" for field in fields])
            
            query = f"""
                INSERT INTO wallet_stats (address, {', '.join(fields)})
                VALUES (%s, {placeholders})
                ON CONFLICT (address)
                DO UPDATE SET {update_set};
            """
            
            # Prepare values for the query
            values = (address,) + tuple(converted_stats.values())
            
            # Execute query
            self.cursor.execute(query, values)
            self.connection.commit()
            self.logger.info(f"Successfully updated stats for wallet: {address}")

        except Exception as e:
            self.logger.error(f"Error updating wallet stats: {e}")
            self.connection.rollback()
            raise

    def update_behavior_metrics(self, address: str, metrics: Dict[str, Any]) -> None:
        """
        Update behavioral metrics in database
        
        Args:
            address: Wallet address
            metrics: Dictionary containing behavioral metrics
        """
        try:
            converted_metrics = self._convert_numpy_types(metrics)
            
            # Ajouter le timestamp actuel pour behavior_analysis_time
            current_time = datetime.now()
            
            query = """
                UPDATE wallet_stats 
                SET 
                    is_bot = %(is_bot)s,
                    bot_probability = %(bot_probability)s,
                    total_swaps = %(total_swaps)s,
                    behavior_analysis_time = %(behavior_analysis_time)s,
                    last_updated = CURRENT_TIMESTAMP
                WHERE address = %(address)s;
                
                INSERT INTO wallet_stats (
                    address, is_bot, bot_probability, 
                    total_swaps, behavior_analysis_time, last_updated
                )
                VALUES (
                    %(address)s, %(is_bot)s, %(bot_probability)s,
                    %(total_swaps)s, %(behavior_analysis_time)s, CURRENT_TIMESTAMP
                )
                ON CONFLICT (address) DO NOTHING;
            """
            
            params = {
                **converted_metrics,
                'address': address,
                'behavior_analysis_time': current_time
            }
            
            self.cursor.execute(query, params)
            self.connection.commit()
            self.logger.info(f"Successfully updated behavioral metrics for wallet: {address}")

        except Exception as e:
            self.logger.error(f"Error updating behavioral metrics: {e}")
            self.connection.rollback()
            raise

    def close(self) -> None:
        """Close database connection"""
        try:
            if self.cursor:
                self.cursor.close()
            if self.connection:
                self.connection.close()
                self.logger.info("Database connection closed successfully")
        except Exception as e:
            self.logger.error(f"Error closing database connection: {e}")

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.close()
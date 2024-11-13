# metrics_calculator.py
from typing import Dict, List, Any, Optional
from decimal import Decimal
from dataclasses import dataclass
from datetime import datetime
import pandas as pd

@dataclass
class TokenMetrics:
    realized_pnl: Decimal = Decimal('0')
    unrealized_pnl: Decimal = Decimal('0')
    usd_invested: Decimal = Decimal('0')
    usd_withdrawn: Decimal = Decimal('0')
    balance: Decimal = Decimal('0')
    trade_count: int = 0
    first_trade_date: Optional[int] = None
    last_trade_date: Optional[int] = None

class MetricsCalculator:
    def __init__(self, logger, config, price_service, file_service):
        """
        Initialise le calculateur de métriques
        
        Args:
            logger: Logger pour les messages
            config: Configuration globale
            price_service: Service de gestion des prix
            file_service: Service de gestion des fichiers
        """
        self.logger = logger
        self.config = config
        self.price_service = price_service
        self.file_service = file_service
        self.token_metrics: Dict[str, TokenMetrics] = {}

    def _process_token_swap(self, 
                          token_data: Dict[str, Any], 
                          is_input: bool, 
                          timestamp: int,
                          sol_price: Decimal) -> None:
        """
        Traite un token dans un swap
        
        Args:
            token_data: Données du token
            is_input: True si token en entrée, False si en sortie
            timestamp: Timestamp du swap
            sol_price: Prix du SOL au moment du swap
        """
        symbol = token_data['symbol']
        amount = Decimal(str(token_data['amount']))

        if symbol not in self.token_metrics:
            self.token_metrics[symbol] = TokenMetrics(
                first_trade_date=timestamp,
                last_trade_date=timestamp
            )
        
        metrics = self.token_metrics[symbol]
        metrics.last_trade_date = timestamp
        metrics.trade_count += 1

        # Calculer la valeur en USD
        if symbol in self.config.SOLANA_ADDRESSES:
            usd_value = amount * sol_price
        else:
            usd_value = self._calculate_token_value(symbol, amount, timestamp)
            if usd_value is None:
                return

        if is_input:
            metrics.usd_invested += usd_value
            metrics.balance -= amount
        else:
            metrics.usd_withdrawn += usd_value
            metrics.balance += amount
    def _calculate_token_value(self, 
                         symbol: str, 
                         amount: Decimal, 
                         timestamp: int) -> Optional[Decimal]:
        """
        Calcule la valeur en USD d'un token donné
        
        Args:
            symbol: Symbole du token
            amount: Montant du token
            timestamp: Timestamp pour le prix
            
        Returns:
            Optional[Decimal]: Valeur en USD ou None si prix non trouvé
        """
        try:
            if symbol in self.config.SOLANA_ADDRESSES:
                sol_price = self.price_service.get_sol_price(timestamp)
                if sol_price is None:
                    self.logger.warning(f"Could not get SOL price at {timestamp}")
                    return None
                return amount * sol_price
                
            # Pour les autres tokens, essayer d'abord d'obtenir le prix en SOL
            sol_price = self.price_service.get_sol_price(timestamp)
            if sol_price is None:
                self.logger.warning("Could not get SOL price for token conversion")
                return None
                
            # Essayer d'obtenir le prix du token en SOL
            token_price_in_sol = self.price_service.get_token_price_in_sol(symbol, timestamp)
            if token_price_in_sol is not None:
                return amount * token_price_in_sol * sol_price
                
            # Si pas de prix en SOL, essayer d'obtenir le prix en USD directement
            token_price_in_usd = self.price_service.get_token_price_in_usd(symbol, timestamp)
            if token_price_in_usd is not None:
                return amount * token_price_in_usd
                
            self.logger.warning(f"Could not get price for {symbol} at {timestamp}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error calculating value for {symbol}: {e}")
            return None

    def process_swap(self, swap: Dict[str, Any]) -> None:
        """
        Traite un swap complet
        
        Args:
            swap: Données du swap
        """
        timestamp = swap.get('timestamp')
        if not timestamp:
            self.logger.warning("Swap without timestamp, skipping")
            return

        # Obtenir le prix du SOL pour ce swap
        sol_price = self.price_service.get_sol_price(timestamp)
        if sol_price is None:
            self.logger.warning(f"Could not get SOL price for timestamp {timestamp}")
            return

        # Traiter les tokens en entrée
        for token_in in swap['tokens_in']:
            self._process_token_swap(token_in, True, timestamp, sol_price)

        # Traiter les tokens en sortie
        for token_out in swap['tokens_out']:
            self._process_token_swap(token_out, False, timestamp, sol_price)

    def calculate_unrealized_pnl(self) -> None:
        """
        Calcule le PnL non réalisé pour tous les tokens
        """
        current_time = int(datetime.now().timestamp())
        
        for symbol, metrics in self.token_metrics.items():
            if metrics.balance <= 0:
                metrics.unrealized_pnl = Decimal('0')
                continue

            if symbol in self.config.SOLANA_ADDRESSES:
                current_price = self.price_service.get_sol_price(current_time)
            else:
                current_price = self.price_service.get_token_price(symbol, current_time)

            if current_price is not None:
                metrics.unrealized_pnl = metrics.balance * current_price
            else:
                self.logger.warning(f"Could not calculate unrealized PnL for {symbol}")
                metrics.unrealized_pnl = Decimal('0')

    def calculate_realized_pnl(self) -> None:
        """
        Calcule le PnL réalisé pour tous les tokens
        """
        for symbol, metrics in self.token_metrics.items():
            if metrics.usd_invested > 0 and metrics.usd_withdrawn == 0 and metrics.balance > 0:
                metrics.realized_pnl = Decimal('0')
            elif metrics.balance < 0:
                metrics.realized_pnl = Decimal('0')
            else:
                metrics.realized_pnl = metrics.usd_withdrawn - metrics.usd_invested

    def calculate_metrics(self, swaps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calcule toutes les métriques pour une liste de swaps
        
        Args:
            swaps: Liste des swaps à analyser
            
        Returns:
            Dict contenant toutes les métriques calculées
        """
        self.token_metrics.clear()
        
        # Traiter tous les swaps
        for swap in swaps:
            print(swap)
            self.process_swap(swap)

        # Calculer les PnL
        self.calculate_realized_pnl()
        self.calculate_unrealized_pnl()

        # Calcul des métriques globales
        total_metrics = {
            'total_realized_pnl': Decimal('0'),
            'total_unrealized_pnl': Decimal('0'),
            'gross_profit': Decimal('0'),
            'total_invested': Decimal('0'),
            'total_trades': 0,
            'total_volume': Decimal('0'),
            'winning_trades': 0,
            'total_token_traded': len(self.token_metrics)
        }

        # Agréger les métriques de tous les tokens
        for metrics in self.token_metrics.values():
            total_metrics['total_realized_pnl'] += metrics.realized_pnl
            total_metrics['total_unrealized_pnl'] += metrics.unrealized_pnl
            total_metrics['total_invested'] += metrics.usd_invested
            total_metrics['total_trades'] += metrics.trade_count
            total_metrics['total_volume'] += metrics.usd_invested + metrics.usd_withdrawn
            
            # Compter les trades gagnants
            if (metrics.usd_withdrawn + metrics.unrealized_pnl) > metrics.usd_invested:
                total_metrics['winning_trades'] += 1

        # Calculer le profit brut
        total_metrics['gross_profit'] = (
            total_metrics['total_realized_pnl'] + 
            total_metrics['total_unrealized_pnl']
        )

        # Calculer les ratios
        if total_metrics['total_token_traded'] > 0:
            total_metrics['win_rate'] = (
                total_metrics['winning_trades'] / 
                total_metrics['total_token_traded'] * 100
            )
        else:
            total_metrics['win_rate'] = 0

        if total_metrics['total_invested'] > 0:
            total_metrics['total_roi'] = (
                total_metrics['gross_profit'] / 
                total_metrics['total_invested'] * 100
            )
        else:
            total_metrics['total_roi'] = 0

        # Convertir les Decimal en float pour la sérialisation JSON
        return {
            k: float(v) if isinstance(v, Decimal) else v 
            for k, v in total_metrics.items()
        }

    def generate_token_summary(self) -> List[Dict[str, Any]]:
        """
        Génère un résumé détaillé par token
        
        Returns:
            Liste des résumés par token
        """
        summary = []
        for symbol, metrics in self.token_metrics.items():
            summary.append({
                'token': symbol,
                'usd_invested': float(metrics.usd_invested),
                'usd_withdrawn': float(metrics.usd_withdrawn),
                'balance': float(metrics.balance),
                'trade_count': metrics.trade_count,
                'first_trade_date': metrics.first_trade_date,
                'last_trade_date': metrics.last_trade_date,
                'realized_pnl': float(metrics.realized_pnl),
                'unrealized_pnl': float(metrics.unrealized_pnl)
            })
        return summary
    
    def analyze_behavior(self, analysis: Dict) -> Dict[str, Any]:
        """
        Analyse le comportement du wallet
        """
        try:
            return {
                'is_bot': analysis['bot_probability'] >= self.config.BOT_THRESHOLD,
                'bot_probability': float(analysis['bot_probability']),  # Assurez-vous que c'est un float
                'total_swaps': len(analysis.get('swaps', [])),
                'analysis_time': float(analysis.get('execution_time', 0)),  # Assurez-vous que c'est un float
                'transactions_analyzed': int(analysis.get('total_transactions', 0)),  # Convertir en int
            }
        except Exception as e:
            self.logger.error(f"Error in analyze_behavior: {str(e)}")
            # Retourner des valeurs par défaut en cas d'erreur
            return {
                'is_bot': False,
                'bot_probability': 0.0,
                'total_swaps': 0,
                'analysis_time': 0.0,
                'transactions_analyzed': 0
            }

    def save_metrics_to_file(self, address: str, metrics: Dict[str, Any]) -> None:
        """
        Sauvegarde les métriques calculées dans un fichier
        """
        data = {
            'address': address,
            'metrics': metrics,
            'token_summary': self.generate_token_summary(),
            'timestamp': int(datetime.now().timestamp())
        }
        self.file_service.save_analysis_result(address, data, subfolder='metrics')
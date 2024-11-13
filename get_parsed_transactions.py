# analyzer.py
import requests
import time
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import joblib
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
import json

class SolanaSwapAnalyzer:
    def __init__(self, logger, config):
        """
        Initialise l'analyseur Solana
        
        Args:
            logger: Logger pour les messages
            config: Instance de la classe Config
        """
        self.logger = logger
        self.config = config
        self.last_request_time = 0
        self.request_count = 0

        # Charger le modèle de détection des bots
        try:
            self.model = joblib.load(self.config.MODEL_PATH)
            self.logger.info("Bot detection model loaded successfully")
        except Exception as e:
            self.logger.error(f"Failed to load bot detection model: {e}")
            self.model = None

    def analyze_wallet(self, address: str, max_transactions: Optional[int] = None) -> Dict:
        """
        Analyse complète d'un wallet Solana
        
        Args:
            address: Adresse du wallet à analyser
            max_transactions: Nombre maximum de transactions à analyser (optional)
            
        Returns:
            Dict contenant les résultats de l'analyse
        """
        self.logger.info(f"Starting analysis for wallet: {address}")
        
        # Utiliser la valeur par défaut de la config si non spécifiée
        max_transactions = max_transactions or self.config.DEFAULT_NBR_TRANSACTIONS
        
        all_transactions = []
        swaps_data = []
        start_time = time.time()
        
        # Récupérer les signatures
        sig_response = self._make_rpc_request(
            "getSignaturesForAddress",
            [address, {"limit": max_transactions}]
        )
        
        if "error" in sig_response:
            self.logger.error("Failed to fetch signatures")
            return {"error": "Error fetching signatures"}
        
        signatures = sig_response.get('result', [])
        total_sigs = len(signatures)
        self.logger.info(f"Found {total_sigs} transactions to analyze")
        
        early_detection_triggered = False
        
        # Analyser chaque transaction
        for idx, sig_info in enumerate(signatures, 1):
            self.logger.debug(f"Processing transaction {idx}/{total_sigs}")
            
            transaction = self._get_transaction(sig_info['signature'])
            if not transaction:
                continue
                
            all_transactions.append(transaction)
            
            # Détecter et analyser les swaps
            if swap_info := self._process_swap(transaction, sig_info):
                swaps_data.append(swap_info)
            
            # Détection précoce des bots
            if (len(all_transactions) == self.config.EARLY_DETECTION_COUNT and 
                 self._perform_early_detection(all_transactions)):
                early_detection_triggered = True
                break
            
            time.sleep(self.config.TRANSACTION_PROCESSING_DELAY)
        
        # Classification finale
        final_bot_probability = self._calculate_bot_probability(all_transactions)
        
        execution_time = time.time() - start_time
        self.logger.info(f"Analysis completed in {execution_time:.2f} seconds")
        
        return {
            'wallet_address': address,
            'total_transactions': len(all_transactions),
            'bot_probability': final_bot_probability,
            'early_detection': {
                'triggered': early_detection_triggered,
                'transactions_analyzed': len(all_transactions)
            },
            'swaps': swaps_data,
            'execution_time': execution_time
        }

    def get_wallet_swaps(self, address: str, max_transactions: Optional[int] = None) -> List[Dict]:
        """
        Récupère uniquement les swaps d'un wallet
        """
        self.logger.info(f"Fetching swaps for wallet: {address}")
        analysis = self.analyze_wallet(address, max_transactions)
        swaps = analysis.get('swaps', [])
        self.logger.info(f"Found {len(swaps)} swaps")
        return swaps

    def _make_rpc_request(self, method: str, params: List) -> Dict:
        """
        Effectue une requête RPC avec gestion du rate limiting
        """
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < self.config.RATE_LIMIT['min_interval']:
            time.sleep(self.config.RATE_LIMIT['min_interval'] - time_since_last)
        
        try:
            response = requests.post(
                self.config.SOLANA_RPC_URL,
                headers={"Content-Type": "application/json"},
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params
                },
                timeout=self.config.RPC_TIMEOUT
            )
            response.raise_for_status()
            self.last_request_time = time.time()
            return response.json()
            
        except Exception as e:
            self.logger.error(f"RPC request failed: {e}")
            return {"error": str(e)}

    def _get_transaction(self, signature: str) -> Optional[Dict]:
        """
        Récupère les détails d'une transaction
        """
        response = self._make_rpc_request(
            "getTransaction",
            [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}]
        )
        
        if "error" in response or not response.get('result'):
            return None
            
        return response['result']

    def _process_swap(self, transaction: Dict, sig_info: Dict) -> Optional[Dict]:
        """
        Traite une transaction pour détecter et analyser un swap
        """
        is_swap, protocol = self._is_swap_transaction(transaction)
        if not is_swap:
            return None
            
        tokens_in, tokens_out = self._analyze_token_changes(transaction)
        if not (tokens_in or tokens_out):
            return None
            
        return {
            'signature': sig_info['signature'],
            'timestamp': sig_info.get('blockTime'),
            'protocol': protocol,
            'tokens_in': [{'amount': amount, 'symbol': symbol} for amount, symbol in tokens_in],
            'tokens_out': [{'amount': amount, 'symbol': symbol} for amount, symbol in tokens_out]
        }

    def _perform_early_detection(self, transactions: List[Dict]) -> bool:
        """
        Effectue une détection précoce des bots
        """
        if not self.model:
            return False
            
        try:
            features = self._extract_features(transactions)
            features_df = pd.DataFrame([features])
            probability = self.model.predict_proba(features_df)[0][1]
            
            if probability >= self.config.BOT_THRESHOLD:
                self.logger.warning(f"Bot behavior detected early with {probability:.2%} probability")
                return True
                
        except Exception as e:
            self.logger.error(f"Early detection failed: {e}")
        
        return False

    def _calculate_bot_probability(self, transactions: List[Dict]) -> float:
        """
        Calcule la probabilité finale qu'un wallet soit un bot
        """
        if not self.model or not transactions:
            return 0.0
            
        try:
            features = self._extract_features(transactions)
            features_df = pd.DataFrame([features])
            probability = float(self.model.predict_proba(features_df)[0][1])
            self.logger.info(f"Final bot probability: {probability:.2%}")
            return probability
            
        except Exception as e:
            self.logger.error(f"Final classification failed: {e}")
            return 0.0

    def _analyze_token_changes(self, transaction: Dict) -> Tuple[List[Tuple[float, str]], List[Tuple[float, str]]]:
        """Analyse les changements de balance de tokens dans une transaction"""
        try:
            pre_balances = {}
            post_balances = {}
            
            # Analyser les balances pre-transaction
            for balance in transaction.get('meta', {}).get('preTokenBalances', []):
                mint = balance.get('mint')
                if not mint:
                    continue
                    
                token_data = balance.get('uiTokenAmount', {})
                amount = float(token_data.get('uiAmount', 0) or 0)
                # Utiliser le mint comme symbole si aucun symbole n'est fourni
                symbol = token_data.get('symbol') or mint[:8]
                
                pre_balances[mint] = {
                    'amount': amount,
                    'symbol': symbol
                }
            
            # Analyser les balances post-transaction
            for balance in transaction.get('meta', {}).get('postTokenBalances', []):
                mint = balance.get('mint')
                if not mint:
                    continue
                    
                token_data = balance.get('uiTokenAmount', {})
                amount = float(token_data.get('uiAmount', 0) or 0)
                symbol = token_data.get('symbol') or mint[:8]
                
                post_balances[mint] = {
                    'amount': amount,
                    'symbol': symbol
                }
            
            tokens_in = []
            tokens_out = []
            
            # Calculer les différences
            all_mints = set(list(pre_balances.keys()) + list(post_balances.keys()))
            
            for mint in all_mints:
                pre_amount = pre_balances.get(mint, {'amount': 0})['amount']
                post_amount = post_balances.get(mint, {'amount': 0})['amount']
                symbol = post_balances.get(mint, {'symbol': mint[:8]})['symbol']
                
                diff = post_amount - pre_amount
                if abs(diff) > 0.000001:  # Seuil minimal pour éviter le bruit
                    if diff > 0:
                        tokens_in.append((abs(diff), symbol))
                    else:
                        tokens_out.append((abs(diff), symbol))
            
            return tokens_in, tokens_out
            
        except Exception as e:
            self.logger.error(f"Error analyzing token changes: {str(e)}")
            return [], []
    
    def _is_swap_transaction(self, transaction: Dict) -> Tuple[bool, str]:
        """Vérifie si une transaction est un swap et retourne le protocole"""
        self.logger.debug("Vérification si la transaction est un swap...")
        
        message = transaction.get('transaction', {}).get('message', {})
        instructions = message.get('instructions', [])
        logs = transaction.get('meta', {}).get('logMessages', [])
        
        # Vérification dans les instructions
        for instruction in instructions:
            program_id = instruction.get('programId')
            if program_id in self.config.SWAP_PROGRAMS:
                protocol = self.config.SWAP_PROGRAMS[program_id]
                self.logger.debug(f"Swap détecté - Protocol: {protocol}")
                return True, protocol
        
        # Vérification dans les logs
        if logs:
            for program_id, protocol in self.config.SWAP_PROGRAMS.items():
                if any(program_id in log for log in logs):
                    self.logger.debug(f"Swap détecté dans les logs - Protocol: {protocol}")
                    return True, protocol
        
        self.logger.debug("Aucun swap détecté")
        return False, ""

    def _extract_features(self, transactions: List[Dict]) -> Dict:
        """Extrait les caractéristiques des transactions pour la classification"""
        self.logger.info("Extraction des features pour la classification...")
        
        # Dictionnaire pour stocker les features extraites
        raw_features = {}
        
        # Caractéristiques temporelles de base
        timestamps = [tx.get('blockTime', 0) for tx in transactions]
        if len(timestamps) > 1:
            time_diffs = np.diff(timestamps)
            raw_features['avg_time_between_tx'] = np.mean(time_diffs)
            raw_features['time_variance'] = np.std(time_diffs)
        else:
            raw_features['avg_time_between_tx'] = 0
            raw_features['time_variance'] = 0
        
        self.logger.debug(f"Features temporelles extraites")
        
        # Caractéristiques des transactions
        raw_features['total_transactions'] = len(transactions)
        
        # Analyse des frais
        fees = [tx.get('meta', {}).get('fee', 0) for tx in transactions]
        raw_features['avg_fee'] = np.mean(fees) if fees else 0
        raw_features['std_fee'] = np.std(fees) if fees else 0
        
        # Analyse des instructions
        instruction_counts = [len(tx.get('transaction', {}).get('message', {}).get('instructions', [])) 
                            for tx in transactions]
        raw_features['avg_instructions_per_tx'] = np.mean(instruction_counts) if instruction_counts else 0
        raw_features['instruction_complexity_score'] = np.std(instruction_counts) if instruction_counts else 0
        
        # Calcul du temps moyen entre transactions pour chaque compte
        account_time_pairs = defaultdict(list)
        for tx in transactions:
            accounts = []
            message = tx.get('transaction', {}).get('message', {})
            if 'accountKeys' in message:
                for acc in message['accountKeys']:
                    if isinstance(acc, dict):
                        acc_key = acc.get('pubkey', '')
                    else:
                        acc_key = acc
                    accounts.append(acc_key)
            
            timestamp = tx.get('blockTime', 0)
            for account in accounts:
                account_time_pairs[account].append(timestamp)
        
        account_avg_times = []
        for timestamps in account_time_pairs.values():
            if len(timestamps) > 1:
                times_sorted = sorted(timestamps)
                time_diffs = np.diff(times_sorted)
                if len(time_diffs) > 0:
                    account_avg_times.append(np.mean(time_diffs))
        
        raw_features['avg_time_between_account_tx'] = np.mean(account_avg_times) if account_avg_times else 0
        
        # Diversité des comptes
        all_accounts = []
        for tx in transactions:
            message = tx.get('transaction', {}).get('message', {})
            accounts = message.get('accountKeys', [])
            all_accounts.extend([acc.get('pubkey', '') if isinstance(acc, dict) else acc for acc in accounts])
        
        unique_accounts = set(all_accounts)
        raw_features['unique_accounts_count'] = len(unique_accounts)
        raw_features['account_diversity_score'] = len(unique_accounts) / len(all_accounts) if all_accounts else 0
        
        # Interactions avec le programme système
        system_program = '11111111111111111111111111111111'
        system_interactions = sum(1 for tx in transactions 
                                if system_program in [acc.get('pubkey', '') if isinstance(acc, dict) else acc 
                                                    for acc in tx.get('transaction', {}).get('message', {}).get('accountKeys', [])])
        raw_features['system_program_interaction_ratio'] = system_interactions / len(transactions) if transactions else 0
        
        # Extraction des signatures
        signatures = []
        for tx in transactions:
            tx_signatures = tx.get('transaction', {}).get('signatures', [])
            signatures.extend(tx_signatures)
        
        raw_features['signature_entropy'] = self._calculate_entropy(signatures) if signatures else 0
        
        # Variations de slots
        slots = [tx.get('slot', 0) for tx in transactions]
        raw_features['slot_variation'] = np.std(slots) if slots else 0
        
        # Liste ordonnée des features comme dans le modèle entraîné
        ordered_feature_names = [
            'total_transactions',
            'avg_fee',
            'std_fee',
            'avg_time_between_tx',
            'time_variance',
            'avg_time_between_account_tx',
            'unique_accounts_count',
            'account_diversity_score',
            'avg_instructions_per_tx',
            'instruction_complexity_score',
            'system_program_interaction_ratio',
            'signature_entropy',
            'slot_variation'
        ]
        
        # Création du DataFrame avec l'ordre correct des features
        features_ordered = {name: raw_features.get(name, 0) for name in ordered_feature_names}
        
        # Vérification que toutes les features sont présentes
        missing_features = [feat for feat in ordered_feature_names if feat not in raw_features]
        if missing_features:
            self.logger.error(f"Features manquantes: {missing_features}")
            raise ValueError(f"Features manquantes: {missing_features}")
        
        self.logger.info("Extraction des features terminée avec succès")
        self.logger.debug(f"Features extraites: {features_ordered}")
        
        # Retourne le dictionnaire des features dans l'ordre correct
        return features_ordered
    def _calculate_entropy(self, data):
        """Calcule l'entropie d'une liste de données"""
        if not data:
            return 0
        
        counts = Counter(data)
        probabilities = [count/len(data) for count in counts.values()]
        return -sum(p * np.log2(p) for p in probabilities)
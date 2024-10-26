# pnl_calculation.py
import os
import pandas as pd
from datetime import datetime
from price_utils import get_sol_price_at_time, get_token_prices, load_sol_price_cache
from config import (
    EXCLUDED_TOKENS, SOLANA_ADDRESSES, INCLUDED_ACTIVITY_TYPES,
    OUTPUT_FOLDER
)
from file_utils import round_to_nearest_hour

def process_transaction(row, price_cache, pnl_tracker, logger):
    # Fonction qui traite une transaction unique et met à jour les métriques PnL
    # input: row (ligne de transaction), price_cache (cache des prix), pnl_tracker (dictionnaire des PnL), logger (pour les logs)
    # output: met à jour pnl_tracker avec les nouvelles valeurs PnL pour la transaction
    token1, token2 = row['token1'], row['token2']
    amount1, amount2 = row['amount1'], row['amount2']
    dt = round_to_nearest_hour(row['block_time'].timestamp())

    # Ignorer les transactions avec des tokens exclus
    if token1 in EXCLUDED_TOKENS or token2 in EXCLUDED_TOKENS:
        logger.debug(f"Skipping transaction with excluded token(s): {token1}, {token2}")
        return

    # Ignorer les transactions qui n'impliquent pas SOL ou WSOL
    if token1 not in SOLANA_ADDRESSES and token2 not in SOLANA_ADDRESSES:
        logger.debug(f"Skipping non-Solana transaction: {token1}, {token2}")
        return

    # Récupérer le prix du SOL au moment de la transaction
    sol_price_at_time = get_sol_price_at_time(dt, price_cache, logger)
    if sol_price_at_time is None:
        logger.warning(f"Unable to process transaction due to missing SOL price for {dt}")
        return

    # Calculer le montant investi ou retiré en USD
    usd_invested = amount1 * sol_price_at_time if token1 in SOLANA_ADDRESSES else 0
    usd_withdrawn = amount2 * sol_price_at_time if token2 in SOLANA_ADDRESSES else 0

    target_token = token2 if token1 in SOLANA_ADDRESSES else token1
    if target_token not in pnl_tracker:
        # Initialiser le tracker PnL pour le token s'il n'existe pas
        pnl_tracker[target_token] = {
            'realized': 0, 'unrealized': 0, 'usd_invested': 0, 'usd_withdrawn': 0, 'balance': 0,
            'trade_count': 0, 'first_trade_date': dt, 'last_trade_date': dt
        }

    pnl = pnl_tracker[target_token]
    if token1 in SOLANA_ADDRESSES:
        pnl['usd_invested'] += usd_invested
        pnl['balance'] += amount2
        logger.debug(f"Processed buy transaction for {target_token}: ${usd_invested} invested, balance: {pnl['balance']}")
    else:
        pnl['usd_withdrawn'] += usd_withdrawn
        pnl['balance'] -= amount1
        logger.debug(f"Processed sell transaction for {target_token}: ${usd_withdrawn} withdrawn, balance: {pnl['balance']}")

    pnl['last_trade_date'] = dt
    pnl['trade_count'] += 1

def calculate_unrealized_pnl(pnl_tracker, price_cache, logger):
    # Fonction pour calculer le PnL non réalisé pour chaque token avec un solde positif
    # input: pnl_tracker (dictionnaire des PnL), price_cache (cache des prix), logger (pour les logs)
    # output: met à jour les valeurs non réalisées dans pnl_tracker
    tokens = [token for token, pnl in pnl_tracker.items() if pnl['balance'] > 0]
    prices = get_token_prices(tokens, price_cache, logger)

    for token, pnl in pnl_tracker.items():
        if pnl['balance'] > 0:
            price = prices.get(token)
            if price is not None:
                pnl['unrealized'] = pnl['balance'] * price
                logger.debug(f"Unrealized PnL for {token}: ${pnl['unrealized']}")
            else:
                pnl['unrealized'] = 0

def calculate_pnl_and_generate_summary(logger, file_path, output_folder, start_date=None):
    # Fonction principale pour calculer le PnL et générer un résumé des transactions
    # input: logger (pour les logs), file_path (chemin du fichier CSV), output_folder (dossier de sortie), start_date (date de début optionnelle)
    # output: retourne un dictionnaire contenant les métriques calculées
    logger.info(f"Starting PnL calculation for file: {file_path}")

    # Charger et filtrer les transactions du fichier CSV
    df = pd.read_csv(file_path)
    df = df[df['activity_type'].isin(INCLUDED_ACTIVITY_TYPES)]
    df['block_time'] = pd.to_datetime(df['block_time'], unit='s')

    if start_date:
        df = df[df['block_time'] >= start_date]
        logger.info(f"Filtered transactions from {start_date}, {len(df)} transactions remaining")

    # Convertir les montants en tenant compte des décimales
    df['amount1'] = df['amount1'] / (10 ** df['decimal1'])
    df['amount2'] = df['amount2'] / (10 ** df['decimal2'])
    df = df.iloc[::-1].reset_index(drop=True)

    pnl_tracker = {}
    summary_data = []
    winning_trades, gross_profit, total_invested, total_unrealized_pnl, total_realized_pnl, total_trades, total_volume = 0, 0, 0, 0, 0, 0, 0

    price_cache = load_sol_price_cache(logger)

    # Traiter chaque transaction
    logger.info(f"Processing {len(df)} transactions")
    for _, row in df.iterrows():
        process_transaction(row, price_cache, pnl_tracker, logger)

    # Calculer le PnL réalisé
    logger.info("Calculating realized PnL")
    for token, pnl in pnl_tracker.items():
        if pnl['usd_invested'] > 0 and pnl['usd_withdrawn'] == 0 and pnl['balance'] > 0:
            pnl['realized'] = 0
        elif pnl['balance'] < 0:
            pnl['realized'] = 0 # ignore cases where can be insider or buy is from a long time ago.
        else:
            pnl['realized'] = pnl['usd_withdrawn'] - pnl['usd_invested']
        logger.debug(f"Realized PnL for {token}: ${pnl['realized']}")

    # Calculer le PnL non réalisé
    logger.info("Calculating unrealized PnL")
    calculate_unrealized_pnl(pnl_tracker, price_cache, logger)

    # Créer un résumé des résultats
    for token, pnl in pnl_tracker.items():
        summary_data.append({
            'Token': token,
            'USD invested': pnl['usd_invested'],
            'USD withdrawn': pnl['usd_withdrawn'],
            'Balance': pnl['balance'],
            'Number of trades': pnl['trade_count'],
            'First trade date': pnl['first_trade_date'],
            'Last trade date': pnl['last_trade_date'],
            'Realized PnL (USD)': pnl['realized'],
            'Unrealized PnL (USD)': pnl['unrealized']
        })
        if (pnl['usd_withdrawn'] + pnl['unrealized']) > pnl['usd_invested']:
            winning_trades += 1

    summary_df = pd.DataFrame(summary_data)
    address = os.path.splitext(os.path.basename(file_path))[0]
    output_file = os.path.join(output_folder, f"{address}_summary.csv")
    summary_df.to_csv(output_file, mode='w', index=False)
    logger.info(f"Saved summary to {output_file}")

    total_token_traded = len(pnl_tracker)

    # Calculer les métriques finales
    for token, pnl in pnl_tracker.items():
        gross_profit += (pnl['usd_withdrawn'] + pnl['unrealized']) - pnl['usd_invested']
        total_invested += pnl['usd_invested']
        total_unrealized_pnl += pnl['unrealized']
        total_realized_pnl += pnl['realized']
        total_trades += pnl['trade_count']
        total_volume += (pnl['usd_withdrawn'] + pnl['usd_invested'])

    # Calculer le taux de réussite et le ROI
    win_rate = (winning_trades / total_token_traded) * 100 if total_trades > 0 else 0
    total_roi = (gross_profit / total_invested) * 100 if total_invested > 0 else 0

    results = {
        'total_realized_pnl': total_realized_pnl,
        'total_unrealized_pnl': total_unrealized_pnl,
        'gross_profit': gross_profit,
        'win_rate': win_rate,
        'total_roi': total_roi,
        'total_invested': total_invested,
        'total_trades': total_trades,
        'total_volume': total_volume,
        'total_token_traded': total_token_traded
    }
    return results

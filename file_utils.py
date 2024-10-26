# file_utils.py
import os
from datetime import datetime, timedelta

def clear_input_folder(folder_path):
    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)


def round_to_nearest_hour(timestamp):
    dt = datetime.fromtimestamp(timestamp)
    # Calcul de l'arrondi à l'heure la plus proche
    rounded_hour = dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1 if dt.minute >= 30 else 0)
    
    # Vérification si l'heure arrondie est dans le futur
    now = datetime.now()
    if rounded_hour > now:
        # Si oui, on revient de 2 heures en arrière
        rounded_hour -= timedelta(hours=2)
    return rounded_hour

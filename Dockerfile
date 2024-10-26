# Utiliser une image de base Python
FROM python:3.11

# Définir le répertoire de travail
WORKDIR /app

# Copier les fichiers de l'application dans le conteneur
COPY . /app

# Installer les dépendances
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install urllib3==1.26.5
RUN pip install --upgrade cfscrape
RUN pip install --upgrade scrapy
RUN pip install --upgrade scrapy_cloudflare_middleware



# Définir la commande à exécuter lors du démarrage du conteneur
CMD ["python", "process_wallet.py"]

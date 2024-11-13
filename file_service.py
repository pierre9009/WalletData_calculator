# file_service.py
import os
import shutil
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import json
from pathlib import Path
import time

class FileService:
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Crée les répertoires nécessaires"""
        directories = [
            self.config.ANALYSIS_OUTPUT_DIR,
            self.config.ARCHIVE_DIR,
            self.config.CACHE_DIR,
            self.config.TEMP_DIR
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            self.logger.debug(f"Ensured directory exists: {directory}")

    def clear_directory(self, directory: str, pattern: Optional[str] = None) -> None:
        """Nettoie un répertoire"""
        try:
            path = Path(directory)
            if not path.exists():
                return
                
            for item in path.iterdir():
                if item.is_file():
                    if pattern is None or item.match(pattern):
                        item.unlink()
                        self.logger.debug(f"Deleted file: {item}")
            
            self.logger.info(f"Directory cleaned: {directory}")
        except Exception as e:
            self.logger.error(f"Error clearing directory {directory}: {e}")

    def cleanup_temp_files(self) -> None:
        """Nettoie les fichiers temporaires"""
        self.clear_directory(self.config.TEMP_DIR)

class AnalysisFileManager:
    def __init__(self, file_service: FileService):
        self.file_service = file_service
        self.logger = file_service.logger
        self.config = file_service.config

    def save_wallet_analysis(self, address: str, analysis_data: Dict) -> str:
        """
        Sauvegarde l'analyse d'un wallet avec organisation par date
        """
        try:
            date_folder = datetime.now().strftime("%Y-%m-%d")
            output_dir = Path(self.config.ANALYSIS_OUTPUT_DIR) / date_folder
            output_dir.mkdir(parents=True, exist_ok=True)
            
            filename = f"{address}_{int(time.time())}.json"
            file_path = output_dir / filename
            
            with open(file_path, 'w') as f:
                json.dump(analysis_data, f, indent=2, default=str)
            
            self.logger.info(f"Analysis saved to {file_path}")
            return str(file_path)
            
        except Exception as e:
            self.logger.error(f"Error saving analysis for {address}: {e}")
            raise

    def get_latest_analysis(self, address: str, max_age_hours: int = 24) -> Optional[Dict]:
        """
        Récupère la dernière analyse pour une adresse
        """
        try:
            output_dir = Path(self.config.ANALYSIS_OUTPUT_DIR)
            cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
            
            latest_file = None
            latest_time = 0
            
            # Rechercher dans tous les sous-dossiers
            for file_path in output_dir.rglob(f"{address}_*.json"):
                file_time = file_path.stat().st_mtime
                if file_time > latest_time and datetime.fromtimestamp(file_time) > cutoff_time:
                    latest_file = file_path
                    latest_time = file_time
            
            if latest_file:
                with open(latest_file, 'r') as f:
                    return json.load(f)
                    
            return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving latest analysis for {address}: {e}")
            return None

    def archive_old_analyses(self, days: int = 30) -> None:
        """
        Archive les anciennes analyses
        """
        try:
            archive_dir = Path(self.config.ARCHIVE_DIR)
            archive_dir.mkdir(parents=True, exist_ok=True)
            
            cutoff_date = datetime.now() - timedelta(days=days)
            output_dir = Path(self.config.ANALYSIS_OUTPUT_DIR)
            
            # Parcourir tous les sous-dossiers
            for date_dir in output_dir.iterdir():
                if not date_dir.is_dir():
                    continue
                    
                try:
                    dir_date = datetime.strptime(date_dir.name, "%Y-%m-%d")
                    if dir_date < cutoff_date:
                        # Créer le dossier d'archive correspondant
                        archive_date_dir = archive_dir / date_dir.name
                        archive_date_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Déplacer tous les fichiers
                        for file_path in date_dir.glob("*.json"):
                            archive_path = archive_date_dir / file_path.name
                            shutil.move(str(file_path), str(archive_path))
                            self.logger.debug(f"Archived {file_path.name}")
                        
                        # Supprimer le dossier source s'il est vide
                        if not any(date_dir.iterdir()):
                            date_dir.rmdir()
                            
                except ValueError:
                    # Ignore les dossiers qui ne suivent pas le format de date
                    continue
                    
            self.logger.info("Archives updated successfully")
            
        except Exception as e:
            self.logger.error(f"Error during archiving: {e}")
            raise

    def get_all_analyses(self, address: str, days: int = 7) -> List[Dict]:
        """
        Récupère toutes les analyses pour une adresse sur une période donnée
        """
        analyses = []
        start_date = datetime.now() - timedelta(days=days)
        
        try:
            output_dir = Path(self.config.ANALYSIS_OUTPUT_DIR)
            for file_path in output_dir.rglob(f"{address}_*.json"):
                if datetime.fromtimestamp(file_path.stat().st_mtime) >= start_date:
                    try:
                        with open(file_path, 'r') as f:
                            analyses.append(json.load(f))
                    except Exception as e:
                        self.logger.error(f"Error reading analysis file {file_path}: {e}")
                    
            return analyses
            
        except Exception as e:
            self.logger.error(f"Error retrieving analyses for {address}: {e}")
            return []
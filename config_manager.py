# config_manager.py
import os
import configparser

class ConfigManager:
    def __init__(self, config_file="config.ini"):
        self.config_file = config_file
        self.config = configparser.ConfigParser()

    def cargar_configuracion(self):
        """Carga la configuración desde el archivo."""
        if os.path.exists(self.config_file):
            self.config.read(self.config_file)
        else:
            self.guardar_configuracion(zona="1", hemisferio="Norte")

    def guardar_configuracion(self, zona, hemisferio):
        """Guarda la configuración en el archivo."""
        self.config["Configuracion"] = {"zona": zona, "hemisferio": hemisferio}
        with open(self.config_file, "w") as f:
            self.config.write(f)

    def obtener_zona(self):
        """Obtiene la zona de la configuración."""
        return self.config.get("Configuracion", "zona", fallback="1")

    def obtener_hemisferio(self):
        """Obtiene el hemisferio de la configuración."""
        return self.config.get("Configuracion", "hemisferio", fallback="Norte")
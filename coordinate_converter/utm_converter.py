# coordinate_converter/utm_converter.py
import utm

def convertir_utm_a_latlon(x, y, zona, hemisferio):
    hemisferio = 'N' if hemisferio == 'Norte' else 'S'
    return utm.to_latlon(float(x), float(y), int(zona), hemisferio)

def convertir_latlon_a_utm(lat, lon):
    """Convierte coordenadas latitud/longitud a UTM."""
    return utm.from_latlon(float(lat), float(lon))

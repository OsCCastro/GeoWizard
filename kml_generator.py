# kml_generator.py
import simplekml

class KMLGenerator:
    def __init__(self, nombre, tipo_geometria, estilos, opacidad):
        self.nombre = nombre
        self.tipo_geometria = tipo_geometria
        self.estilos = estilos
        self.opacidad = opacidad  # Opacidad en porcentaje (1-100)
        self.kml = simplekml.Kml()

    def agregar_coordenadas(self, coordenadas):
        """Agrega coordenadas al archivo KML según el tipo de geometría."""
        if self.tipo_geometria == "Punto":
            for lat, lon in coordenadas:
                punto = self.kml.newpoint(name=self.nombre, coords=[(lon, lat)])
                # Aplicar estilo al punto
                punto.style.iconstyle.icon.href = self.estilos["punto"]["icono"]
                punto.style.iconstyle.color = self._aplicar_opacidad(self.estilos["punto"]["color"], 100)  # Opacidad 100% para íconos
                punto.style.iconstyle.scale = self.estilos["punto"]["escala"]

        elif self.tipo_geometria == "Polilínea":
            linea = self.kml.newlinestring(name=self.nombre, coords=[(lon, lat) for lat, lon in coordenadas])
            # Aplicar estilo a la polilínea
            linea.style.linestyle.color = self._aplicar_opacidad(self.estilos["polilinea"]["color"], self.opacidad)
            linea.style.linestyle.width = self.estilos["polilinea"]["grosor"]

        elif self.tipo_geometria == "Polígono":
            poligono = self.kml.newpolygon(name=self.nombre, outerboundaryis=[(lon, lat) for lat, lon in coordenadas])
            # Aplicar estilo al polígono
            if self.estilos["poligono"]["relleno"]:
                poligono.style.polystyle.color = self._aplicar_opacidad(self.estilos["poligono"]["color_relleno"], self.opacidad)
            if self.estilos["poligono"]["contorno"]:
                poligono.style.linestyle.color = self._aplicar_opacidad(self.estilos["poligono"]["color_borde"], self.opacidad)
                poligono.style.linestyle.width = self.estilos["poligono"]["grosor_borde"]

    def _generar_descripcion(self, coordenadas):
        """Genera una tabla HTML con las coordenadas para la descripción."""
        html = """
        <h3 style="color: #2c3e50; margin-bottom: 10px; border-bottom: 2px solid #3498db; padding-bottom: 5px;">
            Coordenadas del Polígono
        </h3>
        <table style="border-collapse: collapse; width: 100%; margin-bottom: 15px;">
            <thead>
                <tr style="background-color: #3498db; color: white;">
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">No.</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">X</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: center;">Y</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for i, (x, y) in enumerate(coordenadas):
            color_fila = "#f2f2f2" if i % 2 == 0 else "white"
            html += f"""
                <tr style="background-color: {color_fila};">
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{i + 1}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{x:.6f}</td>
                    <td style="padding: 8px; border: 1px solid #ddd; text-align: center;">{y:.6f}</td>
                </tr>
            """
        
        html += """
            </tbody>
        </table>
        <p style="color: #7f8c8d; font-style: italic; text-align: right;">
            Polígono Generado por GeoWizard
        </p>
        """
        return html

    def _aplicar_opacidad(self, color_rrggbb, opacidad):
        """Convierte un color RRGGBB a AABBGGRR con opacidad."""
        # Convertir opacidad (1-100) a hexadecimal (00-FF)
        alpha = int((opacidad / 100) * 255)
        alpha_hex = f"{alpha:02x}"

        # Asegurar que el color esté en formato RRGGBB (6 caracteres)
        color_rrggbb = color_rrggbb.lstrip("#")  # Eliminar "#" si existe
        if len(color_rrggbb) != 6:
            color_rrggbb = "ff0000"  # Rojo por defecto si el formato es incorrecto

        # Separar componentes
        rr = color_rrggbb[0:2]
        gg = color_rrggbb[2:4]
        bb = color_rrggbb[4:6]

        # Formato KML: AABBGGRR
        return f"{alpha_hex}{bb}{gg}{rr}"

    def guardar(self, archivo):
        """Guarda el archivo KML."""
        self.kml.save(archivo)
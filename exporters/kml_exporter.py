# exporters/kml_exporter.py
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from pyproj import Transformer

class KMLExporter:
    @staticmethod
    def export(
        features: list[dict],
        filename: str,
        hemisphere: str,
        zone: str,
        html_dict: dict[int, str] = None
    ):
        """
        Exporta features a un archivo KML, inyectando en la descripción
        (CDATA) el HTML que se indique en html_dict[feat_id]. Si para un
        feat_id no hay entrada en html_dict, usa la descripción UTM por defecto.

        Args:
            features: Lista de features. Cada feature es un dict con {
                "id": valor,            # identificador único del feature
                "type": tipo_geom,      # "Punto"|"Polilínea"|"Polígono"
                "coords": [(x1,y1),...] # lista de tuplas UTM
            }.
            filename: Nombre de archivo KML de salida (debe terminar en .kml).
            hemisphere: "Norte" o "Sur" (string).
            zone: Número de zona UTM (string o int).
            html_dict: (Opcional) Diccionario mapping {feat_id: html_str}.
                       html_str es el bloque de HTML (tabla, párrafos, etc.)
                       que quieres insertar dentro de <description><![CDATA[…]]></description>
                       de ese feature. Si es None o no existe la clave, se usará la descripción UTM.

        Raises:
            ValueError: Si features está vacío, si filename no acaba en ".kml",
                        o si zone/hemi no son válidos.
            RuntimeError: Si ocurre cualquier error al generar o escribir el KML.
        """
        if not features:
            raise ValueError("No hay geometrías para exportar.")

        if not filename.lower().endswith(".kml"):
            raise ValueError("El nombre de archivo debe terminar en .kml")

        # Inicializar html_dict si no se pasa
        if html_dict is None:
            html_dict = {}

        # Validar zona y hemisferio
        try:
            zone_int = int(zone)
            if not (1 <= zone_int <= 60):
                raise ValueError(f"Zona UTM '{zone}' inválida. Debe estar entre 1 y 60.")
            if hemisphere.lower() not in ['norte', 'sur']:
                raise ValueError(f"Hemisferio '{hemisphere}' no reconocido. Debe ser 'Norte' o 'Sur'.")
        except ValueError as e:
            raise ValueError(f"Error en parámetros de zona/hemisferio: {e}")

        try:
            # 1) Definir transformación UTM -> WGS84
            epsg_from = 32600 + zone_int if hemisphere.lower() == "norte" else 32700 + zone_int
            transformer = Transformer.from_crs(f"EPSG:{epsg_from}", "EPSG:4326", always_xy=True)

            # 2) Raíz KML
            kml_root = Element("kml", xmlns="http://www.opengis.net/kml/2.2")
            doc = SubElement(kml_root, "Document")

            for feat in features:
                feat_id   = feat.get("id", None)
                geom_type = feat.get("type", None)
                coords    = feat.get("coords", None)

                # Validar existencia de coords
                if not coords or not isinstance(coords, list):
                    print(f"Advertencia: Feature ID {feat_id} (tipo {geom_type}) no tiene coordenadas. Se omitirá.")
                    continue

                # Crear el Placemark
                pm = SubElement(doc, "Placemark")
                SubElement(pm, "name").text = str(feat_id)

                # Decidir qué descripción (CDATA) usar: HTML personalizado o UTM por defecto
                if feat_id in html_dict and html_dict[feat_id]:
                    # Si existe HTML en el diccionario, lo incrustamos en CDATA
                    raw_html = html_dict[feat_id]
                    desc = SubElement(pm, "description")
                    # Asegurarse de que el string HTML esté completo (<table>…</table>, etc.)
                    desc.text = f"<![CDATA[{raw_html}]]>"
                else:
                    # Si no hay HTML, generamos descripción UTM simple con coords[0]
                    x0, y0 = coords[0]
                    desc_text = (
                        f"Zona: {zone} ({hemisphere})\n"
                        f"Este: {x0:.2f} m\n"
                        f"Norte: {y0:.2f} m"
                    )
                    desc = SubElement(pm, "description")
                    desc.text = f"<![CDATA[{desc_text}]]>"

                # Ahora construir la geometría en WGS84 (lon,lat,0)
                if geom_type == "Punto" or geom_type == "Point":
                    # Sólo un punto
                    geom = SubElement(pm, "Point")
                    lon, lat = transformer.transform(coords[0][0], coords[0][1])
                    SubElement(geom, "coordinates").text = f"{lon:.6f},{lat:.6f},0"

                elif geom_type == "Polilínea" or geom_type == "LineString":
                    # Mínimo 2 coordenadas
                    if len(coords) < 2:
                        continue
                    geom = SubElement(pm, "LineString")
                    coords_text_list = []
                    for x, y in coords:
                        lon, lat = transformer.transform(x, y)
                        coords_text_list.append(f"{lon:.6f},{lat:.6f},0")
                    SubElement(geom, "coordinates").text = " ".join(coords_text_list)

                elif geom_type == "Polígono" or geom_type == "Polygon":
                    # Mínimo 3 coordenadas
                    if len(coords) < 3:
                        continue
                    poly = SubElement(pm, "Polygon")
                    obb  = SubElement(poly, "outerBoundaryIs")
                    lr   = SubElement(obb, "LinearRing")
                    coords_text_list = []
                    # Cerrar el anillo agregando la primera coord al final
                    ring = coords + [coords[0]]
                    for x, y in ring:
                        lon, lat = transformer.transform(x, y)
                        coords_text_list.append(f"{lon:.6f},{lat:.6f},0")
                    SubElement(lr, "coordinates").text = " ".join(coords_text_list)

                else:
                    print(f"Advertencia: Tipo de geometría '{geom_type}' para feature ID {feat_id} no soportado. Se omitirá.")
                    continue

            # Convertir a XML con indentación “bonita”
            xml_bytes = tostring(kml_root, encoding="utf-8", method="xml")
            parsed_xml = minidom.parseString(xml_bytes)
            pretty_kml = parsed_xml.toprettyxml(indent="  ")

            # Escribir el archivo .kml
            with open(filename, "w", encoding="utf-8") as f:
                f.write(pretty_kml)

        except ValueError as ve:
            # Propagar errores de validación
            raise ve
        except Exception as e:
            raise RuntimeError(f"Error durante la generación o escritura del KML: {e}")

# Ejemplo de uso (opcional, para testing directo)
if __name__ == '__main__':
    sample_features_ok = [
        {"id": 1, "type": "Punto", "coords": [(500000.0, 4000000.0)]},
        {"id": 2, "type": "Polilínea", "coords": [(500000.0, 4000000.0), (500100.0, 4000100.0)]},
        {"id": 3, "type": "Polígono", "coords": [(500000.0, 4000000.0), (500100.0, 4000000.0), (500050.0, 4000100.0)]}
    ]
    sample_features_mixed = [
        {"id": "ok_point", "type": "Punto", "coords": [(500000.0, 4000000.0)]},
        {"id": "bad_transform_point", "type": "Punto", "coords": [(99999999.0, 4000000.0)]},
        {"id": "no_coords_point", "type": "Punto", "coords": None},
        {"id": "empty_coords_point", "type": "Punto", "coords": []},
        {"id": "bad_fmt_point", "type": "Punto", "coords": [(500000.0,)]},
        {"id": "ok_line", "type": "Polilínea", "coords": [(500000.0, 4000000.0), (500100.0, 4000100.0)]},
        {"id": "bad_coord_in_line", "type": "Polilínea", "coords": [(500000.0, 4000000.0), (500100.0,)]},
        {"id": "insufficient_line", "type": "Polilínea", "coords": [(500000.0, 4000000.0)]},
        {"id": "no_coords_poly", "type": "Polígono", "coords": []},
        {"id": "invalid_poly", "type": "Polígono", "coords": [(500000.0, 4000000.0)]},
        {"id": "ok_poly", "type": "Polígono", "coords": [(500000.0, 4000000.0), (500100.0, 4000000.0), (500050.0, 4000100.0)]},
        {"id": "unknown_type", "type": "Circulo", "coords": [(10.0,10.0)]}
    ]

    import os
    output_dir = "test_output_kml"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    tests = [
        (sample_features_ok, "test_ok.kml", "Norte", "18", "OK"),
        (sample_features_mixed, "test_mixed_issues.kml", "Norte", "18", "OK (con advertencias)"),
        ([], "test_empty_features.kml", "Norte", "18", "ValueError"),
        (sample_features_ok, "test_bad_zone_str.kml", "Norte", "XYZ", "ValueError"),
        (sample_features_ok, "test_bad_zone_num.kml", "Norte", "99", "ValueError"),
        (sample_features_ok, "test_bad_hemi.kml", "Este", "18", "ValueError"),
        (sample_features_ok, "test_bad_filename.kmz", "Norte", "18", "ValueError") # Prueba de nombre de archivo
    ]

    for features, filename, hemisphere, zone, expected_outcome in tests:
        full_path = os.path.join(output_dir, filename)
        print(f"\nIntentando exportar: {full_path} (Esperado: {expected_outcome})")
        try:
            KMLExporter.export(features, full_path, hemisphere, zone)
            print(f"Archivo {filename} generado exitosamente.")
        except (ValueError, RuntimeError) as e:
            print(f"Error ({expected_outcome} esperado para algunos tests): {e}")

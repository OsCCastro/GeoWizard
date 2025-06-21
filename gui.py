import os
import csv
import json

from PySide6.QtCore import (
    Qt,
    QRegularExpression,
    QSize,
    QItemSelectionModel,
    QEvent,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QRegularExpressionValidator,
    QBrush,
    QPen,
    QPixmap,
    QPainter,
    QColor,
    QIcon,
    QPalette,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QToolBar,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLineEdit,
    QPushButton,
    QLabel,
    QFileDialog,
    QCheckBox,
    QGraphicsView,
    QGraphicsScene,
    QGraphicsTextItem,
    QHeaderView,
    QMenu,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QDialog,
    QTextEdit,
    QStackedLayout,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from config_dialog import ConfigDialog
from help_dialog import HelpDialog
from core.coordinate_manager import CoordinateManager, GeometryType
from exporters.kml_exporter import KMLExporter
from exporters.kmz_exporter import KMZExporter  # Asumiendo que existe
from exporters.shapefile_exporter import ShapefileExporter  # Asumiendo que existe
from importers.csv_importer import CSVImporter
from importers.kml_importer import KMLImporter  # Importar KMLImporter
from core.geometry import GeometryBuilder
from pyproj import Transformer

class UTMDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        # 6-7 dígitos + decimales opcionales
        rx = QRegularExpression(r'^\d{6,7}(\.\d+)?$')
        editor.setValidator(QRegularExpressionValidator(rx, editor))
        editor.installEventFilter(self)
        editor.setProperty("row", index.row())
        editor.setProperty("column", index.column())
        return editor

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Tab:
            table = obj.parent()
            while table and not isinstance(table, QTableWidget):
                table = table.parent()
            if not table:
                return False
            row = obj.property("row")
            col = obj.property("column")
            if col == 1:
                table.setCurrentCell(row, 2)
                item = table.item(row, 2)
                if item is None:
                    item = QTableWidgetItem("")
                    table.setItem(row, 2, item)
                table.editItem(item)
            elif col == 2:
                next_row = row + 1
                if next_row >= table.rowCount():
                    table.insertRow(next_row)
                    id_it = QTableWidgetItem(str(next_row + 1))
                    id_it.setFlags(Qt.ItemIsEnabled)
                    table.setItem(next_row, 0, id_it)
                table.setCurrentCell(next_row, 1)
                item = table.item(next_row, 1)
                if item is None:
                    item = QTableWidgetItem("")
                    table.setItem(next_row, 1, item)
                table.editItem(item)
            return True
        return super().eventFilter(obj, event)

    def setModelData(self, editor, model, index):
        text = editor.text()
        model.setData(index, text)
        if not (model.flags(index) & Qt.ItemIsSelectable and
                model.data(index, Qt.BackgroundRole)):
            color = Qt.black if editor.hasAcceptableInput() else Qt.red
            model.setData(index, QBrush(color), Qt.ForegroundRole)

class CoordTable(QTableWidget):
    def keyPressEvent(self, event):
        # Tab: al salir de Y, saltar a X de la siguiente fila
        if event.key() == Qt.Key_Tab and self.currentColumn() == 2:
            next_row = self.currentRow() + 1
            if next_row < self.rowCount():
                self.setCurrentCell(next_row, 1)
                # Comenzar edición inmediatamente
                item = self.item(next_row, 1)
                if item is None:
                    item = QTableWidgetItem("")
                    self.setItem(next_row, 1, item)
                self.editItem(item)
            return
        super().keyPressEvent(event)

class CanvasView(QGraphicsView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._zoom_factor = 1.15

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0:
            self.scale(self._zoom_factor, self._zoom_factor)
        else:
            self.scale(1 / self._zoom_factor, 1 / self._zoom_factor)
        event.accept()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIG: Gestión de Coordenadas")
        self._build_ui()
        self._create_toolbar()
        self._modo_oscuro = False
        self._toggle_modo(False)
        self.draw_scale = 0.35
        self.point_size = 6
        self.font_size = 8
    
    def _icono(self, nombre, size=QSize(24, 24)):
        ruta = f"icons/{nombre}"
        renderer = QSvgRenderer(ruta)
        pixmap = QPixmap(size)
        pixmap.fill(Qt.transparent)

        color = QApplication.palette().color(QPalette.Text)

        painter = QPainter(pixmap)
        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        renderer.render(painter)
        painter.end()

        return QIcon(pixmap)

    def _build_ui(self):
        central = QWidget()
        main_layout = QHBoxLayout(central)

        #######################
        # Panel de controles  #
        #######################
        control = QVBoxLayout()

        # Hemisferio / Zona
        hz = QHBoxLayout()
        hz.addWidget(QLabel("Hemisferio:"))
        self.cb_hemisferio = QComboBox()
        self.cb_hemisferio.addItems(["Norte","Sur"])
        hz.addWidget(self.cb_hemisferio)
        hz.addWidget(QLabel("Zona UTM:"))
        self.cb_zona = QComboBox()
        self.cb_zona.addItems([str(i) for i in range(1,61)])
        hz.addWidget(self.cb_zona)
        control.addLayout(hz)

        # Tabla de coordenadas
        self.table = CoordTable(1,3)
        self.table.setHorizontalHeaderLabels(["ID","X (Este)","Y (Norte)"])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        # primer ID
        first = QTableWidgetItem("1")
        first.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(0,0,first)
        # validación UTM
        delegate = UTMDelegate(self.table)
        self.table.setItemDelegateForColumn(1, delegate)
        self.table.setItemDelegateForColumn(2, delegate)
        # selección y menú contextual
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.itemChanged.connect(self._on_cell_changed)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_menu)
        control.addWidget(self.table)

        # Geometrías
        geo = QHBoxLayout()
        geo.addWidget(QLabel("Geometría:"))
        self.chk_punto     = QCheckBox("Punto")
        self.chk_polilinea = QCheckBox("Polilínea")
        self.chk_poligono  = QCheckBox("Polígono")
        geo.addWidget(self.chk_punto)
        geo.addWidget(self.chk_polilinea)
        geo.addWidget(self.chk_poligono)
        control.addLayout(geo)

        # Mapa base
        self.chk_mapbase = QCheckBox("Usar mapa base (OSM)")
        self.chk_mapbase.toggled.connect(self._toggle_mapbase)
        control.addWidget(self.chk_mapbase)

        # Proyecto / Formato
        ff = QHBoxLayout()
        ff.addWidget(QLabel("Proyecto:"))
        self.le_nombre = QLineEdit()
        ff.addWidget(self.le_nombre)
        ff.addWidget(QLabel("Formato:"))
        self.cb_format = QComboBox()
        self.cb_format.addItems([".kml",".kmz",".shp"])
        ff.addWidget(self.cb_format)
        control.addLayout(ff)

        # Botón seleccionar carpeta
        bl = QHBoxLayout()
        bl.addStretch()
        btn = QPushButton("Seleccionar carpeta")
        btn.clicked.connect(self._on_guardar)
        bl.addWidget(btn)
        control.addLayout(bl)

        ##################
        # Lienzo (canvas)#
        ##################
        self.canvas = CanvasView()
        self.scene  = QGraphicsScene(self.canvas)
        self.canvas.setScene(self.scene)
        self.canvas.setMinimumSize(400,300)
        self.canvas.setStyleSheet("background-color:white; border:1px solid #ccc; padding:8px;")
        # Permitir desplazamiento con el cursor en lugar de barras de scroll
        self.canvas.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.canvas.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.canvas.setDragMode(QGraphicsView.ScrollHandDrag)

        # Vista web con Leaflet
        self.web_view = QWebEngineView()
        html_path = os.path.join(os.path.dirname(__file__), "map_base.html")
        self.web_view.setUrl(QUrl.fromLocalFile(os.path.abspath(html_path)))

        self.stack = QStackedLayout()
        self.stack.addWidget(self.canvas)
        self.stack.addWidget(self.web_view)
        self.stack.setCurrentWidget(self.canvas)
        view_container = QWidget()
        view_container.setLayout(self.stack)

        # ensamblar
        main_layout.addLayout(control,1)
        main_layout.addWidget(view_container,2)
        self.setCentralWidget(central)

    def _create_toolbar(self):
        tb = QToolBar("Principal")
        self.addToolBar(tb)

        # acciones básicas
        for nombre_icono, text, slot in [
            ("file-fill.svg",       "Nuevo",    self._on_new),
            ("folder-open-fill.svg","Abrir",    self._on_open),
            ("save-3-fill.svg",     "Guardar",  self._on_guardar),
            ("import-fill.svg",     "Importar", self._on_import),
            ("export-fill.svg",     "Exportar", self._on_export)
        ]:
            a = QAction(self._icono(nombre_icono), text, self)
            a.triggered.connect(slot)
            tb.addAction(a)

            if nombre_icono == "save-3-fill.svg":
                csv_action = QAction(
                    self._icono("file-excel-2-fill.svg"),
                    "Exportar CSV",
                    self
                )
                csv_action.svg_filename = "file-excel-2-fill.svg"
                csv_action.setToolTip("Exportar tabla a CSV")
                csv_action.triggered.connect(self._export_csv)
                tb.addAction(csv_action)

        tb.addSeparator()

        for nombre_icono, text, slot in [
            ("arrow-left-box-fill.svg",  "Deshacer", self._on_undo),
            ("arrow-right-box-fill.svg", "Rehacer",  self._on_redo),
        ]:
            a = QAction(self._icono(nombre_icono), text, self)
            a.triggered.connect(slot)
            tb.addAction(a)

        tb.addSeparator()

        # mostrar/ocultar lienzo
        tog = QAction(self._icono("edit-box-fill.svg"), "Mostrar/Ocultar lienzo", self)
        tog.setCheckable(True); tog.setChecked(True)
        tog.toggled.connect(self.canvas.setVisible)
        tb.addAction(tog)
        btn_html = QAction(self._icono("code-box-fill.svg"), "HTML", self)
        btn_html.setToolTip("Generar resumen HTML con coordenadas, perímetro y área")
        btn_html.triggered.connect(self._on_export_html)
        tb.addAction(btn_html)

        sim_action = QAction("Simular", self)
        sim_action.setToolTip("Recargar vista de geometrías")
        sim_action.triggered.connect(self._on_simular)
        tb.addAction(sim_action)

        zoom_in_action = QAction("Zoom +", self)
        zoom_in_action.triggered.connect(self._on_zoom_in)
        tb.addAction(zoom_in_action)

        zoom_out_action = QAction("Zoom -", self)
        zoom_out_action.triggered.connect(self._on_zoom_out)
        tb.addAction(zoom_out_action)

        tb.addSeparator()

        # modo oscuro
        self.action_modo = QAction(self._icono("sun-fill.svg"), "Modo claro", self)
        self.action_modo.setCheckable(True)
        self.action_modo.setChecked(False)
        self.action_modo.toggled.connect(self._toggle_modo)
        tb.addAction(self.action_modo)

        tb.addSeparator()

        # configuraciones y ayuda
        for nombre_icono, text, slot in [
            ("settings-2-fill.svg", "Configuraciones", self._on_settings),
            ("question-fill.svg",   "Ayuda",           self._on_help),
        ]:
            a = QAction(self._icono(nombre_icono), text, self)
            a.triggered.connect(slot)
            tb.addAction(a)

    def _export_csv(self):
        """
        Abre un diálogo para guardar un archivo CSV y vuelca en él todas las filas
        de self.table con las columnas: id, x (este), y (norte).
        Sólo escribe aquellas filas cuyo id no esté vacío.
        """
        filtro = "Archivos CSV (*.csv)"
        ruta, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar tabla a CSV",
            "",
            filtro
        )
        if not ruta:
            return  # El usuario canceló

        if not ruta.lower().endswith(".csv"):
            ruta += ".csv"

        try:
            with open(ruta, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=",")
                # Escribir cabecera
                writer.writerow(["id", "x (este)", "y (norte)"])

                filas = self.table.rowCount()
                for r in range(filas):
                    item_id = self.table.item(r, 0)
                    item_x  = self.table.item(r, 1)
                    item_y  = self.table.item(r, 2)

                    # Tomar el texto o cadena vacía si no existe item
                    id_val = item_id.text().strip() if item_id else ""
                    x_val  = item_x.text().strip()  if item_x  else ""
                    y_val  = item_y.text().strip()  if item_y  else ""

                    # Si el ID está vacío, saltar esta fila
                    if id_val == "":
                        continue

                    # Escribir sólo las filas cuyo ID no esté vacío
                    writer.writerow([id_val, x_val, y_val])

            QMessageBox.information(self, "Exportar CSV", f"CSV guardado correctamente:\n{ruta}")
        except Exception as e:
            QMessageBox.critical(self, "Error al exportar CSV", f"No se pudo escribir el archivo:\n{e}")


    def _toggle_modo(self, activado):
        self._modo_oscuro = activado

        pal = QApplication.palette()

        if activado:
            # ─── MODO OSCURO ───
            pal.setColor(QPalette.Window,    QColor("#2b2b2b"))
            pal.setColor(QPalette.Base,      QColor("#2b2b2b"))
            pal.setColor(QPalette.WindowText, QColor("#ddd"))
            pal.setColor(QPalette.Text,      QColor("#FAF2FF"))
            pal.setColor(QPalette.ButtonText, QColor("#FAF2FF"))

            QApplication.setPalette(pal)
            QApplication.instance().setStyleSheet("")   # ← AHORA CORRECTO

            self.action_modo.setIcon(self._icono("moon-fill.svg"))
            self.action_modo.setText("Modo oscuro")
        else:
            # ─── MODO CLARO ───
            pal.setColor(QPalette.Window,    QColor("#ffffff"))
            pal.setColor(QPalette.Base,      QColor("#ffffff"))
            pal.setColor(QPalette.WindowText, QColor("#000000"))
            pal.setColor(QPalette.Text,      QColor("#222625"))
            pal.setColor(QPalette.ButtonText, QColor("#222625"))

            QApplication.setPalette(pal)
            QApplication.instance().setStyleSheet("")   # ← TAMBIÉN IGUAL

            self.action_modo.setIcon(self._icono("sun-fill.svg"))
            self.action_modo.setText("Modo claro")

    def _on_cell_changed(self, item):
        r, c = item.row(), item.column()
        # auto-agregar fila nueva
        if c in (1,2):
            xi = self.table.item(r,1); yi = self.table.item(r,2)
            if xi and yi and xi.text().strip() and yi.text().strip():
                if r == self.table.rowCount()-1:
                    nr = self.table.rowCount()
                    self.table.insertRow(nr)
                    id_it = QTableWidgetItem(str(nr+1))
                    id_it.setFlags(Qt.ItemIsEnabled)
                    self.table.setItem(nr,0,id_it)
        # refresca preview
        try:
            mgr = self._build_manager_from_table()
            self._redraw_scene(mgr)
        except (ValueError, TypeError) as e:
            print(f"Error al construir features para preview: {e}")


    def _on_cell_clicked(self, row, col):
        if col == 0:
            sel = self.table.selectionModel()
            sel.clearSelection()
            for cc in (1,2):
                idx = self.table.model().index(row,cc)
                sel.select(idx, QItemSelectionModel.Select)
            self.table.setCurrentCell(row,1)

    def _show_table_menu(self, pos):
        menu = QMenu()
        menu.addAction("Añadir fila", self._add_row)
        menu.addAction("Eliminar fila", self._delete_row)
        menu.addSeparator()
        menu.addAction("Copiar", self._copy_selection)
        menu.addAction("Pegar", self._paste_to_table)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_selection(self):
        ranges = self.table.selectedRanges()
        if not ranges:
            return
        text = ""
        for r in ranges:
            for row in range(r.topRow(), r.bottomRow()+1):
                parts = []
                for col in range(r.leftColumn(), r.rightColumn()+1):
                    itm = self.table.item(row,col)
                    parts.append(itm.text() if itm else "")
                text += "\t".join(parts) + "\n"
        QApplication.clipboard().setText(text)

    def _add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        id_it = QTableWidgetItem(str(r + 1))
        id_it.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(r, 0, id_it)
        self.table.setCurrentCell(r, 1)
        item = QTableWidgetItem("")
        self.table.setItem(r, 1, item)
        self.table.editItem(item)

    def _delete_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)
        try:
            mgr = self._build_manager_from_table()
            self._redraw_scene(mgr)
        except (ValueError, TypeError) as e:
            print(f"Error al construir features para preview tras eliminar fila: {e}")


    def _paste_to_table(self):
        lines = QApplication.clipboard().text().splitlines()
        r = self.table.currentRow()
        if r < 0:
            r = 0
            if self.table.item(r,0) and not (self.table.item(r,0).flags() & Qt.ItemIsEditable):
                pass

        for ln_idx, ln in enumerate(lines):
            if not ln.strip():
                continue

            current_id_item = self.table.item(r, 0)
            is_id_cell_uneditable = current_id_item and not (current_id_item.flags() & Qt.ItemIsEditable)

            if r >= self.table.rowCount():
                self.table.insertRow(r)
                id_it = QTableWidgetItem(str(r+1))
                id_it.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(r,0,id_it)
            elif is_id_cell_uneditable and (self.table.item(r,1) and self.table.item(r,1).text() or \
                                          self.table.item(r,2) and self.table.item(r,2).text()):
                pass

            pts = [p.strip() for p in ln.split(",")]
            if len(pts) < 2:
                pts = [p.strip() for p in ln.split("\t")]

            if len(pts) >= 2:
                try:
                    float(pts[0].replace(',','.'))
                    float(pts[1].replace(',','.'))
                except ValueError:
                    QMessageBox.warning(self, "Error de Pegado", f"Línea '{ln}' no contiene coordenadas X,Y numéricas válidas.")
                    continue

                self.table.setItem(r,1, QTableWidgetItem(pts[0].replace(',','.')))
                self.table.setItem(r,2, QTableWidgetItem(pts[1].replace(',','.')))
                r += 1

        try:
            mgr = self._build_manager_from_table()
            self._redraw_scene(mgr)
        except (ValueError, TypeError) as e:
             print(f"Error al construir features para preview tras pegar: {e}")

    def _toggle_mapbase(self, checked):
        if checked:
            self.stack.setCurrentWidget(self.web_view)
            try:
                mgr = self._build_manager_from_table()
                self._update_web_features(mgr)
            except Exception as e:
                QMessageBox.warning(self, "Mapa base", f"No se pudo cargar el mapa: {e}")
        else:
            self.stack.setCurrentWidget(self.canvas)


    def _build_manager_from_table(self):
        coords = []
        for r in range(self.table.rowCount()):
            xi = self.table.item(r,1); yi = self.table.item(r,2)
            if xi and yi and xi.text().strip() and yi.text().strip():
                try:
                    x_val = float(xi.text())
                    y_val = float(yi.text())
                    coords.append((x_val, y_val))
                except ValueError:
                    pass

        mgr = CoordinateManager(
            hemisphere=self.cb_hemisferio.currentText(),
            zone=int(self.cb_zona.currentText())
        )
        nid = 1

        if coords:
            if self.chk_punto.isChecked():
                for x,y in coords:
                    try:
                        mgr.add_feature(nid, GeometryType.PUNTO, [(x,y)])
                        nid += 1
                    except (ValueError, TypeError) as e:
                        QMessageBox.warning(self, "Error al crear Punto", f"Feature ID {nid}: {e}")

            if self.chk_polilinea.isChecked():
                if len(coords) >= 2:
                    try:
                        mgr.add_feature(nid, GeometryType.POLILINEA, coords)
                        nid += 1
                    except (ValueError, TypeError) as e:
                        QMessageBox.warning(self, "Error al crear Polilínea", f"Feature ID {nid}: {e}")
                elif self.chk_polilinea.isEnabled() and self.chk_polilinea.isChecked():
                     QMessageBox.warning(self, "Datos insuficientes", "Se necesitan al menos 2 coordenadas para una Polilínea.")

            if self.chk_poligono.isChecked():
                if len(coords) >= 3:
                    try:
                        mgr.add_feature(nid, GeometryType.POLIGONO, coords)
                        nid += 1
                    except (ValueError, TypeError) as e:
                        QMessageBox.warning(self, "Error al crear Polígono", f"Feature ID {nid}: {e}")
                elif self.chk_poligono.isEnabled() and self.chk_poligono.isChecked():
                    QMessageBox.warning(self, "Datos insuficientes", "Se necesitan al menos 3 coordenadas para un Polígono.")
        return mgr

    def _redraw_scene(self, mgr):
        self.scene.clear()
        if not mgr:
            return

        features_for_paths = mgr.get_features()
        for path, pen in GeometryBuilder.paths_from_features(features_for_paths):
            self.scene.addPath(path, pen)

        if self.chk_punto.isChecked():
            for feat in mgr.get_features():
                if feat["type"] == GeometryType.PUNTO and feat["coords"]:
                    x, y = feat["coords"][0]
                    size = self.point_size * self.draw_scale
                    ellipse = self.scene.addEllipse(
                        x - size / 2,
                        y - size / 2,
                        size,
                        size,
                        QPen(Qt.red),
                        QBrush(Qt.red),
                    )
                    ellipse.setZValue(1)

                    label = QGraphicsTextItem(str(feat.get("id", "")))
                    f = label.font()
                    f.setPointSizeF(self.font_size * self.draw_scale)
                    label.setFont(f)
                    label.setDefaultTextColor(Qt.darkBlue)
                    label.setPos(x + size / 2 + 1, y + size / 2 + 1)
                    label.setZValue(1)
                    self.scene.addItem(label)

        if self.chk_mapbase.isChecked():
            self._update_web_features(mgr)

    def _update_web_features(self, mgr):
        if not self.chk_mapbase.isChecked() or not mgr:
            return
        hemisphere = self.cb_hemisferio.currentText()
        zone = int(self.cb_zona.currentText())
        epsg = 32600 + zone if hemisphere.lower().startswith("n") else 32700 + zone
        transformer = Transformer.from_crs(f"epsg:{epsg}", "epsg:4326", always_xy=True)
        feats = []
        for feat in mgr.get_features():
            latlon = [transformer.transform(x, y) for x, y in feat["coords"]]
            if feat["type"] == GeometryType.PUNTO:
                geom = {"type": "Point", "coordinates": latlon[0]}
            elif feat["type"] == GeometryType.POLILINEA:
                geom = {"type": "LineString", "coordinates": latlon}
            else:
                geom = {"type": "Polygon", "coordinates": [latlon]}
            feats.append({"type": "Feature", "properties": {"id": feat["id"]}, "geometry": geom})

        geojson = {"type": "FeatureCollection", "features": feats}
        js = (
            "window.clearFeatures && window.clearFeatures();" 
            f"window.addFeature({json.dumps(geojson)})"
        )
        self.web_view.page().runJavaScript(js)

    def _on_guardar(self):
        dirp = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de proyecto")
        if not dirp:
            return
        proj = self.le_nombre.text().strip() or "proyecto"
        full_path_filename = os.path.join(dirp, proj + self.cb_format.currentText())

        try:
            mgr = self._build_manager_from_table()
        except (ValueError, TypeError) as e:
            QMessageBox.critical(self, "Error en datos de tabla", f"No se pueden generar las geometrías para exportar: {e}")
            return

        selected_format = self.cb_format.currentText()

        features = mgr.get_features()
        if not features:
            QMessageBox.warning(self, "Nada para exportar", "No hay geometrías definidas para exportar.")
            return

        hemisphere = self.cb_hemisferio.currentText()
        zone = self.cb_zona.currentText()

        try:
            export_successful = False
            if selected_format == ".kml":
                KMLExporter.export(features, full_path_filename, hemisphere, zone)
                export_successful = True
            elif selected_format == ".kmz":
                KMZExporter.export(features, full_path_filename, hemisphere, zone)
                export_successful = True
            elif selected_format == ".shp":
                ShapefileExporter.export(features, full_path_filename, hemisphere, zone)
                export_successful = True
            else:
                QMessageBox.warning(self, "Formato no soportado",
                                    f"La exportación al formato '{selected_format}' aún no está implementada.")
                return

            if export_successful:
                QMessageBox.information(self, "Éxito", f"Archivo guardado en:\n{full_path_filename}")

        except ImportError as ie:
            QMessageBox.critical(self, "Error de dependencia",
                                 f"No se pudo exportar a '{selected_format}'. Dependencia faltante: {str(ie)}. Verifique la instalación.")
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar",
                                 f"Ocurrió un error al guardar en formato '{selected_format}':\n{str(e)}")

    def _on_export(self):
        self._on_guardar()

    def _on_new(self):
        self.table.clearContents()
        self.table.setRowCount(1)
        first = QTableWidgetItem("1"); first.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(0,0,first)
        if self.scene:
            self.scene.clear()

        self.chk_punto.setChecked(False)
        self.chk_polilinea.setChecked(False)
        self.chk_poligono.setChecked(False)
        self.le_nombre.clear()

    def _on_open(self):
        filters = "Archivos de Proyecto SIG (*.kml *.kmz *.shp);;Todos los archivos (*)"
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Proyecto", "", filters
        )
        if path:
            QMessageBox.information(self, "Abrir Proyecto", f"Funcionalidad de abrir proyecto '{path}' aún no implementada.")
            print(f"Abrir proyecto: {path}")

    def _on_import(self):
        filters = "Archivos KML (*.kml);;Archivos de Coordenadas (*.csv *.txt);;Todos los archivos (*)"
        path, selected_filter = QFileDialog.getOpenFileName(
            self, "Importar Coordenadas o Geometrías", "", filters
        )

        if not path:
            return

        file_ext = os.path.splitext(path)[1].lower()

        if file_ext in ['.csv', '.txt']:
            try:
                # 1) Importamos todos los “features” desde el CSV.
                #    Nuestros CSV exportados usan el orden id,x,y con cabecera.
                imported_features = CSVImporter.import_file(
                    path,
                    x_col_idx=1,
                    y_col_idx=2,
                    id_col_idx=0,
                    skip_header=1,
                )

                # 2) Filtramos solo aquellos que tengan:
                #    a) Un campo "id" no vacío (feat.get("id") != "").
                #    b) Al menos una coordenada válida en feat["coords"][0].
                valid_feats = []
                for feat in imported_features:
                    raw_id = str(feat.get("id", "")).strip()
                    coords_list = feat.get("coords", [])
                    # Comprobamos que el ID no esté vacío y que exista coords_list[0] con 2 valores
                    if raw_id != "" \
                    and coords_list \
                    and isinstance(coords_list[0], (list, tuple)) \
                    and len(coords_list[0]) == 2:
                        x0, y0 = coords_list[0]
                        # Comprobamos también que X y Y no sean None ni cadena vacía
                        if x0 is not None and y0 is not None \
                        and str(x0).strip() != "" and str(y0).strip() != "":
                            valid_feats.append(feat)

                if not valid_feats:
                    QMessageBox.information(
                        self,
                        "Importación CSV",
                        "No se importaron geometrías válidas desde el archivo."
                    )
                    return

                # 3) Limpiamos la tabla y creamos tantas filas como valid_feats haya
                self._on_new()
                self.table.setRowCount(len(valid_feats))

                # 4) Recorremos valid_feats, asignamos ID entero consecutivo y mostramos coords
                for i, feat in enumerate(valid_feats):
                    # Forzar ID entero: 1, 2, 3, ...
                    feat_id = i + 1
                    coords_list = feat.get("coords", [])

                    # Celda ID (solo números enteros, ya que raw_id no se usa)
                    id_item = QTableWidgetItem(str(feat_id))
                    id_item.setFlags(Qt.ItemIsEnabled)
                    self.table.setItem(i, 0, id_item)

                    # Celda X y Y con la primera coordenada válida
                    x_coord, y_coord = coords_list[0]
                    self.table.setItem(i, 1, QTableWidgetItem(str(x_coord)))
                    self.table.setItem(i, 2, QTableWidgetItem(str(y_coord)))

                # 5) Activar solamente el checkbox de Punto (porque importamos coordenadas sueltas)
                self.chk_punto.setChecked(True)
                self.chk_polilinea.setChecked(False)
                self.chk_poligono.setChecked(False)

                # 6) Reconstruir el manager y redibujar la escena
                try:
                    mgr = self._build_manager_from_table()
                    self._redraw_scene(mgr)
                    QMessageBox.information(
                        self,
                        "Importación CSV Exitosa",
                        f"{len(valid_feats)} puntos importados desde {os.path.basename(path)}."
                    )
                except (ValueError, TypeError) as e:
                    QMessageBox.critical(
                        self,
                        "Error al procesar datos importados",
                        f"Los datos CSV importados no pudieron ser procesados: {e}"
                    )

            except FileNotFoundError:
                QMessageBox.critical(self, "Error de Importación", f"Archivo no encontrado: {path}")
            except RuntimeError as e:
                QMessageBox.critical(self, "Error de Importación", f"Error al importar archivo CSV: {e}")
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error Inesperado",
                    f"Ocurrió un error inesperado durante la importación CSV: {e}"
                )


            except FileNotFoundError:
                QMessageBox.critical(self, "Error de Importación", f"Archivo no encontrado: {path}")
            except RuntimeError as e:
                QMessageBox.critical(self, "Error de Importación", f"Error al importar archivo CSV: {e}")
            except Exception as e:
                QMessageBox.critical(self, "Error Inesperado", f"Ocurrió un error inesperado durante la importación CSV: {e}")

        elif file_ext == '.kml':
            try:
                hemisphere = self.cb_hemisferio.currentText()
                zone_str = self.cb_zona.currentText()
                if not zone_str:
                    QMessageBox.warning(self, "Zona no seleccionada", "Por favor, seleccione una zona UTM antes de importar KML.")
                    return
                zone = int(zone_str)

                imported_features = KMLImporter.import_file(path, hemisphere, zone)

                if not imported_features:
                    QMessageBox.information(self, "Importación KML", "No se importaron geometrías válidas desde el archivo KML.")
                    return

                self._on_new()

                row_index = 0  # fila actual en la tabla

                for feat in imported_features:
                    feat_id = feat.get("id", row_index + 1)
                    coords = feat.get("coords", [])
                    geom_type = feat.get("type", "").lower()
                    if "polígono" in geom_type and len(coords) >= 3:
                        if coords[0] != coords[-1]:
                            coords.append(coords[0])    

                    if not coords:
                        continue

                    for j, (x, y) in enumerate(coords):
                        if row_index >= self.table.rowCount():
                            self.table.insertRow(row_index)
                        id_str = f"{feat_id}.{j+1}" if len(coords) > 1 else str(feat_id)
                        id_item = QTableWidgetItem(id_str)
                        id_item.setFlags(Qt.ItemIsEnabled)
                        self.table.setItem(row_index, 0, id_item)
                        self.table.setItem(row_index, 1, QTableWidgetItem(f"{x:.2f}"))
                        self.table.setItem(row_index, 2, QTableWidgetItem(f"{y:.2f}"))
                        row_index += 1

                    # Activar el checkbox adecuado
                    if "punto" in geom_type:
                        self.chk_punto.setChecked(True)
                    if "polilínea" in geom_type or "linestring" in geom_type:
                        self.chk_polilinea.setChecked(True)
                    if "polígono" in geom_type or "polygon" in geom_type:
                        self.chk_poligono.setChecked(True)


                # No se cambian los checkboxes. El usuario debe seleccionar el tipo apropiado
                # para que _build_manager_from_table construya las geometrías deseadas.
                # Se informa al usuario.

                try:
                    mgr = self._build_manager_from_table()
                    self._redraw_scene(mgr)
                    QMessageBox.information(self, "Importación KML Exitosa",
                                            f"{len(imported_features)} geometrías importadas desde {os.path.basename(path)}.\n"
                                            "Active los checkboxes de tipo de geometría (Punto, Polilínea, Polígono)\n"
                                            "para visualizar y procesar los datos importados.")
                except (ValueError, TypeError) as e:
                     QMessageBox.critical(self, "Error al procesar datos KML importados",
                                          f"Los datos KML importados no pudieron ser procesados: {e}")

            except FileNotFoundError:
                QMessageBox.critical(self, "Error de Importación KML", f"Archivo no encontrado: {path}")
            except (RuntimeError, ValueError) as e:
                QMessageBox.critical(self, "Error de Importación KML", f"Error al importar archivo KML: {e}")
            except Exception as e:
                QMessageBox.critical(self, "Error Inesperado", f"Ocurrió un error inesperado durante la importación KML: {e}")
        else:
            QMessageBox.warning(self, "Formato no Soportado",
                                f"La importación del formato de archivo '{file_ext}' aún no está implementada.")

    def _on_undo(self):
        QMessageBox.information(self, "Deshacer", "Funcionalidad de Deshacer aún no implementada.")
        print("Deshacer acción")

    def _on_redo(self):
        QMessageBox.information(self, "Rehacer", "Funcionalidad de Rehacer aún no implementada.")
        print("Rehacer acción")

    def _on_settings(self):
        current = {
            "dark_mode": self._modo_oscuro,
            "draw_scale": self.draw_scale,
            "point_size": self.point_size,
            "font_size": self.font_size,
        }
        dialog = ConfigDialog(self, current)
        if dialog.exec():
            vals = dialog.get_values()
            self.draw_scale = vals.get("draw_scale", self.draw_scale)
            self.point_size = vals.get("point_size", self.point_size)
            self.font_size = vals.get("font_size", self.font_size)
            self._toggle_modo(vals.get("dark_mode", self._modo_oscuro))
            try:
                mgr = self._build_manager_from_table()
                self._redraw_scene(mgr)
            except (ValueError, TypeError) as e:
                print(f"Error aplicando configuración: {e}")

    def _on_help(self):
        dialog = HelpDialog(self)
        dialog.exec()

    def _on_export_html(self):
        coords = []
        for r in range(self.table.rowCount()):
            xi = self.table.item(r, 1)
            yi = self.table.item(r, 2)
            if xi and yi:
                try:
                    x = float(xi.text())
                    y = float(yi.text())
                    coords.append((x, y))
                except ValueError:
                    continue

        if len(coords) < 2:
            QMessageBox.warning(self, "Geometría insuficiente", "Se necesitan al menos 2 puntos para calcular perímetro.")
            return

        def distancia(a, b):
            return ((a[0] - b[0])**2 + (a[1] - b[1])**2) ** 0.5

        perimetro = sum(distancia(coords[i], coords[i+1]) for i in range(len(coords)-1))
        if self.chk_poligono.isChecked() and len(coords) >= 3:
            perimetro += distancia(coords[-1], coords[0])

        area = 0
        if self.chk_poligono.isChecked() and len(coords) >= 3:
            area = 0.5 * abs(sum(coords[i][0]*coords[i+1][1] - coords[i+1][0]*coords[i][1] for i in range(-1, len(coords)-1)))

        # HTML visual
        html = "<table border='1' cellpadding='4' cellspacing='0'>"
        html += "<tr><th>ID</th><th>Este (X)</th><th>Norte (Y)</th></tr>"
        for r in range(len(coords)):
            id_val = self.table.item(r, 0).text() if self.table.item(r, 0) else str(r+1)
            html += f"<tr><td>{id_val}</td><td>{coords[r][0]:.2f}</td><td>{coords[r][1]:.2f}</td></tr>"

        # Fila única combinada para Perímetro
        html += f"<tr><td colspan='3'><b>Perímetro:</b> {perimetro:.2f} m</td></tr>"

        # Fila única combinada para Área (si aplica)
        if self.chk_poligono.isChecked() and len(coords) >= 3:
            html += f"<tr><td colspan='3'><b>Área:</b> {area:.2f} m²</td></tr>"

        html += "</table>"



        # Diálogo modal visual
        dlg = QDialog(self)
        dlg.setWindowTitle("Resumen de Coordenadas")
        dlg.setMinimumSize(600, 400)
        layout = QVBoxLayout(dlg)

        view = QTextEdit()
        view.setReadOnly(True)
        view.setHtml(html)

        btn_copiar = QPushButton("Copiar código HTML")
        btn_copiar.clicked.connect(lambda: QApplication.clipboard().setText(html))

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.clicked.connect(dlg.close)

        layout.addWidget(view)
        layout.addWidget(btn_copiar)
        layout.addWidget(btn_cerrar)

        dlg.setLayout(layout)
        dlg.exec()

    def _on_simular(self):
        try:
            mgr = self._build_manager_from_table()
            self._redraw_scene(mgr)
            if self.chk_mapbase.isChecked():
                self._update_web_features(mgr)
            if self.scene.items():
                self.canvas.fitInView(self.scene.itemsBoundingRect(), Qt.KeepAspectRatio)
        except (ValueError, TypeError) as e:
            QMessageBox.warning(self, "Error", f"No se pudo simular: {e}")

    def _on_zoom_in(self):
        self.canvas.scale(1.2, 1.2)

    def _on_zoom_out(self):
        self.canvas.scale(0.8, 0.8)

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

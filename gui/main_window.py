# gui/main_window.py
import tkinter as tk
from tkinter import messagebox, filedialog, colorchooser
from ttkbootstrap import Window, ttk
from config_manager import ConfigManager
from coordinate_converter.utm_converter import convertir_utm_a_latlon
from kml_generator import KMLGenerator

class MainWindow(Window):
    def __init__(self):
        super().__init__(title="GeoWizard", themename="darkly")
        self.resizable(False, False)

        # Configuración
        self.config_manager = ConfigManager()
        self.config_manager.cargar_configuracion()

        # Variables
        self.zona_variable = tk.StringVar(value=self.config_manager.obtener_zona())
        self.hemisferio_variable = tk.StringVar(value=self.config_manager.obtener_hemisferio())
        self.tipo_geometria_variable = tk.StringVar(value="Punto")
        self.nombre_variable = tk.StringVar()

        self.estilos = {
            "punto": {
                "color": "ff0000",  # Rojo (RRGGBB)
                "escala": 1.5,
                "icono": "http://maps.google.com/mapfiles/kml/pushpin/ylw-pushpin.png"
            },
            "polilinea": {
                "color": "0000ff",  # Azul (RRGGBB)
                "grosor": 4
            },
            "poligono": {
                "color_relleno": "00ff00",  # Verde (RRGGBB)
                "color_borde": "ff0000",    # Rojo (RRGGBB)
                "grosor_borde": 2,
                "relleno": True,
                "contorno": True
            }
        }

        # Opacidad predeterminada
        self.opacidad = tk.DoubleVar(value=50)  # Valor entre 0 (transparente) y 1 (opaco)        

        # Interfaz
        self.crear_interfaz()
        self.crear_menu()

        # Configurar evento para mostrar/ocultar el menú con Alt
        self.bind("<Alt_L>", self.toggle_menu)
        self.bind("<Alt_R>", self.toggle_menu)

    def crear_interfaz(self):
        # Frame para menús desplegables
        frame_menus = ttk.Frame(self)
        frame_menus.pack(pady=10)

        ttk.Label(frame_menus, text="Zona:").pack(side=tk.LEFT, padx=5)
        ttk.OptionMenu(frame_menus, self.zona_variable, self.zona_variable.get(), *range(1, 61)).pack(side=tk.LEFT, padx=5)

        ttk.Label(frame_menus, text="Hemisferio:").pack(side=tk.LEFT, padx=5)
        ttk.OptionMenu(frame_menus, self.hemisferio_variable, self.hemisferio_variable.get(), "Norte", "Sur").pack(side=tk.LEFT, padx=5)

        # Selector de tipo de geometría
        ttk.Label(self, text="Tipo de geometría:").pack(pady=5)
        self.tipo_geometria_frame = ttk.Frame(self)
        self.tipo_geometria_frame.pack(pady=5)
        ttk.Radiobutton(self.tipo_geometria_frame, text="Punto", variable=self.tipo_geometria_variable, value="Punto", command=self.actualizar_nombre_etiqueta).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(self.tipo_geometria_frame, text="Polilínea", variable=self.tipo_geometria_variable, value="Polilínea", command=self.actualizar_nombre_etiqueta).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(self.tipo_geometria_frame, text="Polígono", variable=self.tipo_geometria_variable, value="Polígono", command=self.actualizar_nombre_etiqueta).pack(side=tk.LEFT, padx=5)

        # Campo de nombre
        self.nombre_label = ttk.Label(self, text="Nombre del punto:")
        self.nombre_label.pack(pady=5)
        self.nombre_entry = ttk.Entry(self, textvariable=self.nombre_variable)
        self.nombre_entry.pack(pady=5)

        # Campos de coordenadas
        ttk.Label(self, text="Coordenadas X:").pack(pady=5)
        self.coordenadas_x_text = tk.Text(self, height=5, width=30)
        self.coordenadas_x_text.pack(pady=5)

        ttk.Label(self, text="Coordenadas Y:").pack(pady=5)
        self.coordenadas_y_text = tk.Text(self, height=5, width=30)
        self.coordenadas_y_text.pack(pady=5)

        # Botón Configurar
        ttk.Button(self, text="Configurar", command=self.abrir_ventana_configuracion).pack(pady=5)

        # Botón Generar KML
        ttk.Button(self, text="Generar KML", command=self.generar_kml).pack(pady=5)

        # Lienzo para dibujar las coordenadas
        self.lienzo = tk.Canvas(self, width=500, height=400, bg="white")
        self.lienzo.pack(pady=10)

        def agregar_punto(self):
            x = self.coordenadas_x_text.get("1.0", tk.END).strip()
            y = self.coordenadas_y_text.get("1.0", tk.END).strip()
            
            if x and y:
                try:
                    float(x)  # Validar que sea un número
                    float(y)
                    self.ultimo_id += 1
                    self.tabla.insert("", "end", values=(self.ultimo_id, x, y))
                    self.actualizar_lienzo()
                    self.coordenadas_x_text.delete("1.0", tk.END)
                    self.coordenadas_y_text.delete("1.0", tk.END)
                except ValueError:
                    messagebox.showerror("Error", "Las coordenadas deben ser números válidos.")

    def crear_menu(self):
        """Crea el menú superior."""
        self.menu_superior = tk.Menu(self)

        # Menú Archivo
        menu_archivo = tk.Menu(self.menu_superior, tearoff=0)
        menu_archivo.add_command(label="Cargar coordenadas", command=self.cargar_coordenadas)
        menu_archivo.add_separator()
        menu_archivo.add_command(label="Guardar configuración", command=self.guardar_configuracion)
        menu_archivo.add_separator()
        menu_archivo.add_command(label="Salir", command=self.quit)
        self.menu_superior.add_cascade(label="Archivo", menu=menu_archivo)

        # Menú Configuración
        menu_configuracion = tk.Menu(self.menu_superior, tearoff=0)
        menu_configuracion.add_command(label="Configurar zona y hemisferio", command=self.configurar_zona_hemisferio)
        self.menu_superior.add_cascade(label="Configuración", menu=menu_configuracion)

        # Menú About
        menu_about = tk.Menu(self.menu_superior, tearoff=0)
        menu_about.add_command(label="Acerca de", command=self.mostrar_acerca_de)
        self.menu_superior.add_cascade(label="About", menu=menu_about)

        # Ocultar el menú inicialmente
        self.config(menu="")

    def toggle_menu(self, event=None):
        """Muestra u oculta el menú al presionar Alt."""
        if self.cget("menu") == "":
            self.config(menu=self.menu_superior)
        else:
            self.config(menu="")

    def cargar_coordenadas(self):
        archivo = filedialog.askopenfilename(filetypes=[("Archivos CSV", "*.csv")])
        if archivo:
            try:
                with open(archivo, "r") as f:
                    self.tabla.delete(*self.tabla.get_children())
                    self.ultimo_id = 0
                    for linea in f:
                        try:
                            x, y = linea.strip().split(",")
                            float(x)  # Validar coordenadas
                            float(y)
                            self.ultimo_id += 1
                            self.tabla.insert("", "end", values=(self.ultimo_id, x, y))
                        except ValueError:
                            messagebox.showerror("Error", f"Formato incorrecto en línea: {linea}")
                            continue
                self.actualizar_lienzo()
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo cargar el archivo: {e}")

    def guardar_configuracion(self):
        """Guarda la configuración actual."""
        zona = self.zona_variable.get()
        hemisferio = self.hemisferio_variable.get()
        self.config_manager.guardar_configuracion(zona, hemisferio)
        messagebox.showinfo("Información", "La configuración se ha guardado correctamente.")

    def configurar_zona_hemisferio(self):
        """Abre una ventana para configurar la zona y el hemisferio."""
        ventana_config = tk.Toplevel(self)
        ventana_config.title("Configuración")

        ttk.Label(ventana_config, text="Zona:").pack(pady=5)
        zona_entry = ttk.Entry(ventana_config, textvariable=self.zona_variable)
        zona_entry.pack(pady=5)

        ttk.Label(ventana_config, text="Hemisferio:").pack(pady=5)
        hemisferio_entry = ttk.Entry(ventana_config, textvariable=self.hemisferio_variable)
        hemisferio_entry.pack(pady=5)

        ttk.Button(ventana_config, text="Guardar", command=self.guardar_configuracion).pack(pady=10)

    def mostrar_acerca_de(self):
        """Muestra la ventana 'Acerca de'."""
        ventana_acerca_de = tk.Toplevel(self)
        ventana_acerca_de.title("Acerca de")
        ttk.Label(ventana_acerca_de, text="GeoWizard\nVersión 1.0\nDesarrollado por [Tu nombre]").pack(pady=20)

    def actualizar_nombre_etiqueta(self):
        """Actualiza la etiqueta del nombre según el tipo de geometría seleccionado."""
        tipo_geometria = self.tipo_geometria_variable.get()
        if tipo_geometria == "Punto":
            self.nombre_label.config(text="Nombre del punto:")
        elif tipo_geometria == "Polilínea":
            self.nombre_label.config(text="Nombre de la polilínea:")
        elif tipo_geometria == "Polígono":
            self.nombre_label.config(text="Nombre del polígono:")
        self.actualizar_lienzo()  # Actualizar el lienzo

    def generar_kml(self):
        zona = self.zona_variable.get()
        hemisferio = self.hemisferio_variable.get()
        nombre = self.nombre_variable.get()
        tipo_geometria = self.tipo_geometria_variable.get()

        # Validar entradas
        if not zona or not hemisferio or not nombre:
            messagebox.showerror("Error", "Por favor, complete todos los campos.")
            return

        # Obtener coordenadas desde la tabla
        coordenadas = []
        for item in self.tabla.get_children():
            _, x, y = self.tabla.item(item)['values']
            try:
                lat, lon = convertir_utm_a_latlon(x, y, zona, hemisferio)
                coordenadas.append((lat, lon))
            except Exception as e:
                messagebox.showerror("Error de conversión", f"Error en coordenadas ID {_}: {str(e)}")
                return

        # Generar KML
        try:
            kml_generator = KMLGenerator(nombre, tipo_geometria, self.estilos, self.opacidad.get())
            kml_generator.agregar_coordenadas(coordenadas)
            
            # Agregar descripción
            for feature in kml_generator.kml.features:
                feature.description = kml_generator._generar_descripcion(coordenadas)
            
            archivo_kml = filedialog.asksaveasfilename(defaultextension=".kml", filetypes=[("Archivos KML", "*.kml")])
            if archivo_kml:
                kml_generator.guardar(archivo_kml)
                messagebox.showinfo("Éxito", f"Archivo KML generado:\n{archivo_kml}")
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo generar el KML: {str(e)}")

    def abrir_ventana_configuracion(self):
        """Abre la ventana de configuración de estilos."""
        ventana_config = tk.Toplevel(self)
        ventana_config.title("Configurar Estilos")

        # Frame para opciones de polígono
        frame_opciones_poligono = ttk.Frame(ventana_config)
        frame_opciones_poligono.pack(pady=10)

        # Casillas de verificación para relleno y contorno
        self.relleno_poligono = tk.BooleanVar(value=self.estilos["poligono"]["relleno"])
        self.contorno_poligono = tk.BooleanVar(value=self.estilos["poligono"]["contorno"])

        ttk.Checkbutton(frame_opciones_poligono, text="Relleno", variable=self.relleno_poligono).pack(side=tk.LEFT, padx=5)
        ttk.Checkbutton(frame_opciones_poligono, text="Contorno", variable=self.contorno_poligono).pack(side=tk.LEFT, padx=5)

        # Control de opacidad (1-100)
        ttk.Label(frame_opciones_poligono, text="Opacidad (%):").pack(side=tk.LEFT, padx=5)
        self.opacidad_scale = ttk.Scale(frame_opciones_poligono, from_=1, to=100, variable=self.opacidad, orient=tk.HORIZONTAL)
        self.opacidad_scale.pack(side=tk.LEFT, padx=5)

        # Mostrar el valor de la opacidad
        self.opacidad_label = ttk.Label(frame_opciones_poligono, text=f"{self.opacidad.get()}%")
        self.opacidad_label.pack(side=tk.LEFT, padx=5)

        # Actualizar la etiqueta cuando cambia la opacidad
        self.opacidad_scale.configure(command=lambda value: self.opacidad_label.config(text=f"{int(float(value))}%"))

        # Pestañas para cada tipo de geometría
        notebook = ttk.Notebook(ventana_config)
        notebook.pack(padx=10, pady=10)

        # Pestaña para Puntos
        frame_punto = ttk.Frame(notebook)
        notebook.add(frame_punto, text="Punto")

        ttk.Label(frame_punto, text="Color (AABBGGRR):").pack(pady=5)
        self.color_punto = ttk.Entry(frame_punto)
        self.color_punto.insert(0, self.estilos["punto"]["color"])
        self.color_punto.pack(pady=5)

        # Botón para seleccionar color
        ttk.Button(frame_punto, text="Seleccionar color", command=lambda: self.seleccionar_color(self.color_punto)).pack(pady=5)

        ttk.Label(frame_punto, text="Escala:").pack(pady=5)
        self.escala_punto = ttk.Entry(frame_punto)
        self.escala_punto.insert(0, self.estilos["punto"]["escala"])
        self.escala_punto.pack(pady=5)

        ttk.Label(frame_punto, text="URL del ícono:").pack(pady=5)
        self.icono_punto = ttk.Entry(frame_punto)
        self.icono_punto.insert(0, self.estilos["punto"]["icono"])
        self.icono_punto.pack(pady=5)

        # Pestaña para Polilíneas
        frame_polilinea = ttk.Frame(notebook)
        notebook.add(frame_polilinea, text="Polilínea")

        ttk.Label(frame_polilinea, text="Color (AABBGGRR):").pack(pady=5)
        self.color_polilinea = ttk.Entry(frame_polilinea)
        self.color_polilinea.insert(0, self.estilos["polilinea"]["color"])
        self.color_polilinea.pack(pady=5)

        # Botón para seleccionar color
        ttk.Button(frame_polilinea, text="Seleccionar color", command=lambda: self.seleccionar_color(self.color_polilinea)).pack(pady=5)

        ttk.Label(frame_polilinea, text="Grosor de línea:").pack(pady=5)
        self.grosor_polilinea_var = tk.IntVar(value=self.estilos["polilinea"]["grosor"])
        self.grosor_polilinea = ttk.Scale(frame_polilinea, from_=1, to=10, variable=self.grosor_polilinea_var, orient=tk.HORIZONTAL)
        self.grosor_polilinea.pack(pady=5)

        # Campo para editar el grosor manualmente
        self.grosor_polilinea_entry = ttk.Entry(frame_polilinea, textvariable=self.grosor_polilinea_var)
        self.grosor_polilinea_entry.pack(pady=5)

        # Pestaña para Polígonos
        frame_poligono = ttk.Frame(notebook)
        notebook.add(frame_poligono, text="Polígono")

        ttk.Label(frame_poligono, text="Color de relleno (AABBGGRR):").pack(pady=5)
        self.color_relleno_poligono = ttk.Entry(frame_poligono)
        self.color_relleno_poligono.insert(0, self.estilos["poligono"]["color_relleno"])
        self.color_relleno_poligono.pack(pady=5)

        # Botón para seleccionar color
        ttk.Button(frame_poligono, text="Seleccionar color", command=lambda: self.seleccionar_color(self.color_relleno_poligono)).pack(pady=5)

        ttk.Label(frame_poligono, text="Color de borde (AABBGGRR):").pack(pady=5)
        self.color_borde_poligono = ttk.Entry(frame_poligono)
        self.color_borde_poligono.insert(0, self.estilos["poligono"]["color_borde"])
        self.color_borde_poligono.pack(pady=5)

        # Botón para seleccionar color
        ttk.Button(frame_poligono, text="Seleccionar color", command=lambda: self.seleccionar_color(self.color_borde_poligono)).pack(pady=5)

        ttk.Label(frame_poligono, text="Grosor de borde:").pack(pady=5)
        self.grosor_borde_poligono_var = tk.IntVar(value=self.estilos["poligono"]["grosor_borde"])
        self.grosor_borde_poligono = ttk.Scale(frame_poligono, from_=1, to=10, variable=self.grosor_borde_poligono_var, orient=tk.HORIZONTAL)
        self.grosor_borde_poligono.pack(pady=5)

        # Campo para editar el grosor manualmente
        self.grosor_borde_poligono_entry = ttk.Entry(frame_poligono, textvariable=self.grosor_borde_poligono_var)
        self.grosor_borde_poligono_entry.pack(pady=5)

        # Botón para guardar configuraciones
        ttk.Button(ventana_config, text="Guardar", command=lambda: self.guardar_configuraciones(
            self.color_punto.get(),
            self.escala_punto.get(),
            self.icono_punto.get(),
            self.color_polilinea.get(),
            self.grosor_polilinea_var.get(),
            self.color_relleno_poligono.get(),
            self.color_borde_poligono.get(),
            self.grosor_borde_poligono_var.get(),
            self.relleno_poligono.get(),
            self.contorno_poligono.get(),
            self.opacidad.get()
        )).pack(pady=10)

    # gui/main_window.py (fragmento actualizado)
    def seleccionar_color(self, campo_color):
        """Abre un selector de colores y actualiza el campo de texto con formato RRGGBB."""
        color_rgb = colorchooser.askcolor()[1]  # Devuelve formato #RRGGBB
        if color_rgb:
            color_rrggbb = color_rgb.lstrip("#")  # Eliminar el "#"
            campo_color.delete(0, tk.END)
            campo_color.insert(0, color_rrggbb)

    def guardar_configuraciones(self, color_punto, escala_punto, icono_punto, color_polilinea, grosor_polilinea, color_relleno_poligono, color_borde_poligono, grosor_borde_poligono, relleno_poligono, contorno_poligono, opacidad):
        """Guarda las configuraciones de estilos."""
        self.estilos["punto"] = {"color": color_punto, "escala": float(escala_punto), "icono": icono_punto}
        self.estilos["polilinea"] = {"color": color_polilinea, "grosor": int(grosor_polilinea)}
        self.estilos["poligono"] = {
            "color_relleno": color_relleno_poligono,
            "color_borde": color_borde_poligono,
            "grosor_borde": int(grosor_borde_poligono),
            "relleno": relleno_poligono,
            "contorno": contorno_poligono
        }
        self.opacidad.set(opacidad)  # Guardar la opacidad (1-100)
        messagebox.showinfo("Información", "Configuraciones guardadas correctamente.")

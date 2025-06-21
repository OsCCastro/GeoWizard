from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox,
    QDialogButtonBox, QTabWidget,
    QWidget, QDoubleSpinBox, QSpinBox
)
from PySide6.QtCore import Qt

class ConfigDialog(QDialog):
    def __init__(self, parent=None, current_values=None):
        super().__init__(parent)
        self.setWindowTitle("Configuraciones")
        self._build_ui()
        if current_values:
            self.load_values(current_values)

    def load_values(self, values):
        self.theme_checkbox.setChecked(values.get("dark_mode", False))
        self.precision_edit.setText(values.get("precision", ""))
        self.default_dir_edit.setText(values.get("default_dir", ""))
        self.scale_spin.setValue(values.get("draw_scale", 0.35))
        self.point_size_spin.setValue(values.get("point_size", 6))
        self.font_size_spin.setValue(values.get("font_size", 8))

    def _build_ui(self):
        layout = QVBoxLayout(self)

        tabs = QTabWidget()
        layout.addWidget(tabs)

        general = QWidget()
        form = QFormLayout(general)
        self.theme_checkbox = QCheckBox()
        form.addRow("Tema oscuro:", self.theme_checkbox)

        self.precision_edit = QLineEdit()
        self.precision_edit.setPlaceholderText("Ej. 2")
        form.addRow("Decimales (precisión):", self.precision_edit)

        self.default_dir_edit = QLineEdit()
        self.default_dir_edit.setPlaceholderText("Ruta por defecto")
        form.addRow("Carpeta por defecto:", self.default_dir_edit)
        tabs.addTab(general, "General")

        sim = QWidget()
        sim_form = QFormLayout(sim)
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.05, 10.0)
        self.scale_spin.setSingleStep(0.05)
        self.scale_spin.setValue(0.35)
        sim_form.addRow("Escala de dibujo:", self.scale_spin)

        self.point_size_spin = QSpinBox()
        self.point_size_spin.setRange(1, 20)
        self.point_size_spin.setValue(6)
        sim_form.addRow("Tamaño del punto:", self.point_size_spin)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(1, 24)
        self.font_size_spin.setValue(8)
        sim_form.addRow("Tamaño de letra:", self.font_size_spin)
        tabs.addTab(sim, "Simulación")

        # Botones Aceptar / Cancelar
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        """
        Devuelve un dict con los valores ingresados,
        tras un exec() exitoso.
        """
        return {
            "dark_mode":   self.theme_checkbox.isChecked(),
            "precision":   self.precision_edit.text().strip(),
            "default_dir": self.default_dir_edit.text().strip(),
            "draw_scale":  self.scale_spin.value(),
            "point_size":  self.point_size_spin.value(),
            "font_size":   self.font_size_spin.value(),
        }

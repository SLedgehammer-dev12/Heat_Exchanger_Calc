import sys
import json
import os
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QFormLayout, QComboBox, QDoubleSpinBox, QPushButton, QCheckBox,
                             QLabel, QTabWidget, QTableWidget, QTableWidgetItem, QMessageBox, 
                             QGroupBox, QMenuBar, QAction, QFileDialog, QStackedWidget)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt

from heat_exchanger import Fluid, FinTubeHeatExchanger
from fluids_db import get_fluid_list_flat, get_fluid_data, get_mixture_fluid_data, materialize_fluid_data
from reporting import build_calculation_report
from updater import check_for_update, open_release_page
from version import APP_NAME, VERSION
from logging_config import setup_logging

import logging
from PyQt5.QtCore import QObject, pyqtSignal, QThread

LOG_FILE = setup_logging("desktop")
logger = logging.getLogger(__name__)

class QLogHandler(logging.Handler, QObject):
    log_signal = pyqtSignal(str, int)
    
    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.log_signal.emit(msg, record.levelno)
        except Exception:
            pass

from PyQt5.QtWidgets import QDialog, QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, QVBoxLayout, QHBoxLayout, QPushButton, QMessageBox


def to_kg_s(val, unit, density):
    if unit == "kg/h": return val / 3600.0
    if unit == "lb/s": return val * 0.453592
    if unit == "m³/s": return val * density
    if unit == "m³/h": return (val / 3600.0) * density
    if unit == "CFM": return (val * 0.000471947) * density
    return val

def to_celsius(val, unit):
    if unit == "°F": return (val - 32.0) * 5.0 / 9.0
    if unit == "K": return val - 273.15
    return val

def from_celsius(val, unit):
    if unit == "°F": return (val * 9.0 / 5.0) + 32.0
    if unit == "K": return val + 273.15
    return val

def create_unit_combo(items):
    c = QComboBox()
    c.addItems(items)
    return c

def create_input_row(spin, combo):
    lay = QHBoxLayout()
    lay.setContentsMargins(0,0,0,0)
    lay.addWidget(spin)
    lay.addWidget(combo)
    lay.setStretch(0, 3)
    lay.setStretch(1, 1)
    w = QWidget()
    w.setLayout(lay)
    return w


def result_warnings(*results):
    warnings = []
    for result in results:
        if not result:
            continue
        for msg in result.get("warnings", []):
            if msg not in warnings:
                warnings.append(msg)
    return warnings


def fluid_report_data(label, fluid_data, fluid_obj):
    return {
        "label": label,
        "name": fluid_obj.name,
        "source": fluid_data.get("property_source") or getattr(fluid_obj, "property_source", None) or ("CoolProp" if fluid_obj.is_coolprop else "Manual/Correlation"),
        "cp": fluid_obj.cp,
        "density": fluid_obj.density,
        "mu": fluid_obj.mu,
        "k_cond": fluid_obj.k_cond,
    }

class CompositionDialog(QDialog):
    def __init__(self, parent=None, current_comp=None, current_basis="mole"):
        super().__init__(parent)
        self.setWindowTitle('Egzoz Gazı Kompozisyonu Düzenleyici')
        self.resize(500, 400)
        
        self.layout = QVBoxLayout(self)
        
        # Presets
        preset_layout = QHBoxLayout()
        btn_ng = QPushButton('Doğal Gaz (Tipik)')
        btn_ng.clicked.connect(lambda: self.load_preset({'Nitrogen': 75.0, 'Oxygen': 13.0, 'Water': 8.0, 'CarbonDioxide': 4.0}))
        btn_coal = QPushButton('Kömür (Ağır)')
        btn_coal.clicked.connect(lambda: self.load_preset({'Nitrogen': 72.0, 'Oxygen': 6.0, 'Water': 6.0, 'CarbonDioxide': 15.0, 'SulfurDioxide': 1.0}))
        btn_bio = QPushButton('Biyogaz')
        btn_bio.clicked.connect(lambda: self.load_preset({'Nitrogen': 65.0, 'Oxygen': 5.0, 'Water': 15.0, 'CarbonDioxide': 15.0}))
        
        preset_layout.addWidget(btn_ng)
        preset_layout.addWidget(btn_coal)
        preset_layout.addWidget(btn_bio)
        self.layout.addLayout(preset_layout)

        self.combo_basis = QComboBox()
        self.combo_basis.addItems(["Molar yüzde (%)", "Kütlesel yüzde (%)"])
        self.combo_basis.setCurrentText("Kütlesel yüzde (%)" if current_basis == "mass" else "Molar yüzde (%)")
        self.layout.addWidget(QLabel("Kompozisyon Bazı"))
        self.layout.addWidget(self.combo_basis)
        
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(['Gaz Bileşeni', 'Oran (%)'])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout.addWidget(self.table)
        
        btn_layout = QHBoxLayout()
        btn_add = QPushButton('+ Satır Ekle')
        btn_add.clicked.connect(self.add_row)
        btn_rem = QPushButton('- Seçili Satırı Sil')
        btn_rem.clicked.connect(self.remove_row)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_rem)
        self.layout.addLayout(btn_layout)
        
        save_btn = QPushButton('Kaydet ve Çık')
        save_btn.setStyleSheet('background-color: #27ae60; color: white; font-weight: bold; padding: 8px;')
        save_btn.clicked.connect(self.accept)
        self.layout.addWidget(save_btn)
        
        self.gases = ['Nitrogen', 'Oxygen', 'CarbonDioxide', 'Water', 'Argon', 'CarbonMonoxide', 'Methane', 'Hydrogen', 'SulfurDioxide']
        
        if current_comp:
            self.load_preset(current_comp)
        else:
            self.load_preset({'Nitrogen': 76.0, 'Oxygen': 11.0, 'Water': 6.0, 'CarbonDioxide': 7.0})
            
    def load_preset(self, comp_dict):
        self.table.setRowCount(0)
        for gas, val in comp_dict.items():
            self.add_row(gas, val)
            
    def add_row(self, gas_name='Nitrogen', val=0.0):
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        combo = QComboBox()
        combo.addItems(self.gases)
        if gas_name in self.gases:
            combo.setCurrentText(gas_name)
        self.table.setCellWidget(row, 0, combo)
        
        item_val = QTableWidgetItem(str(val))
        self.table.setItem(row, 1, item_val)
        
    def remove_row(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            
    def get_composition(self):
        comp = {}
        for r in range(self.table.rowCount()):
            combo = self.table.cellWidget(r, 0)
            if combo:
                gas = combo.currentText()
                val_str = self.table.item(r, 1).text()
                try:
                    val = float(val_str)
                    if gas in comp:
                        comp[gas] += val
                    else:
                        comp[gas] = val
                except:
                    pass
        return comp

    def get_basis(self):
        return "mass" if "Kütlesel" in self.combo_basis.currentText() else "mole"



FLOW_LABEL_TO_INTERNAL = {
    "Çapraz Akış (Cross Flow Unmixed)": "cross_unmixed",
    "Ters Akış (Counter Flow)": "counter",
    "Paralel Akış (Parallel Flow)": "parallel",
}
LOAD_KEY_ALIASES = {
    "calc_purpose": "purpose",
    "u_calc_mode": "u_mode",
    "hot_fluid_sel": "hot_fluid",
    "cold_fluid_sel": "cold_fluid",
    "T_hot_in": "t_hot_in",
    "T_cold_in": "t_cold_in",
    "T_hot_out_opt": "t_hot_out_opt",
    "T_cold_out_opt": "t_cold_out_opt",
    "U_value": "U",
    "Area": "A",
    "D_o_mm": "Do",
    "D_i_mm": "Di",
    "L_m": "L",
    "N_tubes": "Nt",
    "hot_is_tube": "hot_tube",
    "tube_material": "tube_mat",
    "fin_material": "fin_mat",
    "fin_h_mm": "fin_h",
    "fin_t_mm": "fin_t",
    "fin_density": "fin_dens",
}


def normalize_loaded_data(data):
    normalized = dict(data)
    for new_key, old_key in LOAD_KEY_ALIASES.items():
        if new_key in normalized and old_key not in normalized:
            normalized[old_key] = normalized[new_key]

    flow_value = normalized.get("flow_type")
    if flow_value in FLOW_LABEL_TO_INTERNAL:
        normalized["flow_type"] = FLOW_LABEL_TO_INTERNAL[flow_value]
    if normalized.get("u_mode") == "Geometrik Mod (Malzeme ve Çap ile Hesapla)":
        normalized["u_mode"] = "Geometrik Mod (Malzeme ile Hesapla)"
    return normalized


class HeatExchangerDesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Desktop v{VERSION}")
        self.resize(1100, 800)
        self.all_logs = []
        self.initUI()
        self.setup_ui_logging()
        logger.info("Desktop application started. Version=%s", VERSION)
        QTimer.singleShot(1500, self.check_updates_on_startup)

    def setup_ui_logging(self):
        self.qt_log_handler = QLogHandler()
        self.qt_log_handler.setLevel(logging.DEBUG)
        self.qt_log_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s", "%H:%M:%S"))
        self.qt_log_handler.log_signal.connect(self.append_log)
        logging.getLogger().addHandler(self.qt_log_handler)
        
    def initUI(self):
        # Menu Bar for Save/Load
        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&Dosya')
        
        saveAct = QAction('💾 Kaydet', self)
        saveAct.setShortcut('Ctrl+S')
        saveAct.triggered.connect(self.save_data)
        fileMenu.addAction(saveAct)
        
        loadAct = QAction('📂 Yükle', self)
        loadAct.setShortcut('Ctrl+O')
        loadAct.triggered.connect(self.load_data)
        fileMenu.addAction(loadAct)

        helpMenu = menubar.addMenu('&Yardım')
        updateAct = QAction('Güncellemeyi Kontrol Et', self)
        updateAct.triggered.connect(lambda: self.check_for_updates(show_no_update=True))
        helpMenu.addAction(updateAct)

        logAct = QAction('Log Klasörünü Aç', self)
        logAct.triggered.connect(self.open_log_folder)
        helpMenu.addAction(logAct)

        aboutAct = QAction('Hakkında', self)
        aboutAct.triggered.connect(lambda: QMessageBox.information(
            self,
            "Hakkında",
            f"{APP_NAME} v{VERSION}\nFin-tube heat exchanger calculation and reporting tool."
        ))
        helpMenu.addAction(aboutAct)

    def open_log_folder(self):
        os.startfile(os.path.dirname(LOG_FILE))

    def show_error(self, title, message, exc=None):
        if exc is not None:
            logger.exception("%s: %s", title, message)
        else:
            logger.error("%s: %s", title, message)
        QMessageBox.critical(
            self,
            title,
            f"{message}\n\nDetaylı log dosyası:\n{LOG_FILE}",
        )

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        
        # --- SOL PANEL ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(450)
        
        # 1. Konfigürasyon
        group_config = QGroupBox("⚙️ Ayarlar")
        form_config = QFormLayout(group_config)
        self.combo_flow = QComboBox()
        self.combo_flow.addItems(['cross_unmixed', 'counter', 'parallel'])
        
        self.combo_method = QComboBox()
        self.combo_method.addItems(['Kendi Algoritmamız (Epsilon-NTU)', 'Kendi Algoritmamız (LMTD)', 'HT Kütüphanesi (Epsilon-NTU)', 'HT Kütüphanesi (LMTD)'])
        
        self.combo_purpose = QComboBox()
        self.combo_purpose.addItems(['Sistem Tasarımı (Çıkış Sıcaklıklarını Bul)', 'Performans Değerlendirmesi (Verim Bul)'])
        self.combo_purpose.currentTextChanged.connect(self.toggle_purpose)
        
        self.combo_u_mode = QComboBox()
        self.combo_u_mode.addItems(['Basit Mod (Manuel U Değeri)', 'Geometrik Mod (Malzeme ile Hesapla)'])
        self.combo_u_mode.currentTextChanged.connect(self.toggle_u_mode)
        
        form_config.addRow("Hesap Amacı:", self.combo_purpose)
        form_config.addRow("Akış Tipi:", self.combo_flow)
        form_config.addRow("Ana Çözücü Alg.:", self.combo_method)
        form_config.addRow("U Modu:", self.combo_u_mode)
        left_layout.addWidget(group_config)
        
        fluid_list = get_fluid_list_flat()
        
        # 2. Sıcak Akışkan
        group_hot = QGroupBox("🔴 Sıcak Akışkan")
        form_hot = QFormLayout(group_hot)
        self.combo_hot = QComboBox()
        self.combo_hot.addItems(fluid_list)
        self.combo_hot.setCurrentText("Doğal Gaz Türbin Egzoz Gazı (Manuel)")
        
        self.btn_edit_comp = QPushButton("🔧 Kompozisyon Düzenle")
        self.btn_edit_comp.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        self.btn_edit_comp.clicked.connect(self.open_composition_editor)
        self.btn_edit_comp.hide()
        
        self.combo_hot.currentTextChanged.connect(self.toggle_hot_fluid)
        self.hot_mixture_data = {'Nitrogen': 76.0, 'Oxygen': 11.0, 'Water': 6.0, 'CarbonDioxide': 7.0}
        self.hot_mixture_basis = "mole"
        
        self.spin_m_hot = QDoubleSpinBox(); self.spin_m_hot.setRange(0.001, 100000); self.spin_m_hot.setValue(15.0)
        self.combo_u_m_hot = create_unit_combo(["kg/s", "kg/h", "lb/s", "m³/s", "m³/h", "CFM"])
        self.spin_t_hot = QDoubleSpinBox(); self.spin_t_hot.setRange(-9999.0, 9999.0); self.spin_t_hot.setValue(450.0)
        self.combo_u_t_hot = create_unit_combo(["°C", "°F", "K"])
        self.spin_t_hot_out = QDoubleSpinBox(); self.spin_t_hot_out.setRange(-9999.0, 9999.0); self.spin_t_hot_out.setValue(-999.0)
        self.combo_u_t_hot_out = create_unit_combo(["°C", "°F", "K"])
        
        # Manuel Özellikler
        self.spin_mu_hot = QDoubleSpinBox(); self.spin_mu_hot.setRange(0.000001, 1000); self.spin_mu_hot.setDecimals(6); self.spin_mu_hot.setValue(0.00002); self.spin_mu_hot.setSuffix(" Pa.s")
        self.spin_k_hot = QDoubleSpinBox(); self.spin_k_hot.setRange(0.001, 1000); self.spin_k_hot.setDecimals(4); self.spin_k_hot.setValue(0.03); self.spin_k_hot.setSuffix(" W/mK")

        
        form_hot.addRow("Akışkan:", self.combo_hot)
        form_hot.addRow("", self.btn_edit_comp)
        form_hot.addRow("Debi:", create_input_row(self.spin_m_hot, self.combo_u_m_hot))
        form_hot.addRow("Giriş Sıc.:", create_input_row(self.spin_t_hot, self.combo_u_t_hot))
        self.lbl_t_hot_out = QLabel("Çıkış Sıc.:")
        
        lay_hout = QHBoxLayout(); lay_hout.setContentsMargins(0,0,0,0)
        lay_hout.addWidget(self.spin_t_hot_out)
        lay_hout.addWidget(self.combo_u_t_hot_out)
        lay_hout.setStretch(0, 3); lay_hout.setStretch(1, 1)
        self.w_t_hot_out = QWidget(); self.w_t_hot_out.setLayout(lay_hout)
        
        form_hot.addRow(self.lbl_t_hot_out, self.w_t_hot_out)
        form_hot.addRow("Manuel Viskozite:", self.spin_mu_hot)
        form_hot.addRow("Manuel İletkenlik:", self.spin_k_hot)
        left_layout.addWidget(group_hot)
        
        # 3. Soğuk Akışkan
        group_cold = QGroupBox("🔵 Soğuk Akışkan")
        form_cold = QFormLayout(group_cold)
        self.combo_cold = QComboBox()
        self.combo_cold.addItems(fluid_list)
        self.combo_cold.setCurrentText("Therminol 66")

        self.btn_edit_comp_cold = QPushButton("🔧 Kompozisyon Düzenle")
        self.btn_edit_comp_cold.setStyleSheet("background-color: #3498db; color: white; font-weight: bold;")
        self.btn_edit_comp_cold.clicked.connect(self.open_cold_composition_editor)
        self.btn_edit_comp_cold.hide()
        self.combo_cold.currentTextChanged.connect(self.toggle_cold_fluid)
        self.cold_mixture_data = {'Nitrogen': 76.0, 'Oxygen': 11.0, 'Water': 6.0, 'CarbonDioxide': 7.0}
        self.cold_mixture_basis = "mole"
        
        self.spin_m_cold = QDoubleSpinBox(); self.spin_m_cold.setRange(0.001, 100000); self.spin_m_cold.setValue(5.0)
        self.combo_u_m_cold = create_unit_combo(["kg/s", "kg/h", "lb/s", "m³/s", "m³/h", "CFM"])
        self.spin_t_cold = QDoubleSpinBox(); self.spin_t_cold.setRange(-9999.0, 9999.0); self.spin_t_cold.setValue(120.0)
        self.combo_u_t_cold = create_unit_combo(["°C", "°F", "K"])
        self.spin_t_cold_out = QDoubleSpinBox(); self.spin_t_cold_out.setRange(-9999.0, 9999.0); self.spin_t_cold_out.setValue(-999.0)
        self.combo_u_t_cold_out = create_unit_combo(["°C", "°F", "K"])
        
        self.spin_mu_cold = QDoubleSpinBox(); self.spin_mu_cold.setRange(0.000001, 1000); self.spin_mu_cold.setDecimals(6); self.spin_mu_cold.setValue(0.001); self.spin_mu_cold.setSuffix(" Pa.s")
        self.spin_k_cold = QDoubleSpinBox(); self.spin_k_cold.setRange(0.001, 1000); self.spin_k_cold.setDecimals(4); self.spin_k_cold.setValue(0.15); self.spin_k_cold.setSuffix(" W/mK")
        
        form_cold.addRow("Akışkan:", self.combo_cold)
        form_cold.addRow("", self.btn_edit_comp_cold)
        form_cold.addRow("Debi:", create_input_row(self.spin_m_cold, self.combo_u_m_cold))
        form_cold.addRow("Giriş Sıc.:", create_input_row(self.spin_t_cold, self.combo_u_t_cold))
        self.lbl_t_cold_out = QLabel("Çıkış Sıc.:")
        
        lay_cout = QHBoxLayout(); lay_cout.setContentsMargins(0,0,0,0)
        lay_cout.addWidget(self.spin_t_cold_out)
        lay_cout.addWidget(self.combo_u_t_cold_out)
        lay_cout.setStretch(0, 3); lay_cout.setStretch(1, 1)
        self.w_t_cold_out = QWidget(); self.w_t_cold_out.setLayout(lay_cout)
        
        form_cold.addRow(self.lbl_t_cold_out, self.w_t_cold_out)
        form_cold.addRow("Manuel Viskozite:", self.spin_mu_cold)
        form_cold.addRow("Manuel İletkenlik:", self.spin_k_cold)
        left_layout.addWidget(group_cold)
        
        # 4. U Modu Stack
        self.stack_geom = QStackedWidget()
        
        # 4.a Basit Mod
        page_simple = QWidget()
        form_simple = QFormLayout(page_simple)
        self.spin_U = QDoubleSpinBox(); self.spin_U.setRange(0.1, 10000); self.spin_U.setValue(50.0); self.spin_U.setSuffix(" W/m²K")
        self.spin_A = QDoubleSpinBox(); self.spin_A.setRange(0.1, 100000); self.spin_A.setValue(200.0); self.spin_A.setSuffix(" m²")
        form_simple.addRow("U Katsayısı:", self.spin_U)
        form_simple.addRow("Toplam Alan:", self.spin_A)
        self.stack_geom.addWidget(page_simple)
        
        # 4.b Geometrik Mod
        page_geo = QWidget()
        form_geo = QFormLayout(page_geo)
        
        self.spin_do = QDoubleSpinBox(); self.spin_do.setRange(1, 1000); self.spin_do.setValue(25.4); self.spin_do.setSuffix(" mm")
        self.spin_di = QDoubleSpinBox(); self.spin_di.setRange(1, 1000); self.spin_di.setValue(21.1); self.spin_di.setSuffix(" mm")
        self.spin_l = QDoubleSpinBox(); self.spin_l.setRange(0.1, 100); self.spin_l.setValue(3.0); self.spin_l.setSuffix(" m")
        self.spin_nt = QDoubleSpinBox(); self.spin_nt.setRange(1, 10000); self.spin_nt.setValue(100); self.spin_nt.setDecimals(0)
        
        self.combo_tube_mat = QComboBox()
        self.tube_mats = {"Karbon Çelik": 45.0, "Paslanmaz Çelik 316": 16.0, "Bakır": 400.0, "Alüminyum": 237.0}
        self.combo_tube_mat.addItems(list(self.tube_mats.keys()))
        
        self.combo_hot_tube = QComboBox()
        self.combo_hot_tube.addItems(["Soğuk Akışkan", "Sıcak Akışkan"])
        
        self.chk_finned = QCheckBox("Kanatçıklı (Finned)")
        self.chk_finned.setChecked(True)
        self.spin_fin_h = QDoubleSpinBox(); self.spin_fin_h.setRange(1, 100); self.spin_fin_h.setValue(15.9); self.spin_fin_h.setSuffix(" mm")
        self.spin_fin_t = QDoubleSpinBox(); self.spin_fin_t.setRange(0.1, 10); self.spin_fin_t.setValue(0.4); self.spin_fin_t.setSuffix(" mm")
        self.spin_fin_dens = QDoubleSpinBox(); self.spin_fin_dens.setRange(1, 10000); self.spin_fin_dens.setValue(400); self.spin_fin_dens.setSuffix(" (1/m)"); self.spin_fin_dens.setDecimals(0)
        self.combo_fin_mat = QComboBox()
        self.combo_fin_mat.addItems(["Alüminyum (k=237)", "Karbon Çelik (k=45)"])
        
        form_geo.addRow("Dış Çap (Do):", self.spin_do)
        form_geo.addRow("İç Çap (Di):", self.spin_di)
        form_geo.addRow("Boru Uzunluğu:", self.spin_l)
        form_geo.addRow("Boru Sayısı:", self.spin_nt)
        form_geo.addRow("Boru Malzemesi:", self.combo_tube_mat)
        form_geo.addRow("İç Boruda:", self.combo_hot_tube)
        form_geo.addRow("Kanatçık?:", self.chk_finned)
        form_geo.addRow(" Fin Yüksekliği:", self.spin_fin_h)
        form_geo.addRow(" Fin Kalınlığı:", self.spin_fin_t)
        form_geo.addRow(" Fin Yoğunluğu:", self.spin_fin_dens)
        form_geo.addRow(" Fin Malzemesi:", self.combo_fin_mat)
        
        self.stack_geom.addWidget(page_geo)
        
        left_layout.addWidget(QLabel("🔲 Isı Değiştirici Özellikleri"))
        left_layout.addWidget(self.stack_geom)
        
        # Buton
        self.btn_calc = QPushButton("🚀 HESAPLA VE DOĞRULA")
        self.btn_calc.setMinimumHeight(50)
        self.btn_calc.setStyleSheet("background-color: #2e86c1; color: white; font-weight: bold; font-size: 14px;")
        self.btn_calc.clicked.connect(self.calculate)
        left_layout.addWidget(self.btn_calc)
        
        left_layout.addStretch()
        main_layout.addWidget(left_panel)
        
        # --- SAĞ PANEL (Sekmeler - Sonuçlar) ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)
        
        # Sonuçlar
        self.tab_results = QWidget()
        res_layout = QVBoxLayout(self.tab_results)
        
        # Sonuç Yazıları
        self.lbl_geo_res = QLabel("")
        self.lbl_geo_res.setWordWrap(True)
        res_layout.addWidget(self.lbl_geo_res)
        
        self.lbl_res_q = QLabel("Transfer Edilen Isı (Q): -")
        self.lbl_res_th = QLabel("Sıcak Akışkan Çıkış Sıcaklığı: -")
        self.lbl_res_tc = QLabel("Soğuk Akışkan Çıkış Sıcaklığı: -")
        self.lbl_res_eff = QLabel("Teorik Isı Değiştirici Verimi (ε): -")
        self.lbl_res_act = QLabel("") # Gerçekleşen performans için
        
        for lbl in [self.lbl_res_q, self.lbl_res_th, self.lbl_res_tc, self.lbl_res_eff, self.lbl_res_act]:
            lbl.setFont(QFont("Arial", 12, QFont.Bold))
            lbl.setStyleSheet("color: #2c3e50; padding: 5px;")
            res_layout.addWidget(lbl)
            
        self.btn_export_report = QPushButton("📄 Sonuç Raporunu Dışa Aktar")
        self.btn_export_report.setStyleSheet("background-color: #e67e22; color: white; padding: 10px; font-weight: bold;")
        self.btn_export_report.clicked.connect(self.export_report)
        res_layout.addWidget(self.btn_export_report)
        self.btn_export_report.hide() # Hesaplama yapılana kadar gizli
        
        # Grafik için Figure ve Canvas (Sonuçlar sekmesinin en altına)
        self.figure = plt.figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        res_layout.addWidget(self.canvas)
            
        # Sekme 2: Doğrulama
        self.tab_cc = QWidget()
        cc_layout = QVBoxLayout(self.tab_cc)
        self.table_cc = QTableWidget(4, 8)
        self.table_cc.setHorizontalHeaderLabels(["Metot", "Kaynak", "Durum", "Q (kW)", "Q Sapma (%)", "Sıcak Çıkış (°C)", "Soğuk Çıkış (°C)", "Uyarılar"])
        self.table_cc.horizontalHeader().setStretchLastSection(True)
        cc_layout.addWidget(self.table_cc)
        
        self.tabs.addTab(self.tab_results, "📊 Sonuçlar")
        self.tabs.addTab(self.tab_cc, "🔍 Cross-Check")
        
        # Sekme 3: Sistem Logları
        self.tab_log = QWidget()
        log_layout = QVBoxLayout(self.tab_log)
        
        top_log_lay = QHBoxLayout()
        top_log_lay.addWidget(QLabel("Log Seviyesi Filtresi:"))
        self.combo_log_level = QComboBox()
        self.combo_log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.combo_log_level.setCurrentText("INFO")
        self.combo_log_level.currentTextChanged.connect(self.refresh_logs)
        top_log_lay.addWidget(self.combo_log_level)
        top_log_lay.addStretch()
        
        log_layout.addLayout(top_log_lay)
        
        from PyQt5.QtWidgets import QPlainTextEdit
        self.text_log = QPlainTextEdit()
        self.text_log.setReadOnly(True)
        # Siyah arkaplan ve yesil metin (Hacker style)
        self.text_log.setStyleSheet("background-color: #1e1e1e; color: #00ff00; font-family: Consolas;")
        log_layout.addWidget(self.text_log)
        
        self.tabs.addTab(self.tab_log, "📝 Sistem Logları")
        
        self.toggle_purpose(self.combo_purpose.currentText())
        self.toggle_hot_fluid(self.combo_hot.currentText())
        self.toggle_cold_fluid(self.combo_cold.currentText())

    def export_report(self):
        if not hasattr(self, 'last_res_main'):
            QMessageBox.warning(self, "Hata", "Önce hesaplama yapmalısınız!")
            return
            
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(self, "Raporu Kaydet", "isi_degistirici_raporu.txt", "Text Files (*.txt);;All Files (*)", options=options)
        if fileName:
            try:
                with open(fileName, 'w', encoding='utf-8') as f:
                    f.write(build_calculation_report(self.last_report_context))
                        
                QMessageBox.information(self, "Başarılı", "Rapor başarıyla kaydedildi!")
            except Exception as e:
                self.show_error("Hata", f"Kaydetme hatası: {str(e)}", e)


    
    def append_log(self, msg, levelno):
        if len(self.all_logs) > 5000:
            self.all_logs.pop(0) # Keep max 5000 lines
        self.all_logs.append((msg, levelno))
        

    def filter_and_display_last_log(self, msg, levelno):
        level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}
        if levelno >= level_map.get(self.combo_log_level.currentText(), logging.INFO):
            self.text_log.appendPlainText(msg)

    def refresh_logs(self):
        level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}
        selected_level = level_map.get(self.combo_log_level.currentText(), logging.INFO)
        
        filtered_msgs = [msg for msg, levelno in self.all_logs if levelno >= selected_level]
        self.text_log.setPlainText("\\n".join(filtered_msgs))
        
        # Sona kaydır
        scrollbar = self.text_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def check_updates_on_startup(self):
        self.check_for_updates(show_no_update=False)

    def check_for_updates(self, show_no_update=False):
        result = check_for_update()
        self.append_log(result.get("message", ""), logging.INFO if result.get("ok") else logging.WARNING)
        if result.get("update_available"):
            reply = QMessageBox.information(
                self,
                "Güncelleme Bulundu",
                f"{result['message']}\nMevcut sürüm: v{VERSION}\nRelease sayfası açılsın mı?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                open_release_page(result.get("release_url"))
        elif show_no_update:
            QMessageBox.information(self, "Güncelleme Kontrolü", result.get("message", "Güncelleme bulunamadı."))

    def toggle_hot_fluid(self, text):
        is_mixture = self.is_exhaust_mixture(text)
        self.btn_edit_comp.setVisible(is_mixture)
        self.set_manual_property_controls("hot", self.is_custom_manual(text))

    def toggle_cold_fluid(self, text):
        is_mixture = self.is_exhaust_mixture(text)
        self.btn_edit_comp_cold.setVisible(is_mixture)
        self.set_manual_property_controls("cold", self.is_custom_manual(text))

    def is_exhaust_mixture(self, text):
        data = get_fluid_data(text) or {}
        return bool(data.get("is_mixture")) or "Egzoz" in text or "Kompozisyon" in text

    def is_custom_manual(self, text):
        return "Manuel Giriş" in text

    def set_manual_property_controls(self, side, enabled):
        widgets = (
            (self.spin_mu_hot, self.spin_k_hot)
            if side == "hot"
            else (self.spin_mu_cold, self.spin_k_cold)
        )
        for widget in widgets:
            widget.setEnabled(enabled)
            
    def open_composition_editor(self):
        dialog = CompositionDialog(self, self.hot_mixture_data, self.hot_mixture_basis)
        if dialog.exec_():
            self.hot_mixture_data = dialog.get_composition()
            self.hot_mixture_basis = dialog.get_basis()
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, 'Bilgi', 'Kompozisyon kaydedildi.')

    def open_cold_composition_editor(self):
        dialog = CompositionDialog(self, self.cold_mixture_data, self.cold_mixture_basis)
        if dialog.exec_():
            self.cold_mixture_data = dialog.get_composition()
            self.cold_mixture_basis = dialog.get_basis()
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self, 'Bilgi', 'Kompozisyon kaydedildi.')
            
    def toggle_purpose(self, text):
        if "Performans" in text:
            self.lbl_t_hot_out.show()
            self.w_t_hot_out.show()
            self.lbl_t_cold_out.show()
            self.w_t_cold_out.show()
        else:
            self.lbl_t_hot_out.hide()
            self.w_t_hot_out.hide()
            self.lbl_t_cold_out.hide()
            self.w_t_cold_out.hide()

    def toggle_u_mode(self, text):
        if "Geometrik" in text:
            self.stack_geom.setCurrentIndex(1)
        else:
            self.stack_geom.setCurrentIndex(0)

    def save_data(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(self, "Verileri Kaydet", "heat_exchanger_save.json", "JSON Files (*.json);;All Files (*)", options=options)
        if fileName:
            data = {
                "calc_purpose": self.combo_purpose.currentText(),
                "purpose": self.combo_purpose.currentText(),
                "flow_type": self.combo_flow.currentText(),
                "u_calc_mode": self.combo_u_mode.currentText(),
                "solver_method": self.combo_method.currentText(),
                "u_mode": self.combo_u_mode.currentText(),
                "hot_fluid_sel": self.combo_hot.currentText(),
                "hot_fluid": self.combo_hot.currentText(),
                "hot_mixture_data": self.hot_mixture_data,
                "hot_mixture_basis": self.hot_mixture_basis,
                "m_hot": self.spin_m_hot.value(),
                "T_hot_in": self.spin_t_hot.value(),
                "t_hot_in": self.spin_t_hot.value(),
                "T_hot_out_opt": self.spin_t_hot_out.value(),
                "t_hot_out_opt": self.spin_t_hot_out.value(),
                "cold_fluid_sel": self.combo_cold.currentText(),
                "cold_fluid": self.combo_cold.currentText(),
                "cold_mixture_data": self.cold_mixture_data,
                "cold_mixture_basis": self.cold_mixture_basis,
                "m_cold": self.spin_m_cold.value(),
                "T_cold_in": self.spin_t_cold.value(),
                "t_cold_in": self.spin_t_cold.value(),
                "T_cold_out_opt": self.spin_t_cold_out.value(),
                "t_cold_out_opt": self.spin_t_cold_out.value(),
                "U_value": self.spin_U.value(),
                "U": self.spin_U.value(),
                "Area": self.spin_A.value(),
                "A": self.spin_A.value(),
                "D_o_mm": self.spin_do.value(),
                "Do": self.spin_do.value(),
                "D_i_mm": self.spin_di.value(),
                "Di": self.spin_di.value(),
                "L_m": self.spin_l.value(),
                "L": self.spin_l.value(),
                "N_tubes": self.spin_nt.value(),
                "Nt": self.spin_nt.value(),
                "tube_mat": self.combo_tube_mat.currentText(),
                "hot_tube": self.combo_hot_tube.currentText(),
                "cp_hot": get_fluid_data(self.combo_hot.currentText()).get("cp", 1100.0),
                "density_hot": get_fluid_data(self.combo_hot.currentText()).get("density", 0.5),
                "mu_hot": self.spin_mu_hot.value(),
                "k_hot": self.spin_k_hot.value(),
                "cp_cold": get_fluid_data(self.combo_cold.currentText()).get("cp", 2000.0),
                "density_cold": get_fluid_data(self.combo_cold.currentText()).get("density", 850.0),
                "mu_cold": self.spin_mu_cold.value(),
                "k_cold": self.spin_k_cold.value(),
                "is_finned": self.chk_finned.isChecked(),
                "fin_h": self.spin_fin_h.value(),
                "fin_t": self.spin_fin_t.value(),
                "fin_dens": self.spin_fin_dens.value(),
                "fin_mat": self.combo_fin_mat.currentText()
            }
            with open(fileName, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "Başarılı", "Veriler başarıyla kaydedildi.")
            logger.info("Input data saved: %s", fileName)

    def load_data(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(self, "Verileri Yükle", "", "JSON Files (*.json);;All Files (*)", options=options)
        if fileName:
            try:
                with open(fileName, 'r', encoding='utf-8') as f:
                    data = normalize_loaded_data(json.load(f))
                self.combo_purpose.setCurrentText(data.get("purpose", "Sistem Tasarımı (Çıkış Sıcaklıklarını Bul)"))
                self.combo_flow.setCurrentText(data.get("flow_type", "cross_unmixed"))
                self.combo_method.setCurrentText(data.get("solver_method", "Kendi Algoritmamız (Epsilon-NTU)"))
                self.combo_u_mode.setCurrentText(data.get("u_mode", "Basit Mod"))
                self.combo_hot.setCurrentText(data.get("hot_fluid", "Therminol 66"))
                self.hot_mixture_data = data.get("hot_mixture_data", self.hot_mixture_data)
                self.hot_mixture_basis = data.get("hot_mixture_basis", self.hot_mixture_basis)
                self.spin_m_hot.setValue(data.get("m_hot", 15.0))
                self.spin_t_hot.setValue(data.get("t_hot_in", 450.0))
                self.spin_t_hot_out.setValue(data.get("t_hot_out_opt", -999.0))
                
                self.combo_cold.setCurrentText(data.get("cold_fluid", "Su"))
                self.cold_mixture_data = data.get("cold_mixture_data", self.cold_mixture_data)
                self.cold_mixture_basis = data.get("cold_mixture_basis", self.cold_mixture_basis)
                self.spin_m_cold.setValue(data.get("m_cold", 5.0))
                self.spin_t_cold.setValue(data.get("t_cold_in", 120.0))
                self.spin_t_cold_out.setValue(data.get("t_cold_out_opt", -999.0))
                
                self.spin_mu_hot.setValue(data.get("mu_hot", 0.00002))
                self.spin_k_hot.setValue(data.get("k_hot", 0.03))
                self.spin_mu_cold.setValue(data.get("mu_cold", 0.001))
                self.spin_k_cold.setValue(data.get("k_cold", 0.15))
                
                self.spin_U.setValue(data.get("U", 50.0))
                self.spin_A.setValue(data.get("A", 200.0))
                self.spin_do.setValue(data.get("Do", 25.4))
                self.spin_di.setValue(data.get("Di", 21.1))
                self.spin_l.setValue(data.get("L", 3.0))
                self.spin_nt.setValue(data.get("Nt", 100))
                self.combo_tube_mat.setCurrentText(data.get("tube_mat", "Karbon Çelik"))
                self.combo_hot_tube.setCurrentText(data.get("hot_tube", "Soğuk Akışkan"))
                
                self.chk_finned.setChecked(data.get("is_finned", True))
                self.spin_fin_h.setValue(data.get("fin_h", 15.9))
                self.spin_fin_t.setValue(data.get("fin_t", 0.4))
                self.spin_fin_dens.setValue(data.get("fin_dens", 400.0))
                self.combo_fin_mat.setCurrentText(data.get("fin_mat", "Alüminyum (k=237)"))
                self.toggle_hot_fluid(self.combo_hot.currentText())
                self.toggle_cold_fluid(self.combo_cold.currentText())
                
                QMessageBox.information(self, "Başarılı", "Veriler başarıyla yüklendi.")
            except Exception as e:
                self.show_error("Hata", f"Dosya yüklenirken hata oluştu: {str(e)}", e)

    def calculate(self):
        logger.info(
            "Calculation requested. hot=%s cold=%s u_mode=%s solver=%s",
            self.combo_hot.currentText(),
            self.combo_cold.currentText(),
            self.combo_u_mode.currentText(),
            self.combo_method.currentText(),
        )
        T_hot = to_celsius(self.spin_t_hot.value(), self.combo_u_t_hot.currentText())
        T_cold = to_celsius(self.spin_t_cold.value(), self.combo_u_t_cold.currentText())
        m_hot_raw = self.spin_m_hot.value()
        m_cold_raw = self.spin_m_cold.value()
        
        if T_hot <= T_cold:
            QMessageBox.critical(self, "Hata", "Sıcak akışkanın giriş sıcaklığı, soğuk akışkanın giriş sıcaklığından BÜYÜK olmalıdır!")
            return
            
        try:
            hot_data = materialize_fluid_data(get_fluid_data(self.combo_hot.currentText()), T_hot)
            cold_data = materialize_fluid_data(get_fluid_data(self.combo_cold.currentText()), T_cold)
        except Exception as e:
            self.show_error("Akışkan Hatası", str(e), e)
            return
        
        try:
            if hot_data["is_coolprop"]:
                hot_fluid = Fluid(name=hot_data["name"], is_coolprop=True, calc_temp_c=T_hot)
            elif hot_data.get("is_mixture"):
                logger.info("Calculating hot exhaust mixture properties. basis=%s comp=%s", self.hot_mixture_basis, self.hot_mixture_data)
                hot_mix = get_mixture_fluid_data(self.hot_mixture_data, comp_type=self.hot_mixture_basis, T_c=T_hot, P_pa=101325.0)
                hot_fluid = Fluid(name="Özel Egzoz Gazı", cp=hot_mix['cp'], density=hot_mix['density'], mu=hot_mix['mu'], k_cond=hot_mix['k_cond'], is_coolprop=False)
            else:
                hot_fluid = Fluid(
                    name=hot_data["name"],
                    cp=hot_data.get("cp", 1100.0),
                    density=hot_data.get("density", 0.5),
                    mu=self.spin_mu_hot.value(),
                    k_cond=self.spin_k_hot.value(),
                    is_coolprop=False,
                )
                
            if cold_data["is_coolprop"]:
                cold_fluid = Fluid(name=cold_data["name"], is_coolprop=True, calc_temp_c=T_cold)
            elif cold_data.get("is_mixture"):
                logger.info("Calculating cold exhaust mixture properties. basis=%s comp=%s", self.cold_mixture_basis, self.cold_mixture_data)
                cold_mix = get_mixture_fluid_data(self.cold_mixture_data, comp_type=self.cold_mixture_basis, T_c=T_cold, P_pa=101325.0)
                cold_fluid = Fluid(name="Özel Egzoz Gazı", cp=cold_mix['cp'], density=cold_mix['density'], mu=cold_mix['mu'], k_cond=cold_mix['k_cond'], is_coolprop=False)
            else:
                cold_fluid = Fluid(
                    name=cold_data["name"],
                    cp=cold_data.get("cp", 2000.0),
                    density=cold_data.get("density", 850.0),
                    mu=self.spin_mu_cold.value(),
                    k_cond=self.spin_k_cold.value(),
                    is_coolprop=False,
                )
        except Exception as e:
            self.show_error("Akışkan Hatası", str(e), e)
            return
            
        m_hot = to_kg_s(m_hot_raw, self.combo_u_m_hot.currentText(), hot_fluid.density)
        m_cold = to_kg_s(m_cold_raw, self.combo_u_m_cold.currentText(), cold_fluid.density)
        flow_t = self.combo_flow.currentText()
        
        hx = FinTubeHeatExchanger(hot_fluid, cold_fluid, U=1.0, A=1.0, flow_type=flow_t)
        
        is_rating = "Performans" in self.combo_purpose.currentText()
        
        if "Geometrik" in self.combo_u_mode.currentText():
            geom = {
                'D_o': self.spin_do.value() / 1000.0,
                'D_i': self.spin_di.value() / 1000.0,
                'L': self.spin_l.value(),
                'N_tubes': self.spin_nt.value(),
                'k_wall': self.tube_mats[self.combo_tube_mat.currentText()],
                'is_finned': self.chk_finned.isChecked(),
                'fin_height': self.spin_fin_h.value() / 1000.0,
                'fin_thickness': self.spin_fin_t.value() / 1000.0,
                'fin_density': self.spin_fin_dens.value(),
                'k_fin': 237.0 if "Alüminyum" in self.combo_fin_mat.currentText() else 45.0,
                'pitch': self.spin_do.value() * 2 / 1000.0,
                'D_shell': self.spin_do.value() * 1.5 / 1000.0
            }
            hot_is_tube = True if self.combo_hot_tube.currentText() == "Sıcak Akışkan" else False
            
            try:
                # Akışkan özelliklerini Fluids DB'den veya arayüzden al
                hot_name = self.combo_hot.currentText()
                cold_name = self.combo_cold.currentText()
                hot_data = materialize_fluid_data(get_fluid_data(hot_name), T_hot)
                cold_data = materialize_fluid_data(get_fluid_data(cold_name), T_cold)
                
                if hot_data and hot_data.get('is_mixture'):
                    hot_mix = get_mixture_fluid_data(self.hot_mixture_data, comp_type=self.hot_mixture_basis, T_c=T_hot, P_pa=101325.0)
                    hx.hot_fluid = Fluid(name="Özel Egzoz Gazı", is_coolprop=False, cp=hot_mix['cp'], density=hot_mix['density'], mu=hot_mix['mu'], k_cond=hot_mix['k_cond'])
                elif hot_data and not hot_data.get('is_coolprop'):
                    hx.hot_fluid = Fluid(name=hot_name, is_coolprop=False, cp=hot_data.get('cp', 1000.0), density=hot_data.get('density', 1.0), mu=self.spin_mu_hot.value(), k_cond=self.spin_k_hot.value())
                else:
                    hx.hot_fluid = Fluid(name=hot_data['name'] if hot_data else hot_name, is_coolprop=True, calc_temp_c=T_hot)

                if cold_data and cold_data.get('is_mixture'):
                    cold_mix = get_mixture_fluid_data(self.cold_mixture_data, comp_type=self.cold_mixture_basis, T_c=T_cold, P_pa=101325.0)
                    hx.cold_fluid = Fluid(name="Özel Egzoz Gazı", is_coolprop=False, cp=cold_mix['cp'], density=cold_mix['density'], mu=cold_mix['mu'], k_cond=cold_mix['k_cond'])
                elif cold_data and not cold_data.get('is_coolprop'):
                    hx.cold_fluid = Fluid(name=cold_name, is_coolprop=False, cp=cold_data.get('cp', 1000.0), density=cold_data.get('density', 1.0), mu=self.spin_mu_cold.value(), k_cond=self.spin_k_cold.value())
                else:
                    hx.cold_fluid = Fluid(name=cold_data['name'] if cold_data else cold_name, is_coolprop=True, calc_temp_c=T_cold)

                if geom['D_i'] >= geom['D_o']:
                    QMessageBox.warning(self, "Mantıksal Hata", "Boru dış çapı, iç çapından büyük olmalıdır!")
                    return
                if geom['L'] <= 0 or geom['N_tubes'] < 1:
                    QMessageBox.warning(self, "Mantıksal Hata", "Geometrik uzunluk ve adet sıfırdan büyük olmalıdır!")
                    return
                
                geo_res = hx.calculate_geometric_U(geom, m_hot, m_cold, hot_is_tube)
                self.last_geo_res = geo_res
                hx.U = geo_res['U']
                hx.A = geo_res['A_total']
                geo_warnings = "\n".join(geo_res.get('warnings', []))
                self.lbl_geo_res.setText(
                    f"📐 Geometrik Mod: U={hx.U:.2f} W/m²K, A={hx.A:.2f} m²\n"
                    f"h_i={geo_res['h_i']:.1f}, h_o={geo_res['h_o']:.1f}"
                    + (f"\n{geo_warnings}" if geo_warnings else "")
                )
            except Exception as e:
                self.show_error("Geometrik Hata", f"Geometrik U hesaplanamadı: {str(e)}\nAkışkan özellikleri eksik olabilir.", e)
                return
        else:
            geom = {}
            hx.U = self.spin_U.value()
            hx.A = self.spin_A.value()
            self.last_geo_res = None
            self.lbl_geo_res.setText("")

        sel_method = self.combo_method.currentText()
        is_rating = "Performans" in self.combo_purpose.currentText()
        
        t_out_h = -999.0
        t_out_c = -999.0
        if is_rating:
            t_out_h = to_celsius(self.spin_t_hot_out.value(), self.combo_u_t_hot_out.currentText())
            t_out_c = to_celsius(self.spin_t_cold_out.value(), self.combo_u_t_cold_out.currentText())
            
        try:
            res_custom = hx.solve_ntu(m_hot, m_cold, T_hot, T_cold, source='custom')
            res_custom_lmtd = hx.solve_custom_lmtd(m_hot, m_cold, T_hot, T_cold)
            res_ht = hx.solve_ntu(m_hot, m_cold, T_hot, T_cold, source='ht')
            res_lmtd = hx.solve_lmtd(m_hot, m_cold, T_hot, T_cold, source='ht')
            crosscheck_results = [res_custom, res_custom_lmtd, res_ht, res_lmtd]
            pychemengg_warning = None
            try:
                crosscheck_results.append(hx.solve_pychemengg_ntu(m_hot, m_cold, T_hot, T_cold))
            except ImportError as e:
                pychemengg_warning = str(e)
            except Exception as e:
                pychemengg_warning = f"PyChemEngg doğrulaması çalışmadı: {e}"
        except Exception as e:
            self.show_error("Hesaplama Hatası", str(e), e)
            return
        
        # Seçili olan ana metodu belirle
        res_main = res_custom
        sel_method = self.combo_method.currentText()
        if sel_method == 'Kendi Algoritmamız (LMTD)':
            res_main = res_custom_lmtd
        elif sel_method == 'HT Kütüphanesi (Epsilon-NTU)':
            res_main = res_ht
        elif sel_method == 'HT Kütüphanesi (LMTD)':
            res_main = res_lmtd
            
        self.last_res_main = res_main
        self.last_res_act = None
        self.last_crosscheck_results = crosscheck_results
        self.btn_export_report.show()
        
        t_out_h = to_celsius(self.spin_t_hot_out.value(), self.combo_u_t_hot_out.currentText()) if is_rating else -999.0
        t_out_c = to_celsius(self.spin_t_cold_out.value(), self.combo_u_t_cold_out.currentText()) if is_rating else -999.0
        
        if is_rating and t_out_h > -900.0 and t_out_c > -900.0:
            res_act = hx.calculate_actual_performance(m_hot, m_cold, T_hot, T_cold, t_out_h, t_out_c)
            self.last_res_act = res_act
            
            self.lbl_res_q.setText(f"Gerçekleşen Transfer Edilen Isı (Q_ortalama): {res_act['Q_avg [W]']/1000:.2f} kW")
            self.lbl_res_th.setText(f"Ölçülen Sıcak Çıkış: {t_out_h:.2f} °C  (Tasarım Beklentisi: {res_main['T_hot_out [C]']:.2f} °C)")
            self.lbl_res_tc.setText(f"Ölçülen Soğuk Çıkış: {t_out_c:.2f} °C  (Tasarım Beklentisi: {res_main['T_cold_out [C]']:.2f} °C)")
            self.lbl_res_eff.setText(f"Gerçekleşen Verim (ε): % {res_act['epsilon_actual']*100:.2f}  (Tasarım Verimi: % {res_main.get('epsilon', 0.0)*100:.2f})")
            
            enerji_farki = abs(res_act['Q_hot [W]'] - res_act['Q_cold [W]']) / max(res_act['Q_hot [W]'], 1) * 100
            warnings_text = "\n".join(res_act.get('warnings', []))
            self.lbl_res_act.setText(f"⚠️ Enerji Dengesi Sapması: % {enerji_farki:.2f}\n"
                                     f"Bu sıcaklıklara ulaşmak için Gereken U Katsayısı: {res_act['U_required']:.2f} W/m²K"
                                     + (f"\n{warnings_text}" if warnings_text else ""))
        else:
            self.lbl_res_q.setText(f"Tasarım Isı Yükü (Q): {res_main['Q [W]']/1000:.2f} kW")
            self.lbl_res_th.setText(f"Hesaplanan Sıcak Akışkan Çıkışı: {res_main['T_hot_out [C]']:.2f} °C")
            self.lbl_res_tc.setText(f"Hesaplanan Soğuk Akışkan Çıkışı: {res_main['T_cold_out [C]']:.2f} °C")
            self.lbl_res_eff.setText(f"Sistem Tasarım Verimi (ε): % {res_main.get('epsilon', 0.0)*100:.2f}")
            warnings_text = "\n".join(res_main.get('warnings', []))
            self.lbl_res_act.setText(warnings_text)
        
        # Cross Check
        if pychemengg_warning:
            self.append_log(pychemengg_warning, logging.INFO)
            self.filter_and_display_last_log(pychemengg_warning, logging.INFO)
        self.table_cc.setRowCount(len(crosscheck_results))
        for row, r in enumerate(crosscheck_results):
            q_diff = ""
            if res_main.get('Q [W]', 0) > 0:
                q_diff = f"{abs(r['Q [W]'] - res_main['Q [W]']) / res_main['Q [W]'] * 100:.3f}"
            self.table_cc.setItem(row, 0, QTableWidgetItem(r['Method']))
            self.table_cc.setItem(row, 1, QTableWidgetItem(r['Source']))
            self.table_cc.setItem(row, 2, QTableWidgetItem(r.get('status', 'ok')))
            self.table_cc.setItem(row, 3, QTableWidgetItem(f"{r['Q [W]']/1000:.2f}"))
            self.table_cc.setItem(row, 4, QTableWidgetItem(q_diff))
            self.table_cc.setItem(row, 5, QTableWidgetItem(f"{r['T_hot_out [C]']:.2f}"))
            self.table_cc.setItem(row, 6, QTableWidgetItem(f"{r['T_cold_out [C]']:.2f}"))
            self.table_cc.setItem(row, 7, QTableWidgetItem(" | ".join(r.get('warnings', []))))

        self.last_report_context = {
            "methods": {
                "Hesap amacı": self.combo_purpose.currentText(),
                "Akış tipi": self.combo_flow.currentText(),
                "Akış tipi internal": self.combo_flow.currentText(),
                "Ana çözücü": self.combo_method.currentText(),
                "U modu": self.combo_u_mode.currentText(),
            },
            "inputs": {
                "m_hot_raw": f"{m_hot_raw} {self.combo_u_m_hot.currentText()}",
                "m_cold_raw": f"{m_cold_raw} {self.combo_u_m_cold.currentText()}",
                "m_hot_kg_s": m_hot,
                "m_cold_kg_s": m_cold,
                "T_hot_in_C": T_hot,
                "T_cold_in_C": T_cold,
                "T_hot_out_C": t_out_h if is_rating else None,
                "T_cold_out_C": t_out_c if is_rating else None,
                "U": hx.U,
                "A": hx.A,
            },
            "fluids": {
                "hot": fluid_report_data(self.combo_hot.currentText(), hot_data, hx.hot_fluid),
                "cold": fluid_report_data(self.combo_cold.currentText(), cold_data, hx.cold_fluid),
            },
            "geometry": geom,
            "geo_result": self.last_geo_res,
            "results": {"main": res_main},
            "actual_result": self.last_res_act,
            "crosscheck_results": crosscheck_results,
        }
            
        # Schematic
        hx.plot_schematic(fig=self.figure)
        self.canvas.draw()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = HeatExchangerDesktopApp()
    ex.show()
    sys.exit(app.exec_())

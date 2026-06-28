import json
import logging
import os
import sys

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from config import EXCHANGER_ALLOWED_FLOWS
from engineering_utils import (
    fluid_report_data,
    to_celsius,
    to_kg_s,
)
from exceptions import InvalidGeometryError, InvalidInputError
from fluids_db import get_fluid_data, get_fluid_list_flat, get_mixture_fluid_data, materialize_fluid_data
from heat_exchanger import FinTubeHeatExchanger, Fluid
from logging_config import setup_logging
from reporting import build_calculation_report, build_calculation_report_pdf
from updater import check_for_update, default_download_dir, download_release_asset
from version import APP_NAME, VERSION

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


class CalculationWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str, str, object)

    def __init__(self, snapshot):
        super().__init__()
        self.snapshot = snapshot

    def run(self):
        try:
            self.finished.emit(compute_desktop_calculation(self.snapshot))
        except Exception as exc:
            logger.exception("Desktop background calculation failed.")
            self.failed.emit("Hesaplama Hatası", str(exc), exc)


class UpdateDownloadWorker(QObject):
    finished = pyqtSignal(object)
    failed = pyqtSignal(str, str, object)

    def __init__(self, update_info, target_dir):
        super().__init__()
        self.update_info = update_info
        self.target_dir = target_dir

    def run(self):
        try:
            result = download_release_asset(self.update_info, self.target_dir, app_kind="desktop", timeout=120)
            self.finished.emit(result)
        except Exception as exc:
            logger.exception("Update download failed.")
            self.failed.emit("Güncelleme İndirme Hatası", str(exc), exc)


class UpdateCheckWorker(QObject):
    finished = pyqtSignal(object, bool)

    def __init__(self, show_no_update):
        super().__init__()
        self.show_no_update = show_no_update

    def run(self):
        self.finished.emit(check_for_update(), self.show_no_update)


def create_unit_combo(items):
    c = QComboBox()
    c.addItems(items)
    return c


def create_input_row(spin, combo):
    lay = QHBoxLayout()
    lay.setContentsMargins(0, 0, 0, 0)
    lay.addWidget(spin)
    lay.addWidget(combo)
    lay.setStretch(0, 3)
    lay.setStretch(1, 1)
    w = QWidget()
    w.setLayout(lay)
    return w


def build_fluid_from_selection(selection, fluid_data, mixture_data, mixture_basis, temp_c, mu, k_cond):
    if fluid_data.get("is_iapws"):
        return Fluid(name=fluid_data["name"], is_iapws=True, calc_temp_c=temp_c)
    if fluid_data["is_coolprop"]:
        return Fluid(name=fluid_data["name"], is_coolprop=True, calc_temp_c=temp_c)
    if fluid_data.get("is_mixture"):
        logger.info(
            "Calculating exhaust mixture properties. fluid=%s basis=%s comp=%s", selection, mixture_basis, mixture_data
        )
        mix = get_mixture_fluid_data(mixture_data, comp_type=mixture_basis, T_c=temp_c, P_pa=101325.0)
        fluid = Fluid(
            name="Özel Egzoz Gazı",
            cp=mix["cp"],
            density=mix["density"],
            mu=mix["mu"],
            k_cond=mix["k_cond"],
            is_coolprop=False,
        )
        fluid.property_source = mix.get("property_source")
        return fluid
    return Fluid(
        name=fluid_data["name"],
        cp=fluid_data.get("cp", 1000.0),
        density=fluid_data.get("density", 1.0),
        mu=mu,
        k_cond=k_cond,
        is_coolprop=False,
    )


def compute_desktop_calculation(snapshot):
    logger.info(
        "Calculation requested. hot=%s cold=%s u_mode=%s solver=%s",
        snapshot["hot_selection"],
        snapshot["cold_selection"],
        snapshot["u_mode"],
        snapshot["method"],
    )
    T_hot = to_celsius(snapshot["T_hot_raw"], snapshot["T_hot_unit"])
    T_cold = to_celsius(snapshot["T_cold_raw"], snapshot["T_cold_unit"])
    if T_hot <= T_cold:
        raise InvalidInputError("Sıcak akışkan giriş sıcaklığı soğuk akışkan giriş sıcaklığından büyük olmalıdır.")

    hot_data = materialize_fluid_data(get_fluid_data(snapshot["hot_selection"]), T_hot)
    cold_data = materialize_fluid_data(get_fluid_data(snapshot["cold_selection"]), T_cold)
    hot_fluid = build_fluid_from_selection(
        snapshot["hot_selection"],
        hot_data,
        snapshot["hot_mixture_data"],
        snapshot["hot_mixture_basis"],
        T_hot,
        snapshot["mu_hot"],
        snapshot["k_hot"],
    )
    cold_fluid = build_fluid_from_selection(
        snapshot["cold_selection"],
        cold_data,
        snapshot["cold_mixture_data"],
        snapshot["cold_mixture_basis"],
        T_cold,
        snapshot["mu_cold"],
        snapshot["k_cold"],
    )

    m_hot = to_kg_s(snapshot["m_hot_raw"], snapshot["m_hot_unit"], hot_fluid.density)
    m_cold = to_kg_s(snapshot["m_cold_raw"], snapshot["m_cold_unit"], cold_fluid.density)
    hx = FinTubeHeatExchanger(
        hot_fluid,
        cold_fluid,
        U=1.0,
        A=1.0,
        flow_type=snapshot["flow_type"],
        exchanger_type=snapshot.get("exchanger_type", "finned_tube"),
    )

    geo_res = None
    geom = {}
    if "Geometrik" in snapshot["u_mode"]:
        geom = dict(snapshot["geom"])
        if geom["D_i"] >= geom["D_o"]:
            raise InvalidGeometryError("Boru dış çapı iç çapından büyük olmalıdır.")
        if geom["L"] <= 0 or geom["N_tubes"] < 1:
            raise InvalidGeometryError("Geometrik uzunluk ve adet sıfırdan büyük olmalıdır.")
        geo_res = hx.calculate_geometric_U(geom, m_hot, m_cold, snapshot["hot_is_tube"])
        hx.U = geo_res["U"]
        hx.A = geo_res["A_total"]
    else:
        hx.U = snapshot["U"]
        hx.A = snapshot["A"]

    res_custom = hx.solve_ntu(m_hot, m_cold, T_hot, T_cold, source="custom")
    res_custom_lmtd = hx.solve_custom_lmtd(m_hot, m_cold, T_hot, T_cold)
    res_ht = hx.solve_ntu(m_hot, m_cold, T_hot, T_cold, source="ht")
    res_lmtd = hx.solve_lmtd(m_hot, m_cold, T_hot, T_cold, source="ht")
    crosscheck_results = [res_custom, res_custom_lmtd, res_ht, res_lmtd]

    # Iterative property refinement at midpoint temperatures (2 additional passes)
    for _iter in range(2):
        t_ho = res_custom["T_hot_out [C]"]
        t_co = res_custom["T_cold_out [C]"]
        T_hot_mid = (T_hot + t_ho) / 2.0
        T_cold_mid = (T_cold + t_co) / 2.0
        if abs(T_hot_mid - T_hot) < 1.0 and abs(T_cold_mid - T_cold) < 1.0:
            break

        hot_data = materialize_fluid_data(get_fluid_data(snapshot["hot_selection"]), T_hot_mid)
        cold_data = materialize_fluid_data(get_fluid_data(snapshot["cold_selection"]), T_cold_mid)
        hot_fluid = build_fluid_from_selection(
            snapshot["hot_selection"],
            hot_data,
            snapshot["hot_mixture_data"],
            snapshot["hot_mixture_basis"],
            T_hot_mid,
            snapshot["mu_hot"],
            snapshot["k_hot"],
        )
        cold_fluid = build_fluid_from_selection(
            snapshot["cold_selection"],
            cold_data,
            snapshot["cold_mixture_data"],
            snapshot["cold_mixture_basis"],
            T_cold_mid,
            snapshot["mu_cold"],
            snapshot["k_cold"],
        )
        m_hot = to_kg_s(snapshot["m_hot_raw"], snapshot["m_hot_unit"], hot_fluid.density)
        m_cold = to_kg_s(snapshot["m_cold_raw"], snapshot["m_cold_unit"], cold_fluid.density)
        hx = FinTubeHeatExchanger(
            hot_fluid,
            cold_fluid,
            U=1.0,
            A=1.0,
            flow_type=snapshot["flow_type"],
            exchanger_type=snapshot.get("exchanger_type", "finned_tube"),
        )
        if geo_res is not None:
            geo_res = hx.calculate_geometric_U(geom, m_hot, m_cold, snapshot["hot_is_tube"])
            hx.U = geo_res["U"]
            hx.A = geo_res["A_total"]
        else:
            hx.U = snapshot["U"]
            hx.A = snapshot["A"]
        res_custom = hx.solve_ntu(m_hot, m_cold, T_hot, T_cold, source="custom")
        res_custom_lmtd = hx.solve_custom_lmtd(m_hot, m_cold, T_hot, T_cold)
        res_ht = hx.solve_ntu(m_hot, m_cold, T_hot, T_cold, source="ht")
        res_lmtd = hx.solve_lmtd(m_hot, m_cold, T_hot, T_cold, source="ht")
        crosscheck_results = [res_custom, res_custom_lmtd, res_ht, res_lmtd]
        logger.debug("Midpoint iteration %d: Tho=%.1f Tco=%.1f", _iter + 1, t_ho, t_co)
    # End of iterative property refinement

    pychemengg_warning = None
    try:
        crosscheck_results.append(hx.solve_pychemengg_ntu(m_hot, m_cold, T_hot, T_cold))
    except ImportError as exc:
        pychemengg_warning = str(exc)
    except Exception as exc:
        pychemengg_warning = f"PyChemEngg doğrulaması çalışmadı: {exc}"

    method = snapshot["method"]
    res_main = res_custom
    if method == "Kendi Algoritmamız (LMTD)":
        res_main = res_custom_lmtd
    elif method == "HT Kütüphanesi (Epsilon-NTU)":
        res_main = res_ht
    elif method == "HT Kütüphanesi (LMTD)":
        res_main = res_lmtd

    is_rating = "Performans" in snapshot["purpose"]
    t_out_h = to_celsius(snapshot["T_hot_out_raw"], snapshot["T_hot_out_unit"]) if is_rating else -999.0
    t_out_c = to_celsius(snapshot["T_cold_out_raw"], snapshot["T_cold_out_unit"]) if is_rating else -999.0
    res_act = None
    if is_rating and t_out_h > -900.0 and t_out_c > -900.0:
        res_act = hx.calculate_actual_performance(m_hot, m_cold, T_hot, T_cold, t_out_h, t_out_c)

    report_context = {
        "methods": {
            "Hesap amacı": snapshot["purpose"],
            "Akış tipi": snapshot["flow_label"],
            "Akış tipi internal": snapshot["flow_type"],
            "Ana çözücü": method,
            "U modu": snapshot["u_mode"],
        },
        "inputs": {
            "m_hot_raw": f"{snapshot['m_hot_raw']} {snapshot['m_hot_unit']}",
            "m_cold_raw": f"{snapshot['m_cold_raw']} {snapshot['m_cold_unit']}",
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
            "hot": fluid_report_data(snapshot["hot_selection"], hot_data, hx.hot_fluid),
            "cold": fluid_report_data(snapshot["cold_selection"], cold_data, hx.cold_fluid),
        },
        "geometry": geom,
        "geo_result": geo_res,
        "results": {"main": res_main},
        "actual_result": res_act,
        "crosscheck_results": crosscheck_results,
    }
    return {
        "hx": hx,
        "geo_res": geo_res,
        "res_main": res_main,
        "res_act": res_act,
        "crosscheck_results": crosscheck_results,
        "pychemengg_warning": pychemengg_warning,
        "report_context": report_context,
        "is_rating": is_rating,
        "t_out_h": t_out_h,
        "t_out_c": t_out_c,
    }


class CompositionDialog(QDialog):
    def __init__(self, parent=None, current_comp=None, current_basis="mole"):
        super().__init__(parent)
        self.setWindowTitle("Egzoz Gazı Kompozisyonu Düzenleyici")
        self.resize(500, 400)

        self.layout = QVBoxLayout(self)

        # Presets
        preset_layout = QHBoxLayout()
        btn_ng = QPushButton("Doğal Gaz (Tipik)")
        btn_ng.clicked.connect(
            lambda: self.load_preset({"Nitrogen": 75.0, "Oxygen": 13.0, "Water": 8.0, "CarbonDioxide": 4.0})
        )
        btn_coal = QPushButton("Kömür (Ağır)")
        btn_coal.clicked.connect(
            lambda: self.load_preset(
                {"Nitrogen": 72.0, "Oxygen": 6.0, "Water": 6.0, "CarbonDioxide": 15.0, "SulfurDioxide": 1.0}
            )
        )
        btn_bio = QPushButton("Biyogaz")
        btn_bio.clicked.connect(
            lambda: self.load_preset({"Nitrogen": 65.0, "Oxygen": 5.0, "Water": 15.0, "CarbonDioxide": 15.0})
        )

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
        self.table.setHorizontalHeaderLabels(["Gaz Bileşeni", "Oran (%)"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.layout.addWidget(self.table)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("+ Satır Ekle")
        btn_add.clicked.connect(self.add_row)
        btn_rem = QPushButton("- Seçili Satırı Sil")
        btn_rem.clicked.connect(self.remove_row)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_rem)
        self.layout.addLayout(btn_layout)

        save_btn = QPushButton("Kaydet ve Çık")
        save_btn.setStyleSheet("background-color: #27ae60; color: white; font-weight: bold; padding: 8px;")
        save_btn.clicked.connect(self.accept)
        self.layout.addWidget(save_btn)

        self.gases = [
            "Nitrogen",
            "Oxygen",
            "CarbonDioxide",
            "Water",
            "Argon",
            "CarbonMonoxide",
            "Methane",
            "Hydrogen",
            "SulfurDioxide",
        ]

        if current_comp:
            self.load_preset(current_comp)
        else:
            self.load_preset({"Nitrogen": 76.0, "Oxygen": 11.0, "Water": 6.0, "CarbonDioxide": 7.0})

    def load_preset(self, comp_dict):
        self.table.setRowCount(0)
        for gas, val in comp_dict.items():
            self.add_row(gas, val)

    def add_row(self, gas_name="Nitrogen", val=0.0):
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
                except Exception:
                    pass
        return comp

    def get_basis(self):
        return "mass" if "Kütlesel" in self.combo_basis.currentText() else "mole"


FLOW_LABEL_TO_INTERNAL = {
    "Çapraz Akış (Cross Flow Unmixed)": "cross_unmixed",
    "Ters Akış (Counter Flow)": "counter",
    "Paralel Akış (Parallel Flow)": "parallel",
}
FLOW_LABEL_TO_INTERNAL["Çapraz Akış (Mixed/Unmixed)"] = "cross_mixed_unmixed"
FLOW_INTERNAL_TO_LABEL = {value: key for key, value in FLOW_LABEL_TO_INTERNAL.items()}

EXCHANGER_LABEL_TO_INTERNAL = {
    "Kanatçıklı Boru (Finned Tube)": "finned_tube",
    "Gövde-Boru (Shell & Tube)": "shell_and_tube",
    "Çift Borulu (Double Pipe)": "double_pipe",
}
EXCHANGER_INTERNAL_TO_LABEL = {value: key for key, value in EXCHANGER_LABEL_TO_INTERNAL.items()}

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
    exch_value = normalized.get("exchanger_type")
    if exch_value in EXCHANGER_LABEL_TO_INTERNAL:
        normalized["exchanger_type"] = EXCHANGER_LABEL_TO_INTERNAL[exch_value]
    # Akış tipini eşanjör tipine göre doğrula
    exch_internal = normalized.get("exchanger_type", "finned_tube")
    allowed = EXCHANGER_ALLOWED_FLOWS.get(exch_internal, set())
    flow = normalized.get("flow_type")
    if flow and flow not in allowed and allowed:
        logger.warning(
            "Yüklenen akış tipi '%s', eşanjör tipi '%s' için geçersiz; '%s' kullanılacak.",
            flow,
            exch_internal,
            next(iter(allowed)),
        )
        normalized["flow_type"] = next(iter(allowed))
    return normalized


class HeatExchangerDesktopApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} Desktop v{VERSION}")
        self.resize(1100, 800)
        self.all_logs = []
        self.latest_update_info = None
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
        fileMenu = menubar.addMenu("&Dosya")

        saveAct = QAction("💾 Kaydet", self)
        saveAct.setShortcut("Ctrl+S")
        saveAct.triggered.connect(self.save_data)
        fileMenu.addAction(saveAct)

        loadAct = QAction("📂 Yükle", self)
        loadAct.setShortcut("Ctrl+O")
        loadAct.triggered.connect(self.load_data)
        fileMenu.addAction(loadAct)

        helpMenu = menubar.addMenu("&Yardım")
        updateAct = QAction("Güncellemeyi Kontrol Et", self)
        updateAct.triggered.connect(lambda: self.check_for_updates(show_no_update=True))
        helpMenu.addAction(updateAct)

        logAct = QAction("Log Klasörünü Aç", self)
        logAct.triggered.connect(self.open_log_folder)
        helpMenu.addAction(logAct)

        aboutAct = QAction("Hakkında", self)
        aboutAct.triggered.connect(
            lambda: QMessageBox.information(
                self, "Hakkında", f"{APP_NAME} v{VERSION}\nFin-tube heat exchanger calculation and reporting tool."
            )
        )
        helpMenu.addAction(aboutAct)

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
        self.combo_flow.addItems(list(FLOW_LABEL_TO_INTERNAL.keys()))

        self.combo_method = QComboBox()
        self.combo_method.addItems(
            [
                "Kendi Algoritmamız (Epsilon-NTU)",
                "Kendi Algoritmamız (LMTD)",
                "HT Kütüphanesi (Epsilon-NTU)",
                "HT Kütüphanesi (LMTD)",
            ]
        )

        self.combo_purpose = QComboBox()
        self.combo_purpose.addItems(
            ["Sistem Tasarımı (Çıkış Sıcaklıklarını Bul)", "Performans Değerlendirmesi (Verim Bul)"]
        )
        self.combo_purpose.currentTextChanged.connect(self.toggle_purpose)

        self.combo_u_mode = QComboBox()
        self.combo_u_mode.addItems(["Basit Mod (Manuel U Değeri)", "Geometrik Mod (Malzeme ile Hesapla)"])
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
        self.hot_mixture_data = {"Nitrogen": 76.0, "Oxygen": 11.0, "Water": 6.0, "CarbonDioxide": 7.0}
        self.hot_mixture_basis = "mole"

        self.spin_m_hot = QDoubleSpinBox()
        self.spin_m_hot.setRange(0.001, 100000)
        self.spin_m_hot.setValue(15.0)
        self.combo_u_m_hot = create_unit_combo(["kg/s", "kg/h", "lb/s", "m³/s", "m³/h", "CFM"])
        self.spin_t_hot = QDoubleSpinBox()
        self.spin_t_hot.setRange(-9999.0, 9999.0)
        self.spin_t_hot.setValue(450.0)
        self.combo_u_t_hot = create_unit_combo(["°C", "°F", "K"])
        self.spin_t_hot_out = QDoubleSpinBox()
        self.spin_t_hot_out.setRange(-9999.0, 9999.0)
        self.spin_t_hot_out.setValue(-999.0)
        self.combo_u_t_hot_out = create_unit_combo(["°C", "°F", "K"])

        # Manuel Özellikler
        self.spin_mu_hot = QDoubleSpinBox()
        self.spin_mu_hot.setRange(0.000001, 1000)
        self.spin_mu_hot.setDecimals(6)
        self.spin_mu_hot.setValue(0.00002)
        self.spin_mu_hot.setSuffix(" Pa.s")
        self.spin_k_hot = QDoubleSpinBox()
        self.spin_k_hot.setRange(0.001, 1000)
        self.spin_k_hot.setDecimals(4)
        self.spin_k_hot.setValue(0.03)
        self.spin_k_hot.setSuffix(" W/mK")

        form_hot.addRow("Akışkan:", self.combo_hot)
        form_hot.addRow("", self.btn_edit_comp)
        form_hot.addRow("Debi:", create_input_row(self.spin_m_hot, self.combo_u_m_hot))
        form_hot.addRow("Giriş Sıc.:", create_input_row(self.spin_t_hot, self.combo_u_t_hot))
        self.lbl_t_hot_out = QLabel("Çıkış Sıc.:")

        lay_hout = QHBoxLayout()
        lay_hout.setContentsMargins(0, 0, 0, 0)
        lay_hout.addWidget(self.spin_t_hot_out)
        lay_hout.addWidget(self.combo_u_t_hot_out)
        lay_hout.setStretch(0, 3)
        lay_hout.setStretch(1, 1)
        self.w_t_hot_out = QWidget()
        self.w_t_hot_out.setLayout(lay_hout)

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
        self.cold_mixture_data = {"Nitrogen": 76.0, "Oxygen": 11.0, "Water": 6.0, "CarbonDioxide": 7.0}
        self.cold_mixture_basis = "mole"

        self.spin_m_cold = QDoubleSpinBox()
        self.spin_m_cold.setRange(0.001, 100000)
        self.spin_m_cold.setValue(5.0)
        self.combo_u_m_cold = create_unit_combo(["kg/s", "kg/h", "lb/s", "m³/s", "m³/h", "CFM"])
        self.spin_t_cold = QDoubleSpinBox()
        self.spin_t_cold.setRange(-9999.0, 9999.0)
        self.spin_t_cold.setValue(120.0)
        self.combo_u_t_cold = create_unit_combo(["°C", "°F", "K"])
        self.spin_t_cold_out = QDoubleSpinBox()
        self.spin_t_cold_out.setRange(-9999.0, 9999.0)
        self.spin_t_cold_out.setValue(-999.0)
        self.combo_u_t_cold_out = create_unit_combo(["°C", "°F", "K"])

        self.spin_mu_cold = QDoubleSpinBox()
        self.spin_mu_cold.setRange(0.000001, 1000)
        self.spin_mu_cold.setDecimals(6)
        self.spin_mu_cold.setValue(0.001)
        self.spin_mu_cold.setSuffix(" Pa.s")
        self.spin_k_cold = QDoubleSpinBox()
        self.spin_k_cold.setRange(0.001, 1000)
        self.spin_k_cold.setDecimals(4)
        self.spin_k_cold.setValue(0.15)
        self.spin_k_cold.setSuffix(" W/mK")

        form_cold.addRow("Akışkan:", self.combo_cold)
        form_cold.addRow("", self.btn_edit_comp_cold)
        form_cold.addRow("Debi:", create_input_row(self.spin_m_cold, self.combo_u_m_cold))
        form_cold.addRow("Giriş Sıc.:", create_input_row(self.spin_t_cold, self.combo_u_t_cold))
        self.lbl_t_cold_out = QLabel("Çıkış Sıc.:")

        lay_cout = QHBoxLayout()
        lay_cout.setContentsMargins(0, 0, 0, 0)
        lay_cout.addWidget(self.spin_t_cold_out)
        lay_cout.addWidget(self.combo_u_t_cold_out)
        lay_cout.setStretch(0, 3)
        lay_cout.setStretch(1, 1)
        self.w_t_cold_out = QWidget()
        self.w_t_cold_out.setLayout(lay_cout)

        form_cold.addRow(self.lbl_t_cold_out, self.w_t_cold_out)
        form_cold.addRow("Manuel Viskozite:", self.spin_mu_cold)
        form_cold.addRow("Manuel İletkenlik:", self.spin_k_cold)
        left_layout.addWidget(group_cold)

        # 4. U Modu Stack
        self.stack_geom = QStackedWidget()

        # 4.a Basit Mod
        page_simple = QWidget()
        form_simple = QFormLayout(page_simple)
        self.spin_U = QDoubleSpinBox()
        self.spin_U.setRange(0.1, 10000)
        self.spin_U.setValue(50.0)
        self.spin_U.setSuffix(" W/m²K")
        self.spin_A = QDoubleSpinBox()
        self.spin_A.setRange(0.1, 100000)
        self.spin_A.setValue(200.0)
        self.spin_A.setSuffix(" m²")
        form_simple.addRow("U Katsayısı:", self.spin_U)
        form_simple.addRow("Toplam Alan:", self.spin_A)
        self.stack_geom.addWidget(page_simple)

        # 4.b Geometrik Mod
        page_geo = QWidget()
        form_geo = QFormLayout(page_geo)

        self.spin_do = QDoubleSpinBox()
        self.spin_do.setRange(1, 1000)
        self.spin_do.setValue(25.4)
        self.spin_do.setSuffix(" mm")
        self.spin_di = QDoubleSpinBox()
        self.spin_di.setRange(1, 1000)
        self.spin_di.setValue(21.1)
        self.spin_di.setSuffix(" mm")
        self.spin_l = QDoubleSpinBox()
        self.spin_l.setRange(0.1, 100)
        self.spin_l.setValue(3.0)
        self.spin_l.setSuffix(" m")
        self.spin_nt = QDoubleSpinBox()
        self.spin_nt.setRange(1, 10000)
        self.spin_nt.setValue(100)
        self.spin_nt.setDecimals(0)
        self.spin_d_shell = QDoubleSpinBox()
        self.spin_d_shell.setRange(1, 5000)
        self.spin_d_shell.setValue(50.0)
        self.spin_d_shell.setSuffix(" mm")
        self.spin_rf_i = QDoubleSpinBox()
        self.spin_rf_i.setRange(0, 1)
        self.spin_rf_i.setDecimals(6)
        self.spin_rf_i.setValue(0.0)
        self.spin_rf_i.setSuffix(" m2K/W")
        self.spin_rf_o = QDoubleSpinBox()
        self.spin_rf_o.setRange(0, 1)
        self.spin_rf_o.setDecimals(6)
        self.spin_rf_o.setValue(0.0)
        self.spin_rf_o.setSuffix(" m2K/W")

        self.combo_tube_mat = QComboBox()
        self.tube_mats = {"Karbon Çelik": 45.0, "Paslanmaz Çelik 316": 16.0, "Bakır": 400.0, "Alüminyum": 237.0}
        self.combo_tube_mat.addItems(list(self.tube_mats.keys()))

        self.combo_hot_tube = QComboBox()
        self.combo_hot_tube.addItems(["Soğuk Akışkan", "Sıcak Akışkan"])

        self.chk_finned = QCheckBox("Kanatçıklı (Finned)")
        self.chk_finned.setChecked(True)
        self.spin_fin_h = QDoubleSpinBox()
        self.spin_fin_h.setRange(1, 100)
        self.spin_fin_h.setValue(15.9)
        self.spin_fin_h.setSuffix(" mm")
        self.spin_fin_t = QDoubleSpinBox()
        self.spin_fin_t.setRange(0.1, 10)
        self.spin_fin_t.setValue(0.4)
        self.spin_fin_t.setSuffix(" mm")
        self.spin_fin_dens = QDoubleSpinBox()
        self.spin_fin_dens.setRange(1, 10000)
        self.spin_fin_dens.setValue(400)
        self.spin_fin_dens.setSuffix(" (1/m)")
        self.spin_fin_dens.setDecimals(0)
        self.combo_fin_mat = QComboBox()
        self.combo_fin_mat.addItems(["Alüminyum (k=237)", "Karbon Çelik (k=45)"])
        self.combo_fin_type = QComboBox()
        self.combo_fin_type.addItems(["Dairesel (Annular)", "Düz (Rectangular)"])
        self.chk_finned.toggled.connect(self.toggle_finned)

        self.combo_exchanger = QComboBox()
        self.combo_exchanger.addItems(list(EXCHANGER_LABEL_TO_INTERNAL.keys()))
        self.combo_exchanger.currentIndexChanged.connect(self.on_exchanger_changed)

        form_geo.addRow("Eşanjör Tipi:", self.combo_exchanger)
        form_geo.addRow("Dış Çap (Do):", self.spin_do)
        form_geo.addRow("İç Çap (Di):", self.spin_di)
        form_geo.addRow("Boru Uzunluğu:", self.spin_l)
        form_geo.addRow("Boru Sayısı:", self.spin_nt)
        form_geo.addRow("Gövde İç Çapı:", self.spin_d_shell)
        form_geo.addRow("Fouling İç:", self.spin_rf_i)
        form_geo.addRow("Fouling Dış:", self.spin_rf_o)
        form_geo.addRow("Boru Malzemesi:", self.combo_tube_mat)
        form_geo.addRow("İç Boruda:", self.combo_hot_tube)
        form_geo.addRow("Kanatçık?:", self.chk_finned)
        form_geo.addRow(" Fin Yüksekliği:", self.spin_fin_h)
        form_geo.addRow(" Fin Kalınlığı:", self.spin_fin_t)
        form_geo.addRow(" Fin Yoğunluğu:", self.spin_fin_dens)
        form_geo.addRow(" Fin Malzemesi:", self.combo_fin_mat)
        form_geo.addRow(" Fin Tipi:", self.combo_fin_type)

        self.stack_geom.addWidget(page_geo)

        left_layout.addWidget(QLabel("🔲 Isı Değiştirici Özellikleri"))
        left_layout.addWidget(self.stack_geom)

        # Buton
        self.btn_calc = QPushButton("🚀 HESAPLA VE DOĞRULA")
        self.btn_calc.setMinimumHeight(50)
        self.btn_calc.setStyleSheet("background-color: #2e86c1; color: white; font-weight: bold; font-size: 14px;")
        self.btn_calc.clicked.connect(self.calculate)
        left_layout.addWidget(self.btn_calc)
        self.progress_calc = QProgressBar()
        self.progress_calc.setRange(0, 0)
        self.progress_calc.hide()
        left_layout.addWidget(self.progress_calc)
        self.toggle_finned(self.chk_finned.isChecked())
        self.on_exchanger_changed()

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
        self.lbl_res_act = QLabel("")  # Gerçekleşen performans için

        for lbl in [self.lbl_res_q, self.lbl_res_th, self.lbl_res_tc, self.lbl_res_eff, self.lbl_res_act]:
            lbl.setFont(QFont("Arial", 12, QFont.Bold))
            lbl.setStyleSheet("color: #2c3e50; padding: 5px;")
            res_layout.addWidget(lbl)

        self.btn_export_report = QPushButton("📄 Sonuç Raporunu Dışa Aktar")
        self.btn_export_report.setStyleSheet(
            "background-color: #e67e22; color: white; padding: 10px; font-weight: bold;"
        )
        self.btn_export_report.clicked.connect(self.export_report)
        res_layout.addWidget(self.btn_export_report)
        self.btn_export_report.hide()  # Hesaplama yapılana kadar gizli

        # Grafik için Figure ve Canvas (Sonuçlar sekmesinin en altına)
        self.figure = plt.figure(figsize=(6, 4))
        self.canvas = FigureCanvas(self.figure)
        res_layout.addWidget(self.canvas)
        self.figure_profile = plt.figure(figsize=(6, 3))
        self.canvas_profile = FigureCanvas(self.figure_profile)
        res_layout.addWidget(self.canvas_profile)

        # Sekme 2: Doğrulama
        self.tab_cc = QWidget()
        cc_layout = QVBoxLayout(self.tab_cc)
        self.table_cc = QTableWidget(4, 8)
        self.table_cc.setHorizontalHeaderLabels(
            ["Metot", "Kaynak", "Durum", "Q (kW)", "Q Sapma (%)", "Sıcak Çıkış (°C)", "Soğuk Çıkış (°C)", "Uyarılar"]
        )
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

    def open_log_folder(self):
        import subprocess
        import sys

        log_dir = os.path.dirname(LOG_FILE)
        if sys.platform == "darwin":
            subprocess.run(["open", log_dir])
        elif sys.platform == "win32":
            os.startfile(log_dir)
        else:
            subprocess.run(["xdg-open", log_dir])

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

    def export_report(self):
        if not hasattr(self, "last_res_main"):
            QMessageBox.warning(self, "Hata", "Önce hesaplama yapmalısınız!")
            return

        options = QFileDialog.Options()
        fileName, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Raporu Kaydet",
            "isi_degistirici_raporu.pdf",
            "PDF Files (*.pdf);;Text Files (*.txt);;All Files (*)",
            options=options,
        )
        if fileName:
            try:
                if selected_filter.startswith("PDF") or fileName.lower().endswith(".pdf"):
                    if not fileName.lower().endswith(".pdf"):
                        fileName += ".pdf"
                    with open(fileName, "wb") as f:
                        f.write(build_calculation_report_pdf(self.last_report_context))
                else:
                    if not fileName.lower().endswith(".txt"):
                        fileName += ".txt"
                    with open(fileName, "w", encoding="utf-8") as f:
                        f.write(build_calculation_report(self.last_report_context))

                QMessageBox.information(self, "Başarılı", "Rapor başarıyla kaydedildi!")
            except Exception as e:
                self.show_error("Hata", f"Kaydetme hatası: {str(e)}", e)

    def append_log(self, msg, levelno):
        if len(self.all_logs) > 5000:
            self.all_logs.pop(0)  # Keep max 5000 lines
        self.all_logs.append((msg, levelno))

    def filter_and_display_last_log(self, msg, levelno):
        level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}
        if levelno >= level_map.get(self.combo_log_level.currentText(), logging.INFO):
            self.text_log.appendPlainText(msg)

    def refresh_logs(self):
        level_map = {"DEBUG": logging.DEBUG, "INFO": logging.INFO, "WARNING": logging.WARNING, "ERROR": logging.ERROR}
        selected_level = level_map.get(self.combo_log_level.currentText(), logging.INFO)

        filtered_msgs = [msg for msg, levelno in self.all_logs if levelno >= selected_level]
        self.text_log.setPlainText("\n".join(filtered_msgs))

        # Sona kaydır
        scrollbar = self.text_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def check_updates_on_startup(self):
        self.check_for_updates(show_no_update=False)

    def check_for_updates(self, show_no_update=False):
        if getattr(self, "update_check_thread", None) is not None:
            return
        self.append_log("G?ncelleme kontrol? ba?lat?ld?...", logging.INFO)
        self.update_check_thread = QThread(self)
        self.update_check_worker = UpdateCheckWorker(show_no_update)
        self.update_check_worker.moveToThread(self.update_check_thread)
        self.update_check_thread.started.connect(self.update_check_worker.run)
        self.update_check_worker.finished.connect(self.on_update_check_finished)
        self.update_check_worker.finished.connect(self.update_check_thread.quit)
        self.update_check_worker.finished.connect(self.update_check_worker.deleteLater)
        self.update_check_thread.finished.connect(self.update_check_thread.deleteLater)
        self.update_check_thread.finished.connect(self.on_update_check_thread_done)
        self.update_check_thread.start()

    def on_update_check_thread_done(self):
        self.update_check_thread = None
        self.update_check_worker = None

    def on_update_check_finished(self, result, show_no_update):
        self.latest_update_info = result
        self.append_log(result.get("message", ""), logging.INFO if result.get("ok") else logging.WARNING)
        if result.get("update_available"):
            reply = QMessageBox.information(
                self,
                "G?ncelleme Bulundu",
                f"{result['message']}\nMevcut s?r?m: v{VERSION}\nG?ncelleme paketi indirilsin mi?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply == QMessageBox.Yes:
                self.download_update(result)
        elif show_no_update:
            QMessageBox.information(self, "G?ncelleme Kontrol?", result.get("message", "G?ncelleme bulunamad?."))

    def download_update(self, update_info=None):
        update_info = update_info or self.latest_update_info
        if getattr(self, "update_thread", None) is not None:
            QMessageBox.information(self, "Güncelleme", "Bir güncelleme indirme işlemi zaten devam ediyor.")
            return
        if not update_info or not update_info.get("update_available"):
            QMessageBox.information(self, "Güncelleme", "İndirilecek yeni sürüm bulunamadı.")
            return
        target_dir = QFileDialog.getExistingDirectory(
            self,
            "Güncelleme Paketinin İndirileceği Klasörü Seç",
            default_download_dir(),
        )
        if not target_dir:
            logger.info("Update download cancelled by user.")
            return

        logger.info("Starting update download to %s", target_dir)
        self.append_log(f"Güncelleme indiriliyor: {target_dir}", logging.INFO)
        self.progress_calc.show()
        self.update_thread = QThread(self)
        self.update_worker = UpdateDownloadWorker(update_info, target_dir)
        self.update_worker.moveToThread(self.update_thread)
        self.update_thread.started.connect(self.update_worker.run)
        self.update_worker.finished.connect(self.on_update_download_finished)
        self.update_worker.failed.connect(self.on_update_download_failed)
        self.update_worker.finished.connect(self.update_thread.quit)
        self.update_worker.failed.connect(self.update_thread.quit)
        self.update_worker.finished.connect(self.update_worker.deleteLater)
        self.update_worker.failed.connect(self.update_worker.deleteLater)
        self.update_thread.finished.connect(self.update_thread.deleteLater)
        self.update_thread.finished.connect(self.on_update_download_thread_done)
        self.update_thread.start()

    def on_update_download_thread_done(self):
        self.progress_calc.hide()
        self.update_thread = None
        self.update_worker = None

    def on_update_download_failed(self, title, message, exc):
        self.show_error(title, message, exc)

    def on_update_download_finished(self, result):
        logger.info("Update downloaded: %s (%s bytes)", result["path"], result["size"])
        QMessageBox.information(
            self,
            "Güncelleme İndirildi",
            f"Güncelleme paketi indirildi:\n{result['path']}\n\nProgramı kapatıp zip içindeki yeni sürümü kullanabilirsiniz.",
        )

    def toggle_hot_fluid(self, text):
        is_mixture = self.is_exhaust_mixture(text)
        self.btn_edit_comp.setVisible(is_mixture)
        self.set_manual_property_controls("hot", self.is_custom_manual(text))

    def toggle_cold_fluid(self, text):
        is_mixture = self.is_exhaust_mixture(text)
        self.btn_edit_comp_cold.setVisible(is_mixture)
        self.set_manual_property_controls("cold", self.is_custom_manual(text))

    def toggle_finned(self, checked):
        for widget in (self.spin_fin_h, self.spin_fin_t, self.spin_fin_dens, self.combo_fin_mat, self.combo_fin_type):
            widget.setVisible(checked)

    def is_exhaust_mixture(self, text):
        data = get_fluid_data(text) or {}
        return bool(data.get("is_mixture")) or "Egzoz" in text or "Kompozisyon" in text

    def is_custom_manual(self, text):
        return "Manuel Giriş" in text

    def set_manual_property_controls(self, side, enabled):
        widgets = (self.spin_mu_hot, self.spin_k_hot) if side == "hot" else (self.spin_mu_cold, self.spin_k_cold)
        for widget in widgets:
            widget.setEnabled(enabled)

    def open_composition_editor(self):
        dialog = CompositionDialog(self, self.hot_mixture_data, self.hot_mixture_basis)
        if dialog.exec_():
            self.hot_mixture_data = dialog.get_composition()
            self.hot_mixture_basis = dialog.get_basis()
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.information(self, "Bilgi", "Kompozisyon kaydedildi.")

    def open_cold_composition_editor(self):
        dialog = CompositionDialog(self, self.cold_mixture_data, self.cold_mixture_basis)
        if dialog.exec_():
            self.cold_mixture_data = dialog.get_composition()
            self.cold_mixture_basis = dialog.get_basis()
            from PyQt5.QtWidgets import QMessageBox

            QMessageBox.information(self, "Bilgi", "Kompozisyon kaydedildi.")

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

    def on_exchanger_changed(self):
        exch_internal = EXCHANGER_LABEL_TO_INTERNAL.get(self.combo_exchanger.currentText(), "finned_tube")
        allowed = EXCHANGER_ALLOWED_FLOWS.get(exch_internal, {"cross_unmixed"})
        # Refill combo_flow with only allowed types
        current = self.combo_flow.currentText()
        self.combo_flow.blockSignals(True)
        self.combo_flow.clear()
        for label, internal in FLOW_LABEL_TO_INTERNAL.items():
            if internal in allowed:
                self.combo_flow.addItem(label)
        idx = self.combo_flow.findText(current)
        if idx >= 0:
            self.combo_flow.setCurrentIndex(idx)
        elif self.combo_flow.count() > 0:
            self.combo_flow.setCurrentIndex(0)
        self.combo_flow.blockSignals(False)
        # Show/hide fin-related fields based on exchanger type
        is_finned = exch_internal == "finned_tube"
        self.chk_finned.setVisible(is_finned)
        self.toggle_finned(is_finned and self.chk_finned.isChecked())

    def save_data(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Verileri Kaydet", "heat_exchanger_save.json", "JSON Files (*.json);;All Files (*)", options=options
        )
        if fileName:
            data = {
                "calc_purpose": self.combo_purpose.currentText(),
                "purpose": self.combo_purpose.currentText(),
                "flow_type": FLOW_LABEL_TO_INTERNAL.get(self.combo_flow.currentText(), self.combo_flow.currentText()),
                "flow_label": self.combo_flow.currentText(),
                "exchanger_type": EXCHANGER_LABEL_TO_INTERNAL.get(self.combo_exchanger.currentText(), "finned_tube"),
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
                "D_shell_mm": self.spin_d_shell.value(),
                "R_f_i": self.spin_rf_i.value(),
                "R_f_o": self.spin_rf_o.value(),
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
                "fin_mat": self.combo_fin_mat.currentText(),
                "fin_type": self.combo_fin_type.currentText(),
            }
            with open(fileName, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            QMessageBox.information(self, "Başarılı", "Veriler başarıyla kaydedildi.")
            logger.info("Input data saved: %s", fileName)

    def load_data(self):
        options = QFileDialog.Options()
        fileName, _ = QFileDialog.getOpenFileName(
            self, "Verileri Yükle", "", "JSON Files (*.json);;All Files (*)", options=options
        )
        if fileName:
            try:
                with open(fileName, encoding="utf-8") as f:
                    data = normalize_loaded_data(json.load(f))
                self.combo_purpose.setCurrentText(data.get("purpose", "Sistem Tasarımı (Çıkış Sıcaklıklarını Bul)"))
                flow_value = data.get("flow_type", "cross_unmixed")
                self.combo_flow.setCurrentText(FLOW_INTERNAL_TO_LABEL.get(flow_value, flow_value))
                exch_value = data.get("exchanger_type", "finned_tube")
                self.combo_exchanger.setCurrentText(
                    EXCHANGER_INTERNAL_TO_LABEL.get(exch_value, "Kanatçıklı Boru (Finned Tube)")
                )
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
                self.spin_d_shell.setValue(data.get("D_shell_mm", 50.0))
                self.spin_rf_i.setValue(data.get("R_f_i", 0.0))
                self.spin_rf_o.setValue(data.get("R_f_o", 0.0))
                self.combo_tube_mat.setCurrentText(data.get("tube_mat", "Karbon Çelik"))
                self.combo_hot_tube.setCurrentText(data.get("hot_tube", "Soğuk Akışkan"))

                self.chk_finned.setChecked(data.get("is_finned", True))
                self.spin_fin_h.setValue(data.get("fin_h", 15.9))
                self.spin_fin_t.setValue(data.get("fin_t", 0.4))
                self.spin_fin_dens.setValue(data.get("fin_dens", 400.0))
                self.combo_fin_mat.setCurrentText(data.get("fin_mat", "Alüminyum (k=237)"))
                self.combo_fin_type.setCurrentText(data.get("fin_type", "Dairesel (Annular)"))
                self.toggle_finned(self.chk_finned.isChecked())
                self.toggle_hot_fluid(self.combo_hot.currentText())
                self.toggle_cold_fluid(self.combo_cold.currentText())

                QMessageBox.information(self, "Başarılı", "Veriler başarıyla yüklendi.")
            except Exception as e:
                self.show_error("Hata", f"Dosya yüklenirken hata oluştu: {str(e)}", e)

    def calculate(self):
        if not self.btn_calc.isEnabled():
            return
        try:
            snapshot = self.create_calculation_snapshot()
        except Exception as exc:
            self.show_error("Girdi Hatası", str(exc), exc)
            return
        self.btn_calc.setEnabled(False)
        self.progress_calc.show()
        self.calc_thread = QThread(self)
        self.calc_worker = CalculationWorker(snapshot)
        self.calc_worker.moveToThread(self.calc_thread)
        self.calc_thread.started.connect(self.calc_worker.run)
        self.calc_worker.finished.connect(self.on_calculation_finished)
        self.calc_worker.failed.connect(self.on_calculation_failed)
        self.calc_worker.finished.connect(self.calc_thread.quit)
        self.calc_worker.failed.connect(self.calc_thread.quit)
        self.calc_worker.finished.connect(self.calc_worker.deleteLater)
        self.calc_worker.failed.connect(self.calc_worker.deleteLater)
        self.calc_thread.finished.connect(self.calc_thread.deleteLater)
        self.calc_thread.finished.connect(self.on_calculation_thread_done)
        self.calc_thread.start()

    def create_calculation_snapshot(self):
        flow_label = self.combo_flow.currentText()
        flow_type = FLOW_LABEL_TO_INTERNAL.get(flow_label, flow_label)
        exchanger_type = EXCHANGER_LABEL_TO_INTERNAL.get(self.combo_exchanger.currentText(), "finned_tube")
        return {
            "purpose": self.combo_purpose.currentText(),
            "flow_label": flow_label,
            "flow_type": flow_type,
            "exchanger_type": exchanger_type,
            "method": self.combo_method.currentText(),
            "u_mode": self.combo_u_mode.currentText(),
            "hot_selection": self.combo_hot.currentText(),
            "cold_selection": self.combo_cold.currentText(),
            "hot_mixture_data": dict(self.hot_mixture_data),
            "hot_mixture_basis": self.hot_mixture_basis,
            "cold_mixture_data": dict(self.cold_mixture_data),
            "cold_mixture_basis": self.cold_mixture_basis,
            "m_hot_raw": self.spin_m_hot.value(),
            "m_cold_raw": self.spin_m_cold.value(),
            "m_hot_unit": self.combo_u_m_hot.currentText(),
            "m_cold_unit": self.combo_u_m_cold.currentText(),
            "T_hot_raw": self.spin_t_hot.value(),
            "T_cold_raw": self.spin_t_cold.value(),
            "T_hot_unit": self.combo_u_t_hot.currentText(),
            "T_cold_unit": self.combo_u_t_cold.currentText(),
            "T_hot_out_raw": self.spin_t_hot_out.value(),
            "T_cold_out_raw": self.spin_t_cold_out.value(),
            "T_hot_out_unit": self.combo_u_t_hot_out.currentText(),
            "T_cold_out_unit": self.combo_u_t_cold_out.currentText(),
            "mu_hot": self.spin_mu_hot.value(),
            "k_hot": self.spin_k_hot.value(),
            "mu_cold": self.spin_mu_cold.value(),
            "k_cold": self.spin_k_cold.value(),
            "U": self.spin_U.value(),
            "A": self.spin_A.value(),
            "hot_is_tube": self.combo_hot_tube.currentText() == "Sıcak Akışkan",
            "geom": {
                "D_o": self.spin_do.value() / 1000.0,
                "D_i": self.spin_di.value() / 1000.0,
                "L": self.spin_l.value(),
                "N_tubes": self.spin_nt.value(),
                "k_wall": self.tube_mats[self.combo_tube_mat.currentText()],
                "is_finned": self.chk_finned.isChecked(),
                "fin_height": self.spin_fin_h.value() / 1000.0,
                "fin_thickness": self.spin_fin_t.value() / 1000.0,
                "fin_density": self.spin_fin_dens.value(),
                "k_fin": 237.0 if "Alüminyum" in self.combo_fin_mat.currentText() else 45.0,
                "fin_type": "rectangular" if "Rectangular" in self.combo_fin_type.currentText() else "annular",
                "pitch": self.spin_do.value() * 2 / 1000.0,
                "pitch_parallel": self.spin_do.value() * 2 / 1000.0,
                "tube_layout_angle": "30",
                "tube_arrangement": "staggered",
                "D_shell": self.spin_d_shell.value() / 1000.0,
                "R_f_i": self.spin_rf_i.value(),
                "R_f_o": self.spin_rf_o.value(),
            },
        }

    def on_calculation_thread_done(self):
        self.progress_calc.hide()
        self.btn_calc.setEnabled(True)
        self.calc_thread = None
        self.calc_worker = None

    def on_calculation_failed(self, title, message, exc):
        self.show_error(title, message, exc)

    def on_calculation_finished(self, payload):
        self.apply_calculation_result(payload)

    def apply_calculation_result(self, payload):
        hx = payload["hx"]
        geo_res = payload["geo_res"]
        res_main = payload["res_main"]
        res_act = payload["res_act"]
        crosscheck_results = payload["crosscheck_results"]
        pychemengg_warning = payload["pychemengg_warning"]
        is_rating = payload["is_rating"]
        t_out_h = payload["t_out_h"]
        t_out_c = payload["t_out_c"]

        self.last_geo_res = geo_res
        self.last_res_main = res_main
        self.last_res_act = res_act
        self.last_crosscheck_results = crosscheck_results
        self.last_report_context = payload["report_context"]
        self.btn_export_report.show()

        if geo_res:
            geo_warnings = "\n".join(geo_res.get("warnings", []))
            dp_text = ""
            if geo_res.get("delta_p_tube", 0) > 0:
                dp_text = (
                    f"\nΔP_boru = {geo_res['delta_p_tube'] / 1000:.3f} kPa"
                    f"  |  ΔP_gövde = {geo_res['delta_p_shell'] / 1000:.3f} kPa"
                )
            exch_label = EXCHANGER_INTERNAL_TO_LABEL.get(hx.exchanger_type, hx.exchanger_type)
            self.lbl_geo_res.setText(
                f"📐 {exch_label}: U={hx.U:.2f} W/m²K, A={hx.A:.2f} m²\n"
                f"h_i={geo_res['h_i']:.1f} W/m²K, h_o={geo_res['h_o']:.1f} W/m²K"
                + dp_text
                + (f"\n{geo_warnings}" if geo_warnings else "")
            )
        else:
            self.lbl_geo_res.setText("")

        if is_rating and res_act:
            self.lbl_res_q.setText(
                f"Gerçekleşen Transfer Edilen Isı (Q_ortalama): {res_act['Q_avg [W]'] / 1000:.2f} kW"
            )
            self.lbl_res_th.setText(
                f"Ölçülen Sıcak Çıkış: {t_out_h:.2f} °C  (Tasarım Beklentisi: {res_main['T_hot_out [C]']:.2f} °C)"
            )
            self.lbl_res_tc.setText(
                f"Ölçülen Soğuk Çıkış: {t_out_c:.2f} °C  (Tasarım Beklentisi: {res_main['T_cold_out [C]']:.2f} °C)"
            )
            self.lbl_res_eff.setText(
                f"Gerçekleşen Verim (ε): % {res_act['epsilon_actual'] * 100:.2f}  (Tasarım Verimi: % {res_main.get('epsilon', 0.0) * 100:.2f})"
            )
            enerji_farki = abs(res_act["Q_hot [W]"] - res_act["Q_cold [W]"]) / max(abs(res_act["Q_hot [W]"]), 1) * 100
            warnings_text = "\n".join(res_act.get("warnings", []))
            self.lbl_res_act.setText(
                f"⚠️ Enerji Dengesi Sapması: % {enerji_farki:.2f}\n"
                f"Bu sıcaklıklara ulaşmak için Gereken U Katsayısı: {res_act['U_required']:.2f} W/m²K"
                + (f"\n{warnings_text}" if warnings_text else "")
            )
        else:
            self.lbl_res_q.setText(f"Tasarım Isı Yükü (Q): {res_main['Q [W]'] / 1000:.2f} kW")
            self.lbl_res_th.setText(f"Hesaplanan Sıcak Akışkan Çıkışı: {res_main['T_hot_out [C]']:.2f} °C")
            self.lbl_res_tc.setText(f"Hesaplanan Soğuk Akışkan Çıkışı: {res_main['T_cold_out [C]']:.2f} °C")
            self.lbl_res_eff.setText(f"Sistem Tasarım Verimi (ε): % {res_main.get('epsilon', 0.0) * 100:.2f}")
            self.lbl_res_act.setText("\n".join(res_main.get("warnings", [])))

        if pychemengg_warning:
            self.append_log(pychemengg_warning, logging.INFO)
            self.filter_and_display_last_log(pychemengg_warning, logging.INFO)
        self.table_cc.setRowCount(len(crosscheck_results))
        for row, result in enumerate(crosscheck_results):
            q_diff = ""
            if res_main.get("Q [W]", 0) > 0:
                q_diff = f"{abs(result['Q [W]'] - res_main['Q [W]']) / res_main['Q [W]'] * 100:.3f}"
            self.table_cc.setItem(row, 0, QTableWidgetItem(result["Method"]))
            self.table_cc.setItem(row, 1, QTableWidgetItem(result["Source"]))
            self.table_cc.setItem(row, 2, QTableWidgetItem(result.get("status", "ok")))
            self.table_cc.setItem(row, 3, QTableWidgetItem(f"{result['Q [W]'] / 1000:.2f}"))
            self.table_cc.setItem(row, 4, QTableWidgetItem(q_diff))
            self.table_cc.setItem(row, 5, QTableWidgetItem(f"{result['T_hot_out [C]']:.2f}"))
            self.table_cc.setItem(row, 6, QTableWidgetItem(f"{result['T_cold_out [C]']:.2f}"))
            self.table_cc.setItem(row, 7, QTableWidgetItem(" | ".join(result.get("warnings", []))))

        hx.plot_enhanced_schematic(result=res_main, fig=self.figure)
        self.canvas.draw()
        hx.plot_temperature_profile(res_main, fig=self.figure_profile)
        self.canvas_profile.draw()

    def _calculate_impl(self):
        payload = compute_desktop_calculation(self.create_calculation_snapshot())
        self.apply_calculation_result(payload)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = HeatExchangerDesktopApp()
    ex.show()
    sys.exit(app.exec_())

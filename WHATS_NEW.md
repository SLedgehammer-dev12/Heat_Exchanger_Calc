# What's New in Heat Exchanger Calc v0.4.1
# Isı Değiştirici Hesap Aracı v0.4.1 Yenilikler

---

## Türkçe Özeti

### 🚀 v0.4.1 Sürümü ile Gelen Kritik Düzeltmeler ve İyileştirmeler

1. **`app_shared` Modül Bulunamadı Hatası Çözüldü (`ModuleNotFoundError: app_shared`)**:
   - `app_desktop.py`, `app_web.py`, `run_desktop.py` ve `run_web.py` dosyalarının en başına akıllı `sys.path` bootstrap eklendi.
   - Program hangi klasörden veya kısayoldan çalıştırılırsa çalıştırılsın ya da PyInstaller geçici dizininden (`_MEIPASS`) açılsın, paylaşılan çekirdek modüller (`app_shared`, `version` vb.) sorunsuz yüklenir.
   - `build_windows.ps1` ve `build_macos.sh` paketleme scriptlerine `--paths .`, `--paths $PSScriptRoot` ve `--add-data "app_shared.py;."` eklenerek exe/app paketlerinin içine eksiksiz gömülmesi sağlandı.

2. **NumPy 2.x PyInstaller Başlatma Çökmesi Düzeltildi (`ModuleNotFoundError: numpy._core._exceptions`)**:
   - NumPy 2.x ile paketlenen Windows çalıştırılabilir dosyalarında oluşan başlatma hatası, spec dosyalarına ve build scriptlerine `--collect-all numpy` ve `--hidden-import numpy._core._exceptions` eklenerek giderildi.
   - SciPy FFT rutinleri (`--collect-all scipy`) ve SSL sertifika deposu (`--collect-all certifi`) tek dosya (one-file) exe içerisine dahil edildi.

3. **Tam Test Güvencesi**:
   - Tüm 170 adet birim test (`test_lmtd_iter.py`) %100 başarıyla geçmektedir.
   - PyInstaller spec yapılandırmaları regresyon testleriyle kilitlendi.

---

### 🌟 v0.4.0 Serisi ile Eklenen Temel Mühendislik Yetenekleri

- **Çok Geçişli (Multipass) Boru Tarafı Hidroliği**:
  - $n_{passes}$ geçiş sayısı için akış kesit alanı $A_{c,i} = \frac{N}{n_{passes}} \frac{\pi D_i^2}{4}$ ve akış boyu $L_{flow} = L \cdot n_{passes}$ formülleri tam standarda uyarlandı. Hız ve basınç düşüşü sapmaları giderildi.
- **Halkasal (Dairesel) Kanat Yüzey Alanı Formülasyonu**:
  - İki yüzey alanı ve kanat ucu (tip) kalınlığı hesaba katıldı: $A_{fin} = 2\pi h_b (D_o + h_b) + \pi D_{fin} t_f$.
- **Ağırlıklı Toplam Yüzey Verimi ($\eta_o$)**:
  - Yalın boru yüzeyi haksız yere kanat verimiyle cezalandırılmadan doğrudan eklendi: $\eta_o = \frac{A_{bare} + \eta_{fin} A_{fin}}{A_{total}}$.
- **Minimum Akış Kesit Alanı ($A_{min}$) ve Kanat Engellemesi**:
  - Kanatların ön cephede yarattığı alan tıkanıklığı ($2 h_b t_f n_f N_T$) net serbest alandan düşüldü; hava hızı ve dış basınç düşüşü gerçekçi değerlere ulaştı.
- **ASME UG-27(c)(1) ve TEMA RCB-1.511 Mekanik Tasarım**:
  - Dış çap formülasyonu ($t = \frac{P R_o}{S E + 0.4 P}$) getirildi ve TEMA standardı gereğince eşanjör borularında korozyon payı sıfırlandı.
- **Bell-Delaware Gövde Tarafı Analitik Modeli**:
  - Gövde-boru eşanjörlerinde 5 Delaware düzeltme faktörü ($J_c, J_l, J_b, J_s, J_r$) analitik kübik spline fonksiyonlarıyla tam çözülür hale getirildi.
- **API 661 / ISO 13706 Kanat Bağlantı Tipleri**:
  - L-Fin, LL-Fin, KL-Fin, G-Fin ve Extruded fin tipleri, temas ısıl direnci ($R_{contact}$) ve sıcaklık limit uyarıları ile entegre edildi.
- **1D Sayısal Segmentli Çözücü (`solve_segmented`)**:
  - Eşanjör boyunca değişken fiziksel özellikler için $N$-segment sonlu hacim $\epsilon$-NTU algoritması eklendi.
- **Çift Platform ve Çok Dilli Mimari**:
  - Hem PyQt5 Masaüstü hem Streamlit Web arayüzü aynı sağlam çekirdekten beslenir.
  - Türkçe ve İngilizce tam gettext yerelleştirme desteği sağlandı.

---

## English Summary

### 🚀 Critical Fixes in v0.4.1

1. **Resolved `ModuleNotFoundError: No module named 'app_shared'`**:
   - Added robust `sys.path` bootstrapping to `app_desktop.py`, `app_web.py`, `run_desktop.py`, and `run_web.py`.
   - The application seamlessly discovers shared modules (`app_shared`, `version`, etc.) regardless of launch location, desktop shortcuts, or PyInstaller temporary extraction directories (`sys._MEIPASS`).
   - Packaged with `--paths .`, `--paths $PSScriptRoot`, and `--add-data "app_shared.py;."` in build scripts and spec files.

2. **Fixed NumPy 2.x PyInstaller Startup Crash (`ModuleNotFoundError: numpy._core._exceptions`)**:
   - Bundled complete NumPy submodules and exception classes via `--collect-all numpy` and `--hidden-import numpy._core._exceptions`.
   - Bundled complete SciPy dynamic libraries (`--collect-all scipy`) and Certifi SSL certificate bundles (`--collect-all certifi`).

3. **100% Verified Test Suite**:
   - All 170 unit and regression tests pass without errors.

---

## Supported Platforms / Desteklenen Platformlar

| Platform | Executable / Runner | Description |
| :--- | :--- | :--- |
| **Windows x64** | `HeatExchangerCalcDesktop.exe` | Standalone PyQt5 GUI executable |
| **Windows x64** | `HeatExchangerCalcWeb.exe` | Self-hosted Streamlit web browser executable |
| **macOS (Apple Silicon & Intel)** | `HeatExchangerCalcDesktop` | Standalone GUI executable |
| **macOS (Apple Silicon & Intel)** | `HeatExchangerCalcWeb` | Self-hosted Streamlit web executable |
| **Cross-Platform Python** | `python3 run_desktop.py` / `python3 run_web.py` | Source execution on Python 3.10 - 3.13 |

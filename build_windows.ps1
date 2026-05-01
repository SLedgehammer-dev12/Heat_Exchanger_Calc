param(
    [string]$CertificateThumbprint = "",
    [switch]$SkipClean
)

$ErrorActionPreference = "Stop"

if (-not $SkipClean) {
    Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue
}

$common = @(
    "--noconfirm",
    "--onedir",
    "--noupx",
    "--icon", "app_icon.ico",
    "--version-file", "version_info.txt",
    "--hidden-import", "scipy._cyutility",
    "--hidden-import", "engineering_utils",
    "--hidden-import", "reportlab",
    "--collect-data", "chemicals",
    "--collect-data", "thermo",
    "--collect-data", "fluids",
    "--collect-data", "ht",
    "--collect-all", "reportlab",
    "--exclude-module", "tkinter",
    "--exclude-module", "IPython",
    "--exclude-module", "notebook",
    "--exclude-module", "jupyter",
    "--add-data", "data;data"
)

pyinstaller @common --windowed --name HeatExchangerCalcDesktop app_desktop.py

$webArgs = @(
    "--hidden-import", "app_web",
    "--hidden-import", "fluids_db",
    "--hidden-import", "heat_exchanger",
    "--hidden-import", "reporting",
    "--hidden-import", "updater",
    "--hidden-import", "version",
    "--hidden-import", "logging_config",
    "--hidden-import", "engineering_utils",
    "--collect-all", "streamlit",
    "--copy-metadata", "streamlit",
    "--add-data", "app_web.py;."
)
pyinstaller @common @webArgs --console --name HeatExchangerCalcWeb run_web.py

if ($CertificateThumbprint) {
    $targets = @(
        "dist\HeatExchangerCalcDesktop\HeatExchangerCalcDesktop.exe",
        "dist\HeatExchangerCalcWeb\HeatExchangerCalcWeb.exe"
    )
    foreach ($target in $targets) {
        & signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /sha1 $CertificateThumbprint $target
    }
}

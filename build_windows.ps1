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
    "--onefile",
    "--noupx",
    "--icon", "app_icon.ico",
    "--version-file", "version_info.txt",
    "--hidden-import", "scipy._cyutility",
    "--hidden-import", "engineering_utils",
    "--hidden-import", "reportlab",
    "--hidden-import", "config",
    "--hidden-import", "units",
    "--hidden-import", "model_types",
    "--hidden-import", "i18n",
    "--hidden-import", "pint",
    "--hidden-import", "iapws",
    "--hidden-import", "exceptions",
    "--hidden-import", "helpers",
    "--hidden-import", "correlations",
    "--hidden-import", "plot_theme",
    "--collect-data", "chemicals",
    "--collect-data", "thermo",
    "--collect-data", "fluids",
    "--collect-data", "ht",
    "--collect-data", "pint",
    "--collect-data", "iapws",
    "--collect-all", "reportlab",
    "--exclude-module", "tkinter",
    "--exclude-module", "IPython",
    "--exclude-module", "notebook",
    "--exclude-module", "jupyter",
    "--add-data", "data;data",
    "--add-data", "locale;locale"
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

# --- Release packaging ---
$version = "0.1.7"
New-Item -ItemType Directory -Force -Path release | Out-Null

Copy-Item "dist\HeatExchangerCalcDesktop.exe" "release\HeatExchangerCalcDesktop-v$version-windows-x64.exe" -Force
Copy-Item "dist\HeatExchangerCalcWeb.exe" "release\HeatExchangerCalcWeb-v$version-windows-x64.exe" -Force

Push-Location release
Get-FileHash *.exe -Algorithm SHA256 | ForEach-Object { "$($_.Hash.ToLower())  $($_.Name)" } | Out-File -Encoding ASCII SHA256SUMS.txt
Pop-Location

Write-Host "✅ Release packages created in release\"

if ($CertificateThumbprint) {
    $targets = @(
        "release\HeatExchangerCalcDesktop-v$version-windows-x64.exe",
        "release\HeatExchangerCalcWeb-v$version-windows-x64.exe"
    )
    foreach ($target in $targets) {
        & signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /sha1 $CertificateThumbprint $target
    }
}

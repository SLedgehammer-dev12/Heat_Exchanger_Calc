import hashlib
import json
import os
import shutil
import urllib.error
import urllib.request
import webbrowser

from exceptions import UpdaterError
from version import GITHUB_REPO, VERSION


def _parse_version(value):
    value = str(value).strip().lstrip("vV")
    parts = []
    for part in value.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits or 0))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def check_for_update(timeout=5):
    """Return update metadata from GitHub Releases."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "HeatExchangerCalc-Updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return {
                "ok": True,
                "update_available": False,
                "message": "Henüz yayınlanmış bir GitHub release bulunamadı.",
            }
        return {"ok": False, "update_available": False, "message": f"Güncelleme kontrolü başarısız: HTTP {exc.code}"}
    except Exception as exc:
        return {"ok": False, "update_available": False, "message": f"Güncelleme kontrolü başarısız: {exc}"}

    latest = payload.get("tag_name", "").lstrip("v")
    release_url = payload.get("html_url", f"https://github.com/{GITHUB_REPO}/releases")
    assets = [
        {
            "name": asset.get("name", ""),
            "download_url": asset.get("browser_download_url", ""),
            "size": asset.get("size", 0),
            "digest": asset.get("digest", ""),
        }
        for asset in payload.get("assets", [])
    ]
    update_available = bool(latest) and _parse_version(latest) > _parse_version(VERSION)
    return {
        "ok": True,
        "update_available": update_available,
        "current_version": VERSION,
        "latest_version": latest or "-",
        "release_url": release_url,
        "assets": assets,
        "message": (f"Yeni sürüm bulundu: v{latest}" if update_available else f"Program güncel: v{VERSION}"),
    }


def open_release_page(url=None):
    webbrowser.open(url or f"https://github.com/{GITHUB_REPO}/releases/latest")


def select_release_asset(update_info, app_kind="desktop"):
    assets = update_info.get("assets", []) if update_info else []
    needle = "desktop" if app_kind == "desktop" else "web"
    for asset in assets:
        name = asset.get("name", "").lower()
        if needle in name and name.endswith(".zip"):
            return asset
    for asset in assets:
        if asset.get("name", "").lower().endswith(".zip"):
            return asset
    return None


def default_download_dir():
    downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    return downloads if os.path.isdir(downloads) else os.path.expanduser("~")


def download_release_asset(update_info, target_dir, app_kind="desktop", timeout=30):
    asset = select_release_asset(update_info, app_kind=app_kind)
    if not asset:
        raise UpdaterError("İndirilecek uygun release paketi bulunamadı.")
    if not target_dir:
        raise UpdaterError("İndirme klasörü seçilmedi.")
    os.makedirs(target_dir, exist_ok=True)
    url = asset.get("download_url")
    if not url:
        raise UpdaterError("Release asset indirme bağlantısı bulunamadı.")

    target_path = os.path.join(target_dir, asset["name"])
    part_path = target_path + ".part"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "HeatExchangerCalc-Updater"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response, open(part_path, "wb") as output:
        shutil.copyfileobj(response, output, length=1024 * 1024)
    os.replace(part_path, target_path)
    digest = asset.get("digest", "")
    if digest.startswith("sha256:"):
        expected_hash = digest.split(":", 1)[1].lower()
        sha256 = hashlib.sha256()
        with open(target_path, "rb") as downloaded:
            for chunk in iter(lambda: downloaded.read(1024 * 1024), b""):
                sha256.update(chunk)
        actual_hash = sha256.hexdigest().lower()
        if actual_hash != expected_hash:
            os.remove(target_path)
            raise UpdaterError("İndirilen dosyanın SHA256 doğrulaması başarısız oldu.")
    return {
        "path": target_path,
        "name": asset["name"],
        "size": os.path.getsize(target_path),
        "digest": digest,
    }

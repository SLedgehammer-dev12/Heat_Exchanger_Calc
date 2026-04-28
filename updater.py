import json
import urllib.error
import urllib.request
import webbrowser

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
    update_available = bool(latest) and _parse_version(latest) > _parse_version(VERSION)
    return {
        "ok": True,
        "update_available": update_available,
        "current_version": VERSION,
        "latest_version": latest or "-",
        "release_url": release_url,
        "message": (
            f"Yeni sürüm bulundu: v{latest}"
            if update_available
            else f"Program güncel: v{VERSION}"
        ),
    }


def open_release_page(url=None):
    webbrowser.open(url or f"https://github.com/{GITHUB_REPO}/releases/latest")


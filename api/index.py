import hashlib
import json
import os
import time
from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
import requests

PORTAL_URL = "http://portal.wisp.cat/stalker_portal/server/load.php"
MAC_BASE = "00:1A:79:65:7B:01"
BASE_PROXY_URL = "https://stream-tv-digital.hf.space"

app = FastAPI()

status_data = {
    "last_update": "Hali yangilanmagan",
    "total_channels": 1,
    "status": "Kuting...",
}

def get_session():
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like"
            " Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
        ),
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://portal.wisp.cat/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Pragma": "no-cache",
    }
    session.headers.update(headers)
    session.cookies.set("mac", MAC_BASE, domain="portal.wisp.cat")
    session.cookies.set("stb_lang", "en", domain="portal.wisp.cat")
    session.cookies.set("timezone", "Europe/London", domain="portal.wisp.cat")

    try:
        session.get("http://portal.wisp.cat/stalker_portal/c/", timeout=5)
    except Exception:
        pass

    try:
        session.get("http://portal.wisp.cat/stalker_portal/c/xpcom.common.js", timeout=5)
    except Exception:
        pass

    try:
        session.get("http://portal.wisp.cat/stalker_portal/c/version.js", timeout=5)
    except Exception:
        pass

    token = ""
    try:
        hs_url = "http://portal.wisp.cat/stalker_portal/server/load.php?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        r = session.get(hs_url, timeout=10).json()
        token = r.get("js", {}).get("token", "")
        if token:
            session.cookies.set("token", token, domain="portal.wisp.cat")
            session.headers.update({"Authorization": f"Bearer {token}"})
    except Exception:
        pass

    metrics_data = json.dumps({
        "type": "stb",
        "model": "MAG254",
        "mac": MAC_BASE,
        "sn": "C29FF3A4A8F7B",
        "uid": "662591BD155567306F4C764C06503277A88F46A33171F128147ABFD5BDEF3EF3",
        "random": "b9a90b92ac722147751dbbf9a06fd3a6dec9c08f"
    })

    token_param = f"&token={token}" if token else ""
    prof_url = (
        f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1"
        f"{token_param}"
        "&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.3.0; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c"
        "&num_banks=2&sn=C29FF3A4A8F7B&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi"
        "&device_id=ED8631D5017C0DC1C1F6EF359AED6D2A894486F6D12876E3BE38B9A377953846"
        "&device_id2=ED8631D5017C0DC1C1F6EF359AED6D2A894486F6D12876E3BE38B9A377953846"
        "&signature=02D90DC0532B449B16E8DC52B55521F8823B0FDD8B7C09D80930627FBF4EC212"
        "&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0"
        f"&metrics={metrics_data}"
        f"&hw_version_2=df793726342adb400f308f1c587784ae29c4f28a&timestamp={int(time.time())}&api_signature=262&prehash=1bef54600c63cfdc086dad053d447f3ade6e628f"
    )
    
    try:
        session.get(prof_url, timeout=10)
    except Exception:
        pass

    try:
        acc_url = f"{PORTAL_URL}?type=account_info&action=get_main_info&JsHttpRequest=1-xml"
        session.get(acc_url, timeout=10)
    except Exception:
        pass

    return session

def update_playlist():
    global status_data
    status_data["status"] = "Yangilanmoqda..."

    session = get_session()
    channels_url = f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml"

    channels = []
    for _ in range(2):
        try:
            channels_res = session.get(channels_url, timeout=10).json()
            channels = channels_res.get("js", {}).get("data", [])
            if channels:
                break
        except Exception:
            time.sleep(1)

    if not channels:
        cmd = "ffmpeg http://lb.wisp.cat/lb0/5kanalHDUA/video.m3u8"
        ch_name = "5 Kanal HD"
    else:
        target_channel = channels[0]
        ch_name = target_channel.get("name", "Kanal")
        cmd = target_channel.get("cmd", "ffmpeg http://lb.wisp.cat/lb0/5kanalHDUA/video.m3u8")

    temp_file = "/tmp/playlist.tmp"
    final_file = "/tmp/playlist.json"

    success = False
    stream_url = None

    for attempt in range(2):
        try:
            time.sleep(0.2)
            link_url = f"{PORTAL_URL}?type=itv&action=create_link&cmd={requests.utils.quote(cmd)}&JsHttpRequest=1-xml"
            link_res = session.get(link_url, timeout=10).json()
            stream_cmd = link_res.get("js", {}).get("cmd")

            if stream_cmd:
                if stream_cmd.startswith("ffmpeg "):
                    stream_url = stream_cmd.replace("ffmpeg ", "").strip()
                else:
                    stream_url = stream_cmd
                success = True
                break
        except Exception:
            session = get_session()

    if not success or not stream_url:
        stream_url = (
            cmd.replace("ffmpeg ", "").replace("ch:ffrt ", "").strip()
            if "http" in cmd
            else "http://lb.wisp.cat/lb0/5kanalHDUA/video.m3u8"
        )

    channels_list = [{"name": ch_name, "url": stream_url}]

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(channels_list, f, ensure_ascii=False, indent=4)

    if os.path.exists(final_file):
        os.remove(final_file)
    os.rename(temp_file, final_file)

    status_data["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    status_data["status"] = "Muvaffaqiyatli"

@app.get("/", response_class=HTMLResponse)
def admin_panel():
    # Автообновление плейлиста на лету, если его нет или прошло больше 60 секунд
    if not os.path.exists("/tmp/playlist.json") or (time.time() - os.path.getmtime("/tmp/playlist.json") > 60):
        try:
            update_playlist()
        except Exception:
            pass

    return f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <title>Admin Panel</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 50px; }}
            .card {{ background: #1e293b; padding: 30px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }}
            .badge {{ background: #22c55e; color: white; padding: 5px 12px; border-radius: 20px; font-weight: bold; }}
            a {{ color: #38bdf8; text-decoration: none; display: block; margin-top: 15px; font-size: 18px; }}
            a:hover {{ text-decoration: underline; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Admin Panel</h2>
            <p>Holati: <span class="badge">{status_data["status"]}</span></p>
            <p><b>Kanal:</b> {status_data["total_channels"]} ta</p>
            <p><b>Oxirgi yangilangan vaqt:</b> {status_data["last_update"]}</p>
            <hr style="border: 0.5px solid #334155; margin: 20px 0;">
            <a href="https://ksiomi-redmi.hf.space" target="_blank">TEST ADMIN</a>
        </div>
    </body>
    </html>
    """

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/playlist.json")
def download_json():
    if not os.path.exists("/tmp/playlist.json") or (time.time() - os.path.getmtime("/tmp/playlist.json") > 60):
        try:
            update_playlist()
        except Exception:
            pass

    if os.path.exists("/tmp/playlist.json"):
        with open("/tmp/playlist.json", "r", encoding="utf-8") as f:
            content = json.load(f)
        return content
    return {"error": "Hali playlist tayyor emas!"}, 404

@app.get("/pl.m3u8", response_class=PlainTextResponse)
def download_m3u8():
    if not os.path.exists("/tmp/playlist.json") or (time.time() - os.path.getmtime("/tmp/playlist.json") > 60):
        try:
            update_playlist()
        except Exception:
            pass

    if not os.path.exists("/tmp/playlist.json"):
        return "#EXTM3U\n# Xatolik: Playlist hali tayyorlanmadi"

    try:
        with open("/tmp/playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
    except Exception:
        return "#EXTM3U\n# Xatolik: Playlistni o'qib bo'lmadi"

    m3u_lines = ["#EXTM3U"]
    for ch in channels:
        name = ch.get("name", "Kanal")
        url = ch.get("url", "")
        m3u_lines.append(f"#EXTINF:-1,{name}")
        m3u_lines.append(url)

    return "\n".join(m3u_lines)

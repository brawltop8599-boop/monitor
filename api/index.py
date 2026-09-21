import hashlib
import json
import os
import time
from fastapi import FastAPI, Response, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
import requests

PORTAL_URL = "http://app.ttt5.me/stalker_portal/server/load.php"
PORTAL_BASE = "http://app.ttt5.me"

MAC_BASE = "00:1A:79:67:D2:D4"
SN_BASE = "E64E3F8B8C092"
UID_BASE = "D19D40486081779F90A66F60EB9836A1D2A63ED493961445338D76A01F31F6D4"
DEVICE_ID = "20FB21AA77D58B6DC9200101EED68B82C4350765274BC3373EA9758DC8F3EA9E"

# Укажите ваш домен на Vercel (например: https://your-project.vercel.app)
BASE_PROXY_URL = "https://blacktulipstav.onrender.com" 
SECRET_KEY = "TvZaTak"
TELEGRAM_GROUP_URL = "https://t.me/+2lWVU6CKQsVkMWRi"  

app = FastAPI()

# В памяти для Serverless
memory_cache = {
    "channels": [],
    "genres": {},
    "last_update": 0
}

def get_session():
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3",
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://app.ttt5.me/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Connection": "close",
    }
    session.headers.update(headers)
    session.cookies.set("mac", MAC_BASE, domain="app.ttt5.me")
    session.cookies.set("stb_lang", "en", domain="app.ttt5.me")
    session.cookies.set("timezone", "Europe/London", domain="app.ttt5.me")

    try:
        session.get("http://app.ttt5.me/stalker_portal/c/", timeout=3)
    except Exception:
        pass

    token = ""
    try:
        hs_url = f"{PORTAL_URL}?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        r = session.get(hs_url, timeout=5).json()
        js_data = r.get("js", {})
        token = js_data.get("token", "")
        if token:
            session.cookies.set("token", token, domain="app.ttt5.me")
            session.headers.update({"Authorization": f"Bearer {token}"})
    except Exception:
        pass

    return session

def load_channels_cached():
    # Кэшируем на 5 минут в памяти экземпляра функции
    if time.time() - memory_cache["last_update"] < 300 and memory_cache["channels"]:
        return memory_cache["channels"], memory_cache["genres"]

    session = get_session()
    genres_map = {}
    try:
        g_resp = session.get(f"{PORTAL_URL}?type=itv&action=get_genres&JsHttpRequest=1-xml", timeout=5).json()
        for g in g_resp.get("js", []):
            if g.get("id") is not None:
                genres_map[str(g.get("id"))] = g.get("title", "Umumiy")
    except Exception:
        pass

    channels = []
    try:
        res = session.get(f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml", timeout=6).json()
        data = res.get("js", {}).get("data", [])
        if isinstance(data, list):
            channels = data
    except Exception:
        pass

    if not channels:
        try:
            res = session.get(f"{PORTAL_URL}?type=itv&action=get_ordered_list&genre=*&sortby=number&order=asc&JsHttpRequest=1-xml", timeout=6).json()
            data = res.get("js", {}).get("data", [])
            if isinstance(data, list):
                channels = data
        except Exception:
            pass

    channels_list = []
    for ch in channels:
        logo = ch.get("logo", "")
        if logo and not logo.startswith("http"):
            logo = f"http://app.ttt5.me/stalker_portal/misc/logos/{logo}"
        
        genre_id = str(ch.get("tv_genre_id", ch.get("genre_id", "")))
        channels_list.append({
            "name": ch.get("name", "Kanal"),
            "cmd": ch.get("cmd", ""),
            "group": genres_map.get(genre_id, "Umumiy"),
            "logo": logo
        })

    if channels_list:
        memory_cache["channels"] = channels_list
        memory_cache["genres"] = genres_map
        memory_cache["last_update"] = time.time()

    return channels_list, genres_map

@app.get("/", response_class=RedirectResponse)
def root_redirect():
    return RedirectResponse(url=TELEGRAM_GROUP_URL, status_code=302)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/playlist.json")
def download_json(key: str = ""):
    if key != SECRET_KEY:
        return [{"name": "Xato kalit", "group": "Stub", "url": "https://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4"}]

    channels, _ = load_channels_cached()
    result = []
    for index, ch in enumerate(channels):
        result.append({
            "name": ch["name"],
            "group": ch.get("group", "Umumiy"),
            "logo": ch.get("logo", ""),
            "url": f"{BASE_PROXY_URL}/ch/{index}?key={SECRET_KEY}"
        })
    return result

@app.get("/pl.m3u8", response_class=PlainTextResponse)
@app.get("/playlist.m3u8", response_class=PlainTextResponse)
def download_m3u8(key: str = ""):
    headers = {"Content-Disposition": "attachment; filename=playlist.m3u8"}
    if key != SECRET_KEY:
        return PlainTextResponse("#EXTM3U\n#EXTINF:-1,Xato kalit\nhttps://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4", headers=headers)

    channels, _ = load_channels_cached()
    m3u_lines = ["#EXTM3U"]
    for index, ch in enumerate(channels):
        stream_link = f"{BASE_PROXY_URL}/ch/{index}?key={SECRET_KEY}"
        m3u_lines.append(f"#EXTINF:-1 tvg-name=\"{ch['name']}\" group-title=\"{ch['group']}\",{ch['name']}")
        m3u_lines.append(stream_link)

    return PlainTextResponse("\n".join(m3u_lines), headers=headers)

@app.get("/ch/{index}")
def proxy_stream(index: int, key: str = ""):
    if key != SECRET_KEY:
        return RedirectResponse(url="https://github.com/brawltop8599-boop/ads-stub/raw/refs/heads/main/v.mp4", status_code=302)

    channels, _ = load_channels_cached()
    if index >= len(channels):
        return Response("Kanal topilmadi", status_code=404)

    cmd = channels[index].get("cmd", "")
    session = get_session()
    stream_url = ""
    
    try:
        clean_cmd = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if clean_cmd.startswith(prefix):
                clean_cmd = clean_cmd[len(prefix):].strip()
                
        link_url = f"{PORTAL_URL}?type=itv&action=create_link&cmd={requests.utils.quote(clean_cmd)}&JsHttpRequest=1-xml"
        link_res = session.get(link_url, timeout=5).json()
        stream_cmd = link_res.get("js", {}).get("cmd")
        if stream_cmd:
            stream_url = stream_cmd
            for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
                if stream_url.startswith(prefix):
                    stream_url = stream_url[len(prefix):].strip()
    except Exception:
        pass

    if not stream_url or "://" not in stream_url:
        stream_url = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if stream_url.startswith(prefix):
                stream_url = stream_url[len(prefix):].strip()

    if stream_url.startswith("/"):
        stream_url = f"{PORTAL_BASE}{stream_url}"

    if stream_url and "token=" not in stream_url:
        tkn = session.cookies.get("token")
        if tkn:
            stream_url += ("&" if "?" in stream_url else "?") + f"token={tkn}"

    return RedirectResponse(url=stream_url, status_code=302)

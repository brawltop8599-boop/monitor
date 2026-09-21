import hashlib
import json
import os
import time
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse
import requests

PORTAL_URL = "http://app.ttt5.me/stalker_portal/server/load.php"
MAC_BASE = "00:1A:79:69:E5:45"

app = FastAPI()

def get_base_url(request: Request = None):
    if request:
        host = request.headers.get("host")
        if host:
            protocol = "https" if "vercel.app" in host or (request.url and request.url.scheme == "https") else "http"
            return f"{protocol}://{host}"
    vercel_url = os.environ.get("VERCEL_URL")
    if vercel_url:
        return f"https://{vercel_url}"
    return "http://localhost:8000"

def get_session(force_new=False):
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like"
            " Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
        ),
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://app.ttt5.me/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "close",
        "Pragma": "no-cache",
    }
    session.headers.update(headers)
    session.cookies.set("mac", MAC_BASE, domain="app.ttt5.me")
    session.cookies.set("stb_lang", "en", domain="app.ttt5.me")
    session.cookies.set("timezone", "Europe/London", domain="app.ttt5.me")

    try:
        session.get("http://app.ttt5.me/stalker_portal/c/", timeout=5)
    except Exception:
        pass

    token = ""
    random_val = "f113bcdf5643a1304e51821e196324694cc63b63"
    try:
        hs_url = (
            "http://app.ttt5.me/stalker_portal/server/load.php?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        )
        r = session.get(hs_url, timeout=10).json()
        js_data = r.get("js", {})
        token = js_data.get("token", "")
        random_val = js_data.get("random", random_val)
        
        if token:
            session.cookies.set("token", token, domain="app.ttt5.me")
            session.headers.update({"Authorization": f"Bearer {token}"})
    except Exception:
        pass

    metrics_data = json.dumps({
        "type": "stb",
        "model": "MAG254",
        "mac": MAC_BASE,
        "sn": "0407B4BF76218",
        "uid": "5E1285BD5AF191EC376A28D7E5A1715CEB1AD52D1401D4AB63FDA492DB92D792",
        "random": random_val,
    })

    token_param = f"&token={token}" if token else ""
    prof_url = (
        f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1"
        f"{token_param}"
        "&ver=ImageDescription: 0.2.18-r23-250; ImageDate: Thu Sep 13 11:31:16 EEST 2018; PORTAL version: 5.3.0; API Version: JS API version: 343; STB API version: 146; Player Engine version: 0x58c"
        "&num_banks=2&sn=08AFC4CEE5C20&stb_type=MAG250&client_type=STB&image_version=218&video_out=hdmi"
        "&device_id=53FF962B702C6BF53568E9C1754D5DCFD40047AC4E7183D751E561144474F196"
        "&device_id2=53FF962B702C6BF53568E9C1754D5DCFD40047AC4E7183D751E561144474F196"
        "&signature=750D0CDFABAE18DC8CDF63CF947C8468DD8B64A6B6C8222C7C4B1FB37FB7BAA2"
        "&auth_second_step=1&hw_version=1.7-BD-00&not_valid_token=0"
        f"&metrics={metrics_data}"
        f"&hw_version_2=993f7da2a2a6bf7fd7e91daff521f0329b92803&timestamp={int(time.time())}&api_signature=262&prehash=f72d83731a918aa2171706f4a6100b76cd0062d8"
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

def fetch_channels_data(session):
    genres_map = {}
    try:
        genres_url = f"{PORTAL_URL}?type=itv&action=get_genres&JsHttpRequest=1-xml"
        g_resp = session.get(genres_url, timeout=10).json()
        g_data = g_resp.get("js", [])
        if isinstance(g_data, list):
            for g in g_data:
                gid = g.get("id")
                gtitle = g.get("title", "Boshqa")
                if gid is not None:
                    genres_map[str(gid)] = gtitle
    except Exception:
        pass

    channels = []
    seen_cmds = set()

    try:
        channels_url = f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
        channels_res = session.get(channels_url, timeout=10).json()
        data = channels_res.get("js", {}).get("data", [])
        if isinstance(data, list):
            channels = data
    except Exception:
        pass

    if not channels:
        try:
            list_url = f"{PORTAL_URL}?type=itv&action=get_ordered_list&genre=*&sortby=number&order=asc&hd=0&fav=0&not_my_genres=0&JsHttpRequest=1-xml"
            res = session.get(list_url, timeout=10).json()
            data = res.get("js", {}).get("data", [])
            if not data and isinstance(res.get("js"), list):
                data = res.get("js", [])
            if isinstance(data, list):
                channels = data
        except Exception:
            pass

    try:
        if genres_map:
            for gid in genres_map.keys():
                sub_url = f"{PORTAL_URL}?type=itv&action=get_ordered_list&genre={gid}&sortby=number&order=asc&hd=0&fav=0&not_my_genres=0&JsHttpRequest=1-xml"
                sub_resp = session.get(sub_url, timeout=5).json()
                sub_data = sub_resp.get("js", {}).get("data", [])
                if isinstance(sub_data, list):
                    for ch in sub_data:
                        cmd = ch.get("cmd", "")
                        if cmd and cmd not in seen_cmds:
                            seen_cmds.add(cmd)
                            channels.append(ch)
    except Exception:
        pass

    return channels, genres_map

def load_or_update_playlist():
    final_file = "playlist.json"
    
    # Agar fayl oxirgi 1 soat ichida yaratilgan bo'lsa, qayta yuklamaymiz (tez ishlashi uchun)
    if os.path.exists(final_file):
        if (time.time() - os.path.getmtime(final_file)) < 3600:
            try:
                with open(final_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

    session = get_session()
    channels, genres_map = fetch_channels_data(session)

    channels_list = []
    for ch in channels:
        ch_name = ch.get("name", "Kanal")
        cmd = ch.get("cmd", "")
        
        logo = ch.get("logo", "")
        if logo and not logo.startswith("http"):
            logo = f"http://app.ttt5.me/stalker_portal/misc/logos/{logo}"

        genre_id = str(ch.get("tv_genre_id", ch.get("genre_id", "")))
        group_title = genres_map.get(genre_id, "Umumiy")

        if cmd:
            channels_list.append({
                "name": ch_name,
                "cmd": cmd,
                "group": group_title,
                "logo": logo
            })

    if channels_list:
        with open(final_file, "w", encoding="utf-8") as f:
            json.dump(channels_list, f, ensure_ascii=False, indent=4)
            
    return channels_list

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
def admin_panel():
    channels = []
    if os.path.exists("playlist.json"):
        try:
            with open("playlist.json", "r", encoding="utf-8") as f:
                channels = json.load(f)
        except Exception:
            pass
            
    total = len(channels)
    last_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(os.path.getmtime("playlist.json"))) if os.path.exists("playlist.json") else "Hali yo'q"

    return f"""
    <!DOCTYPE html>
    <html lang="uz">
    <head>
        <meta charset="UTF-8">
        <title>IPTV Admin Panel</title>
        <style>
            body {{ font-family: Arial, sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding: 50px; }}
            .card {{ background: #1e293b; padding: 30px; border-radius: 12px; display: inline-block; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }}
            .badge {{ background: #22c55e; color: white; padding: 5px 12px; border-radius: 20px; font-weight: bold; }}
            a {{ color: #38bdf8; text-decoration: none; display: block; margin-top: 15px; font-size: 18px; }}
            a:hover {{ text-decoration: underline; }}
            .btn {{ background: #3b82f6; color: white; padding: 10px 20px; border-radius: 6px; display: inline-block; margin-top: 15px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🚀 IPTV Proxy Admin Panel</h2>
            <p>Holati: <span class="badge">Aktiv va Tayyor ✅</span></p>
            <p><b>Kanallar soni:</b> {total} ta</p>
            <p><b>Oxirgi yangilangan vaqt:</b> {last_time}</p>
            <hr style="border: 0.5px solid #334155; margin: 20px 0;">
            <a href="/pl.m3u8" target="_blank">📥 M3U Playlist (/pl.m3u8)</a>
            <a href="/playlist.json" target="_blank" style="color: #94a3b8; font-size: 14px;">📄 JSON ni ko'rish (/playlist.json)</a>
            <a href="/refresh" class="btn">🔄 Kanallarni Yangilash</a>
        </div>
    </body>
    </html>
    """

@app.get("/refresh")
def force_refresh():
    if os.path.exists("playlist.json"):
        os.remove("playlist.json")
    load_or_update_playlist()
    return RedirectResponse(url="/", status_code=302)

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/playlist.json")
def download_json(request: Request):
    channels = load_or_update_playlist()
    if channels:
        base_url = get_base_url(request)
        result = []
        for index, ch in enumerate(channels):
            result.append({
                "name": ch["name"],
                "group": ch.get("group", "Umumiy"),
                "logo": ch.get("logo", ""),
                "url": f"{base_url}/stream/{index}"
            })
        return result
    return JSONResponse(content={"error": "Kanal topilmadi yoki portal javob bermadi!"}, status_code=404)

@app.get("/pl.m3u8", response_class=PlainTextResponse)
def download_m3u8(request: Request):
    channels = load_or_update_playlist()
    if not channels:
        return "#EXTM3U\n# Xatolik: Kanal topilmadi yoki portal javob bermadi"

    base_url = get_base_url(request)
    m3u_lines = ["#EXTM3U"]
    for index, ch in enumerate(channels):
        name = ch.get("name", "Kanal")
        group = ch.get("group", "Umumiy")
        logo = ch.get("logo", "")
        stream_link = f"{base_url}/stream/{index}"
        
        m3u_line = f"#EXTINF:-1 tvg-name=\"{name}\" tvg-logo=\"{logo}\" group-title=\"{group}\",{name}"
        m3u_lines.append(m3u_line)
        m3u_lines.append(stream_link)

    return "\n".join(m3u_lines)

@app.get("/stream/{index}")
def proxy_stream(index: int):
    if not os.path.exists("playlist.json"):
        return Response("Playlist topilmadi", status_code=404)
    
    try:
        with open("playlist.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
        target = channels[index]
        cmd = target.get("cmd", "")
    except Exception as e:
        return Response(f"Kanal topilmadi: {e}", status_code=404)

    session = get_session()
    stream_url = ""
    
    try:
        clean_cmd = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if clean_cmd.startswith(prefix):
                clean_cmd = clean_cmd[len(prefix):].strip()
                
        link_url = f"{PORTAL_URL}?type=itv&action=create_link&cmd={requests.utils.quote(clean_cmd)}&JsHttpRequest=1-xml"
        link_res = session.get(link_url, timeout=10).json()
        
        stream_cmd = link_res.get("js", {}).get("cmd")
        if stream_cmd:
            stream_url = stream_cmd
            for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
                if stream_url.startswith(prefix):
                    stream_url = stream_url[len(prefix):].strip()
    except Exception as e:
        print(f"Create link xatolik (stream): {e}")

    if not stream_url and "http" in cmd:
        stream_url = cmd
        for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
            if stream_url.startswith(prefix):
                stream_url = stream_url[len(prefix):].strip()

    if stream_url and "token=" not in stream_url:
        session_token = session.cookies.get("token")
        if session_token:
            separator = "&" if "?" in stream_url else "?"
            stream_url = f"{stream_url}{separator}token={session_token}"

    if not stream_url:
        return Response("Stream URL yaratib bo'lmadi", status_code=500)

    return RedirectResponse(url=stream_url, status_code=302)

import hashlib
import json
import os
import time
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, StreamingResponse
import requests

PORTAL_URL = "http://app.ttt5.me/stalker_portal/server/load.php"
MAC_BASE = "00:1A:79:69:E5:45"
PLAYLIST_FILE = "/tmp/playlist.json"

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

def get_session():
    session = requests.Session()
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (QtEmbedded; U; Linux; C) AppleWebKit/533.3 (KHTML, like"
            " Gecko) MAG200 stbapp ver: 2 rev: 250 Safari/533.3"
        ),
        "X-User-Agent": "Model: MAG250; Link: WiFi",
        "Referer": "http://app.ttt5.me/stalker_portal/c/index.html",
        "Accept": "*/*",
        "Connection": "close",
    }
    session.headers.update(headers)
    session.cookies.set("mac", MAC_BASE, domain="app.ttt5.me")
    session.cookies.set("stb_lang", "en", domain="app.ttt5.me")
    session.cookies.set("timezone", "Europe/London", domain="app.ttt5.me")

    token = ""
    random_val = "f113bcdf5643a1304e51821e196324694cc63b63"
    
    try:
        hs_url = f"{PORTAL_URL}?type=stb&action=handshake&token=&JsHttpRequest=1-xml"
        r = session.get(hs_url, timeout=4).json()
        js_data = r.get("js", {})
        token = js_data.get("token", "")
        random_val = js_data.get("random", random_val)
        
        if token:
            session.cookies.set("token", token, domain="app.ttt5.me")
            session.headers.update({"Authorization": f"Bearer {token}"})
    except Exception as e:
        print(f"Handshake error: {e}")

    # Сразу шлем профиль с токеном
    metrics_data = json.dumps({
        "type": "stb", "model": "MAG254", "mac": MAC_BASE,
        "sn": "0407B4BF76218", "uid": "5E1285BD5AF191EC376A28D7E5A1715CEB1AD52D1401D4AB63FDA492DB92D792",
        "random": random_val,
    })

    token_param = f"&token={token}" if token else ""
    prof_url = (
        f"{PORTAL_URL}?type=stb&action=get_profile&JsHttpRequest=1-xml&hd=1{token_param}"
        f"&metrics={metrics_data}&timestamp={int(time.time())}"
    )
    try:
        session.get(prof_url, timeout=4)
    except Exception as e:
        print(f"Profile error: {e}")

    return session

def fetch_channels_data(session):
    channels = []
    debug_body = ""
    
    try:
        channels_url = f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
        res = session.get(channels_url, timeout=10)
        debug_body = res.text[:400] # Сохраняем кусок ответа для отладки
        
        # Проверяем, действительно ли пришел JSON (а не HTML-ошибка)
        if res.status_code == 200 and res.text.strip().startswith("{"):
            channels_res = res.json()
            js_field = channels_res.get("js")
            if isinstance(js_field, list):
                channels = js_field
            elif isinstance(js_field, dict):
                channels = js_field.get("data", js_field.get("channels", []))
    except Exception as e:
        debug_body = f"JSON Parse Exception: {str(e)}"

    if not channels:
        # Сохраняем текст ответа сервера в файл отладки
        try:
            with open(PLAYLIST_FILE + ".debug", "w", encoding="utf-8") as f:
                f.write(f"Status 200 but not JSON. Body start: {debug_body}")
        except Exception:
            pass

    return channels    
def load_or_update_playlist():
    if os.path.exists(PLAYLIST_FILE):
        if (time.time() - os.path.getmtime(PLAYLIST_FILE)) < 3600:
            try:
                with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data:
                        return data
            except Exception:
                pass

    session = get_session()
    
    # Отладочный запрос с перехватом текста ответа
    channels = []
    debug_info = ""
    try:
        channels_url = f"{PORTAL_URL}?type=itv&action=get_all_channels&JsHttpRequest=1-xml"
        res = session.get(channels_url, timeout=10)
        debug_info = f"Status: {res.status_code}, Body: {res.text[:400]}"
        
        channels_res = res.json()
        js_field = channels_res.get("js")
        if isinstance(js_field, list):
            channels = js_field
        elif isinstance(js_field, dict):
            channels = js_field.get("data", js_field.get("channels", []))
    except Exception as e:
        debug_info = f"Exception: {str(e)}"

    if not channels:
        # Сохраним отладочную информацию во временный файл, чтобы вернуть ее клиенту
        try:
            with open(PLAYLIST_FILE + ".debug", "w", encoding="utf-8") as f:
                f.write(debug_info)
        except Exception:
            pass
        return []

    channels_list = []
    for ch in channels:
        ch_name = ch.get("name", "Kanal")
        cmd = ch.get("cmd", "")
        
        logo = ch.get("logo", "")
        if logo and not logo.startswith("http"):
            logo = f"http://app.ttt5.me/stalker_portal/misc/logos/{logo}"

        group_title = ch.get("genre_title", ch.get("tv_genre_id", "Umumiy"))

        if cmd:
            channels_list.append({
                "name": ch_name,
                "cmd": cmd,
                "group": str(group_title),
                "logo": logo
            })

    if channels_list:
        try:
            with open(PLAYLIST_FILE, "w", encoding="utf-8") as f:
                json.dump(channels_list, f, ensure_ascii=False, indent=4)
        except Exception:
            pass
            
    return channels_list
    
@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
def admin_panel():
    channels = []
    if os.path.exists(PLAYLIST_FILE):
        try:
            with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
                channels = json.load(f)
        except Exception:
            pass
            
    total = len(channels)
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
            <p>Holati: <span class="badge">Ishlayapti ✅ (Proxy Mode)</span></p>
            <p><b>Kanallar soni:</b> {total} ta</p>
            <hr style="border: 0.5px solid #334155; margin: 20px 0;">
            <a href="/pl.m3u8" target="_blank">📥 M3U Playlist (/pl.m3u8)</a>
            <a href="/playlist.json" target="_blank" style="color: #94a3b8; font-size: 14px;">📄 JSON ni ko'rish (/playlist.json)</a>
            <a href="/refresh" class="btn">🔄 Yangilash</a>
        </div>
    </body>
    </html>
    """

@app.get("/refresh")
def force_refresh():
    if os.path.exists(PLAYLIST_FILE):
        os.remove(PLAYLIST_FILE)
    load_or_update_playlist()
    return RedirectResponse(url="/", status_code=302)

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
    return JSONResponse(content={"error": "Kanal topilmadi!"}, status_code=404)

@app.get("/pl.m3u8", response_class=PlainTextResponse)
def download_m3u8(request: Request):
    channels = load_or_update_playlist()
    if not channels:
        debug_msg = "Kanal topilmadi"
        if os.path.exists(PLAYLIST_FILE + ".debug"):
            try:
                with open(PLAYLIST_FILE + ".debug", "r", encoding="utf-8") as f:
                    debug_msg = f.read()
            except Exception:
                pass
        return f"#EXTM3U\n# Xatolik: {debug_msg}"

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
def proxy_stream(index: int, request: Request):
    if not os.path.exists(PLAYLIST_FILE):
        return Response("Playlist topilmadi", status_code=404)
    
    try:
        with open(PLAYLIST_FILE, "r", encoding="utf-8") as f:
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
        link_res = session.get(link_url, timeout=5).json()
        
        stream_cmd = link_res.get("js", {}).get("cmd") or link_res.get("js", {}).get("url")
        if stream_cmd:
            stream_url = stream_cmd
            for prefix in ["ffmpeg ", "ch:ffrt ", "ffrt ", "ch:"]:
                if stream_url.startswith(prefix):
                    stream_url = stream_url[len(prefix):].strip()
    except Exception:
        pass

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

    try:
        upstream_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*"
        }
        
        range_header = request.headers.get("range")
        if range_header:
            upstream_headers["Range"] = range_header

        req = requests.get(stream_url, headers=upstream_headers, stream=True, timeout=10)
        
        if req.status_code >= 400 and req.status_code != 206:
            return Response(f"Upstream error: {req.status_code}", status_code=req.status_code)

        excluded_headers = ["content-encoding", "transfer-encoding", "connection"]
        response_headers = {
            key: value for key, value in req.headers.items()
            if key.lower() not in excluded_headers
        }
        response_headers["Access-Control-Allow-Origin"] = "*"

        return StreamingResponse(
            req.iter_content(chunk_size=65536),
            status_code=req.status_code,
            headers=response_headers,
            media_type=req.headers.get("content-type", "video/mp2t")
        )
    except Exception as e:
        return Response(f"Proxy error: {e}", status_code=500)

import html
import gzip
import os
from pathlib import Path
import config
import time
from datetime import datetime

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Transcript Ticket {channel_name} - {date}</title>
<style>
:root {{ --af-blue:#002395; --af-red:#ED2939; --bg:#0f0f12; --card:#1a1a1e; --text:#e9e9ee; --muted:#9aa0a6; }}
*{{box-sizing:border-box}}
body{{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:var(--bg);color:var(--text)}}
header{{background:linear-gradient(135deg,var(--af-blue),#001a6b);padding:28px 24px;color:white}}
header h1{{margin:0;font-size:22px}}
header p{{margin:6px 0 0;opacity:.85}}
.container{{max-width:900px;margin:24px auto;padding:0 16px}}
.meta{{background:var(--card);border:1px solid #2a2a30;border-radius:12px;padding:16px;display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:18px}}
.meta div span{{display:block;font-size:11px;letter-spacing:.08em;color:var(--muted);text-transform:uppercase}}
.meta div strong{{font-size:14px}}
.message{{background:var(--card);border:1px solid #2a2a30;border-radius:12px;padding:12px 14px;margin:10px 0;display:flex;gap:12px}}
.avatar{{width:40px;height:40px;border-radius:50%;flex-shrink:0;object-fit:cover;background:#2a2a30}}
.content{{flex:1;min-width:0}}
.author{{font-weight:600;font-size:14px}} .author small{{color:var(--muted);font-weight:400;margin-left:6px}}
.text{{margin:6px 0 0;white-space:pre-wrap;word-break:break-word;font-size:14px;line-height:1.5}}
.time{{font-size:11px;color:var(--muted);margin-top:6px}}
.attach{{display:inline-block;margin-top:8px;background:#23232a;border:1px solid #333;padding:6px 10px;border-radius:8px;font-size:12px;color:#cfd2d6;text-decoration:none}}
.bot{{border-color:#1e3a5f}}
.system{{background:#1e1e22;border-style:dashed}}
footer{{text-align:center;color:var(--muted);font-size:12px;padding:24px}}
</style>
</head>
<body>
<header>
  <h1>✈️ Air France Helpine — Transcript</h1>
  <p>Ticket #{channel_name} • {date} • {count} messages</p>
</header>
<div class="container">
  <div class="meta">
    <div><span>Utilisateur</span><strong>{user_tag} ({user_id})</strong></div>
    <div><span>Salon</span><strong>#{channel_name} ({channel_id})</strong></div>
    <div><span>Ouvert</span><strong>{opened}</strong></div>
    <div><span>Fermé</span><strong>{closed}</strong></div>
  </div>
  {messages_html}
  <footer>Généré par Air France Helpine Bot • {gen_date} • Stockage optimisé (gzip + WAL)</footer>
</div>
</body>
</html>
"""

def _escape(s: str) -> str:
    return html.escape(s or "")

def build_transcript_html(channel_name: str, channel_id: int, user_tag: str, user_id: int,
                          opened_ts: int, closed_ts: int, messages: list) -> str:
    def fmt(ts):
        return datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M:%S") if ts else "—"

    msgs_html = ""
    for m in messages:
        author = _escape(m.get("author_name") or m.get("author_id") or "Inconnu")
        content = _escape(m.get("content") or "")
        # Légère mise en forme markdown -> html simple (évite stockage lourd)
        content = content.replace("\n", "<br>")
        is_bot = m.get("is_bot") == 1
        ts = m.get("created_at")
        attach_html = ""
        if m.get("attachments"):
            # attachments stocké comme string join
            for url in m["attachments"].split("|"):
                if url.strip():
                    attach_html += f'<br><a class="attach" href="{_escape(url)}" target="_blank">📎 { _escape(url.split("/")[-1][:40]) }</a>'
        avatar = "https://cdn.discordapp.com/embed/avatars/0.png"
        # on ne stocke pas l'avatar pour optimiser
        cls = "message bot" if is_bot else "message"
        msgs_html += f"""
        <div class="{cls}">
          <img class="avatar" src="{avatar}" alt="">
          <div class="content">
            <div class="author">{author} <small>{fmt(ts)}</small></div>
            <div class="text">{content}{attach_html}</div>
          </div>
        </div>
        """

    return HTML_TEMPLATE.format(
        channel_name=_escape(channel_name),
        channel_id=channel_id,
        user_tag=_escape(user_tag),
        user_id=user_id,
        date=fmt(closed_ts or int(time.time())),
        count=len(messages),
        opened=fmt(opened_ts),
        closed=fmt(closed_ts),
        messages_html=msgs_html or "<p style='text-align:center;color:#9aa0a6'>Aucun message</p>",
        gen_date=fmt(int(time.time())),
    )

async def save_transcript(channel_name: str, channel_id: int, user_tag: str, user_id: int,
                          opened_ts: int, closed_ts: int, messages: list) -> str:
    """
    Génère et sauvegarde le transcript en HTML + gzip pour optimiser le stockage.
    Retourne le chemin du fichier.
    """
    html_content = build_transcript_html(channel_name, channel_id, user_tag, user_id, opened_ts, closed_ts, messages)
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in channel_name)
    filename = f"{safe_name}-{channel_id}-{int(time.time())}.html"
    dir_path = Path(config.TRANSCRIPT_DIR)
    dir_path.mkdir(parents=True, exist_ok=True)
    full_path = dir_path / filename

    # Écriture HTML
    full_path.write_text(html_content, encoding="utf-8")

    # Compression optionnelle
    if config.TRANSCRIPT_COMPRESSION:
        gz_path = Path(str(full_path) + ".gz")
        with open(full_path, "rb") as f_in, gzip.open(gz_path, "wb", compresslevel=9) as f_out:
            f_out.write(f_in.read())
        # On garde le .gz et supprime le .html non compressé pour économiser ~70%
        os.remove(full_path)
        return str(gz_path)
    return str(full_path)

def get_transcript_size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except:
        return 0

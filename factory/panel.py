"""Video paneli: GitHub Releases'taki tüm videoları README.md'nin başına tablo olarak yazar.
Depo ana sayfası (github.com/<kullanıcı>/<depo>) böylece izleme/indirme paneli olur."""
import json
import os
import re
import urllib.request

START, END = "<!-- PANEL:START -->", "<!-- PANEL:END -->"


def releases(repo, token):
    out, page = [], 1
    while True:
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/releases?per_page=100&page={page}",
                                     headers=dict({"Accept": "application/vnd.github+json"}, **({"Authorization": f"Bearer {token}"} if token else {})))
        data = json.loads(urllib.request.urlopen(req, timeout=60).read())
        out += data
        if len(data) < 100:
            return out
        page += 1


def build(repo, token):
    rel = [r for r in releases(repo, token) if r["tag_name"].startswith("video-")]
    rel.sort(key=lambda r: r["created_at"], reverse=True)
    lines = [START, "", "# 🎬 Video Paneli", "",
             f"**{len(rel)} video** · yeni videolar her gün otomatik eklenir · "
             f"[tüm sürümler](https://github.com/{repo}/releases)", "",
             "| Kapak | Video | İndir |", "|:-:|---|:-:|"]
    for r in rel:
        a = {x["name"]: x["browser_download_url"] for x in r["assets"]}
        mp4 = next((u for n, u in a.items() if n.endswith(".mp4")), None)
        jpg = next((u for n, u in a.items() if n.endswith(".jpg")), None)
        srt = next((u for n, u in a.items() if n.endswith(".srt")), None)
        if not mp4:
            continue
        mb = next((x["size"] for x in r["assets"] if x["name"].endswith(".mp4")), 0) / 1e6
        date = r["created_at"][:10]
        title = re.sub(r"\s*#shorts", "", r["name"] or r["tag_name"]).replace("|", "-")
        thumb = f'<a href="{mp4}"><img src="{jpg}" width="120"></a>' if jpg else ""
        dl = f"[▶️ MP4 ({mb:.0f} MB)]({mp4})" + (f"<br>[💬 Altyazı]({srt})" if srt else "") + \
             f"<br>[📝 Metin]({r['html_url']})"
        lines.append(f"| {thumb} | **{title}**<br>{date} | {dl} |")
    if not rel:
        lines.append("| | İlk video hazırlanıyor… | |")
    lines += ["", END]
    return "\n".join(lines)


def update_readme(path="README.md"):
    repo, token = os.environ["GITHUB_REPOSITORY"], os.environ["GH_TOKEN"]
    panel = build(repo, token)
    txt = open(path, encoding="utf-8").read()
    if START in txt:
        txt = re.sub(re.escape(START) + ".*?" + re.escape(END), lambda m: panel, txt, flags=re.S)
    else:
        txt = panel + "\n\n---\n\n" + txt
    open(path, "w", encoding="utf-8").write(txt)
    print("panel güncellendi")


if __name__ == "__main__":
    update_readme()

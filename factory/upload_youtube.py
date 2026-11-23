"""Optional free auto-upload to YouTube (long videos + Shorts) (YouTube Data API v3, free quota ~6 uploads/day).

Needs env: YT_CLIENT_ID, YT_CLIENT_SECRET, YT_REFRESH_TOKEN  (see README).
"""
import os


def upload(video_path, title, description, tags, privacy="public"):
    if not all(os.environ.get(k) for k in ("YT_CLIENT_ID", "YT_CLIENT_SECRET", "YT_REFRESH_TOKEN")):
        print("  [youtube] anahtar yok, yükleme atlandı")
        return None
    return _do_upload(video_path, title, description, tags, privacy)


def _client():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"],
                        client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                        token_uri="https://oauth2.googleapis.com/token",
                        scopes=["https://www.googleapis.com/auth/youtube.upload"])
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def _do_upload(video_path, title, description, tags, privacy):
    from googleapiclient.http import MediaFileUpload
    yt = _client()
    body = {"snippet": {"title": title[:100], "description": description, "tags": [t.lstrip("#") for t in tags],
                        "categoryId": "27", "defaultLanguage": "tr"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    req = yt.videos().insert(part="snippet,status", body=body,
                             media_body=MediaFileUpload(video_path, chunksize=-1, resumable=True))
    resp = None
    while resp is None:
        _, resp = req.next_chunk()
    print("  [youtube] yüklendi: https://youtu.be/" + resp["id"])
    return resp["id"]


def set_thumbnail(video_id, path):
    """Özel kapak (kanal telefonla doğrulanmış olmalı; olmazsa sessizce geçer)."""
    try:
        from googleapiclient.http import MediaFileUpload
        _client().thumbnails().set(videoId=video_id, media_body=MediaFileUpload(path)).execute()
        print("  [youtube] kapak ayarlandı")
    except Exception as e:  # noqa: BLE001
        print(f"  [youtube] kapak ayarlanamadı: {e}")

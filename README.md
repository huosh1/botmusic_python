# 🎵 Discord Music Bot (systemd)

A simple but powerful **Discord music bot** running with **systemd** for auto-restart and persistence.  
Supports **YouTube** and **SoundCloud** (single tracks and playlists).  

👉 **You can add it on your Discord server here:**  
[https://huoshi.pythonanywhere.com/bot](https://huoshi.pythonanywhere.com/bot)

---

## ⚙️ Features
- Play local MP3 files or YouTube/SoundCloud links (broken)
- Playlist support
- Queue system (`!queue`, `!skip`, `!clear`)
- Pause/Resume/Stop
- Volume control
- FFmpeg integration
- Auto-restart via `systemd`

---

## 📦 Installation

### 1. Install dependencies
```bash
sudo apt update
sudo apt install -y ffmpeg libopus0 python3-venv

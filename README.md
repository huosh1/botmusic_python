# 🎵 Discord Multi Music Bot

A simple **Discord music bot** supporting **multiple servers at the same time**.  
It can play music from **YouTube**, **SoundCloud**, or local MP3 files, using **FFmpeg** and **yt-dlp**.

---

## 🚀 Features

- ✅ Multi-server support (each guild has its own queue & player loop)  
- ✅ Play tracks from SoundCloud,..  
- ✅ Local file support (`./music/*.mp3`)  
- ✅ Playlist support (SoundCloud sets)  
- ✅ Queue management (`!queue`, `!skip`, `!clear`)  
- ✅ Volume control (`!volume 0-100`)  
- ✅ Debug & format inspection commands  
- ✅ systemd integration for 24/7 hosting  

---

## 📂 Project structure

```

bot-multi/
├── multibot.py        # Main bot source code
├── requirements.txt   # Python dependencies
└── README.md          # Documentation (this file)

````

---

## ⚙️ Installation (Ubuntu 20.04+)

```bash
# Clone repository
git clone https://github.com/huosh1/botmusic_python.git
cd botmusic_python

# Setup virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
````

Dependencies inside `requirements.txt`:

```
discord.py[voice]<3.0,>=2.3
yt-dlp>=2024.10.0
PyNaCl>=1.5.0,<1.6
```

Also make sure **FFmpeg** is installed:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

---

## 🔑 Configuration

Edit `multibot.py` and replace:

```python
TOKEN = "YOUR_DISCORD_BOT_TOKEN"
```

with your bot token from the [Discord Developer Portal](https://discord.com/developers/applications).

---

## ▶️ Usage

Run manually (inside venv):

```bash
python3 multibot.py
```

Or install as a systemd service for auto-restart:

`/etc/systemd/system/multibot.service` :

```ini
[Unit]
Description=Discord Multi Music Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/bot-multi
Environment=PATH=/home/ubuntu/bot-multi/.venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=/home/ubuntu/bot-multi/.venv/bin/python multibot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reexec
sudo systemctl enable multibot.service
sudo systemctl start multibot.service
```

---

## 🎶 Commands

```
!play <url/file>     → Add song to queue
!playlist <url>      → Add a playlist
!pause               → Pause
!resume              → Resume
!skip                → Skip current song
!stop                → Stop and clear queue
!leave               → Disconnect bot
!queue               → Show queue
!current             → Show current song
!volume <0-100>      → Adjust volume
!list                → List local files
!formats <url>       → Show available formats
!debug <url>         → Debug media link
!test_ffmpeg         → Check FFmpeg installation
```

## 🌐 Add the bot to your server

👉 [Click here to invite](https://huoshi.pythonanywhere.com/bot)


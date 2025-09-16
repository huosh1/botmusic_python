## You can add it on your server discord : 
https://huoshi.pythonanywhere.com/bot

# Discord Music Bot (systemd)

## Dépendances
```bash
sudo apt update
sudo apt install -y ffmpeg libopus0 python3-venv
cd /home/ubuntu/discord
python3 -m venv .venv
. .venv/bin/activate
pip install --upgrade pip
pip install "discord.py[voice]" yt-dlp
deactivate

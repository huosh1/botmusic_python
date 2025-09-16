import discord
from discord.ext import commands
import asyncio
import os
import yt_dlp
import urllib.parse
from typing import Optional

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)  # si tu veux désactiver l'aide par défaut: help_command=None

# Chemin vers FFmpeg - CHANGE CE CHEMIN selon ton installation !
# Windows: r"C:\ffmpeg\bin\ffmpeg.exe"
# Si FFmpeg est dans le PATH, laisse None
FFMPEG_PATH = None  # Change ça si FFmpeg n'est pas dans le PATH

# Options pour yt-dlp (gère SoundCloud et autres)
ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,           # on remettra False pour la résolution des playlists
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(title)s.%(ext)s',
    'restrictfilenames': True,
    'logtostderr': False,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
}

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

class MusicBot:
    def __init__(self):
        self.voice_client: Optional[discord.VoiceClient] = None
        self.current_song: Optional[str] = None
        self.queue: asyncio.Queue = asyncio.Queue()
        self.player_task: Optional[asyncio.Task] = None
        self.next_event: Optional[asyncio.Event] = None
        self.stopped = False  # pour !stop qui vide la queue

    async def join_channel(self, ctx):
        """Rejoindre le canal vocal de l'utilisateur"""
        if ctx.author.voice is None:
            await ctx.send("Tu dois être dans un canal vocal !")
            return False

        channel = ctx.author.voice.channel
        if self.voice_client is None:
            self.voice_client = await channel.connect()
        elif self.voice_client.channel != channel:
            await self.voice_client.move_to(channel)
        return True

    async def ensure_player(self, ctx):
        """Démarre la task lecteur si pas encore lancée"""
        if self.player_task is None or self.player_task.done():
            self.stopped = False
            self.player_task = asyncio.create_task(self.player_loop(ctx))

    async def enqueue_stream(self, title: str, stream_url: str):
        """Ajoute un flux (déjà résolu) à la queue"""
        await self.queue.put({"title": title, "url": stream_url})

    async def resolve_url(self, url: str):
        """Résout un URL (track ou playlist) -> liste d'items (title, url)"""
        results = []
        # autoriser playlists pour la résolution
        opts = ydl_opts.copy()
        opts["noplaylist"] = False
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if info is None:
                return results
            if "entries" in info and info["entries"]:
                for entry in info["entries"]:
                    if not entry:
                        continue
                    title = entry.get("title", "Titre inconnu")
                    stream_url = entry.get("url")
                    if stream_url:
                        results.append((title, stream_url))
            else:
                title = info.get("title", "Titre inconnu")
                stream_url = info.get("url")
                if stream_url:
                    results.append((title, stream_url))
        return results

    async def player_loop(self, ctx):
        """Lit en boucle tout ce qui arrive dans la queue"""
        while not self.stopped:
            item = await self.queue.get()  # attend si vide
            title, stream_url = item["title"], item["url"]

            # Si un morceau joue, stop pour enchaîner proprement
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
                await asyncio.sleep(0.5)

            try:
                # Crée la source FFmpeg
                if FFMPEG_PATH:
                    source = discord.FFmpegPCMAudio(stream_url, executable=FFMPEG_PATH, **ffmpeg_options)
                else:
                    source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)

                self.next_event = asyncio.Event()
                self.current_song = title

                def _after(err):
                    # callback thread → on rebondit sur l’event loop
                    if err:
                        print(f"Player error: {err}")
                    if self.next_event and not self.next_event.is_set():
                        asyncio.run_coroutine_threadsafe(self._signal_next(), asyncio.get_event_loop())

                if self.voice_client:
                    self.voice_client.play(source, after=_after)
                    await ctx.send(f"▶️ Lecture : {title}")

                    # Attendre la fin
                    while self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
                        if self.next_event:
                            try:
                                await asyncio.wait_for(self.next_event.wait(), timeout=0.5)
                            except asyncio.TimeoutError:
                                pass
                        else:
                            await asyncio.sleep(0.5)

            except Exception as e:
                await ctx.send(f"❌ Erreur de lecture: {e}")

            finally:
                self.queue.task_done()
                self.current_song = None

    async def _signal_next(self):
        if self.next_event and not self.next_event.is_set():
            self.next_event.set()

    async def play_file(self, ctx, file_path):
        """Envoie un fichier local dans la queue"""
        if not os.path.exists(file_path):
            await ctx.send(f"❌ Fichier non trouvé : {file_path}")
            return
        if not await self.join_channel(ctx):
            return
        if self.voice_client is None:
            return

        title = os.path.basename(file_path)
        await self.enqueue_stream(title, file_path)
        await self.ensure_player(ctx)
        await ctx.send(f"➕ Ajouté à la file : {title}")

    async def play_url(self, ctx, url):
        """Résout un lien (track OU playlist) et alimente la queue"""
        if not await self.join_channel(ctx):
            return
        await ctx.send("🔄 Récupération du lien...")

        try:
            items = await self.resolve_url(url)
            if not items:
                await ctx.send("❌ Aucun flux audio trouvé")
                return

            # Empile tout (si playlist → plusieurs titres)
            for title, stream_url in items:
                await self.enqueue_stream(title, stream_url)

            await self.ensure_player(ctx)
            if len(items) == 1:
                await ctx.send(f"➕ Ajouté à la file : {items[0][0]}")
            else:
                await ctx.send(f"🎶 **{len(items)}** titres ajoutés à la file")

        except Exception as e:
            error_msg = str(e).lower()
            if "private" in error_msg or "unavailable" in error_msg:
                await ctx.send("❌ Cette musique est privée ou indisponible")
            elif "geo" in error_msg or "location" in error_msg:
                await ctx.send("❌ Cette musique est bloquée dans votre région")
            elif "copyright" in error_msg:
                await ctx.send("❌ Problème de droits d'auteur")
            else:
                await ctx.send(f"❌ Erreur lors du téléchargement : {str(e)}")

class MusicBotManager:
    """Un MusicBot par serveur (guild)"""
    def __init__(self):
        self.bots = {}  # {guild_id: MusicBot}

    def get_bot(self, guild_id: int) -> MusicBot:
        if guild_id not in self.bots:
            self.bots[guild_id] = MusicBot()
        return self.bots[guild_id]

music_manager = MusicBotManager()

@bot.event
async def on_ready():
    print(f'{bot.user} est connecté !')

# --- COMMANDES ---

@bot.command(name='play', aliases=['p'])
async def play(ctx, *, query):
    """Jouer un fichier MP3 ou un lien (track/playlist)"""
    if ctx.guild is None:
        return
    music_bot = music_manager.get_bot(ctx.guild.id)

    if query.startswith('http'):
        await music_bot.play_url(ctx, query)
    else:
        if not query.endswith('.mp3'):
            query += '.mp3'
        possible_paths = [
            os.path.join("music", query),
            query,
            os.path.join(".", query)
        ]
        file_path = None
        for path in possible_paths:
            if os.path.exists(path):
                file_path = path
                break
        if file_path is None:
            await ctx.send(f"❌ Fichier non trouvé : {query}")
            await ctx.send("💡 Utilise `!list` pour voir les fichiers disponibles")
            return
        await music_bot.play_file(ctx, file_path)

@bot.command(name='stop')
async def stop(ctx):
    """Arrêter la musique et vider la file"""
    if ctx.guild is None:
        return
    music_bot = music_manager.get_bot(ctx.guild.id)

    music_bot.stopped = True
    try:
        while not music_bot.queue.empty():
            music_bot.queue.get_nowait()
            music_bot.queue.task_done()
    except Exception:
        pass
    if music_bot.voice_client and (music_bot.voice_client.is_playing() or music_bot.voice_client.is_paused()):
        music_bot.voice_client.stop()
    await ctx.send("⏹️ Musique arrêtée et file vidée")

@bot.command(name='pause')
async def pause(ctx):
    """Mettre en pause"""
    if ctx.guild is None:
        return
    music_bot = music_manager.get_bot(ctx.guild.id)

    if music_bot.voice_client and music_bot.voice_client.is_playing():
        music_bot.voice_client.pause()
        await ctx.send("⏸️ Musique en pause")

@bot.command(name='resume')
async def resume(ctx):
    """Reprendre"""
    if ctx.guild is None:
        return
    music_bot = music_manager.get_bot(ctx.guild.id)

    if music_bot.voice_client and music_bot.voice_client.is_paused():
        music_bot.voice_client.resume()
        await ctx.send("▶️ Musique reprise")

@bot.command(name='leave', aliases=['disconnect'])
async def leave(ctx):
    """Quitter le canal vocal"""
    if ctx.guild is None:
        return
    music_bot = music_manager.get_bot(ctx.guild.id)

    if music_bot.voice_client:
        await music_bot.voice_client.disconnect()
        music_bot.voice_client = None
        await ctx.send("👋 Bot déconnecté")

@bot.command(name='current', aliases=['now'])
async def current(ctx):
    """Afficher la chanson actuelle"""
    if ctx.guild is None:
        return
    music_bot = music_manager.get_bot(ctx.guild.id)

    if music_bot.current_song:
        await ctx.send(f"🎵 En cours : {music_bot.current_song}")
    else:
        await ctx.send("Aucune musique en cours")

@bot.command(name='list', aliases=['ls'])
async def list_music(ctx):
    """Lister les fichiers MP3 disponibles"""
    music_files = []
    if os.path.exists("music"):
        for file in os.listdir("music"):
            if file.endswith(('.mp3', '.wav', '.m4a', '.flac')):
                music_files.append(f"music/{file}")
    for file in os.listdir("."):
        if file.endswith(('.mp3', '.wav', '.m4a', '.flac')):
            music_files.append(file)
    if music_files:
        files_list = "\n".join([f"• {os.path.basename(file)}" for file in music_files[:15]])
        await ctx.send(f"🎵 **Fichiers disponibles :**\n```\n{files_list}\n```")
    else:
        await ctx.send("❌ Aucun fichier audio trouvé dans ./music/ ou le dossier courant")

@bot.command(name='playforce')
async def playforce(ctx, *, url):
    """Forcer la lecture avec options simplifiées (peut bypass certains soucis)"""
    if ctx.guild is None:
        return
    music_bot = music_manager.get_bot(ctx.guild.id)

    if not await music_bot.join_channel(ctx):
        return
    await ctx.send("🔄 Force download...")

    try:
        simple_opts = {
            'format': 'worst[acodec!=none]/bestaudio/best',
            'quiet': True,
            'no_warnings': True
        }
        with yt_dlp.YoutubeDL(simple_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Titre inconnu')
            formats = info.get('formats', [])
            stream_url = None
            for fmt in formats:
                if fmt.get('acodec') and fmt.get('acodec') != 'none':
                    stream_url = fmt.get('url')
                    break
            if not stream_url:
                stream_url = info.get('url')
            if not stream_url:
                await ctx.send("❌ Aucun stream trouvé")
                return

            # Ici, on empile aussi dans la queue pour rester cohérent
            await music_bot.enqueue_stream(title, stream_url)
            await music_bot.ensure_player(ctx)
            await ctx.send(f"🔧 **Force basic** : {title}")

    except Exception as e:
        await ctx.send(f"❌ Erreur générale : {str(e)}")

@bot.command(name='formats')
async def show_formats(ctx, *, url):
    """Voir tous les formats disponibles"""
    try:
        with yt_dlp.YoutubeDL({'quiet': True}) as ydl:
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            format_list = []
            for i, fmt in enumerate(formats[:10]):
                codec = fmt.get('acodec', 'none')
                ext = fmt.get('ext', 'unknown')
                quality = fmt.get('abr', 'unknown')
                format_list.append(f"{i}: {codec} | {ext} | {quality}kbps")
            formats_text = "\n".join(format_list)
            await ctx.send(f"🎵 **Formats disponibles:**\n```\n{formats_text}\n```")
    except Exception as e:
        await ctx.send(f"❌ Erreur formats : {e}")

@bot.command(name='debug')
async def debug(ctx, *, url):
    """Debug un lien (titre, durée, url, nb de formats)"""
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Titre inconnu')
            stream_url = info.get('url')
            duration = info.get('duration', 'Inconnue')
            formats = info.get('formats', [])
            debug_msg = f"""
🔍 **Debug Info:**
**Titre:** {title}
**Durée:** {duration}s
**Stream URL:** {"✅ Trouvée" if stream_url else "❌ Manquante"}
**Formats disponibles:** {len(formats)}
            """
            await ctx.send(debug_msg)
    except Exception as e:
        await ctx.send(f"❌ Erreur debug : {e}")

@bot.command(name='volume')
async def volume(ctx, vol: int = None):
    """Changer le volume (0-100)"""
    if vol is None:
        await ctx.send("Usage: `!volume <0-100>`")
        return
    if vol < 0 or vol > 100:
        await ctx.send("Volume doit être entre 0 et 100")
        return
    volume_float = vol / 100
    global ffmpeg_options
    ffmpeg_options['options'] = f'-vn -filter:a "volume={volume_float}"'
    await ctx.send(f"🔊 Volume réglé à {vol}%")

@bot.command(name='test_ffmpeg')
async def test_ffmpeg(ctx):
    """Tester si FFmpeg marche"""
    try:
        import subprocess
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            await ctx.send("✅ FFmpeg trouvé et fonctionnel !")
        else:
            await ctx.send("❌ FFmpeg trouvé mais erreur")
    except FileNotFoundError:
        await ctx.send("❌ FFmpeg non trouvé dans le PATH")
    except Exception as e:
        await ctx.send(f"❌ Erreur FFmpeg : {e}")

@bot.command(name="playlist")
async def playlist(ctx, url: str):
    """Ajoute toute une playlist à la file (SoundCloud/YouTube)"""
    if ctx.guild is None:
        return
    music_bot = music_manager.get_bot(ctx.guild.id)
    # On réutilise la logique de play_url qui gère track OU playlist et alimente la queue
    await music_bot.play_url(ctx, url)

@bot.command(name="queue", aliases=["q"])
async def show_queue(ctx):
    """Afficher la file d'attente"""
    if ctx.guild is None:
        return
    music_bot = music_manager.get_bot(ctx.guild.id)

    if music_bot.current_song is None and music_bot.queue.empty():
        await ctx.send("🧺 La file est vide.")
        return

    items = []
    if not music_bot.queue.empty():
        try:
            size = music_bot.queue.qsize()
            for _ in range(size):
                item = music_bot.queue.get_nowait()
                items.append(item)
                music_bot.queue.put_nowait(item)  # remettre
        except Exception:
            pass

    lines = []
    if music_bot.current_song:
        lines.append(f"🎵 **En cours** : {music_bot.current_song}")
    for i, it in enumerate(items[:15], start=1):
        lines.append(f"{i}. {it['title']}")

    msg = "\n".join(lines) if lines else "🧺 La file est vide."
    await ctx.send(f"**Queue :**\n```\n{msg}\n```")

@bot.command(name="skip", aliases=["s"])
async def skip(ctx):
    """Passer au morceau suivant"""
    if ctx.guild is None:
        return
    music_bot = music_manager.get_bot(ctx.guild.id)

    if music_bot.voice_client and music_bot.voice_client.is_playing():
        music_bot.voice_client.stop()
        await ctx.send("⏭️ Skip")
    else:
        await ctx.send("Rien à passer.")

@bot.command(name="clear")
async def clear_queue(ctx):
    """Vider la file d'attente"""
    if ctx.guild is None:
        return
    music_bot = music_manager.get_bot(ctx.guild.id)

    cleared = 0
    try:
        while not music_bot.queue.empty():
            music_bot.queue.get_nowait()
            music_bot.queue.task_done()
            cleared += 1
    except Exception:
        pass
    await ctx.send(f"🧹 File vidée ({cleared} éléments).")

@bot.command(name='help_music')
async def help_music(ctx):
    """Afficher l'aide complète"""
    help_text = """
🎵 **Commandes du bot musical** 🎵

**▶️ Lecture**
`!play <fichier>`      → Ajouter un fichier MP3 local (sans .mp3)
`!play <url>`          → Ajouter un lien SoundCloud/YouTube (track ou playlist)
`!playlist <url>`      → Ajouter explicitement une playlist complète
`!playforce <url>`     → Forcer la lecture avec options simplifiées

**⏯️ Contrôle**
`!pause`               → Mettre en pause
`!resume`              → Reprendre
`!skip` / `!s`         → Passer au morceau suivant
`!stop`                → Arrêter et vider la file
`!leave` / `!disconnect` → Déconnecter le bot du vocal
`!volume <0-100>`      → Régler le volume

**📋 File d’attente**
`!queue` / `!q`        → Afficher la file en cours
`!clear`               → Vider la file
`!current` / `!now`    → Afficher la chanson actuelle

**📂 Fichiers locaux**
`!list` / `!ls`        → Lister les fichiers audio disponibles

**🔧 Outils & Debug**
`!formats <url>`       → Voir les formats audio disponibles
`!debug <url>`         → Infos debug sur un lien
`!test_ffmpeg`         → Vérifier que FFmpeg est fonctionnel

---
**Exemples :**
`!play let` (joue let.mp3 dans ./music)
`!play https://soundcloud.com/...`
`!playlist https://soundcloud.com/user/sets/...`
    """
    await ctx.send(help_text)

if __name__ == "__main__":
    # Lis le token depuis l'environnement (systemd: /etc/discord-music.env)
    TOKEN = os.getenv("DISCORD_TOKEN", "")
    if not TOKEN:
        raise SystemExit("Missing DISCORD_TOKEN env var")
    print("Démarrage du bot...")
    bot.run(TOKEN)


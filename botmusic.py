import discord
from discord.ext import commands
import asyncio
import os
import yt_dlp
import urllib.parse

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Chemin vers FFmpeg - CHANGE CE CHEMIN selon ton installation !
# Exemples courants :
# Windows: r"C:\ffmpeg\bin\ffmpeg.exe"
# Si FFmpeg est dans le PATH, laisse None
FFMPEG_PATH = None  # Change ça si FFmpeg n'est pas dans le PATH

# Options pour yt-dlp (gère SoundCloud et autres)
ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
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
        self.voice_client = None
        self.current_song = None

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

    async def play_file(self, ctx, file_path):
        """Jouer un fichier MP3 local"""
        if not os.path.exists(file_path):
            await ctx.send(f"❌ Fichier non trouvé : {file_path}")
            return
        
        if not await self.join_channel(ctx):
            return
        
        try:
            if self.voice_client and self.voice_client.is_playing():
                self.voice_client.stop()
            
            # Utiliser FFmpeg avec ou sans chemin spécifique
            if FFMPEG_PATH:
                source = discord.FFmpegPCMAudio(file_path, executable=FFMPEG_PATH, **ffmpeg_options)
            else:
                source = discord.FFmpegPCMAudio(file_path, **ffmpeg_options)
            
            if self.voice_client:
                self.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)
                self.current_song = os.path.basename(file_path)
                await ctx.send(f"🎵 Lecture en cours : {self.current_song}")
                
        except Exception as e:
            await ctx.send(f"❌ Erreur lors de la lecture : {str(e)}")

    async def play_url(self, ctx, url):
        """Jouer un lien SoundCloud/YouTube"""
        if not await self.join_channel(ctx):
            return
        
        await ctx.send("🔄 Téléchargement en cours...")
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get('title', 'Titre inconnu')
                stream_url = info.get('url')
                
                if stream_url is None:
                    await ctx.send("❌ Impossible de récupérer le lien audio")
                    return
                
                if self.voice_client and self.voice_client.is_playing():
                    self.voice_client.stop()
                
                if FFMPEG_PATH:
                    source = discord.FFmpegPCMAudio(stream_url, executable=FFMPEG_PATH, **ffmpeg_options)
                else:
                    source = discord.FFmpegPCMAudio(stream_url, **ffmpeg_options)
                
                if self.voice_client:
                    self.voice_client.play(source, after=lambda e: print(f'Player error: {e}') if e else None)
                    self.current_song = title
                    await ctx.send(f"🎵 Lecture en cours : {title}")
                
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

music_bot = MusicBot()

@bot.event
async def on_ready():
    print(f'{bot.user} est connecté !')

@bot.command(name='play', aliases=['p'])
async def play(ctx, *, query):
    """Jouer un fichier MP3 ou un lien"""
    # Vérifier si c'est un URL
    if query.startswith('http'):
        await music_bot.play_url(ctx, query)
    else:
        # Traiter comme un fichier local
        if not query.endswith('.mp3'):
            query += '.mp3'
        
        # Chercher dans plusieurs endroits
        possible_paths = [
            os.path.join("music", query),  # ./music/fichier.mp3
            query,                         # fichier.mp3 (dossier courant)
            os.path.join(".", query)      # ./fichier.mp3
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
    """Arrêter la musique"""
    if music_bot.voice_client and music_bot.voice_client.is_playing():
        music_bot.voice_client.stop()
        await ctx.send("⏹️ Musique arrêtée")

@bot.command(name='pause')
async def pause(ctx):
    """Mettre en pause"""
    if music_bot.voice_client and music_bot.voice_client.is_playing():
        music_bot.voice_client.pause()
        await ctx.send("⏸️ Musique en pause")

@bot.command(name='resume')
async def resume(ctx):
    """Reprendre"""
    if music_bot.voice_client and music_bot.voice_client.is_paused():
        music_bot.voice_client.resume()
        await ctx.send("▶️ Musique reprise")

@bot.command(name='leave', aliases=['disconnect'])
async def leave(ctx):
    """Quitter le canal vocal"""
    if music_bot.voice_client:
        await music_bot.voice_client.disconnect()
        music_bot.voice_client = None
        await ctx.send("👋 Bot déconnecté")

@bot.command(name='current', aliases=['now'])
async def current(ctx):
    """Afficher la chanson actuelle"""
    if music_bot.current_song:
        await ctx.send(f"🎵 En cours : {music_bot.current_song}")
    else:
        await ctx.send("Aucune musique en cours")

@bot.command(name='list', aliases=['ls'])
async def list_music(ctx):
    """Lister les fichiers MP3 disponibles"""
    music_files = []
    
    # Chercher dans le dossier music
    if os.path.exists("music"):
        for file in os.listdir("music"):
            if file.endswith(('.mp3', '.wav', '.m4a', '.flac')):
                music_files.append(f"music/{file}")
    
    # Chercher dans le dossier courant
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
    """Forcer la lecture avec options simplifiées"""
    if not await music_bot.join_channel(ctx):
        return
    
    await ctx.send("🔄 Force download...")
    
    try:
        # Options ultra-simples
        simple_opts = {
            'format': 'worst[acodec!=none]/bestaudio/best',  # Prendre la PIRE qualité (plus compatible)
            'quiet': True,
            'no_warnings': True
        }
        
        with yt_dlp.YoutubeDL(simple_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            title = info.get('title', 'Titre inconnu')
            
            # Prendre tous les formats disponibles et choisir
            formats = info.get('formats', [])
            stream_url = None
            
            # Chercher un format audio spécifique
            for fmt in formats:
                if fmt.get('acodec') and fmt.get('acodec') != 'none':
                    stream_url = fmt.get('url')
                    print(f"Format choisi: {fmt.get('format_id')} - {fmt.get('acodec')} - {fmt.get('ext')}")
                    break
            
            if not stream_url:
                stream_url = info.get('url')  # Fallback
            
            if not stream_url:
                await ctx.send("❌ Aucun stream trouvé")
                return
            
            if music_bot.voice_client and music_bot.voice_client.is_playing():
                music_bot.voice_client.stop()
                await asyncio.sleep(1)
            
            # Options FFmpeg ultra-basiques
            basic_ffmpeg = {
                'options': '-vn'
            }
            
            try:
                if FFMPEG_PATH:
                    source = discord.FFmpegPCMAudio(stream_url, executable=FFMPEG_PATH, **basic_ffmpeg)
                else:
                    source = discord.FFmpegPCMAudio(stream_url, **basic_ffmpeg)
                
                if music_bot.voice_client:
                    music_bot.voice_client.play(source, after=lambda e: print(f'Basic play error: {e}') if e else print('Basic play OK'))
                    music_bot.current_song = title
                    await ctx.send(f"🔧 **Force basic** : {title}")
                    
            except Exception as ffmpeg_error:
                await ctx.send(f"❌ Erreur FFmpeg : {ffmpeg_error}")
    
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
            for i, fmt in enumerate(formats[:10]):  # Limite à 10
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
    """Debug un lien SoundCloud"""
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
        await ctx.send(f"❌ Erreur debug : {str(e)}")

@bot.command(name='volume')
async def volume(ctx, vol: int = None):
    """Changer le volume (0-100)"""
    if vol is None:
        await ctx.send("Usage: `!volume <0-100>`")
        return
    
    if vol < 0 or vol > 100:
        await ctx.send("Volume doit être entre 0 et 100")
        return
    
    # Convertir en décimal pour FFmpeg
    volume_float = vol / 100
    global ffmpeg_options
    ffmpeg_options['options'] = f'-vn -filter:a "volume={volume_float}"'
    await ctx.send(f"🔊 Volume réglé à {vol}%")

@bot.command(name='test_ffmpeg')
async def test_ffmpeg(ctx):
    """Tester si FFmpeg marche"""
    try:
        # Test simple de FFmpeg
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

@bot.command(name='help_music')
async def help_music(ctx):
    """Afficher l'aide"""
    help_text = """
🎵 **Commandes du bot musical** 🎵

`!play <fichier>` - Jouer un fichier MP3 local (sans .mp3)
`!play <url>` - Jouer depuis SoundCloud/YouTube
`!list` - Voir tous les fichiers disponibles
`!stop` - Arrêter la musique
`!pause` - Mettre en pause
`!resume` - Reprendre
`!current` - Chanson actuelle
`!leave` - Déconnecter le bot
`!test_ffmpeg` - Tester FFmpeg

**Exemples :**
`!play let` (pour let.mp3)
`!play https://soundcloud.com/...`
    """
    await ctx.send(help_text)

if __name__ == "__main__":
    # Remplace par ton token de bot Discord
    TOKEN = ""
    
    print("Démarrage du bot...")
    print("Assure-toi d'avoir installé les dépendances :")
    print("pip install discord.py yt-dlp PyNaCl")
    print("Et d'avoir FFmpeg installé sur ton système")
    
    bot.run(TOKEN)

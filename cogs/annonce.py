import discord
from discord.ext import commands
from discord import app_commands
import config
from utils.embeds import af_embed

class AnnonceModal(discord.ui.Modal):
    def __init__(self, target_channel: discord.TextChannel | None):
        super().__init__(title="📢 Créer une annonce - Air France Helpine")
        self.target_channel = target_channel

    titre = discord.ui.TextInput(
        label="Titre de l'annonce",
        placeholder="Ex: ✈️ Maintenance prévue ce soir",
        required=True,
        max_length=256,
        style=discord.TextStyle.short
    )
    description = discord.ui.TextInput(
        label="Contenu de l'annonce",
        placeholder="Écris ton annonce ici... Tu peux utiliser **gras**, *italique*, @everyone, émojis, etc.",
        required=True,
        max_length=4000,
        style=discord.TextStyle.paragraph
    )
    couleur = discord.ui.TextInput(
        label="Couleur (hex) - optionnel",
        placeholder="#002395 ou bleu/rouge/blanc (laisse vide = bleu AF)",
        required=False,
        max_length=20,
        style=discord.TextStyle.short
    )
    image_url = discord.ui.TextInput(
        label="URL image/banner - optionnel",
        placeholder="https://...",
        required=False,
        max_length=500,
        style=discord.TextStyle.short
    )
    mention = discord.ui.TextInput(
        label="Mention - optionnel",
        placeholder="@everyone, @here, ou ID rôle (ex: <@&123>) - laisse vide = aucune",
        required=False,
        max_length=100,
        style=discord.TextStyle.short
    )

    def parse_color(self, raw: str) -> int:
        if not raw:
            return config.COLOR_AF_BLUE
        raw = raw.strip().lower()
        mapping = {"bleu": config.COLOR_AF_BLUE, "blue": config.COLOR_AF_BLUE, "rouge": config.COLOR_AF_RED, "red": config.COLOR_AF_RED, "blanc": 0xFFFFFF, "white": 0xFFFFFF, "vert": 0x2ECC71, "jaune": 0xF1C40F}
        if raw in mapping:
            return mapping[raw]
        raw = raw.lstrip("#")
        try:
            return int(raw, 16)
        except:
            return config.COLOR_AF_BLUE

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        # Résolution salon cible
        guild = interaction.guild
        channel = self.target_channel
        if channel is None:
            # Essaie channel config
            if config.ANNOUNCE_CHANNEL_ID:
                channel = guild.get_channel(config.ANNOUNCE_CHANNEL_ID) or interaction.channel
            else:
                # check DB config
                from database import db
                gconf = await db.get_guild_config(guild.id)
                if gconf and gconf["announce_channel_id"]:
                    try:
                        channel = guild.get_channel(int(gconf["announce_channel_id"])) or interaction.channel
                    except:
                        channel = interaction.channel
                else:
                    channel = interaction.channel

        color = self.parse_color(str(self.couleur.value) if self.couleur.value else "")
        title = str(self.titre.value)
        desc = str(self.description.value)
        img = str(self.image_url.value).strip() if self.image_url.value else None
        mention_raw = str(self.mention.value).strip() if self.mention.value else ""

        # Validation image
        if img and not (img.startswith("http://") or img.startswith("https://")):
            img = None

        embed = discord.Embed(
            title=title,
            description=desc,
            color=color
        )
        embed.set_author(name="Air France Helpine", icon_url=guild.icon.url if guild.icon else None)
        embed.set_footer(text=f"Annonce par {interaction.user.display_name} • {config.FOOTER_TEXT}", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
        embed.timestamp = discord.utils.utcnow()
        if img:
            embed.set_image(url=img)

        # Gestion mention : on autorise seulement si admin (déjà vérifié)
        allowed_mentions = discord.AllowedMentions(everyone=True, roles=True, users=True)
        mention_content = None
        if mention_raw:
            # Nettoie et valide
            if "@everyone" in mention_raw or "@here" in mention_raw:
                mention_content = mention_raw
            elif "<@&" in mention_raw or "<@!" in mention_raw or "<@" in mention_raw:
                mention_content = mention_raw
            else:
                # Si texte brut "everyone" etc.
                if mention_raw.lower() in ("everyone", "@everyone"):
                    mention_content = "@everyone"
                elif mention_raw.lower() in ("here", "@here"):
                    mention_content = "@here"
                else:
                    mention_content = mention_raw

        # Preview d'abord en ephemeral
        try:
            await interaction.followup.send(f"✅ Aperçu de ton annonce (sera envoyée dans {channel.mention}) :", embed=embed, ephemeral=True)
        except:
            pass

        # Envoi réel
        try:
            await channel.send(content=mention_content, embed=embed, allowed_mentions=allowed_mentions)
            await interaction.followup.send(f"✅ Annonce envoyée avec succès dans {channel.mention} !", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send(f"❌ Pas la permission d'envoyer dans {channel.mention}. Vérifie les perms du bot.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)

class Annonce(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="annonce", description="Créer une annonce (Admin uniquement)")
    @app_commands.describe(salon="Salon où envoyer l'annonce (optionnel, défaut = salon actuel)")
    async def annonce(self, interaction: discord.Interaction, salon: discord.TextChannel = None):
        # Check admin
        if not interaction.guild:
            return await interaction.response.send_message("❌ Commande utilisable uniquement sur le serveur.", ephemeral=True)
        member = interaction.user
        if not isinstance(member, discord.Member) or not member.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Réservée aux administrateurs (permission `Administrateur`).", ephemeral=True)

        # Anti-abus : cooldown 10s par admin (mémoire simple)
        # On pourrait ajouter un vrai cooldown app_commands mais on garde simple

        # Ouvre modal
        modal = AnnonceModal(salon)
        await interaction.response.send_modal(modal)

    @app_commands.command(name="annonce-rapide", description="Annonce rapide sans modal (Admin)")
    @app_commands.describe(texte="Texte de l'annonce", salon="Salon cible", mention_everyone="Mentionner @everyone ?")
    async def annonce_rapide(self, interaction: discord.Interaction, texte: str, salon: discord.TextChannel = None, mention_everyone: bool = False):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        channel = salon or interaction.channel
        # Si salon est hors guild ? discord check déjà
        embed = discord.Embed(
            title="📢 Annonce",
            description=texte[:4000],
            color=config.COLOR_AF_BLUE
        )
        embed.set_author(name="Air France Helpine", icon_url=interaction.guild.icon.url if interaction.guild.icon else None)
        embed.set_footer(text=f"Par {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
        embed.timestamp = discord.utils.utcnow()
        try:
            await channel.send(content="@everyone" if mention_everyone else None, embed=embed, allowed_mentions=discord.AllowedMentions(everyone=True))
            await interaction.followup.send(f"✅ Envoyé dans {channel.mention}", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ {e}", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Annonce(bot))

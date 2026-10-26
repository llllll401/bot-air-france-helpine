import discord
from discord.ext import commands
from discord import app_commands
import config
from database import db
from utils.embeds import af_embed

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup-tickets", description="Configurer le système de tickets (Admin)")
    @app_commands.describe(categorie="Catégorie des tickets", role_staff="Rôle staff", salon_logs="Salon logs", salon_annonces="Salon annonces")
    async def setup_tickets(self, interaction: discord.Interaction,
                            categorie: discord.CategoryChannel = None,
                            role_staff: discord.Role = None,
                            salon_logs: discord.TextChannel = None,
                            salon_annonces: discord.TextChannel = None):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        updates = {}
        if categorie:
            updates["category_id"] = categorie.id
        if role_staff:
            updates["staff_role_id"] = role_staff.id
        if salon_logs:
            updates["log_channel_id"] = salon_logs.id
        if salon_annonces:
            updates["announce_channel_id"] = salon_annonces.id
        if not updates:
            gconf = await db.get_guild_config(interaction.guild.id)
            embed = af_embed(
                title="⚙️ Config actuelle",
                description=(
                    f"**Serveur :** {interaction.guild.name} (`{interaction.guild.id}`)\n"
                    f"**Catégorie :** <#{gconf['category_id']}> (`{gconf['category_id']}`)\n"
                    f"**Rôle staff :** <@&{gconf['staff_role_id']}> (`{gconf['staff_role_id']}`)\n"
                    f"**Logs :** {'<#' + gconf['log_channel_id'] + '>' if gconf['log_channel_id'] else 'Non défini'}\n"
                    f"**Annonces :** {'<#' + gconf['announce_channel_id'] + '>' if gconf['announce_channel_id'] else 'Non défini'}"
                )
            )
            return await interaction.followup.send(embed=embed, ephemeral=True)
        await db.update_guild_config(interaction.guild.id, **updates)
        await interaction.followup.send(embed=af_embed(description="✅ Configuration mise à jour ! Redémarrage non nécessaire.", color=config.COLOR_SUCCESS), ephemeral=True)

    @app_commands.command(name="sync", description="Resync les slash commands (Admin)")
    async def sync_cmd(self, interaction: discord.Interaction):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        synced = await self.bot.tree.sync()
        # sync guild spécifique pour instantanéité
        try:
            await self.bot.tree.sync(guild=interaction.guild)
        except:
            pass
        await interaction.followup.send(f"✅ {len(synced)} commandes sync globalement.", ephemeral=True)

    @app_commands.command(name="bot-info", description="Infos du bot")
    async def infos_bot(self, interaction: discord.Interaction):
        embed = af_embed(
            title="✈️ Air France Helpine - Bot Info",
            description=(
                f"**Serveur :** {interaction.guild.name if interaction.guild else 'DM'}\n"
                f"**Latence :** {round(self.bot.latency*1000)} ms\n"
                f"**Guilds :** {len(self.bot.guilds)}\n"
                f"**Tickets ouverts :** {(await db.get_stats())['open']}\n"
                f"**DB :** `{config.DB_PATH}` (WAL, gzip transcripts)\n"
                f"**Catégorie :** `{config.TICKET_CATEGORY_ID}`\n"
                f"**Staff rôle :** `{config.STAFF_ROLE_ID}`"
            )
        )
        embed.set_thumbnail(url=self.bot.user.display_avatar.url if self.bot.user.display_avatar else None)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="purge-transcripts", description="Purge les vieux transcripts (Admin)")
    @app_commands.describe(jours="Supprimer transcripts plus vieux que X jours (défaut 30)")
    async def purge_transcripts(self, interaction: discord.Interaction, jours: int = 30):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        # Implémentation simple : liste fichiers et supprime
        import os, time
        from pathlib import Path
        dir_path = Path(config.TRANSCRIPT_DIR)
        count = 0
        freed = 0
        cutoff = time.time() - jours * 86400
        for f in dir_path.glob("*.*"):
            try:
                if f.stat().st_mtime < cutoff:
                    freed += f.stat().st_size
                    f.unlink()
                    count += 1
            except:
                pass
        await interaction.followup.send(f"✅ {count} transcripts supprimés ({freed/1024/1024:.2f} MB libérés).", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))

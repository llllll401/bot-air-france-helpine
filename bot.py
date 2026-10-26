import asyncio
import logging
import sys
import discord
from discord.ext import commands
import config
from database import db

# --- Logging ---
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
# Réduit bruit discord
logging.getLogger("discord").setLevel(logging.WARNING)
log = logging.getLogger("airfrance-bot")

# --- Intents ---
intents = discord.Intents.default()
intents.message_content = True  # Privilégié - à activer sur dev portal
intents.members = True
intents.guilds = True
intents.dm_messages = True
intents.guild_messages = True

class HelpineBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",  # fallback préfix, mais tout est en slash + MP
            intents=intents,
            help_command=None,
            activity=discord.Activity(type=discord.ActivityType.watching, name=config.BOT_ACTIVITY),
            allowed_mentions=discord.AllowedMentions(everyone=False, roles=True, users=True, replied_user=False)
        )
        self.db = db

    async def setup_hook(self):
        log.info(f"Config source : {config.log_config_source()} | Guild={config.GUILD_ID} Cat={config.TICKET_CATEGORY_ID} Staff={config.STAFF_ROLE_ID}")
        log.info("Initialisation DB...")
        await self.db.init()
        log.info("Chargement cogs...")
        await self.load_extension("cogs.tickets")
        await self.load_extension("cogs.annonce")
        await self.load_extension("cogs.admin")
        log.info("Cogs chargés.")

        # Views persistantes (survivent au redémarrage)
        from cogs.tickets import TicketControlView
        self.add_view(TicketControlView())
        log.info("Views persistantes enregistrées.")

        # Sync commands - global + guild pour instantanéité
        # On sync guild principale immédiatement
        try:
            guild = discord.Object(id=config.GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            log.info(f"Slash sync guild {config.GUILD_ID}: {len(synced)} cmds")
        except Exception as e:
            log.warning(f"Sync guild échoué (normal si guild non en cache) : {e}")
            try:
                synced = await self.tree.sync()
                log.info(f"Sync global: {len(synced)} cmds")
            except Exception as e2:
                log.error(f"Sync global échoué: {e2}")

    async def on_ready(self):
        log.info(f"✅ Connecté en tant que {self.user} ({self.user.id})")
        log.info(f"Serveurs: {len(self.guilds)} - {[f'{g.name} ({g.id})' for g in self.guilds]}")
        # Vérif catégorie existe
        guild = self.get_guild(config.GUILD_ID)
        if guild:
            cat = guild.get_channel(config.TICKET_CATEGORY_ID)
            if cat:
                log.info(f"Catégorie tickets OK: {cat.name} ({cat.id})")
            else:
                log.warning(f"Catégorie {config.TICKET_CATEGORY_ID} introuvable sur {guild.name} - vérifie l'ID")
            role = guild.get_role(config.STAFF_ROLE_ID)
            if role:
                log.info(f"Rôle staff OK: {role.name} ({role.id})")
            else:
                log.warning(f"Rôle staff {config.STAFF_ROLE_ID} introuvable")

        # Restaure tickets ouverts
        try:
            open_tickets = await self.db.get_all_open_tickets()
            log.info(f"Tickets ouverts en DB: {len(open_tickets)}")
            # Vérif que les salons existent encore
            for t in open_tickets:
                ch = self.get_channel(int(t["channel_id"]))
                if not ch:
                    # essaie fetch
                    try:
                        ch = await self.fetch_channel(int(t["channel_id"]))
                    except:
                        log.warning(f"Salon ticket {t['channel_id']} introuvable - utilisateur {t['user_id']}")
        except Exception as e:
            log.error(f"Restauration tickets: {e}")

        log.info("Bot prêt - en attente de MPs ✈️")

    async def on_error(self, event, *args, **kwargs):
        log.exception(f"Erreur event {event}", exc_info=sys.exc_info())

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        # Gestion erreurs slash propre
        if isinstance(error, discord.app_commands.CheckFailure):
            try:
                if interaction.response.is_done():
                    await interaction.followup.send("❌ Tu n'as pas la permission.", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ Tu n'as pas la permission.", ephemeral=True)
            except:
                pass
            return
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            try:
                msg = f"⏳ Cooldown : réessaie dans {error.retry_after:.1f}s"
                if interaction.response.is_done():
                    await interaction.followup.send(msg, ephemeral=True)
                else:
                    await interaction.response.send_message(msg, ephemeral=True)
            except:
                pass
            return
        log.error(f"App command error: {error}", exc_info=error)
        try:
            if interaction.response.is_done():
                await interaction.followup.send(f"❌ Erreur : {error}", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ Erreur : {error}", ephemeral=True)
        except:
            pass

bot = HelpineBot()

# --- Lancement ---
async def main():
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "ton_token_ici":
        log.error("DISCORD_TOKEN manquant ! Mets-le dans config.json")
        sys.exit(1)
    async with bot:
        await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Arrêt demandé")

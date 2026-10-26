import discord
from discord.ext import commands, tasks
from discord import app_commands
import asyncio
import time
import re
import io
import json
import config
from database import db
from utils.embeds import af_embed, ticket_open_embed, dm_welcome_embed, dm_already_open_embed, ticket_closed_embed
from utils.transcript import save_transcript, get_transcript_size
import gzip

# --- Cooldown en mémoire (optimisé) ---
_cooldowns: dict[int, float] = {}

# --- Views persistantes ---

class StaffReplyModal(discord.ui.Modal, title="Répondre au ticket"):
    reponse = discord.ui.TextInput(
        label="Ta réponse (sera envoyée en MP)",
        style=discord.TextStyle.paragraph,
        placeholder="Écris ta réponse ici...",
        required=True,
        max_length=2000
    )

    def __init__(self, ticket_channel_id: int):
        super().__init__()
        self.ticket_channel_id = ticket_channel_id

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        ticket = await db.get_ticket_by_channel(self.ticket_channel_id)
        if not ticket:
            return await interaction.followup.send("❌ Ticket introuvable (fermé ?)", ephemeral=True)

        guild = interaction.client.get_guild(int(ticket["guild_id"]))
        user = await interaction.client.fetch_user(int(ticket["user_id"]))
        content = str(self.reponse.value)

        # Envoi DM
        try:
            embed = af_embed(
                description=content,
                color=config.COLOR_AF_BLUE
            )
            embed.set_author(name=f"Réponse du staff • {interaction.user.display_name}", icon_url=interaction.user.display_avatar.url if interaction.user.display_avatar else None)
            embed.set_footer(text=f"Air France Helpine • Réponds ici en MP pour continuer")
            await user.send(embed=embed)
            # Log dans le salon
            await interaction.channel.send(f"✅ **{interaction.user.mention} → {user.mention}** : {content[:1500]}")
            # DB log
            await db.log_message(int(ticket["id"]), interaction.user.id, str(interaction.user), content, is_bot=False)
            await interaction.followup.send("✅ Réponse envoyée en MP !", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ Impossible d'envoyer le MP (utilisateur a bloqué le bot ou MP fermés).", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Erreur : {e}", ephemeral=True)

class TicketControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Répondre", style=discord.ButtonStyle.primary, emoji="✉️", custom_id="ticket:reply")
    async def reply_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Ticket non trouvé en DB.", ephemeral=True)
        await interaction.response.send_modal(StaffReplyModal(interaction.channel.id))

    @discord.ui.button(label="Claim", style=discord.ButtonStyle.secondary, emoji="👤", custom_id="ticket:claim")
    async def claim_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Ticket introuvable.", ephemeral=True)
        if ticket["claimed_by"]:
            try:
                claim_user = await interaction.client.fetch_user(int(ticket["claimed_by"]))
                if int(ticket["claimed_by"]) == interaction.user.id:
                    return await interaction.response.send_message("ℹ️ Tu as déjà claim ce ticket.", ephemeral=True)
                return await interaction.response.send_message(f"ℹ️ Déjà claim par {claim_user} (<@{ticket['claimed_by']}>)", ephemeral=True)
            except:
                pass
        await db.claim_ticket(interaction.channel.id, interaction.user.id)
        embed = af_embed(description=f"✅ Ticket claim par {interaction.user.mention}", color=config.COLOR_SUCCESS)
        await interaction.response.send_message(embed=embed)

    @discord.ui.button(label="Transcript", style=discord.ButtonStyle.secondary, emoji="📋", custom_id="ticket:transcript")
    async def transcript_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.followup.send("❌ Ticket introuvable.", ephemeral=True)
        msgs = await db.get_ticket_messages(int(ticket["id"]))
        if not msgs:
            # fallback : fetch historique discord (si DB vide, optimisation : on peut fetch)
            try:
                history = []
                async for m in interaction.channel.history(limit=200, oldest_first=True):
                    if m.author.bot and m.embeds and "Nouveau ticket MP" in (m.embeds[0].title or ""):
                        continue
                    history.append({"author_name": str(m.author), "author_id": str(m.author.id), "content": m.content, "created_at": int(m.created_at.timestamp()), "is_bot": 1 if m.author.bot else 0, "attachments": "|".join([a.url for a in m.attachments])})
                msgs = history
            except:
                msgs = []

        user = await interaction.client.fetch_user(int(ticket["user_id"]))
        path = await save_transcript(
            interaction.channel.name, interaction.channel.id, str(user), int(ticket["user_id"]),
            int(ticket["created_at"]), int(time.time()), msgs
        )
        size_kb = get_transcript_size(path) / 1024
        await interaction.followup.send(
            f"✅ Transcript généré : `{path}` ({size_kb:.1f} KB, compressé gzip)\nEnvoi du fichier...",
            ephemeral=True
        )
        try:
            # Envoi du fichier (décompressé à la volée si gz)
            if path.endswith(".gz"):
                with gzip.open(path, "rb") as f:
                    data = f.read()
                file = discord.File(io.BytesIO(data), filename=interaction.channel.name + ".html")
            else:
                file = discord.File(path)
            await interaction.followup.send(file=file, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Fichier sauvegardé mais envoi échoué : {e}", ephemeral=True)

    @discord.ui.button(label="Fermer", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="ticket:close")
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Es-tu sûr de vouloir fermer ce ticket ?", view=ConfirmCloseView(), ephemeral=True)

class ConfirmCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Oui, fermer", style=discord.ButtonStyle.danger, emoji="🔒")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        cog = interaction.client.get_cog("Tickets")
        if cog:
            await cog.close_ticket_flow(interaction.channel, interaction.user, reason=f"Fermé par {interaction.user} via bouton")
            # disable view
            for child in self.children:
                child.disabled = True
            try:
                await interaction.edit_original_response(view=self)
            except:
                pass

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content="Annulé.", view=self)

class Tickets(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.inactivity_check.start()

    def cog_unload(self):
        self.inactivity_check.cancel()

    @tasks.loop(hours=6)
    async def inactivity_check(self):
        # Auto-close inactivité (optionnel) - optimisé : ne fetch pas tout
        if config.AUTO_CLOSE_DAYS <= 0:
            return
        try:
            tickets = await db.get_all_open_tickets()
            now = int(time.time())
            for t in tickets:
                if now - int(t["created_at"]) > config.AUTO_CLOSE_DAYS * 86400:
                    # Vérif dernier message ? Pour l'instant on skip auto-close si pas d'activité DB
                    # On log juste
                    pass
        except Exception as e:
            print(f"[inactivity_check] {e}")

    @inactivity_check.before_loop
    async def before_inactivity(self):
        await self.bot.wait_until_ready()

    async def create_ticket_channel(self, user: discord.User, guild: discord.Guild, first_message: discord.Message) -> discord.TextChannel:
        # Récup config DB (permet override)
        gconf = await db.get_guild_config(guild.id)
        category_id = int(gconf["category_id"]) if gconf and gconf["category_id"] else config.TICKET_CATEGORY_ID
        staff_role_id = int(gconf["staff_role_id"]) if gconf and gconf["staff_role_id"] else config.STAFF_ROLE_ID

        category = guild.get_channel(category_id)
        # fallback si catégorie introuvable
        if category is None or not isinstance(category, discord.CategoryChannel):
            # essaie fetch
            try:
                category = await guild.fetch_channel(category_id)
            except:
                category = None

        staff_role = guild.get_role(staff_role_id)
        # nom optimisé : ticket-nom-xxxx (max 100 chars)
        safe_name = re.sub(r'[^a-z0-9_-]', '', user.name.lower().replace(" ", "-"))[:12] or "user"
        channel_name = f"ticket-{safe_name}-{str(user.id)[-4:]}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True, manage_messages=True),
        }
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)

        # Création salon
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Ticket MP de {user} ({user.id}) • ouvert {discord.utils.format_dt(discord.utils.utcnow(), style='F')}",
            reason=f"Ticket MP ouvert par {user} ({user.id})"
        )

        # DB
        ticket_id = await db.create_ticket(user.id, channel.id, guild.id)
        # Log premier message
        attachments = "|".join([a.url for a in first_message.attachments]) if first_message.attachments else None
        await db.log_message(ticket_id, user.id, str(user), first_message.content, attachments, is_bot=False)

        # Embeds
        embed = ticket_open_embed(user, guild.name)
        # Ajoute contenu initial
        if first_message.content:
            embed.add_field(name="💬 Premier message", value=first_message.content[:1024], inline=False)
        if first_message.attachments:
            embed.add_field(name="📎 Pièces jointes", value="\n".join([f"[{a.filename}]({a.url})" for a in first_message.attachments])[:1024], inline=False)

        view = TicketControlView()
        await channel.send(
            content=f"{staff_role.mention if staff_role else ''} Nouveau ticket !",
            embed=embed,
            view=view
        )
        # Ping propre : message séparé pour notif staff sans embed
        if first_message.content and len(first_message.content) > 0:
            # Transférer le message tel quel dans le salon (avec fichiers)
            files = []
            for att in first_message.attachments:
                try:
                    # On transfère via URL embed plutôt que download pour optimiser bande passante
                    # Mais si petit fichier (<8MB) on peut re-upload pour persistance
                    if att.size < 8 * 1024 * 1024:
                        b = await att.read()
                        files.append(discord.File(io.BytesIO(b), filename=att.filename))
                except:
                    pass
            relay_embed = af_embed(
                description=first_message.content[:4000] or "*Pièce jointe seule*",
                color=0x2B2D31
            )
            relay_embed.set_author(name=str(user), icon_url=user.display_avatar.url if user.display_avatar else None)
            relay_embed.set_footer(text=f"MP → Ticket • {user.id}")
            if files:
                await channel.send(embed=relay_embed, files=files)
            else:
                await channel.send(embed=relay_embed)

        return channel

    async def close_ticket_flow(self, channel: discord.TextChannel, closer: discord.User | discord.Member, reason: str = None, notify_user: bool = True):
        ticket = await db.get_ticket_by_channel(channel.id)
        if not ticket:
            try:
                await channel.send(embed=af_embed(description="❌ Ticket non trouvé en DB, suppression manuelle.", color=config.COLOR_ERROR))
            except:
                pass
            return

        # Génération transcript
        msgs = await db.get_ticket_messages(int(ticket["id"]))
        # Fallback : si peu de messages en DB (ex: relais non loggé), on complète via historique
        if len(msgs) < 2:
            try:
                hist = []
                async for m in channel.history(limit=500, oldest_first=True):
                    # ignore bot embeds de contrôle
                    if m.author.id == self.bot.user.id and m.embeds and m.embeds[0].title and "Nouveau ticket" in m.embeds[0].title:
                        continue
                    hist.append({
                        "author_name": str(m.author),
                        "author_id": str(m.author.id),
                        "content": m.content or (m.embeds[0].description if m.embeds else ""),
                        "created_at": int(m.created_at.timestamp()),
                        "is_bot": 1 if m.author.bot else 0,
                        "attachments": "|".join([a.url for a in m.attachments])
                    })
                if len(hist) > len(msgs):
                    msgs = hist
            except Exception as e:
                print(f"[transcript fallback] {e}")

        user_id = int(ticket["user_id"])
        try:
            user = await self.bot.fetch_user(user_id)
            user_tag = str(user)
        except:
            user = None
            user_tag = f"User {user_id}"

        path = await save_transcript(
            channel.name, channel.id, user_tag, user_id,
            int(ticket["created_at"]), int(time.time()), msgs
        )
        # DB update
        await db.close_ticket(channel.id, reason)
        await db.set_transcript_path(channel.id, path)

        # Embed de fermeture dans le salon
        try:
            await channel.send(embed=ticket_closed_embed(reason))
        except:
            pass

        # Log channel
        gconf = await db.get_guild_config(int(ticket["guild_id"]))
        log_ch_id = None
        if gconf and gconf["log_channel_id"]:
            try:
                log_ch_id = int(gconf["log_channel_id"])
            except:
                pass
        if not log_ch_id:
            log_ch_id = config.LOG_CHANNEL_ID

        if log_ch_id:
            try:
                log_ch = self.bot.get_channel(log_ch_id) or await self.bot.fetch_channel(log_ch_id)
                log_embed = af_embed(
                    title="🔒 Ticket fermé",
                    description=f"**Salon :** #{channel.name} (`{channel.id}`)\n**Utilisateur :** <@{user_id}> (`{user_id}`)\n**Fermé par :** {closer} (`{closer.id}`)\n**Raison :** {reason or 'Aucune'}\n**Transcript :** `{path}` ({get_transcript_size(path)/1024:.1f} KB)",
                    color=config.COLOR_ERROR
                )
                await log_ch.send(embed=log_embed)
                # Envoi fichier si petit
                if get_transcript_size(path) < 8 * 1024 * 1024:
                    try:
                        if path.endswith(".gz"):
                            with gzip.open(path, "rb") as f:
                                data = f.read()
                            file = discord.File(io.BytesIO(data), filename=channel.name + ".html")
                        else:
                            file = discord.File(path)
                        await log_ch.send(file=file)
                    except Exception as e:
                        print(f"[log transcript file] {e}")
            except Exception as e:
                print(f"[log channel] {e}")

        # Notif DM user
        if notify_user and user:
            try:
                embed = af_embed(
                    title="🔒 Ticket fermé",
                    description=f"Ton ticket `{channel.name}` a été fermé.\n**Raison :** {reason or 'Aucune raison donnée'}\n\nTu peux rouvrir un nouveau ticket en renvoyant un MP au bot.",
                    color=config.COLOR_ERROR
                )
                await user.send(embed=embed)
            except:
                pass

        # Suppression différée (10s) - permet de voir le transcript
        await asyncio.sleep(10)
        try:
            await channel.delete(reason=f"Ticket fermé par {closer} - {reason}")
        except discord.NotFound:
            pass
        except discord.Forbidden:
            # Fallback : archive (renomme + retire permissions)
            try:
                await channel.edit(name=f"ferme-{channel.name}"[:100], overwrites={
                    channel.guild.default_role: discord.PermissionOverwrite(view_channel=False)
                })
                await channel.send("⚠️ Pas la permission de supprimer, salon archivé.")
            except:
                pass

    # --- Events ---

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        # --- DM → Ticket ---
        if message.guild is None:
            # C'est un MP
            # Anti-ban check
            if await db.is_banned(message.author.id):
                try:
                    await message.author.send(embed=af_embed(description="🚫 Tu es banni du système de tickets. Contacte un administrateur sur le serveur.", color=config.COLOR_ERROR))
                except:
                    pass
                return

            # Commande textuelle !fermer en DM
            if message.content.strip().lower() in ("!fermer", "!close", "fermer", "close"):
                ticket = await db.get_open_ticket_by_user(message.author.id)
                if ticket:
                    guild = self.bot.get_guild(int(ticket["guild_id"])) or self.bot.get_guild(config.GUILD_ID)
                    if guild:
                        ch = guild.get_channel(int(ticket["channel_id"]))
                        if ch:
                            await message.author.send(embed=af_embed(description="🔒 Fermeture de ton ticket en cours...", color=config.COLOR_WARNING))
                            await self.close_ticket_flow(ch, message.author, reason="Fermé par l'utilisateur en MP", notify_user=False)
                            return
                await message.author.send(embed=af_embed(description="ℹ️ Tu n'as aucun ticket ouvert.", color=config.COLOR_WARNING))
                return

            # Cooldown
            now = time.time()
            last = _cooldowns.get(message.author.id, 0)
            if now - last < 3:  # anti-spam 3s
                return
            _cooldowns[message.author.id] = now

            # Vérifie ticket existant
            existing = await db.get_open_ticket_by_user(message.author.id)
            guild = self.bot.get_guild(config.GUILD_ID)
            # Fallback : si bot sur un seul serveur, prend le premier guild
            if guild is None:
                if len(self.bot.guilds) == 1:
                    guild = self.bot.guilds[0]
                elif self.bot.guilds:
                    # cherche par ID
                    for g in self.bot.guilds:
                        if g.id == config.GUILD_ID:
                            guild = g
                            break
                    if not guild:
                        guild = self.bot.guilds[0]

            if not guild:
                try:
                    await message.author.send("❌ Bot non configuré sur un serveur. Contacte un admin.")
                except:
                    pass
                return

            if existing:
                # Transférer message au salon existant
                ch = guild.get_channel(int(existing["channel_id"]))
                if ch:
                    # Cooldown création ticket (évite spam création)
                    # Mais ici on est en relay, on autorise
                    await self.relay_dm_to_channel(message, ch, existing)
                    # Ack user
                    try:
                        await message.add_reaction("✅")
                    except:
                        await message.author.send(embed=af_embed(description="✅ Message transféré au staff.", color=config.COLOR_SUCCESS))
                    return
                else:
                    # Salon supprimé mais ticket encore open => on le ferme et on recrée
                    await db.close_ticket(int(existing["channel_id"]), reason="Salon supprimé, recréation")
                    # continue vers création

            # Vérifie cooldown création ticket
            # On stocke dernier ticket fermé ? Simple : vérifie si dernier ticket fermé il y a < TICKET_COOLDOWN_SECONDS
            # Pour l'instant on check via ticket existant déjà fait, sinon on autorise création
            # Optionnel : anti-spam création rapide
            # On peut stocker en mémoire
            ticket_cooldown_key = f"create_{message.author.id}"
            if ticket_cooldown_key in _cooldowns:
                if now - _cooldowns[ticket_cooldown_key] < config.TICKET_COOLDOWN_SECONDS:
                    remaining = int(config.TICKET_COOLDOWN_SECONDS - (now - _cooldowns[ticket_cooldown_key]))
                    try:
                        await message.author.send(embed=af_embed(description=f"⏳ Attends {remaining}s avant de rouvrir un ticket.", color=config.COLOR_WARNING))
                    except:
                        pass
                    return

            # Création nouveau ticket
            try:
                channel = await self.create_ticket_channel(message.author, guild, message)
                _cooldowns[ticket_cooldown_key] = now
                # DM confirmation
                try:
                    await message.author.send(embed=dm_welcome_embed())
                    await message.add_reaction("🎫")
                except:
                    pass
            except discord.Forbidden:
                try:
                    await message.author.send("❌ Le bot n'a pas les permissions pour créer un salon (Gérer les salons + Voir la catégorie). Contacte un admin.")
                except:
                    pass
            except Exception as e:
                print(f"[create_ticket] {e}")
                try:
                    await message.author.send(f"❌ Erreur lors de la création du ticket : {e}")
                except:
                    pass
            return

        # --- Salon ticket → DM ---
        else:
            # Message dans un salon de ticket ? On vérifie DB
            ticket = await db.get_ticket_by_channel(message.channel.id)
            if not ticket:
                return
            if ticket["status"] != "open":
                return
            # Ignore messages du bot déjà gérés
            # Si staff/admin envoie message, on relaie en DM
            # On ignore les commandes slash (interaction)
            # Permissions : staff ou admin
            member = message.author
            if isinstance(member, discord.Member):
                gconf = await db.get_guild_config(message.guild.id)
                staff_role_id = int(gconf["staff_role_id"]) if gconf and gconf["staff_role_id"] else config.STAFF_ROLE_ID
                is_staff = member.guild_permissions.administrator or any(r.id == staff_role_id for r in member.roles)
                # Option : autoriser aussi le bot à ne pas relay ses propres embeds de contrôle
                if not is_staff:
                    # Si ce n'est pas staff, on ne relay pas (évite boucle si user dans serveur)
                    # Mais on peut quand même log
                    return

            # Relay
            try:
                user = await self.bot.fetch_user(int(ticket["user_id"]))
            except:
                return

            # Log DB
            attachments_str = "|".join([a.url for a in message.attachments]) if message.attachments else None
            await db.log_message(int(ticket["id"]), message.author.id, str(message.author), message.content, attachments_str, is_bot=False)

            # Construit contenu à envoyer en DM
            content = message.content or ""
            # Nettoie mentions @everyone pour DM
            content = content.replace("@everyone", "@\u200beveryone").replace("@here", "@\u200bhere")

            embed = af_embed(description=content[:4000] if content else None, color=config.COLOR_AF_BLUE)
            embed.set_author(name=f"{message.author.display_name} (Staff)", icon_url=message.author.display_avatar.url if message.author.display_avatar else None)
            embed.set_footer(text=f"Air France Helpine • Réponds ici pour répondre au staff")
            # Ajoute référence salon pour debug staff
            if message.attachments:
                embed.add_field(name="📎 Fichiers", value="\n".join([f"[{a.filename}]({a.url})" for a in message.attachments])[:1024], inline=False)

            files = []
            for att in message.attachments:
                try:
                    if att.size < 8 * 1024 * 1024:
                        b = await att.read()
                        files.append(discord.File(io.BytesIO(b), filename=att.filename))
                except:
                    pass

            try:
                if files:
                    await user.send(embed=embed, files=files)
                elif content or message.attachments:
                    await user.send(embed=embed)
                # Ack dans salon
                try:
                    await message.add_reaction("✅")
                except:
                    pass
            except discord.Forbidden:
                await message.channel.send(f"⚠️ {message.author.mention} Impossible d'envoyer le DM à l'utilisateur (MP fermés/bloqués).", delete_after=10)
            except Exception as e:
                print(f"[relay channel->DM] {e}")

    async def relay_dm_to_channel(self, dm_message: discord.Message, channel: discord.TextChannel, ticket: dict):
        # Log DB
        attachments_str = "|".join([a.url for a in dm_message.attachments]) if dm_message.attachments else None
        await db.log_message(int(ticket["id"]), dm_message.author.id, str(dm_message.author), dm_message.content, attachments_str, is_bot=False)

        # Embed relay
        content = dm_message.content or ""
        embed = af_embed(description=content[:4000] if content else "*Pièce jointe seule*", color=0x2B2D31)
        embed.set_author(name=str(dm_message.author), icon_url=dm_message.author.display_avatar.url if dm_message.author.display_avatar else None)
        embed.set_footer(text=f"MP → Ticket • {dm_message.author.id} • {discord.utils.format_dt(discord.utils.utcnow(), style='T')}")

        files = []
        for att in dm_message.attachments:
            try:
                if att.size < 8 * 1024 * 1024:
                    b = await att.read()
                    files.append(discord.File(io.BytesIO(b), filename=att.filename))
                else:
                    embed.add_field(name="📎 Fichier trop lourd", value=f"[{att.filename}]({att.url}) ({att.size/1024/1024:.1f} MB)", inline=False)
            except Exception as e:
                embed.add_field(name="📎 Fichier", value=f"[{att.filename}]({att.url})", inline=False)

        # Gestion stickers / embeds DM ?
        try:
            if files:
                await channel.send(embed=embed, files=files)
            else:
                # Si pas de contenu mais attachments URL déjà dans embed, on envoie
                await channel.send(embed=embed)
        except discord.Forbidden:
            print("[relay_dm_to_channel] forbidden")
        except Exception as e:
            print(f"[relay_dm_to_channel] {e}")

    # --- Slash commands ticket management ---

    @app_commands.command(name="fermer", description="Fermer ce ticket")
    @app_commands.describe(raison="Raison de fermeture")
    async def fermer(self, interaction: discord.Interaction, raison: str = None):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Utilise cette commande dans un salon ticket du serveur.", ephemeral=True)
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Ce salon n'est pas un ticket.", ephemeral=True)
        # perm check
        member = interaction.user
        if isinstance(member, discord.Member):
            if not (member.guild_permissions.administrator or any(r.id == config.STAFF_ROLE_ID for r in member.roles)):
                return await interaction.response.send_message("❌ Réservé au staff.", ephemeral=True)
        await interaction.response.defer()
        await self.close_ticket_flow(interaction.channel, interaction.user, reason=raison or f"Fermé par {interaction.user} via /fermer")

    @app_commands.command(name="transcript", description="Générer le transcript du ticket")
    async def transcript_cmd(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message("❌ Dans un salon ticket uniquement.", ephemeral=True)
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Ce salon n'est pas un ticket.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        msgs = await db.get_ticket_messages(int(ticket["id"]))
        if len(msgs) < 2:
            async for m in interaction.channel.history(limit=500, oldest_first=True):
                if m.author.id == self.bot.user.id and m.embeds and m.embeds[0].title and "Nouveau ticket" in m.embeds[0].title:
                    continue
                msgs.append({"author_name": str(m.author), "author_id": str(m.author.id), "content": m.content, "created_at": int(m.created_at.timestamp()), "is_bot": 1 if m.author.bot else 0, "attachments": "|".join([a.url for a in m.attachments])})
        user = await self.bot.fetch_user(int(ticket["user_id"]))
        path = await save_transcript(interaction.channel.name, interaction.channel.id, str(user), int(ticket["user_id"]), int(ticket["created_at"]), int(time.time()), msgs)
        size_kb = get_transcript_size(path) / 1024
        await interaction.followup.send(f"✅ Transcript : `{path}` ({size_kb:.1f} KB)", ephemeral=True)
        try:
            if path.endswith(".gz"):
                with gzip.open(path, "rb") as f:
                    data = f.read()
                file = discord.File(io.BytesIO(data), filename=interaction.channel.name + ".html")
            else:
                file = discord.File(path)
            await interaction.followup.send(file=file, ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"⚠️ Envoi échoué : {e}", ephemeral=True)

    @app_commands.command(name="claim", description="Claim le ticket en cours")
    async def claim(self, interaction: discord.Interaction):
        ticket = await db.get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            return await interaction.response.send_message("❌ Pas un salon ticket.", ephemeral=True)
        if ticket["claimed_by"]:
            return await interaction.response.send_message(f"ℹ️ Déjà claim par <@{ticket['claimed_by']}>", ephemeral=True)
        await db.claim_ticket(interaction.channel.id, interaction.user.id)
        await interaction.response.send_message(embed=af_embed(description=f"✅ Ticket claim par {interaction.user.mention}", color=config.COLOR_SUCCESS))

    @app_commands.command(name="ticket-stats", description="Statistiques des tickets")
    async def ticket_stats(self, interaction: discord.Interaction):
        stats = await db.get_stats()
        open_t = stats["open"]
        closed = stats["closed"]
        total = stats["total"]
        uniq = stats["unique_users"]
        embed = af_embed(title="📊 Statistiques Tickets", description=f"**Ouverts :** {open_t}\n**Fermés :** {closed}\n**Total :** {total}\n**Utilisateurs uniques :** {uniq}", color=config.COLOR_AF_BLUE)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="ban-ticket", description="Bannir un utilisateur du système de tickets")
    @app_commands.describe(utilisateur="Utilisateur à bannir", raison="Raison")
    async def ban_ticket(self, interaction: discord.Interaction, utilisateur: discord.User, raison: str = "Aucune raison"):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await db.ban_user(utilisateur.id, raison, interaction.user.id)
        await interaction.response.send_message(embed=af_embed(description=f"🚫 {utilisateur.mention} banni des tickets. Raison : {raison}", color=config.COLOR_ERROR))

    @app_commands.command(name="unban-ticket", description="Débannir un utilisateur")
    @app_commands.describe(utilisateur="Utilisateur à débannir")
    async def unban_ticket(self, interaction: discord.Interaction, utilisateur: discord.User):
        if not interaction.guild or not isinstance(interaction.user, discord.Member) or not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ Admin uniquement.", ephemeral=True)
        await db.unban_user(utilisateur.id)
        await interaction.response.send_message(embed=af_embed(description=f"✅ {utilisateur.mention} débanni.", color=config.COLOR_SUCCESS))

async def setup(bot: commands.Bot):
    await bot.add_cog(Tickets(bot))

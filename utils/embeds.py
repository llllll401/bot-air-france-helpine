import discord
import config

def af_embed(title: str = None, description: str = None, color: int = config.COLOR_AF_BLUE) -> discord.Embed:
    e = discord.Embed(title=title, description=description, color=color)
    e.set_footer(text=config.FOOTER_TEXT)
    return e

def ticket_open_embed(user: discord.User | discord.Member, guild_name: str):
    e = af_embed(
        title="🎫 Nouveau ticket MP",
        description=(
            f"**Utilisateur :** {user.mention} (`{user.id}`)\n"
            f"**Nom :** {user} ({user.global_name or user.name})\n"
            f"**Serveur :** {guild_name}\n\n"
            f"Le membre a envoyé un MP au bot. Réponds directement dans ce salon : ton message sera transféré en MP.\n"
            f"Pièces jointes et embeds sont transférés automatiquement."
        ),
        color=config.COLOR_AF_BLUE
    )
    e.set_thumbnail(url=user.display_avatar.url if user.display_avatar else None)
    e.add_field(name="Commandes rapides", value="`Répondre` → modal • `Fermer` → clôture + transcript • `/transcript`", inline=False)
    return e

def dm_welcome_embed():
    return af_embed(
        title="✈️ Ticket créé — Air France Helpine",
        description=(
            "Ton message a été reçu ! Un membre du staff va te répondre ici en MP.\n\n"
            "**Comment ça marche ?**\n"
            "• Écris simplement dans ce MP, tout est transféré au staff\n"
            "• Tu peux envoyer images/fichiers\n"
            "• Tape `!fermer` pour fermer ton ticket toi-même\n\n"
            "*Merci de patienter, temps de réponse moyen < 15 min.*"
        ),
        color=config.COLOR_SUCCESS
    )

def dm_already_open_embed(channel_mention: str):
    return af_embed(
        title="ℹ️ Ticket déjà ouvert",
        description=f"Tu as déjà un ticket en cours : {channel_mention}\nEnvoie ton message ici, il sera transféré.",
        color=config.COLOR_WARNING
    )

def ticket_closed_embed(reason: str = None):
    desc = "Ce ticket a été fermé."
    if reason:
        desc += f"\n**Raison :** {reason}"
    desc += "\n\nUn transcript a été sauvegardé. Le salon sera supprimé dans 10 secondes (ou archivé)."
    return af_embed(title="🔒 Ticket fermé", description=desc, color=config.COLOR_ERROR)

def announce_preview_embed(title: str, description: str, image_url: str = None, color: int = config.COLOR_AF_BLUE):
    e = af_embed(title=title, description=description, color=color)
    if image_url:
        e.set_image(url=image_url)
    e.set_author(name="📢 Annonce Air France Helpine")
    return e

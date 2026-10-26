import discord
from discord import app_commands
import config

def is_staff(member: discord.Member) -> bool:
    if member.guild_permissions.administrator:
        return True
    # check role staff
    return any(r.id == config.STAFF_ROLE_ID for r in member.roles)

def staff_only():
    def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        member = interaction.user
        if isinstance(member, discord.Member):
            return is_staff(member)
        return False
    return app_commands.check(predicate)

def admin_only():
    def predicate(interaction: discord.Interaction) -> bool:
        if interaction.guild is None:
            return False
        member = interaction.user
        if isinstance(member, discord.Member):
            return member.guild_permissions.administrator
        return False
    return app_commands.check(predicate)

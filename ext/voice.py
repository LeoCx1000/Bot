import asyncio

import discord
from discord.ext import commands

from utils import AloneBot


class Voice(commands.Cog):
    def __init__(self, bot: AloneBot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_voice_join(self, member: discord.Member, state: discord.VoiceState):
        assert state.channel
        vc = self.bot.guild_configs.get(state.channel.guild.id, {}).get("voice_channel", None)
        category_channel_id = self.bot.guild_configs.get(state.channel.guild.id, {}).get("voice_category", None)

        if not category_channel_id:
            return

        if not vc or state.channel.id != vc:
            return

        if await self.bot.db.fetch(
            "SELECT * FROM voice WHERE user_id = $1 AND guild_id = $2",
            member.id,
            state.channel.guild.id,
        ):
            return await member.send("You can only have 1 private channel per server!")

        new_vc = await member.guild.create_voice_channel(
            name=member.display_name,
            category=member.guild.get_channel(category_channel_id),  # type: ignore
            reason="Made by the personal voice chat module",
        )

        await member.move_to(channel=new_vc)
        self.bot.guild_configs[member.guild.id].setdefault("community_voice_channels", {})[new_vc.id] = member.id
        await self.bot.db.execute(
            "INSERT INTO voice VALUES ($1, $2, $3)",
            member.guild.id,
            member.id,
            new_vc.id,
        )
        await member.send("Welcome to your own voice chat! Here, you lay the rules. your house, your magic. Have fun!")

    @commands.Cog.listener()
    async def on_voice_leave(self, member: discord.Member, state: discord.VoiceState):
        assert state.channel

        vc = self.bot.guild_configs.get(member.guild.id, {}).get("community_voice_channels", {})
        if not vc or not state.channel.id in vc:
            return

        if not state.channel.members:
            channel = state.channel

            def channel_check(_: discord.Member, state: discord.VoiceState) -> bool:
                return state.channel == channel

            try:
                owner_id = vc.get(state.channel.id)
                assert owner_id

                owner = member.guild.get_member(owner_id)
                assert owner

                message = await owner.send(
                    "I will delete your private channel for inactivity in 5 minutes if it's not used!"
                )
                await self.bot.wait_for("voice_join", timeout=300, check=channel_check)
                await message.delete()

            except asyncio.TimeoutError:
                try:
                    if channel:
                        await channel.delete()

                    await self.bot.db.execute("DELETE FROM voice WHERE channel_id = $1", state.channel.id)
                except Exception:
                    pass


async def setup(bot: AloneBot):
    await bot.add_cog(Voice(bot))

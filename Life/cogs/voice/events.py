"""
Life Discord bot
Copyright (C) 2020 MrRandom#9258

Life is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public
License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later
version.

Life is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with Life.  If not, see
<https://www.gnu.org/licenses/>.
"""

from discord.ext import commands


class MusicEvents(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_diorite_track_start(self, event):
        self.bot.dispatch('life_track_start', event.player.guild.id)

    @commands.Cog.listener()
    async def on_diorite_track_end(self, event):
        self.bot.dispatch('life_track_end', event.player.guild.id)

    @commands.Cog.listener()
    async def on_diorite_track_stuck(self, event):
        await event.player.channel.send('The current track got stuck while playing, ideally this should not happen so'
                                        'you can join my support server for more help.')
        self.bot.dispatch('life_track_end', event.player.guild.id)

    @commands.Cog.listener()
    async def on_diorite_track_error(self, event):
        await event.player.channel.send(f'Something went wrong while playing a track. Error: `{event.error}`')
        self.bot.dispatch('life_track_end', event.player.guild.id)

    @commands.Cog.listener()
    async def on_diorite_websocket_closed(self, event):
        await event.player.channel.send(f'Your nodes websocket decided to disconnect, ideally this should not happen so'
                                        f'you can join my support server for more help.')


def setup(bot):
    bot.add_cog(MusicEvents(bot))

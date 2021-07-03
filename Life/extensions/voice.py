"""
Copyright (c) 2020-present Axelancerr

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

from __future__ import annotations

import logging
import math
from typing import Union

import discord
import slate
from discord.ext import commands
from slate import obsidian

from core import colours, config, emojis
from core.bot import Life
from utilities import checks, context, converters, custom, exceptions, utils


class Options(commands.FlagConverter, delimiter=" ", prefix="--", case_insensitive=True):
    music: bool = False
    soundcloud: bool = False
    local: bool = False
    http: bool = False
    next: bool = False
    now: bool = False


class QueueOptions(commands.FlagConverter, delimiter=" ", prefix="--", case_insensitive=True):
    next: bool = False
    now: bool = False


class SearchOptions(commands.FlagConverter, delimiter=" ", prefix="--", case_insensitive=True):
    music: bool = False
    soundcloud: bool = False
    local: bool = False
    http: bool = False


def get_source(flags: Union[Options, SearchOptions]) -> slate.Source:

    if flags.music:
        return slate.Source.YOUTUBE_MUSIC
    elif flags.soundcloud:
        return slate.Source.SOUNDCLOUD
    elif flags.local:
        return slate.Source.LOCAL
    elif flags.http:
        return slate.Source.HTTP

    return slate.Source.YOUTUBE


__log__: logging.Logger = logging.getLogger("extensions.voice")


class Voice(commands.Cog):

    def __init__(self, bot: Life) -> None:
        self.bot = bot

    #

    async def load(self) -> None:

        for node in config.NODES:
            try:
                await self.bot.slate.create_node(
                        type=obsidian.ObsidianNode,
                        bot=self.bot,
                        host=node["host"],
                        port=node["port"],
                        password=node["password"],
                        identifier=node["identifier"],
                        region=discord.VoiceRegion.us_east,
                        spotify_client_id=config.SPOTIFY_CLIENT_ID,
                        spotify_client_secret=config.SPOTIFY_CLIENT_SECRET
                )
            except slate.NodeConnectionError:
                continue

    # Events

    @commands.Cog.listener()
    async def on_obsidian_track_start(self, player: custom.Player, event: obsidian.ObsidianTrackStart) -> None:

        player._track_start_event.set()
        player._track_start_event.clear()

    @commands.Cog.listener()
    async def on_obsidian_track_end(self, player: custom.Player, event: obsidian.ObsidianTrackEnd) -> None:

        player._track_end_event.set()
        player._track_end_event.clear()

        player.skip_request_ids = set()

    @commands.Cog.listener()
    async def on_obsidian_track_exception(self, player: custom.Player, event: obsidian.ObsidianTrackException) -> None:

        track = None
        try:
            track = await player.node.decode_track(track_id=event.track_id)
        except slate.HTTPError:
            pass

        title = getattr(track or player.current, "title", "Not Found")
        await player.send(f"There was an error of severity `{event.severity}` while playing the track `{title}`.\nReason: {event.message}")

        player._track_end_event.set()
        player._track_end_event.clear()

        player.skip_request_ids = set()

    @commands.Cog.listener()
    async def on_obsidian_track_stuck(self, player: custom.Player, event: obsidian.ObsidianTrackStuck) -> None:

        track = None
        try:
            track = await player.node.decode_track(track_id=event.track_id)
        except slate.HTTPError:
            pass

        title = getattr(track or player.current, "title", "Not Found")
        await player.send(f"Something went wrong while playing the track `{title}`. Use `{config.PREFIX}support` for more help.")

        player._track_end_event.set()
        player._track_end_event.clear()

        player.skip_request_ids = set()

    # Join/Leave commands

    @commands.command(name="join", aliases=["summon", "connect"])
    @checks.is_author_connected(same_channel=False)
    async def join(self, ctx: context.Context) -> None:
        """
        Joins the bot to your voice channel.
        """

        if ctx.voice_client and ctx.voice_client.is_connected() is True:
            raise exceptions.EmbedError(colour=colours.RED, emoji=emojis.CROSS, description=f"I am already connected to {ctx.voice_client.voice_channel.mention}.")

        await ctx.author.voice.channel.connect(cls=custom.Player)
        ctx.voice_client._text_channel = ctx.channel

        await ctx.send(embed=utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description=f"Joined {ctx.voice_client.voice_channel.mention}"))

    @commands.command(name="disconnect", aliases=["dc", "leave", "destroy"])
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=False)
    async def disconnect(self, ctx: context.Context) -> None:
        """
        Disconnects the bot its voice channel.
        """

        await ctx.send(embed=utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description=f"Left voice channel {ctx.voice_client.voice_channel.mention}"))
        await ctx.voice_client.disconnect()

    # Play commands

    @commands.command(name="play", invoke_without_command=True)
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=True)
    async def play(self, ctx: context.Context, query: str, *, options: Options) -> None:
        """
        Queues tracks with the given name or url.

        `query`: The query to search for tracks with.

        **Flags:**
        `--music`: Searches [youtube music](https://music.youtube.com/) for results.
        `--soundcloud`: Searches [soundcloud](https://soundcloud.com/) for results.
        `--next`: Puts the track that is found at the start of the queue.
        `--now`: Skips the current track and plays the track that is found.

        **Usage:**
        `l-play If I Can't Have You by Shawn Mendes --now`
        `l-play Senorita by Shawn Mendes --next`
        `l-play Lost In Japan by Shawn Mendes --soundcloud --now`
        """

        async with ctx.channel.typing():
            await ctx.voice_client.queue_search(query=query, ctx=ctx, now=options.now, next=options.next, source=get_source(options))

    @commands.command(name="search")
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=True)
    async def search(self, ctx: context.Context, query: str, *, options: Options) -> None:
        """
        Choose which track to play based on a search.

        `query`: The query to search for tracks with.

        **Flags:**
        `--music`: Searches [youtube music](https://music.youtube.com/) for results.
        `--soundcloud`: Searches [soundcloud](https://soundcloud.com/) for results.
        `--next`: Puts the track that is found at the start of the queue.
        `--now`: Skips the current track and plays the track that is found.

        **Usage:**
        `l-search If I Can't Have You by Shawn Mendes --now`
        `l-search Senorita by Shawn Mendes --next`
        `l-search Lost In Japan by Shawn Mendes --soundcloud --now`
        """

        async with ctx.channel.typing():
            await ctx.voice_client.queue_search(query=query, ctx=ctx, now=options.now, next=options.next, source=get_source(options), choose=True)

    # Platform specific play commands

    @commands.command(name="youtube-music", aliases=["youtube_music", "youtubemusic", "yt-music", "yt_music", "ytmusic", "ytm"])
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=True)
    async def youtube_music(self, ctx: context.Context, query: str, *, options: QueueOptions) -> None:
        """
        Queues tracks from youtube music with the given name or url.

        `query`: The query to search for tracks with.

        **Flags:**
        `--next`: Puts the track that is found at the start of the queue.
        `--now`: Skips the current track and plays the track that is found.

        **Usage:**
        `l-youtube-music Lost In Japan by Shawn Mendes --now`
        `l-ytm If I Can't Have You by Shawn Mendes --next`
        """

        async with ctx.channel.typing():
            await ctx.voice_client.queue_search(query=query, ctx=ctx, now=options.now, next=options.next, source=slate.Source.YOUTUBE_MUSIC)

    @commands.command(name="soundcloud", aliases=["sc"])
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=True)
    async def soundcloud(self, ctx: context.Context, query: str, *, options: QueueOptions) -> None:
        """
        Queues tracks from soundcloud with the given name or url.

        `query`: The query to search for tracks with.

        **Flags:**
        `--next`: Puts the track that is found at the start of the queue.
        `--now`: Skips the current track and plays the track that is found.

        **Usage:**
        `l-soundcloud Lost In Japan by Shawn Mendes --now`
        `l-sc If I Can't Have You by Shawn Mendes --next`
        """

        async with ctx.channel.typing():
            await ctx.voice_client.queue_search(query=query, ctx=ctx, now=options.now, next=options.next, source=slate.Source.SOUNDCLOUD)

    # Queue specific play commands

    @commands.command(name="play-next", aliases=["play_next", "playnext", "pnext"])
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=True)
    async def play_next(self, ctx: context.Context, query: str, *, options: SearchOptions) -> None:
        """
        Queues tracks at the start of the queue.

        `query`: The query to search for tracks with.

        **Flags:**
        `--music`: Searches [youtube music](https://music.youtube.com/) for results.
        `--soundcloud`: Searches [soundcloud](https://soundcloud.com/) for results.

        **Usage:**
        `l-play-next Lost In Japan by Shawn Mendes --music`
        `l-pnext If I Can't Have You by Shawn Mendes --soundcloud`
        """

        async with ctx.channel.typing():
            await ctx.voice_client.queue_search(query=query, ctx=ctx, next=True, source=get_source(options))

    @commands.command(name="play-now", aliases=["play_now", "playnow", "pnow"])
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=True)
    async def play_now(self, ctx: context.Context, query: str, *, options: SearchOptions) -> None:
        """
        Queues tracks and skips the current track.

        `query`: The query to search for tracks with.

        **Flags:**
        `--music`: Searches [youtube music](https://music.youtube.com/) for results.
        `--soundcloud`: Searches [soundcloud](https://soundcloud.com/) for results.

        **Usage:**
        `l-play-now Lost In Japan by Shawn Mendes --music`
        `l-pnow If I Can't Have You by Shawn Mendes --soundcloud`
        """

        async with ctx.channel.typing():
            await ctx.voice_client.queue_search(query=query, ctx=ctx, now=True, source=get_source(options))

    # Pause/Resume commands

    @commands.command(name="pause")
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=False)
    async def pause(self, ctx: context.Context) -> None:
        """
        Pauses the current track.
        """

        if ctx.voice_client.paused:
            raise exceptions.EmbedError(colour=colours.RED, emoji=emojis.CROSS, description="The player is already paused.")

        await ctx.voice_client.set_pause(True)
        await ctx.reply(embed=utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description="The player is now paused."))

    @commands.command(name="resume", aliases=["continue", "unpause"])
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=False)
    async def resume(self, ctx: context.Context) -> None:
        """
        Resumes the current track.
        """

        if ctx.voice_client.paused is False:
            raise exceptions.EmbedError(colour=colours.RED, emoji=emojis.CROSS, description="The player is not paused.")

        await ctx.voice_client.set_pause(False)
        await ctx.reply(embed=utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description="The player is now resumed."))

    # Seek commands

    @commands.command(name="seek")
    @checks.is_track_seekable()
    @checks.is_voice_client_playing()
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=False)
    async def seek(self, ctx: context.Context, *, time: converters.TimeConverter) -> None:
        """
        Seeks to a position in the current track.

        `time`: The position to seek too.
        """

        # noinspection PyTypeChecker
        milliseconds = time * 1000

        if 0 < milliseconds > ctx.voice_client.current.length:
            raise exceptions.EmbedError(
                    colour=colours.RED,
                    emoji=emojis.CROSS,
                    description=f"That is not a valid amount of time, please choose a time between **0s** and **{utils.format_seconds(ctx.voice_client.current.length // 1000, friendly=True)}**."
            )

        await ctx.voice_client.set_position(milliseconds)

        embed = utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description=f"The players position is now **{utils.format_seconds(ctx.voice_client.position // 1000, friendly=True)}**.")
        await ctx.reply(embed=embed)

    @commands.command(name="forward", aliases=["fwd"])
    @checks.is_track_seekable()
    @checks.is_voice_client_playing()
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=False)
    async def forward(self, ctx: context.Context, *, time: converters.TimeConverter) -> None:
        """
        Seeks forward on the current track.

        `time`: The amount of time to seek forward.
        """

        # noinspection PyTypeChecker
        milliseconds = time * 1000

        position = ctx.voice_client.position
        remaining = ctx.voice_client.current.length - position

        if milliseconds >= remaining:
            raise exceptions.EmbedError(
                    colour=colours.RED,
                    emoji=emojis.CROSS,
                    description=f"That is not a valid amount of time. Please choose an amount lower than **{utils.format_seconds(remaining // 1000, friendly=True)}**."
            )

        await ctx.voice_client.set_position(position + milliseconds)

        embed = utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description=f"The players position is now **{utils.format_seconds(ctx.voice_client.position // 1000, friendly=True)}**.")
        await ctx.reply(embed=embed)

    @commands.command(name="rewind", aliases=["rwd", "backward"])
    @checks.is_track_seekable()
    @checks.is_voice_client_playing()
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=False)
    async def rewind(self, ctx: context.Context, *, time: converters.TimeConverter) -> None:
        """
        Seeks backward on the current track.

        `time`: The amount of time to seek backward.
        """

        # noinspection PyTypeChecker
        milliseconds = time * 1000

        position = ctx.voice_client.position

        if milliseconds >= ctx.voice_client.position:
            raise exceptions.EmbedError(
                    colour=colours.RED,
                    emoji=emojis.CROSS,
                    description=f"That is not a valid amount of time. Please choose an amount lower than **{utils.format_seconds(ctx.voice_client.position // 1000, friendly=True)}**."
            )

        await ctx.voice_client.set_position(position - milliseconds)

        embed = utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description=f"The players position is now **{utils.format_seconds(ctx.voice_client.position // 1000, friendly=True)}**.")
        await ctx.reply(embed=embed)

    @commands.command(name="replay", aliases=["restart"])
    @checks.is_track_seekable()
    @checks.is_voice_client_playing()
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=False)
    async def replay(self, ctx: context.Context) -> None:
        """
        Seeks to the start of the current track.
        """

        await ctx.voice_client.set_position(position=0)

        embed = utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description=f"The players position is now **{utils.format_seconds(ctx.voice_client.position // 1000, friendly=True)}**.")
        await ctx.reply(embed=embed)

    # Loop commands

    @commands.command(name="loop", aliases=["loop-current", "loop_current"])
    @checks.is_voice_client_playing()
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=False)
    async def loop(self, ctx: context.Context) -> None:
        """
        Loops the current track.
        """

        if ctx.voice_client.queue.loop_mode is not slate.QueueLoopMode.CURRENT:
            ctx.voice_client.queue.set_loop_mode(slate.QueueLoopMode.CURRENT)
        else:
            ctx.voice_client.queue.set_loop_mode(slate.QueueLoopMode.OFF)

        embed = utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description=f"The queue looping mode is now **{ctx.voice_client.queue.loop_mode.name.title()}**.")
        await ctx.reply(embed=embed)

    @commands.command(name="queueloop", aliases=["loopqueue", "loop-queue", "loop_queue"])
    @checks.is_voice_client_playing()
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=False)
    async def queueloop(self, ctx: context.Context) -> None:
        """
        Loops the queue.
        """

        if ctx.voice_client.queue.loop_mode is not slate.QueueLoopMode.QUEUE:
            ctx.voice_client.queue.set_loop_mode(slate.QueueLoopMode.QUEUE)
        else:
            ctx.voice_client.queue.set_loop_mode(slate.QueueLoopMode.OFF)

        embed = utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description=f"The queue looping mode is now **{ctx.voice_client.queue.loop_mode.name.title()}**.")
        await ctx.reply(embed=embed)

    # Skip commands

    @commands.command(name="skip", aliases=["voteskip", "vote-skip", "vote_skip", "vs", "forceskip", "force-skip", "force_skip", "fs"])
    @checks.is_voice_client_playing()
    @checks.is_author_connected(same_channel=True)
    @checks.has_voice_client(try_join=False)
    async def skip(self, ctx: context.Context, amount: int = 1) -> None:
        """
        Votes to skip the current track.
        """

        try:
            await commands.check_any(
                    commands.is_owner(), checks.is_guild_owner(), checks.is_track_requester(),
                    checks.has_any_permissions(manage_guild=True, kick_members=True, ban_members=True, manage_messages=True, manage_channels=True)
            ).predicate(ctx=ctx)

        except commands.CheckAnyFailure:

            if ctx.author not in ctx.voice_client.listeners:
                raise exceptions.EmbedError(colour=colours.RED, emoji=emojis.CROSS, description="You can not vote to skip as you are currently deafened.")

            if ctx.author.id in ctx.voice_client.skip_request_ids:
                ctx.voice_client.skip_request_ids.remove(ctx.author.id)
                message = "Removed your vote to skip, "
            else:
                ctx.voice_client.skip_request_ids.add(ctx.author.id)
                message = "Added your vote to skip, "

            skips_needed = math.floor(75 * len(ctx.voice_client.listeners) / 100)

            if len(ctx.voice_client.skip_request_ids) < skips_needed:
                raise exceptions.EmbedError(
                        colour=colours.GREEN,
                        emoji=emojis.TICK,
                        description=f"{message} currently on **{len(ctx.voice_client.skip_request_ids)}** out of **{skips_needed}** votes needed to skip."
                )

            await ctx.voice_client.stop()
            await ctx.reply(embed=utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description="Skipped the current track."))
            return

        if 0 <= amount > len(ctx.voice_client.queue) + 1:
            raise exceptions.EmbedError(
                    colour=colours.RED,
                    emoji=emojis.CROSS,
                    description=f'There are not enough tracks in the queue to skip that many. Choose a number between **1** and **{len(ctx.voice_client.queue) + 1}**.'
            )

        for index, track in enumerate(ctx.voice_client.queue[:amount - 1]):
            try:
                if track.requester.id != ctx.author.id:
                    raise commands.CheckAnyFailure
                await commands.check_any(
                        commands.is_owner(), checks.is_guild_owner(), checks.has_any_permissions(manage_guild=True, kick_members=True, ban_members=True, manage_messages=True, manage_channels=True)
                ).predicate(ctx=ctx)
            except commands.CheckAnyFailure:
                raise exceptions.EmbedError(colour=colours.RED, emoji=emojis.CROSS, description=f"You do not have permission to skip the next **{amount}** tracks in the queue.")

        for _ in enumerate(ctx.voice_client.queue[:amount - 1]):
            ctx.voice_client.queue.get()

        await ctx.voice_client.stop()
        await ctx.reply(embed=utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description=f"Skipped **{amount}** track{'s' if amount != 1 else ''}."))

    # Misc

    @commands.command(name="nowplaying", aliases=["np"])
    @checks.is_voice_client_playing()
    @checks.has_voice_client(try_join=False)
    async def nowplaying(self, ctx: context.Context) -> None:
        """
        Shows the player controller.
        """

        await ctx.voice_client.invoke_controller()

    @commands.command(name="save", aliases=["grab", "yoink"])
    @checks.is_voice_client_playing()
    @checks.has_voice_client(try_join=False)
    async def save(self, ctx: context.Context) -> None:
        """
        Saves the current track to your DM's.
        """

        try:
            embed = discord.Embed(
                    colour=colours.MAIN,
                    title=ctx.voice_client.current.title,
                    url=ctx.voice_client.current.uri,
                    description=f"`Author:` {ctx.voice_client.current.author}\n"
                                f"`Source:` {ctx.voice_client.current.source.value.title()}\n"
                                f"`Length:` {utils.format_seconds(ctx.voice_client.current.length // 1000, friendly=True)}\n"
                                f"`Live:` {ctx.voice_client.current.is_stream()}\n"
                                f"`Seekable:` {ctx.voice_client.current.is_seekable()}"
            ).set_image(
                    url=ctx.voice_client.current.thumbnail
            )

            await ctx.author.send(embed=embed)
            await ctx.reply(embed=utils.embed(colour=colours.GREEN, emoji=emojis.TICK, description="Saved the current track to our DM's."))

        except discord.Forbidden:
            raise exceptions.EmbedError(colour=colours.RED, emoji=emojis.CROSS, description=f"I am unable to DM you.")


def setup(bot: Life) -> None:
    bot.add_cog(Voice(bot=bot))

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

import collections
import copy
import logging
import re
import time
import traceback
from typing import Optional, Type, Union

import aiohttp
import aioredis
import aioscheduler
import asyncpg
import discord
import ksoftapi
import mystbin
import psutil
import slate
import spotify
from discord.ext import commands

from core import config
from utilities import checks, context, help, managers


__log__: logging.Logger = logging.getLogger("bot")


class Life(commands.AutoShardedBot):

    def __init__(self) -> None:
        super().__init__(
                status=discord.Status.dnd,
                activity=discord.Activity(type=discord.ActivityType.playing, name="aaaaa!"),
                allowed_mentions=discord.AllowedMentions(everyone=False, users=True, roles=True, replied_user=False),
                help_command=help.HelpCommand(),
                intents=discord.Intents.all(),
                command_prefix=self.get_prefix,
                case_insensitive=True,
                owner_ids=config.OWNER_IDS,
        )

        self.session: aiohttp.ClientSession = aiohttp.ClientSession()
        self.process: psutil.Process = psutil.Process()
        self.socket_stats: collections.Counter = collections.Counter()

        self.ERROR_LOG: discord.Webhook = discord.Webhook.from_url(session=self.session, url=config.ERROR_WEBHOOK_URL)
        self.GUILD_LOG: discord.Webhook = discord.Webhook.from_url(session=self.session, url=config.GUILD_WEBHOOK_URL)
        self.DMS_LOG: discord.Webhook = discord.Webhook.from_url(session=self.session, url=config.DM_WEBHOOK_URL)

        self.db: Optional[asyncpg.Pool] = None
        self.redis: Optional[aioredis.Redis] = None

        self.scheduler: aioscheduler.Manager = aioscheduler.Manager()
        self.mystbin: mystbin.Client = mystbin.Client(session=self.session)
        self.ksoft: ksoftapi.Client = ksoftapi.Client(api_key=config.KSOFT_TOKEN)
        self.spotify: spotify.Client = spotify.Client(client_id=config.SPOTIFY_CLIENT_ID, client_secret=config.SPOTIFY_CLIENT_SECRET)
        self.spotify_http: spotify.HTTPClient = spotify.HTTPClient(client_id=config.SPOTIFY_CLIENT_ID, client_secret=config.SPOTIFY_CLIENT_SECRET)
        self.slate: Type[slate.NodePool] = slate.NodePool

        self.user_manager: managers.UserManager = managers.UserManager(bot=self)
        self.guild_manager: managers.GuildManager = managers.GuildManager(bot=self)

        self.first_ready: bool = True
        self.start_time: float = time.time()

        self.add_check(checks.global_check, call_once=True)

    #

    async def get_prefix(self, message: discord.Message) -> list[str]:

        if not message.guild:
            return commands.when_mentioned_or(config.PREFIX, "I-", "")(self, message)

        guild_config = self.guild_manager.get_config(message.guild.id)
        return commands.when_mentioned_or(config.PREFIX, "I-", *guild_config.prefixes)(self, message)

    async def process_commands(self, message: discord.Message) -> None:

        if message.author.bot:
            return

        ctx = await self.get_context(message)

        if ctx.command and ctx.command.name in ["play", "yt-music", "soundcloud", "search", "play-now", "play-next"]:

            content = message.content
            start = content.index(ctx.invoked_with) + len(ctx.invoked_with) + 1
            try:
                end = content.index(" --")
            except ValueError:
                end = len(content)
            query = '"' + content[start:end] + '"'

            content = content[:start] + query + content[end:]

            message = copy.copy(message)
            message.content = re.sub(r"--([^\s]+)\s*", r"--\1 true ", content)

            ctx = await self.get_context(message)

        await self.invoke(ctx)

    async def get_context(self, message: discord.Message, *, cls=context.Context) -> context.Context:
        return await super().get_context(message=message, cls=cls)

    async def is_owner(self, user: Union[discord.User, discord.Member]) -> bool:
        return user.id in config.OWNER_IDS

    #

    async def start(self, token: str, *, reconnect: bool = True) -> None:

        try:
            __log__.debug("[POSTGRESQL] Attempting connection.")
            db = await asyncpg.create_pool(**config.POSTGRESQL, max_inactive_connection_lifetime=0)
        except Exception as e:
            __log__.critical(f"[POSTGRESQL] Error while connecting.\n{e}\n")
            raise ConnectionError()
        else:
            __log__.info("[POSTGRESQL] Successful connection.")
            self.db = db

        try:
            __log__.debug("[REDIS] Attempting connection.")
            redis = aioredis.from_url(url=config.REDIS, decode_responses=True, retry_on_timeout=True)
            await redis.ping()
        except (aioredis.ConnectionError, aioredis.ResponseError) as e:
            __log__.critical(f"[REDIS] Error while connecting.\n{e}\n")
            raise ConnectionError()
        else:
            __log__.info("[REDIS] Successful connection.")
            self.redis = redis

        for extension in config.EXTENSIONS:
            try:
                self.load_extension(extension)
                __log__.info(f"[EXTENSIONS] Loaded - {extension}")
            except commands.ExtensionNotFound:
                __log__.warning(f"[EXTENSIONS] Extension not found - {extension}")
            except commands.NoEntryPointError:
                __log__.warning(f"[EXTENSIONS] No entry point - {extension}")
            except commands.ExtensionFailed as error:
                __log__.warning(f"[EXTENSIONS] Failed - {extension} - Reason: {traceback.print_exception(type(error), error, error.__traceback__)}")

        await super().start(token=token, reconnect=reconnect)

    async def close(self) -> None:

        await self.session.close()
        await self.ksoft.close()
        await self.spotify.close()
        await self.spotify_http.close()

        if self.db:
            await self.db.close()
        if self.redis:
            await self.redis.close()

        await super().close()

    # Events

    async def on_ready(self) -> None:

        if self.first_ready is True:
            self.first_ready = False

        self.scheduler.start()

        await self.user_manager.load()
        await self.guild_manager.load()

        await self.cogs['Voice'].load()

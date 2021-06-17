#  Life
#  Copyright (C) 2020 Axel#3456
#
#  Life is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software
#  Foundation, either version 3 of the License, or (at your option) any later version.
#
#  Life is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
#  PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License along with Life. If not, see https://www.gnu.org/licenses/.

import contextlib
import logging
import sys
import traceback
from typing import Any, Optional

import discord
import pendulum
import slate
from discord.ext import commands

import config
from bot import Life
from utilities import context, enums, exceptions, utils


__log__ = logging.getLogger(__name__)


class Events(commands.Cog):

    def __init__(self, bot: Life) -> None:
        self.bot = bot

        self.BAD_ARGUMENT_ERRORS = {
            commands.MessageNotFound:               'A message for the argument `{argument}` was not found.',
            commands.MemberNotFound:                'A member for the argument `{argument}` was not found.',
            commands.UserNotFound:                  'A user for the argument `{argument}` was not found.',
            commands.ChannelNotFound:               'A channel for the argument `{argument}` was not found.',
            commands.RoleNotFound:                  'A role for the argument `{argument}` was not found.',
            commands.EmojiNotFound:                 'An emoji for the argument `{argument}` was not found.',
            commands.ChannelNotReadable:            'I do not have permission to read the channel `{argument}`',
            commands.BadInviteArgument:             'The invite `{argument}` was not valid or is expired.',
            commands.PartialEmojiConversionFailure: 'The argument `{argument}` did not match the partial emoji format.',
            commands.BadBoolArgument:               'The argument `{argument}` was not a valid True or False value.',
            commands.BadColourArgument:             'The argument `{argument}` was not a valid colour type.',
            commands.BadArgument:                   'I was unable to convert an argument that you used.',
        }

        self.COOLDOWN_BUCKETS = {
            commands.BucketType.default:  'for the whole bot',
            commands.BucketType.user:     'for you',
            commands.BucketType.member:   'for you',
            commands.BucketType.role:     'for your role',
            commands.BucketType.guild:    'for this server',
            commands.BucketType.channel:  'for this channel',
            commands.BucketType.category: 'for this channel category'
        }

        self.CONCURRENCY_BUCKETS = {
            commands.BucketType.default:  'for all users',
            commands.BucketType.user:     'per user',
            commands.BucketType.member:   'per member',
            commands.BucketType.role:     'per role',
            commands.BucketType.guild:    'per server',
            commands.BucketType.channel:  'per channel',
            commands.BucketType.category: 'per channel category',
        }

        self.OTHER_ERRORS = {
            exceptions.ArgumentError:               '{error}',
            exceptions.GeneralError:                '{error}',
            exceptions.ImageError:                  '{error}',
            exceptions.VoiceError:                  '{error}',
            slate.NodesNotFound:                    'There are no player nodes available right now.',

            commands.TooManyArguments:              'You used too many arguments. Use `{prefix}help {command}` for more information on what arguments to use.',

            commands.UnexpectedQuoteError:          'There was an unexpected quote character in the arguments you passed.',
            commands.InvalidEndOfQuotedStringError: 'There was an unexpected space after a quote character in the arguments you passed.',
            commands.ExpectedClosingQuoteError:     'There is a missing quote character in the arguments you passed.',

            commands.CheckFailure:                  '{error}',
            commands.PrivateMessageOnly:            'The command `{command}` can only be used in private messages',
            commands.NoPrivateMessage:              'The command `{command}` can not be used in private messages.',
            commands.NotOwner:                      'The command `{command}` can only be used by owners.',
            commands.NSFWChannelRequired:           'The command `{command}` can only be run in a NSFW channel.',

            commands.DisabledCommand:               'The command `{command}` has been disabled.',
        }

        self.RED = discord.Colour(0xFF0000)
        self.ORANGE = discord.Colour(0xFAA61A)
        self.GREEN = discord.Colour(0x00FF00)

    # Logging methods

    @staticmethod
    async def _log_attachments(webhook: discord.Webhook, message: discord.Message) -> None:

        with contextlib.suppress(discord.HTTPException, discord.NotFound, discord.Forbidden):
            for attachment in message.attachments:
                await webhook.send(
                        content=f'Attachment from message with id `{message.id}`:', file=await attachment.to_file(use_cached=True), username=f'{message.author}',
                        avatar_url=utils.avatar(person=message.author)
                )

    @staticmethod
    async def _log_embeds(webhook: discord.Webhook, message: discord.Message) -> None:

        for embed in message.embeds:
            await webhook.send(
                    content=f'Embed from message with id `{message.id}`:', embed=embed, username=f'{message.author}',
                    avatar_url=utils.avatar(person=message.author)
            )

    async def _log_dm(self, message: discord.Message) -> None:

        content = await utils.safe_content(self.bot.mystbin, message.content) if message.content else '*No content*'

        embed = discord.Embed(colour=self.GREEN, title=f'DM from `{message.author}`:', description=content)
        embed.add_field(
                name='Info:',
                value=f'''
                `Channel:` {message.channel} `{message.channel.id}`
                `Author:` {message.author} `{message.author.id}`
                `Time:` {utils.format_datetime(datetime=pendulum.now(tz="UTC"))}
                `Jump:` [Click here]({message.jump_url})
                ''',
                inline=False
        )
        embed.set_footer(text=f'ID: {message.id}')
        await self.bot.DMS_LOG.send(embed=embed, username=f'{message.author}', avatar_url=utils.avatar(person=message.author))

        await self._log_attachments(webhook=self.bot.DMS_LOG, message=message)
        await self._log_embeds(webhook=self.bot.DMS_LOG, message=message)

    # Error handling

    @commands.Cog.listener()
    async def on_command_error(self, ctx: context.Context, error: Any) -> Optional[discord.Message]:

        error = getattr(error, 'original', error)

        __log__.error(
                f'''[COMMANDS] Error while running command. Name: {ctx.command} | Error: {type(error)} | Invoker: {ctx.author} | Channel: {ctx.channel} ({ctx.channel.id}) \
                {f" | Guild: {ctx.guild} ({ctx.guild.id})" if ctx.guild else ""}'''
        )

        if isinstance(error, commands.CommandNotFound):
            return

        if isinstance(error, commands.BotMissingPermissions):
            permissions = '\n'.join([f'> {permission}' for permission in error.missing_perms])
            message = f'I am missing the following permissions required to run the command `{ctx.command.qualified_name}`.\n{permissions}'
            await ctx.try_dm(content=message)
            return

        if isinstance(error, exceptions.EmbedError):
            await ctx.reply(embed=error.embed)
            return

        message = None

        if isinstance(error, commands.BadLiteralArgument):
            message = f'The argument `{error.param.name}` must be one of {", ".join([f"`{arg}`" for arg in error.literals])}.'

        elif isinstance(error, commands.BadArgument):
            message = self.BAD_ARGUMENT_ERRORS.get(type(error), 'None').format(argument=getattr(error, 'argument', 'None'))

        elif isinstance(error, commands.CommandOnCooldown):
            message = f'''
            The command `{ctx.command.qualified_name}` is on cooldown {self.COOLDOWN_BUCKETS.get(error.cooldown.type)}. You can retry in `{utils.format_seconds(error.retry_after, friendly=True)}`
            '''

        elif isinstance(error, commands.MaxConcurrencyReached):
            message = f'''
            The command `{ctx.command.qualified_name}` is being ran at its maximum of {error.number} time{"s" if error.number > 1 else ""} {self.CONCURRENCY_BUCKETS.get(error.per)}. Retry a bit later.
            '''

        elif isinstance(error, commands.MissingPermissions):
            permissions = '\n'.join([f'> {permission}' for permission in error.missing_perms])
            message = f'You are missing the following permissions required to run the command `{ctx.command.qualified_name}`.\n{permissions}'

        elif isinstance(error, commands.MissingRequiredArgument):
            message = f'You missed the `{error.param.name}` argument. Use `{config.PREFIX}help {ctx.command.qualified_name}` for more information on what arguments to use.'

        elif isinstance(error, commands.BadUnionArgument):
            message = f'I was unable to convert the `{error.param.name}` argument. Use `{config.PREFIX}help {ctx.command.qualified_name}` for more help on what arguments to use.'

        elif isinstance(error, commands.MissingRole):
            message = f'The role `{error.missing_role}` is required to run this command.'

        elif isinstance(error, commands.BotMissingRole):
            message = f'The bot requires the role `{error.missing_role}` to run this command.'

        elif isinstance(error, commands.MissingAnyRole):
            message = f'The roles {", ".join([f"`{role}`" for role in error.missing_roles])} are required to run this command.'

        elif isinstance(error, commands.BotMissingAnyRole):
            message = f'The bot requires the roles {", ".join([f"`{role}`" for role in error.missing_roles])} to run this command.'

        if message:
            await ctx.reply(message)
        elif (message := self.OTHER_ERRORS.get(type(error))) is not None:
            await ctx.reply(message.format(command=ctx.command.qualified_name, error=error, prefix=config.PREFIX))
        else:
            await self.handle_traceback(ctx=ctx, error=error)

    async def handle_traceback(self, *, ctx: context.Context, error) -> None:

        await ctx.reply('Something went wrong while executing that command.')

        error_traceback = ''.join(traceback.format_exception(type(error), error, error.__traceback__))
        print(f'\n{error_traceback}\n', file=sys.stderr)
        __log__.error(f'[COMMANDS]\n\n{traceback}\n\n')

        info = f'''
        {f"`Guild:` {ctx.guild} `{ctx.guild.id}`" if ctx.guild else ""}
        `Channel:` {ctx.channel} `{ctx.channel.id}`
        `Author:` {ctx.author} `{ctx.author.id}`
        `Time:` {utils.format_datetime(pendulum.now(tz="UTC"))}
        '''

        embed = discord.Embed(colour=ctx.colour, description=ctx.message.content)
        embed.add_field(name='Info:', value=info)
        await self.bot.ERROR_LOG.send(embed=embed, username=f'{ctx.author}', avatar_url=utils.avatar(person=ctx.author))

        error_traceback = await utils.safe_content(self.bot.mystbin, f'```py{error_traceback}```', syntax='python', max_characters=2000)
        await self.bot.ERROR_LOG.send(content=error_traceback, username=f'{ctx.author}', avatar_url=utils.avatar(person=ctx.author))

    # Bot events

    @commands.Cog.listener()
    async def on_socket_response(self, message: dict[str, Any]) -> None:

        if (event := message.get('t')) is not None:
            self.bot.socket_stats[event] += 1

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:

        if before.content == after.content:
            return

        await self.bot.process_commands(after)

    @commands.Cog.listener()
    async def on_ready(self) -> None:

        print(f'[BOT] The bot is now ready. Name: {self.bot.user} | ID: {self.bot.user.id}\n')
        __log__.info(f'Bot is now ready. Name: {self.bot.user} | ID: {self.bot.user.id}')

    # Guild logging

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild) -> None:

        __log__.info(f'Joined a guild. Name: {guild.name} | ID: {guild.id} | Owner: {guild.owner} | Members: {len(guild.members)}')

        time = utils.format_datetime(pendulum.now(tz='UTC'))
        embed = discord.Embed(colour=discord.Colour.gold(), title='Joined a guild',
                              description=f'`Name:` {guild.name}\n`ID:` {guild.id}\n`Owner:` {guild.owner}\n`Time:` {time}\n`Members:` {len(guild.members)}')
        embed.set_thumbnail(url=str(guild.icon.replace(format='gif' if guild.icon.is_animated() else 'png')))
        await self.bot.GUILD_LOG.send(embed=embed, avatar_url=guild.icon.replace(format='png'))

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild) -> None:

        __log__.info(f'Left a guild. Name: {guild.name} | ID: {guild.id} | Owner: {guild.owner} | Members: {len(guild.members)}')

        time = utils.format_datetime(pendulum.now(tz='UTC'))
        embed = discord.Embed(colour=discord.Colour.gold(), title='Left a guild',
                              description=f'`Name:` {guild.name}\n`ID:` {guild.id}\n`Owner:` {guild.owner}\n`Time:` {time}\n`Members:` {len(guild.members)}')
        embed.set_thumbnail(url=str(guild.icon.replace(format='gif' if guild.icon.is_animated() else 'png')))
        await self.bot.GUILD_LOG.send(embed=embed, avatar_url=guild.icon.replace(format='png'))

    # DM Logging

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:

        if config.ENV == enums.Environment.DEV:
            return

        if message.guild or message.is_system():
            return

        await self._log_dm(message)


def setup(bot: Life) -> None:
    bot.add_cog(Events(bot=bot))

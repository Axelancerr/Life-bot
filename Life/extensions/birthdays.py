import textwrap
from typing import Optional

import discord
import pendulum
from discord.ext import commands

from core import colours
from core.bot import Life
from utilities import context, converters, exceptions, utils


class Birthdays(commands.Cog):

    def __init__(self, bot: Life) -> None:
        self.bot = bot

    @commands.group(name='birthday', aliases=['birthdays', 'bd'], invoke_without_command=True)
    async def birthday(self, ctx: context.Context, *, person: Optional[discord.Member]) -> None:
        """
        Display yours or another members birthday.

        `person`: The person to display the birthday of. Can be their ID, Username, Nickname or @Mention, If not provided than your birthday will be displayed.
        """

        person = person or ctx.author
        user_config = self.bot.user_manager.get_config(person.id)

        if not user_config.birthday:
            raise exceptions.ArgumentError(f'`{person}` has not set their birthday. Use `{utils.format_command(self.bot.get_command("birthday set"))}` to set it.')
        if user_config.birthday_private and ctx.author.id != person.id:
            raise exceptions.ArgumentError(f'`{person}` has their birthday set as private. Use `{utils.format_command(self.bot.get_command("birthday public"))}` to change this.')

        embed = discord.Embed(
                colour=colours.MAIN,
                title=f'{person}\'s birthday information:',
                description=textwrap.dedent(
                        f'''
                        `Birthday:` {utils.format_date(user_config.birthday)}
                        `Next birthday date:` {utils.format_date(user_config.next_birthday)}
                        `Next birthday:` In {utils.format_difference(user_config.next_birthday)}
                        `Age:` {user_config.age}
                        '''
                )
        )
        await ctx.reply(embed=embed)

    @birthday.command(name='set')
    async def birthday_set(self, ctx: context.Context, *, date: converters.DatetimeConverter) -> None:
        """
        Set your birthday.

        `date`: Your birthday. This should include some form of date such as `tomorrow`, `in 3 weeks` or `1st january 2020`.
        """

        entries = {index: (date_phrase, datetime) for index, (date_phrase, datetime) in enumerate(date['found'].items())}
        if len(entries) != 1:
            choice = await ctx.choice(
                    entries=[f'`{index + 1}.` **{phrase}**\n`{utils.format_date(datetime)}`' for index, (phrase, datetime) in entries.items()],
                    per_page=5, title='Multiple dates were detected within your query:', header='Please select the number that best matches your birthday:\n\n'
            )
            result = entries[choice]
        else:
            result = entries[0]

        if result[1] > pendulum.now(tz='UTC').subtract(years=13) or result[1] < pendulum.now(tz='UTC').subtract(years=200):
            raise exceptions.ArgumentError('You must be more than 13 and less than 200 years old.')

        user_config = await self.bot.user_manager.get_or_create_config(ctx.author.id)

        await user_config.set_birthday(result[1])
        await ctx.reply(f'Your birthday has been set to `{utils.format_date(user_config.birthday)}`.')

    @birthday.command(name='reset')
    async def birthday_reset(self, ctx: context.Context) -> None:
        """
        Resets your birthday information.
        """

        user_config = await self.bot.user_manager.get_or_create_config(ctx.author.id)

        await user_config.set_birthday()
        await ctx.reply('Your birthday was reset.')

    @birthday.command(name='private')
    async def birthday_private(self, ctx: context.Context) -> None:
        """
        Make your birthday private.
        """

        user_config = await self.bot.user_manager.get_or_create_config(ctx.author.id)

        if user_config.birthday_private is True:
            raise exceptions.GeneralError('Your birthday is already private.')

        await user_config.set_birthday(user_config.birthday, private=True)
        await ctx.reply('Your birthday is now private.')

    @birthday.command(name='public')
    async def birthday_public(self, ctx: context.Context) -> None:
        """
        Make your birthday public.
        """

        user_config = await self.bot.user_manager.get_or_create_config(ctx.author.id)

        if user_config.birthday_private is False:
            raise exceptions.GeneralError('Your birthday is already public.')

        await user_config.set_birthday(user_config.birthday, private=False)
        await ctx.reply('Your birthday is now public.')

    @birthday.command(name='list', aliases=['upcoming'])
    async def birthday_upcoming(self, ctx: context.Context) -> None:
        """
        Display a list of upcoming birthdays in the server.
        """

        if not (birthdays := self.bot.user_manager.birthdays(guild_id=getattr(ctx.guild, 'id', None))):
            raise exceptions.ArgumentError('There are no users who have set their birthday, or everyone has set them to be private.')

        entries = [
            textwrap.dedent(
                    f'''
                    __**{ctx.guild.get_member(user_config.id)}:**__
                    `Birthday:` {utils.format_date(user_config.birthday)}
                    `Next birthday date:` {utils.format_date(user_config.next_birthday)}
                    `Next birthday:` In {utils.format_difference(user_config.next_birthday)}
                    `Age:` {user_config.age}
                    '''
            )
            for user_config in birthdays
        ]
        await ctx.paginate_embed(entries=entries, per_page=3, title='Upcoming birthdays:')

    @birthday.command(name='next')
    async def birthday_next(self, ctx: context.Context) -> None:
        """
        Display the next person to have a birthday in the server.
        """

        if not (birthdays := self.bot.user_manager.birthdays(guild_id=getattr(ctx.guild, 'id', None))):
            raise exceptions.ArgumentError('There are no users who have set their birthday, or everyone has set them to be private.')

        user_config = birthdays[0]
        member = ctx.guild.get_member(user_config.id)

        embed = discord.Embed(
                colour=colours.MAIN,
                title=f'{member}\'s birthday information:',
                description=textwrap.dedent(
                        f'''
                        `Birthday:` {utils.format_date(user_config.birthday)}
                        `Next birthday date:` {utils.format_date(user_config.next_birthday)}
                        `Next birthday:` In {utils.format_difference(user_config.next_birthday)}
                        `Age:` {user_config.age}
                        '''
                )
        )
        await ctx.reply(embed=embed)

    @birthday.command(name='card', aliases=['c'])
    async def birthday_card(self, ctx: context.Context) -> None:
        """
        Creates an image with the birthday month of all servers members.
        """

        async with ctx.typing():
            file = await self.bot.user_manager.create_birthday_card(guild_id=getattr(ctx.guild, 'id', None))
            await ctx.reply(file=file)


def setup(bot: Life) -> None:
    bot.add_cog(Birthdays(bot=bot))

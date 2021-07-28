import pendulum
import rapidfuzz
from discord.ext import commands
from pendulum.tz.timezone import Timezone

from utilities import context, exceptions


class TimezoneConverter(commands.Converter):

    async def convert(self, ctx: context.Context, argument: str) -> Timezone:

        if argument not in pendulum.timezones:
            msg = '\n'.join(f'- `{match}`' for match, _, _ in rapidfuzz.process.extract(query=argument, choices=pendulum.timezones, processor=lambda s: s))
            raise exceptions.ArgumentError(f'That was not a recognised timezone. Maybe you meant one of these?\n{msg}')

        return pendulum.timezone(argument)

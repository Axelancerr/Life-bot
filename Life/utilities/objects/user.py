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

from __future__ import annotations

import logging
import math
from typing import Any, Optional, TYPE_CHECKING

import pendulum
from pendulum.tz.timezone import Timezone

from utilities import enums, objects


if TYPE_CHECKING:
    from bot import Life

__log__ = logging.getLogger('utilities.objects.user')


class DefaultUserConfig:

    __slots__ = '_bot', '_id', '_created_at', '_blacklisted', '_blacklisted_reason', '_timezone', '_timezone_private', '_birthday', '_birthday_private', '_xp', '_coins', '_notifications', \
                '_reminders', '_todos', '_requires_db_update'

    def __init__(self, bot: Life, data: dict[str, Any]) -> None:

        self._bot: Life = bot

        self._id: int = data.get('id', 0)
        self._created_at: pendulum.DateTime = pendulum.instance(created_at, tz='UTC') if (created_at := data.get('created_at')) else pendulum.now(tz='UTC')

        self._blacklisted: bool = data.get('blacklisted', False)
        self._blacklisted_reason: Optional[str] = data.get('blacklisted_reason')

        self._timezone: Optional[Timezone] = pendulum.timezone(timezone) if (timezone := data.get('timezone')) else None
        self._timezone_private: bool = data.get('timezone_private', False)

        self._birthday: Optional[pendulum.Date] = pendulum.Date(birthday.year, birthday.month, birthday.day) if (birthday := data.get('birthday')) else None
        self._birthday_private: bool = data.get('birthday_private', False)

        self._xp: int = data.get('xp', 0)
        self._coins: int = data.get('coins', 0)

        self._notifications: Optional[objects.Notifications] = None
        self._reminders: dict[int, objects.Reminder] = {}
        self._todos: dict[int, objects.Todo] = {}

        self._requires_db_update: set[enums.Updateable] = set()

    def __repr__(self) -> str:
        return f'<DefaultUserConfig id=\'{self.id}\' blacklisted={self.blacklisted} timezone=\'{self.timezone}\' xp={self.xp} coins={self.coins} level={self.level}>'

    # Properties

    @property
    def bot(self) -> Life:
        return self._bot

    @property
    def id(self) -> int:
        return self._id

    @property
    def created_at(self) -> pendulum.DateTime:
        return self._created_at

    @property
    def blacklisted(self) -> bool:
        return self._blacklisted

    @property
    def blacklisted_reason(self) -> Optional[str]:
        return self._blacklisted_reason

    @property
    def timezone(self) -> Optional[Timezone]:
        return self._timezone

    @property
    def timezone_private(self) -> bool:
        return self._timezone_private

    @property
    def birthday(self) -> Optional[pendulum.Date]:
        return self._birthday

    @property
    def birthday_private(self) -> bool:
        return self._birthday_private

    @property
    def xp(self) -> int:
        return self._xp

    @property
    def coins(self) -> int:
        return self._coins

    @property
    def notifications(self) -> Optional[objects.Notifications]:
        return self._notifications

    @property
    def reminders(self) -> dict[int, objects.Reminder]:
        return self._reminders

    @property
    def todos(self) -> dict[int, objects.Todo]:
        return self._todos

    # Dynamic properties

    @property
    def age(self) -> Optional[int]:

        if not self.birthday:
            return None

        now = pendulum.now(tz='UTC')
        date = pendulum.date(year=now.year, month=now.month, day=now.day)

        return (date - self.birthday).in_years()

    @property
    def next_birthday(self) -> Optional[pendulum.DateTime]:

        if not self.birthday or not self.age:
            return None

        now = pendulum.now(tz='UTC')
        date = now.date()

        year = date.year if date < self.birthday.add(years=self.age) else self.birthday.year + self.age + 1
        return now.set(year=year, month=self.birthday.month, day=self.birthday.day, hour=0, minute=0, second=0, microsecond=0)

    @property
    def time(self) -> Optional[pendulum.DateTime]:

        if not self.timezone:
            return None

        return pendulum.now(tz=self.timezone)

    @property
    def level(self) -> int:
        return math.floor((((self.xp / 100) ** (1.0 / 1.5)) / 3))

    @property
    def next_level_xp(self) -> int:
        return round((((((self.level + 1) * 3) ** 1.5) * 100) - self.xp))


class UserConfig(DefaultUserConfig):

    def __repr__(self) -> str:
        return f'<UserConfig id=\'{self.id}\' blacklisted={self.blacklisted} timezone=\'{self.timezone}\' xp={self.xp} coins={self.coins} level={self.level}>'

    # Config

    async def set_blacklisted(self, blacklisted: bool, *, reason: Optional[str] = None) -> None:

        data = await self.bot.db.fetchrow(
                'UPDATE users SET blacklisted = $1, blacklisted_reason = $2 WHERE id = $3 RETURNING blacklisted, blacklisted_reason',
                blacklisted, reason, self.id
        )

        self._blacklisted = data['blacklisted']
        self._blacklisted_reason = data['blacklisted_reason']

    async def set_timezone(self, timezone: Timezone, *, private: Optional[bool] = None) -> None:

        private = self.timezone_private if private is None else private

        data = await self.bot.db.fetchrow('UPDATE users SET timezone = $1, timezone_private = $2 WHERE id = $3 RETURNING timezone, timezone_private', timezone.name, private, self.id)
        self._timezone = pendulum.timezone(tz) if (tz := data.get('timezone')) else None
        self._timezone_private = private

    async def set_birthday(self, birthday: pendulum.Date, *, private: Optional[bool] = None) -> None:

        private = self.timezone_private if private is None else private

        data = await self.bot.db.fetchrow('UPDATE users SET birthday = $1, birthday_private = $2 WHERE id = $3 RETURNING birthday, birthday_private', birthday, private, self.id)
        self._birthday = pendulum.Date(year=birthday.year, month=birthday.month, day=birthday.day) if (birthday := data.get('birthday')) else None
        self._birthday_private = private

    def change_coins(self, coins: int, *, operation: enums.Operation = enums.Operation.ADD) -> None:

        if operation == enums.Operation.SET:
            self._coins = coins
        elif operation == enums.Operation.ADD:
            self._coins += coins
        elif operation == enums.Operation.MINUS:
            self._coins -= coins

        self._requires_db_update.add(enums.Updateable.COINS)

    def change_xp(self, xp: int, *, operation: enums.Operation = enums.Operation.ADD) -> None:

        if operation == enums.Operation.SET:
            self._xp = xp
        elif operation == enums.Operation.ADD:
            self._xp += xp
        elif operation == enums.Operation.MINUS:
            self._xp -= xp

        self._requires_db_update.add(enums.Updateable.XP)

    # Reminders

    async def create_reminder(
            self, *, channel_id: int, datetime: pendulum.DateTime, content: str, jump_url: Optional[str] = None, repeat_type: enums.ReminderRepeatType = enums.ReminderRepeatType.NEVER
    ) -> objects.Reminder:

        data = await self.bot.db.fetchrow(
                'INSERT INTO reminders (user_id, channel_id, datetime, content, jump_url, repeat_type) VALUES ($1, $2, $3, $4, $5, $6) RETURNING *',
                self.id, channel_id, datetime, content, jump_url, repeat_type.value
        )

        reminder = objects.Reminder(bot=self.bot, user_config=self, data=data)
        self._reminders[reminder.id] = reminder

        if not reminder.done:
            reminder.schedule()

        __log__.info(f'[REMINDERS] Created reminder with id \'{reminder.id}\'for user with id \'{reminder.user_id}\'.')
        return reminder

    def get_reminder(self, reminder_id: int) -> Optional[objects.Reminder]:
        return self.reminders.get(reminder_id)

    async def delete_reminder(self, reminder_id: int) -> None:

        if not (reminder := self.get_reminder(reminder_id)):
            return

        await reminder.delete()

    # Todos

    async def create_todo(self, *, content: str, jump_url: Optional[str] = None) -> objects.Todo:

        data = await self.bot.db.fetchrow('INSERT INTO todos (user_id, content, jump_url) VALUES ($1, $2, $3) RETURNING *', self.id, content, jump_url)

        todo = objects.Todo(bot=self.bot, user_config=self, data=data)
        self._todos[todo.id] = todo

        __log__.info(f'[TODOS] Created todo with id \'{todo.id}\'for user with id \'{todo.user_id}\'.')
        return todo

    def get_todo(self, todo_id: int) -> Optional[objects.Todo]:
        return self.todos.get(todo_id)

    async def delete_todo(self, todo_id: int) -> None:

        if not (todo := self.get_todo(todo_id)):
            return

        await todo.delete()

    # Misc

    async def delete(self) -> None:

        await self.bot.db.execute('DELETE FROM users WHERE id = $1', self.id)

        for reminder in self.reminders.values():
            if not reminder.done:
                self.bot.scheduler.cancel(reminder.task)

        del self.bot.user_manager.configs[self.id]

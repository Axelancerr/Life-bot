import asyncio
import collections
import random


class Queue:

    def __init__(self, bot, guild):

        self.bot = bot
        self.guild = guild

        self.loop = asyncio.get_event_loop()
        self.getters = collections.deque()
        self.putters = collections.deque()
        self.unfinished_tasks = 0
        self.finished = asyncio.locks.Event(loop=self.loop)
        self.finished.set()

        self.queue_list = []

    def __repr__(self):
        return f"<LifeMusicQueue entries={self.size}>"

    @staticmethod
    def wakeup_next(waiters):

        while waiters:
            waiter = waiters.popleft()
            if not waiter.done():
                waiter.set_result(None)
                break

    def task_done(self):

        if self.unfinished_tasks <= 0:
            raise ValueError('task_done() called too many times')
        self.unfinished_tasks -= 1
        if self.unfinished_tasks == 0:
            self.finished.set()

    @property
    def is_empty(self):

        if not self.queue_list:
            return True
        return False

    @property
    def size(self):

        return len(self.queue_list)

    def clear(self):

        self.queue_list.clear()

    def reverse(self):

        self.queue_list.reverse()

    def shuffle(self):

        random.shuffle(self.queue_list)

    def extend(self, items: list):

        self.queue_list.extend(items)
        self.bot.dispatch(f"{self.guild.id}_queue_add")

    def put(self, item):

        self.queue_list.append(item)
        self.bot.dispatch(f"{self.guild.id}_queue_add")

    def put_pos(self, item, position: int = 0):

        self.queue_list.insert(position, item)
        self.bot.dispatch(f"{self.guild.id}_queue_add")

    async def get(self):

        while self.is_empty:
            getter = self.loop.create_future()
            self.getters.append(getter)
            try:
                await getter
            except Exception:
                getter.cancel()
                try:
                    self.getters.remove(getter)
                except ValueError:
                    pass
                if not self.is_empty and not getter.cancelled():
                    self.wakeup_next(self.getters)
                raise
        self.wakeup_next(self.putters)

        return self.queue_list.pop(0)

    async def get_pos(self, position: int = 0):

        while self.is_empty:
            getter = self.loop.create_future()
            self.getters.append(getter)
            try:
                await getter
            except Exception:
                getter.cancel()
                try:
                    self.getters.remove(getter)
                except ValueError:
                    pass
                if not self.is_empty and not getter.cancelled():
                    self.wakeup_next(self.getters)
                raise
        self.wakeup_next(self.putters)

        return self.queue_list.pop(position)

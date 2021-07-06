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

import logging
from typing import Optional

import discord
from discord.ext import commands

from core import colours, emojis
from core.bot import Life
from utilities import converters, exceptions
from utilities.context import Context


__log__: logging.Logger = logging.getLogger("cogs.todos")


def setup(bot: Life) -> None:
    bot.add_cog(Todo(bot))


class Todo(commands.Cog):

    def __init__(self, bot: Life) -> None:
        self.bot = bot

    @commands.group(name="todo", aliases=["todos"], invoke_without_command=True)
    async def todo(self, ctx: Context, *, content: Optional[str]) -> None:
        """
        Creates a todo.

        `content`: The content of your todo. Must be under 150 characters.

        **Usage:**
        `l-todo Finish documentation`
        """

        if content is not None:
            await ctx.invoke(self.todo_add, content=content)
            return

        user_config = await self.bot.user_manager.get_or_create_config(ctx.author.id)

        if not user_config.todos:
            raise exceptions.EmbedError(colour=colours.RED, description=f"{emojis.CROSS}  You don't have any todos.")

        await ctx.paginate_embed(
                entries=[f"[`**{todo.id}:**`]({todo.jump_url}) {todo.content}" for todo in user_config.todos.values()],
                per_page=10,
                title=f"Todo list for **{ctx.author}**:"
        )

    @todo.command(name="list")
    async def todo_list(self, ctx: Context) -> None:
        """
        Shows your todos.

        **Usage:**
        `l-todo list`
        """

        await ctx.invoke(self.todo, content=None)

    @todo.command(name="add", aliases=["make", "create"])
    async def todo_add(self, ctx: Context, *, content: converters.TodoContentConverter) -> None:
        """
        Creates a todo.

        `content`: The content of your todo. Must be under 150 characters.

        **Usage:**
        `l-todo Finish documentation`
        """

        user_config = await self.bot.user_manager.get_or_create_config(ctx.author.id)

        if len(user_config.todos) > 100:
            raise exceptions.EmbedError(colour=colours.RED, description=f"{emojis.CROSS}  You have 100 todos, try finishing some before adding any more.")

        todo = await user_config.create_todo(content=str(content), jump_url=ctx.message.jump_url)

        embed = discord.Embed(colour=colours.GREEN, description=f"{emojis.TICK}  Todo **{todo.id}** created.")
        await ctx.reply(embed=embed)

    @todo.command(name="delete", aliases=["remove"])
    async def todo_delete(self, ctx: Context, todo_ids: commands.Greedy[int]) -> None:
        """
        Deletes todos.

        `todo_ids`: A list of todo ids to delete, separated by spaces.

        **Usage:**
        `l-todo delete 1 2`
        """

        user_config = await self.bot.user_manager.get_or_create_config(ctx.author.id)

        if not user_config.todos:
            raise exceptions.EmbedError(colour=colours.RED, description=f"{emojis.CROSS}  You don't have any todos.")

        todos = set()

        for todo_id in todo_ids:

            if not (todo := user_config.get_todo(todo_id)):
                raise exceptions.EmbedError(colour=colours.RED, description=f"{emojis.CROSS}  You don't have a todo with id **{todo_id}**.")

            todos.add(todo)

        for todo in todos:
            await todo.delete()

        await ctx.paginate_embed(
                entries=[f"[`**{todo.id}:**`]({todo.jump_url}) {todo.content}" for todo in todos],
                per_page=10,
                colour=colours.GREEN,
                title=f"{emojis.TICK}  Deleted **{len(todos)}** todo{'s' if len(todos) > 1 else ''}:"
        )

    @todo.command(name="clear")
    async def todo_clear(self, ctx: Context) -> None:
        """
        Clears your todos.

        **Usage:**
        `l-todo clear`
        """

        user_config = await self.bot.user_manager.get_or_create_config(ctx.author.id)

        if not user_config.todos:
            raise exceptions.EmbedError(colour=colours.RED, description=f"{emojis.CROSS}  You don't have any todos.")

        for todo in user_config.todos.copy().values():
            await todo.delete()

        embed = discord.Embed(colour=colours.GREEN, description=f"{emojis.TICK}  Cleared your todo list.")
        await ctx.reply(embed=embed)

    @todo.command(name="edit", aliases=["update"])
    async def todo_edit(self, ctx: Context, todo_id: int, *, content: converters.TodoContentConverter) -> None:
        """
        Edits a todo.

        `todo_id`: The id of the todo to edit.
        `content`: The content of the todo.
        """

        user_config = await self.bot.user_manager.get_or_create_config(ctx.author.id)

        if not user_config.todos:
            raise exceptions.EmbedError(colour=colours.RED, description=f"{emojis.CROSS}  You don't have any todos.")

        if not (todo := user_config.get_todo(todo_id)):
            raise exceptions.EmbedError(colour=colours.RED, description=f"{emojis.CROSS}  You don't have a todo with id **{todo_id}**.")

        await todo.change_content(content=str(content), jump_url=ctx.message.jump_url)

        embed = discord.Embed(colour=colours.GREEN, description=f"{emojis.TICK}  Edited content of todo.")
        await ctx.reply(embed=embed)
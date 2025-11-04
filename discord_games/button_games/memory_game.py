from __future__ import annotations

from typing import Optional, ClassVar
import random
import asyncio

import discord
from discord.ext import commands

from ..utils import *


class MemoryButton(discord.ui.Button["MemoryView"]):
    def __init__(self, emoji: str, *, row: int = 0) -> None:
        self.value = emoji
        super().__init__(label="\u200b", style=discord.ButtonStyle.grey, row=row)

    async def callback(self, interaction: discord.Interaction) -> None:
        view = self.view
        game = view.game

        # If stop button was pressed or already game over
        if view.stopped:
            return await interaction.response.defer()

        # First click
        if view.first is None:
            self.emoji = self.value
            self.style = discord.ButtonStyle.blurple
            self.disabled = True
            view.first = self
            await interaction.response.edit_message(view=view)
            return

        # Second click
        elif view.second is None and self != view.first:
            self.emoji = self.value
            self.style = discord.ButtonStyle.primary  # purple-like
            self.disabled = True
            view.second = self
            game.moves += 1
            game.embed.set_field_at(0, name="\u200b", value=f"Moves: `{game.moves}`")
            await interaction.response.edit_message(view=view, embed=game.embed)

            # Check match
            if view.first.value == view.second.value:
                view.first.style = discord.ButtonStyle.success
                view.second.style = discord.ButtonStyle.success
                view.first = None
                view.second = None

                # check win condition
                if all(b.disabled for b in view.children if isinstance(b, discord.ui.Button) and b.value):
                    await interaction.message.edit(content="🎉 Game Over, You Won!", view=view)
                    view.stop()
            else:
                await asyncio.sleep(view.pause_time)

                # Reset both
                for b in (view.first, view.second):
                    b.emoji = None
                    b.style = discord.ButtonStyle.grey
                    b.disabled = False

                view.first = None
                view.second = None

                await interaction.message.edit(view=view, embed=game.embed)

        else:
            await interaction.response.defer()


class StopButton(discord.ui.Button):
    def __init__(self):
        super().__init__(emoji="🛑", style=discord.ButtonStyle.danger, row=4)

    async def callback(self, interaction: discord.Interaction):
        view: MemoryView = self.view
        view.stopped = True

        for child in view.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
                if child != self:
                    child.style = discord.ButtonStyle.danger

        await interaction.response.edit_message(
            content="🟥 **Game Stopped!**", view=view
        )
        view.stop()


class MemoryView(BaseView):
    DEFAULT_ITEMS: ClassVar[list[str]] = [
        "🥝", "🍓", "🍹", "🍋",
        "🥭", "🍎", "🍊", "🍍",
        "🍑", "🍇", "🍉", "🥬",
    ]

    def __init__(
        self,
        game: MemoryGame,
        items: list[str],
        *,
        pause_time: float,
        timeout: Optional[float] = None,
    ) -> None:
        super().__init__(timeout=timeout)
        self.game = game
        self.pause_time = pause_time
        self.first: Optional[MemoryButton] = None
        self.second: Optional[MemoryButton] = None
        self.stopped: bool = False

        if not items:
            items = self.DEFAULT_ITEMS[:]
        assert len(items) == 12

        items *= 2
        random.shuffle(items)
        random.shuffle(items)
        items.insert(12, None)

        board = chunk(items, count=5)

        for i, row in enumerate(board):
            for item in row:
                if item:
                    button = MemoryButton(item, row=i)
                    self.add_item(button)
                else:
                    stop = StopButton()
                    stop.row = i
                    self.add_item(stop)


class MemoryGame:
    """
    Memory Game with matching logic and color animations.
    """

    def __init__(self) -> None:
        self.embed_color: Optional[DiscordColor] = None
        self.embed: Optional[discord.Embed] = None
        self.moves: int = 0

    async def start(
        self,
        ctx: commands.Context[commands.Bot],
        *,
        embed_color: DiscordColor = DEFAULT_COLOR,
        items: list[str] = [],
        pause_time: float = 0.7,
        timeout: Optional[float] = None,
    ) -> discord.Message:
        self.embed_color = embed_color
        self.embed = discord.Embed(
            description="🧩 **Memory Game**",
            color=self.embed_color
        )
        self.embed.add_field(name="\u200b", value="Moves: `0`")

        self.view = MemoryView(
            game=self,
            items=items,
            pause_time=pause_time,
            timeout=timeout,
        )

        self.message = await ctx.send(embed=self.embed, view=self.view)
        await double_wait(
            wait_for_delete(ctx, self.message),
            self.view.wait(),
        )
        return self.message

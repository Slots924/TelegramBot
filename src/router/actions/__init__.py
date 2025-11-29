"""Збірник хендлерів дій для LLMRouter."""

from src.router.actions.add_reaction_action import handle_add_reaction
from src.router.actions.fake_typing_action import handle_fake_typing
from src.router.actions.ignore_action import handle_ignore
from src.router.actions.send_messages_action import handle_send_messages
from src.router.actions.send_message_action import handle_send_message
from src.router.actions.wait_action import handle_wait

__all__ = [
    "handle_add_reaction",
    "handle_fake_typing",
    "handle_ignore",
    "handle_send_messages",
    "handle_send_message",
    "handle_wait",
]

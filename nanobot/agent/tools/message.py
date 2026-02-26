"""Message tool for sending messages to users."""

from typing import Any, Awaitable, Callable
from contextvars import ContextVar

from nanobot.agent.tools.base import Tool
from nanobot.bus.events import OutboundMessage

# Context variables for thread-safe state management
_channel_ctx: ContextVar[str] = ContextVar("message_tool_channel", default="")
_chat_id_ctx: ContextVar[str] = ContextVar("message_tool_chat_id", default="")
_message_id_ctx: ContextVar[str | None] = ContextVar("message_tool_message_id", default=None)
_sent_in_turn_ctx: ContextVar[bool] = ContextVar("message_tool_sent_in_turn", default=False)


class MessageTool(Tool):
    """Tool to send messages to users on chat channels."""

    def __init__(
        self,
        send_callback: Callable[[OutboundMessage], Awaitable[None]] | None = None,
        default_channel: str = "",
        default_chat_id: str = "",
        default_message_id: str | None = None,
    ):
        self._send_callback = send_callback
        # Initialize defaults if provided (though context vars are preferred)
        if default_channel:
            _channel_ctx.set(default_channel)
        if default_chat_id:
            _chat_id_ctx.set(default_chat_id)
        if default_message_id:
            _message_id_ctx.set(default_message_id)

    def set_context(self, channel: str, chat_id: str, message_id: str | None = None) -> None:
        """Set the current message context."""
        _channel_ctx.set(channel)
        _chat_id_ctx.set(chat_id)
        _message_id_ctx.set(message_id)

    def set_send_callback(self, callback: Callable[[OutboundMessage], Awaitable[None]]) -> None:
        """Set the callback for sending messages."""
        self._send_callback = callback

    def start_turn(self) -> None:
        """Reset per-turn send tracking."""
        _sent_in_turn_ctx.set(False)
    
    @property
    def _sent_in_turn(self) -> bool:
        return _sent_in_turn_ctx.get()

    @property
    def name(self) -> str:
        return "message"

    @property
    def description(self) -> str:
        return "Send a message to the user. Use this when you want to communicate something."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The message content to send"
                },
                "channel": {
                    "type": "string",
                    "description": "Optional: target channel (telegram, discord, etc.)"
                },
                "chat_id": {
                    "type": "string",
                    "description": "Optional: target chat/user ID"
                },
                "media": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: list of file paths to attach (images, audio, documents)"
                }
            },
            "required": ["content"]
        }

    async def execute(
        self,
        content: str,
        channel: str | None = None,
        chat_id: str | None = None,
        message_id: str | None = None,
        media: list[str] | None = None,
        **kwargs: Any
    ) -> str:
        channel = channel or _channel_ctx.get()
        chat_id = chat_id or _chat_id_ctx.get()
        message_id = message_id or _message_id_ctx.get()

        if not channel or not chat_id:
            return "Error: No target channel/chat specified"

        if not self._send_callback:
            return "Error: Message sending not configured"

        msg = OutboundMessage(
            channel=channel,
            chat_id=chat_id,
            content=content,
            media=media or [],
            metadata={
                "message_id": message_id,
            }
        )

        try:
            await self._send_callback(msg)
            _sent_in_turn_ctx.set(True)
            media_info = f" with {len(media)} attachments" if media else ""
            return f"Message sent to {channel}:{chat_id}{media_info}"
        except Exception as e:
            return f"Error sending message: {str(e)}"

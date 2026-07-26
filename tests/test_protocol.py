"""Tests for the agent communication protocol."""

from core.protocol import AgentMessage


class TestAgentMessage:
    def test_create_message(self):
        msg = AgentMessage(sender="supervisor", receiver="coder", task="write code")
        assert msg.sender == "supervisor"
        assert msg.receiver == "coder"
        assert msg.task == "write code"
        assert msg.status == "pending"
        assert msg.timestamp is not None

    def test_reply_swaps_sender_receiver(self):
        msg = AgentMessage(sender="supervisor", receiver="coder", task="debug")
        reply = msg.reply("fixed it", status="completed")
        assert reply.sender == "coder"
        assert reply.receiver == "supervisor"
        assert reply.task == "debug"
        assert reply.response == "fixed it"
        assert reply.status == "completed"

    def test_reply_preserves_conversation_id(self):
        msg = AgentMessage(
            sender="a", receiver="b", task="x",
            conversation_id="conv-123",
        )
        reply = msg.reply("done")
        assert reply.conversation_id == "conv-123"

    def test_to_dict(self):
        msg = AgentMessage(sender="s", receiver="r", task="t", response="resp")
        d = msg.to_dict()
        assert d["sender"] == "s"
        assert d["receiver"] == "r"
        assert d["task"] == "t"
        assert d["response"] == "resp"
        assert d["status"] == "pending"

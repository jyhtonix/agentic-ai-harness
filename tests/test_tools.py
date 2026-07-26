"""Tests for the tool modules."""

import pytest
from tools.code_runner import run, _validate


class TestCodeRunner:
    @pytest.mark.asyncio
    async def test_simple_print(self):
        result = await run("print('hello')")
        assert "hello" in result["stdout"]
        assert result["stderr"] == ""

    @pytest.mark.asyncio
    async def test_os_import_blocked(self):
        with pytest.raises(PermissionError, match="Import not allowed"):
            _validate("import os")

    @pytest.mark.asyncio
    async def test_subprocess_import_blocked(self):
        with pytest.raises(PermissionError, match="Import not allowed"):
            _validate("from subprocess import run")

    @pytest.mark.asyncio
    async def test_syntax_error(self):
        with pytest.raises(ValueError, match="Syntax error"):
            await run("def broken(")

    @pytest.mark.asyncio
    async def test_runtime_error_caught(self):
        result = await run("1/0")
        assert "ZeroDivisionError" in result["stderr"]

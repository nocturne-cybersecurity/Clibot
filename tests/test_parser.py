"""Tests for parser functionality."""
import pytest
from core.parser import Parser, Risk
from core.context import Context


@pytest.fixture
def parser():
    """Create a parser instance."""
    return Parser()


@pytest.fixture
def context():
    """Create a context instance."""
    return Context()


def test_parse_delete(parser, context):
    """Test parsing delete command."""
    plan = parser.parse("elimina /tmp/archivo.txt", context)
    assert plan is not None
    assert plan.operations
    assert plan.operations[0].name == 'delete'
    assert plan.operations[0].capability == 'filesystem'


def test_parse_create(parser, context):
    """Test parsing create command."""
    plan = parser.parse("crea archivo hola.txt", context)
    assert plan is not None
    assert plan.operations
    assert plan.operations[0].name == 'create'


def test_parse_move(parser, context):
    """Test parsing move command."""
    plan = parser.parse("mueve a.txt a /tmp", context)
    assert plan is not None
    assert plan.operations
    assert plan.operations[0].name == 'move'


def test_parse_mkdir(parser, context):
    """Test parsing mkdir command."""
    plan = parser.parse("crea carpeta /tmp/nueva", context)
    assert plan is not None
    assert plan.operations
    assert plan.operations[0].name == 'mkdir'


def test_parse_touch(parser, context):
    """Test parsing touch command."""
    plan = parser.parse("touch /tmp/archivo.txt", context)
    assert plan is not None
    assert plan.operations
    assert plan.operations[0].name == 'create'


def test_parse_edit(parser, context):
    """Test parsing edit command."""
    plan = parser.parse("modifica /tmp/archivo.txt", context)
    assert plan is not None
    assert plan.operations
    assert plan.operations[0].name == 'write'


def test_parse_apt_install(parser, context):
    """Test parsing apt install command."""
    plan = parser.parse("apt install vim", context)
    assert plan is not None
    assert plan.operations
    assert plan.operations[0].name == 'apt_install'
    assert plan.operations[0].capability == 'package_manager'


def test_parse_pip_install(parser, context):
    """Test parsing pip install command."""
    plan = parser.parse("pip install requests", context)
    assert plan is not None
    assert plan.operations
    assert plan.operations[0].name == 'pip_install'


def test_parse_npm_install(parser, context):
    """Test parsing npm install command."""
    plan = parser.parse("npm install lodash", context)
    assert plan is not None
    assert plan.operations
    assert plan.operations[0].name == 'npm_install'

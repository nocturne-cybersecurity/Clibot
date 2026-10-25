import pytest
from core.contracts import Operation, Plan
from core.planner import Planner

def test_orders_dependencies():
    a=Operation('x','a'); b=Operation('x','b',dependencies=[a.id])
    assert Planner().ordered(Plan([b,a]))==[a,b]

def test_rejects_cycle():
    a=Operation('x','a'); b=Operation('x','b',dependencies=[a.id]); a.dependencies=[b.id]
    with pytest.raises(ValueError):Planner().ordered(Plan([a,b]))

def test_intent_plugins_are_extensible_without_parser_edits():
    from intelligence.intent_registry import IntentRegistry
    registry=IntentRegistry()
    registry.register('hello',[r'\bhello\b'],lambda text,context:Plan([],text,'handled'),priority=10)
    assert registry.match('hello there').clarification=='handled'

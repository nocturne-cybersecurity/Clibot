"""Small priority router for independently developed intent plugins."""
from dataclasses import dataclass
import re
from typing import Callable
from intelligence.rules import normalize

@dataclass(frozen=True)
class IntentRule:
    name: str
    patterns: tuple[str, ...]
    handler: Callable
    priority: int = 50

class IntentRegistry:
    def __init__(self):self._rules={};self._compiled={}
    def register(self,name,patterns,handler,priority=50):
        if name in self._rules:raise ValueError(f'Intent already registered: {name}')
        compiled=tuple(re.compile(p,re.I) for p in patterns)
        if not compiled:raise ValueError('An intent needs at least one pattern')
        self._rules[name]=IntentRule(name,tuple(patterns),handler,priority)
        self._compiled[name]=compiled
    def match(self,text,context=None):
        normalized=normalize(text)
        for rule in sorted(self._rules.values(),key=lambda item:(-item.priority,item.name)):
            if any(pattern.search(normalized) for pattern in self._compiled[rule.name]):
                plan=rule.handler(text,context)
                if plan is not None:return plan
        return None
    @property
    def names(self):return tuple(sorted(self._rules))
intent_registry=IntentRegistry()

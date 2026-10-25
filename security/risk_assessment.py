"""Conservative baseline risk classification."""
from core.contracts import Risk
def assess(operation):
    value=operation.risk
    if operation.name in {'delete','format','partition'}:return Risk.DESTRUCTIVE
    if operation.name in {'change','install','remove','mount','unmount','scan'}:return Risk.HIGH
    return value

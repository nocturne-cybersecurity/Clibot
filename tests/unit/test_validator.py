import pytest
from core.contracts import Operation, Plan
from core.validator import Validator, ValidationError
from capabilities import registry

def test_accepts_registered_operation():Validator(registry).validate(Plan([Operation('system','info')]))

def test_rejects_missing_argument():
    with pytest.raises(ValidationError):Validator(registry).validate(Plan([Operation('filesystem','read',{})]))

def test_protected_path_rejected():
    with pytest.raises(ValidationError):Validator(registry).validate(Plan([Operation('filesystem','delete',{'path':'/etc'})]))

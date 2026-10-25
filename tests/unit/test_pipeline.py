import shutil, pytest
from execution.command import Command
from core.pipeline import run_pipeline

@pytest.mark.skipif(not shutil.which('printf') or not shutil.which('tr'),reason='basic Unix tools unavailable')
def test_two_stage_pipeline():
    result=run_pipeline([Command(shutil.which('printf'),['hello']),Command(shutil.which('tr'),['a-z','A-Z'])])
    assert result['success'] and result['stdout']=='HELLO'

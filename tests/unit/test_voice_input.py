import pytest

from interface.voice import VoiceInput, VoiceInputError, voice_command


@pytest.mark.parametrize('spoken', [
    'micro off',
    'micrófono off',
    'apaga el micrófono',
    'desactiva el microfono',
])
def test_spoken_microphone_off_maps_to_terminal_command(spoken):
    assert voice_command(spoken) == '/micro off'


def test_other_speech_is_preserved_as_a_natural_language_request():
    assert voice_command('abre chrome') == 'abre chrome'


def test_missing_speech_model_reports_setup_instructions(tmp_path):
    voice = VoiceInput(tmp_path / 'missing-model')
    with pytest.raises(VoiceInputError, match='pip install -e'):
        voice.prepare()

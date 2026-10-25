from capabilities.filesystem import create_file, listing, digest, copy, move, delete

def test_file_lifecycle(tmp_path):
    source=tmp_path/'a file.txt';create_file(source,'hello')
    assert 'a file.txt' in [x['name'] for x in listing(tmp_path)]
    assert len(digest(source))==64
    clone=tmp_path/'copy';copy(source,clone);assert clone.read_text()=='hello'
    moved=tmp_path/'moved';move(clone,moved);assert moved.exists()
    delete(moved);assert not moved.exists()

def test_move_file_into_existing_directory(tmp_path):
    source=tmp_path/'hello.txt';source.write_text('hello')
    destination=tmp_path/'Downloads';destination.mkdir()
    result=move(source,destination)
    assert result==str(destination/'hello.txt')
    assert not source.exists() and (destination/'hello.txt').read_text()=='hello'

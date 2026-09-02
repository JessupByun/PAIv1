from main import _is_pokernow_game_url


def test_accepts_pokernow_game_urls():
    assert _is_pokernow_game_url("https://www.pokernow.club/games/abc123")
    assert _is_pokernow_game_url("https://pokernow.club/games/abc123")
    assert _is_pokernow_game_url("https://www.pokernow.com/games/abc123")


def test_rejects_non_pokernow_urls():
    # The old startswith() check let a lookalike host through as long as the
    # string began with the expected prefix.
    assert not _is_pokernow_game_url("https://pokernow.club.evil.com/games/abc")
    assert not _is_pokernow_game_url("https://www.pokernow.club/sessions/new")
    assert not _is_pokernow_game_url("not a url")

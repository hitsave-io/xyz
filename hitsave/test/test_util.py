from hitsave.util import decorate_ansi


def test_decorate(snapshot):
    x = decorate_ansi("hello", bold=True, fg="blue")
    y = "I say " + x + " to you."
    snapshot.assert_match(y, "hello")

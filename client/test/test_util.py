from hitsave.util import decorate_ansi, human_size


def test_decorate(snapshot):
    x = decorate_ansi("hello", bold=True, fg="blue")
    y = "I say " + x + " to you."
    snapshot.assert_match(y, "hello")


def test_human_size(snapshot):
    sizes = [
        1,
        100,
        999,
        1000,
        1024,
        2000,
        2048,
        3000,
        9999,
        10000,
        2048000000,
        9990000000,
        9000000000000000000000,
    ]
    snapshot.assert_match("\n".join(map(human_size, sizes)) + "\n", "bytes")

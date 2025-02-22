from goats_tom.templatetags import starts_with


def test_starts_with():
    assert starts_with("Python", "Py")
    assert not starts_with("Python", "python")
    assert not starts_with(None, "Py")
    assert not starts_with(123, "1")
    assert not starts_with("", "anything")
    assert starts_with("anything", "")

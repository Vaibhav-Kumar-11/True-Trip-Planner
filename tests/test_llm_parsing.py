from tools.llm import _try_parse


def test_parses_plain_json():
    assert _try_parse('{"a": 1}') == {"a": 1}


def test_parses_json_wrapped_in_code_fence():
    text = '```json\n{"a": 1}\n```'
    assert _try_parse(text) == {"a": 1}


def test_parses_json_wrapped_in_plain_code_fence():
    text = '```\n{"a": 1}\n```'
    assert _try_parse(text) == {"a": 1}


def test_returns_none_for_invalid_json():
    assert _try_parse("this is not json") is None

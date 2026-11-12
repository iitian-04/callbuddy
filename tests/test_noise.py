from callbuddy.noise import is_noise


def test_noise_transcriptions_are_dropped():
    assert is_noise(".") and is_noise(" ... ") and is_noise("") and is_noise("-")
    assert not is_noise("Hello.") and not is_noise("7") and not is_noise("ok")

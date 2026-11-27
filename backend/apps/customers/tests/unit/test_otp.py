from apps.customers.domain.otp import generate_otp_code, hash_otp_code


def test_generate_otp_code_is_six_digits():
    code = generate_otp_code()

    assert len(code) == 6
    assert code.isdigit()


def test_generate_otp_code_varies_across_calls():
    codes = {generate_otp_code() for _ in range(20)}

    assert len(codes) > 1


def test_hash_otp_code_is_deterministic_and_never_the_raw_code():
    code = "042017"

    digest = hash_otp_code(code)

    assert digest == hash_otp_code(code)
    assert digest != code

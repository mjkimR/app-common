import bcrypt
from app_prebuilt_user.passwords import PasswordHasher
from app_prebuilt_user.throttle import FailedLoginThrottle

hasher = PasswordHasher()


def test_new_hashes_are_argon2id_and_verify():
    hashed = hasher.hash("password123")

    assert hashed.startswith("$argon2id$")
    assert hasher.verify("password123", hashed)
    assert not hasher.verify("password124", hashed)
    assert not hasher.needs_rehash(hashed)


def test_a_bcrypt_hash_written_before_still_verifies_and_asks_for_a_rehash():
    legacy = bcrypt.hashpw(b"password123", bcrypt.gensalt(rounds=4)).decode()

    assert hasher.verify("password123", legacy)
    assert not hasher.verify("wrong", legacy)
    assert hasher.needs_rehash(legacy)


def test_a_long_password_verifies_against_bcrypt_the_way_it_was_hashed():
    # bcrypt only ever read the first 72 bytes; hashes written through passlib relied on that.
    password = "x" * 100
    legacy = bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt(rounds=4)).decode()

    assert hasher.verify(password, legacy)


def test_a_value_that_is_no_hash_never_verifies():
    assert not hasher.verify("password123", "not-a-hash")
    assert not hasher.verify("password123", "")
    assert hasher.needs_rehash("not-a-hash")


def test_failed_logins_expire_and_a_lockout_ends():
    throttle = FailedLoginThrottle(max_failures=3, window_seconds=60, lockout_seconds=300)

    assert throttle.record_failure("a", 0.0) is False
    assert throttle.record_failure("a", 1.0) is False
    # The early failures have left the window, so this one starts no lockout.
    assert throttle.record_failure("a", 100.0) is False
    assert throttle.record_failure("a", 101.0) is False
    assert throttle.record_failure("a", 102.0) is True
    assert throttle.retry_after("a", 103.0) == 299
    assert throttle.retry_after("a", 402.0) is None
    assert throttle.retry_after("b", 103.0) is None

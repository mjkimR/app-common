"""Password hashing: Argon2id for new hashes, bcrypt accepted for hashes written before it."""

import bcrypt
from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import InvalidHashError, VerificationError

# bcrypt reads at most 72 bytes. Hashes written through passlib used that silent truncation, so verifying them
# has to keep it; bcrypt >= 5 raises on longer input instead.
_BCRYPT_MAX_BYTES = 72
_BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


class PasswordHasher:
    def __init__(self) -> None:
        self._argon2 = Argon2Hasher()
        # Verified against when the account does not exist, so a missing account costs as much as a wrong password.
        self._dummy_hash = self._argon2.hash("dummy-password-for-constant-time-verification")

    def hash(self, password: str) -> str:
        return self._argon2.hash(password)

    def verify(self, password: str, hashed_password: str) -> bool:
        if hashed_password.startswith(_BCRYPT_PREFIXES):
            try:
                return bcrypt.checkpw(password.encode()[:_BCRYPT_MAX_BYTES], hashed_password.encode())
            except ValueError:
                return False
        try:
            return self._argon2.verify(hashed_password, password)
        except (VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, hashed_password: str) -> bool:
        """True for a bcrypt hash, and for an Argon2 hash made with weaker parameters than the current ones."""
        if hashed_password.startswith(_BCRYPT_PREFIXES):
            return True
        try:
            return self._argon2.check_needs_rehash(hashed_password)
        except InvalidHashError:
            return True

    def dummy_verify(self) -> None:
        self.verify("not-the-password", self._dummy_hash)

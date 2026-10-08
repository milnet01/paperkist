"""Everything Paperkist encrypts or decrypts. The only module that imports nacl.

The formats written here are fixed by docs/specs/DEED-0002-vault-format.md
(§ 4.2 the key record, § 4.3 content streams and sealed messages, § 4.4 the
associated data). A vault on a stranger's disk depends on every byte, so a
change here is a format change.
"""

from __future__ import annotations

import base64
import binascii
import json
import unicodedata
from typing import BinaryIO

import nacl.bindings as sodium
import nacl.exceptions
import nacl.pwhash.argon2id as argon2id
import nacl.utils

from paperkist.errors import NotEnoughMemory, VaultCorrupt, VaultTooNew, WrongPassword

KEY_RECORD_VERSION = 1
PIECE = 65536  # plaintext bytes per secretstream piece

_KEY_BYTES = 32
_SALT_BYTES = argon2id.SALTBYTES
_NONCE_BYTES = sodium.crypto_aead_xchacha20poly1305_ietf_NPUBBYTES
_TAG_BYTES = sodium.crypto_aead_xchacha20poly1305_ietf_ABYTES
_STREAM_HEADER = sodium.crypto_secretstream_xchacha20poly1305_HEADERBYTES
_PIECE_OUT = PIECE + sodium.crypto_secretstream_xchacha20poly1305_ABYTES
_MESSAGE = sodium.crypto_secretstream_xchacha20poly1305_TAG_MESSAGE
_FINAL = sodium.crypto_secretstream_xchacha20poly1305_TAG_FINAL

# The only settings unlock() will derive with. The folder is untrusted, so a
# record outside these is refused before it can hang an open (§ 4.2).
_OPSLIMIT_RANGE = range(1, 21)
_MEMLIMIT_MIN = 8192
_MEMLIMIT_MAX = 4 * 2**30


def associated_data(role: str, fmt: int, doc_id: str = "") -> bytes:
    """The bytes every ciphertext is bound to (§ 4.4)."""
    return b"\x00".join(
        [
            # The app's old name, kept: existing vaults need it (DEED-0023).
            b"deedbox",
            role.encode("ascii"),
            str(fmt).encode("ascii"),
            doc_id.encode("ascii"),
        ]
    )


def new_key_record(
    password: str, *, opslimit: int | None = None, memlimit: int | None = None
) -> tuple[bytes, bytes]:
    """A new random vault key, and the record that unlocks it with `password`."""
    ops = argon2id.OPSLIMIT_MODERATE if opslimit is None else opslimit
    mem = argon2id.MEMLIMIT_MODERATE if memlimit is None else memlimit
    salt = nacl.utils.random(_SALT_BYTES)
    vault_key = nacl.utils.random(_KEY_BYTES)
    nonce = nacl.utils.random(_NONCE_BYTES)
    wrapped = sodium.crypto_aead_xchacha20poly1305_ietf_encrypt(
        vault_key,
        associated_data("key", KEY_RECORD_VERSION),
        nonce,
        _derive(password, salt, ops, mem),
    )
    record = {
        "version": KEY_RECORD_VERSION,
        "kdf": "argon2id13",
        "opslimit": ops,
        "memlimit": mem,
        "parallelism": 1,
        "salt": _b64(salt),
        "wrap": "xchacha20poly1305-ietf",
        "nonce": _b64(nonce),
        "wrapped_key": _b64(wrapped),
    }
    return json.dumps(record).encode("utf-8"), vault_key


def unlock(key_record: bytes, password: str) -> bytes:
    """The vault key inside `key_record`, if `password` opens it."""
    try:
        record = json.loads(key_record.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as err:
        raise VaultCorrupt("the key record is not valid JSON") from err
    if not isinstance(record, dict):
        raise VaultCorrupt("the key record is not an object")

    version = record.get("version")
    if _is_int(version) and version > KEY_RECORD_VERSION:
        raise VaultTooNew(f"key record version {version}")
    ops, mem = record.get("opslimit"), record.get("memlimit")
    if not (
        version == KEY_RECORD_VERSION
        and record.get("kdf") == "argon2id13"
        and record.get("wrap") == "xchacha20poly1305-ietf"
        and record.get("parallelism") == 1
        and _is_int(ops)
        and ops in _OPSLIMIT_RANGE
        and _is_int(mem)
        and _MEMLIMIT_MIN <= mem <= _MEMLIMIT_MAX
    ):
        raise VaultCorrupt("the key record's settings are not ones Paperkist writes")
    salt = _unb64(record.get("salt"), _SALT_BYTES)
    nonce = _unb64(record.get("nonce"), _NONCE_BYTES)
    wrapped = _unb64(record.get("wrapped_key"), _KEY_BYTES + _TAG_BYTES)

    kek = _derive(password, salt, ops, mem)
    try:
        return sodium.crypto_aead_xchacha20poly1305_ietf_decrypt(
            wrapped, associated_data("key", KEY_RECORD_VERSION), nonce, kek
        )
    except nacl.exceptions.CryptoError as err:
        raise WrongPassword from err


def seal(key: bytes, plaintext: bytes, ad: bytes) -> bytes:
    """One sealed message: nonce followed by ciphertext."""
    nonce = nacl.utils.random(_NONCE_BYTES)
    return nonce + sodium.crypto_aead_xchacha20poly1305_ietf_encrypt(
        plaintext, ad, nonce, key
    )


def unseal(key: bytes, blob: bytes, ad: bytes) -> bytes:
    if len(blob) < _NONCE_BYTES + _TAG_BYTES:
        raise VaultCorrupt("sealed message too short")
    try:
        return sodium.crypto_aead_xchacha20poly1305_ietf_decrypt(
            blob[_NONCE_BYTES:], ad, blob[:_NONCE_BYTES], key
        )
    except nacl.exceptions.CryptoError as err:
        raise VaultCorrupt("sealed message failed to decrypt") from err


def encrypt_stream(key: bytes, src: BinaryIO, dst: BinaryIO, ad: bytes) -> None:
    """Write `src` to `dst` as a secretstream. The last piece is always short."""
    state = sodium.crypto_secretstream_xchacha20poly1305_state()
    dst.write(sodium.crypto_secretstream_xchacha20poly1305_init_push(state, key))
    piece = _read_exactly(src, PIECE)
    while len(piece) == PIECE:
        dst.write(
            sodium.crypto_secretstream_xchacha20poly1305_push(
                state, piece, ad, _MESSAGE
            )
        )
        piece = _read_exactly(src, PIECE)
    dst.write(
        sodium.crypto_secretstream_xchacha20poly1305_push(state, piece, ad, _FINAL)
    )


def decrypt_stream(key: bytes, src: BinaryIO, dst: BinaryIO, ad: bytes) -> None:
    """Decrypt a secretstream from `src` into `dst`.

    Secretstream does not notice a stream cut short, so this requires the
    last piece to be the only one tagged final, short, and at end of file.
    """
    header = _read_exactly(src, _STREAM_HEADER)
    if len(header) != _STREAM_HEADER:
        raise VaultCorrupt("stream header missing")
    state = sodium.crypto_secretstream_xchacha20poly1305_state()
    try:
        sodium.crypto_secretstream_xchacha20poly1305_init_pull(state, header, key)
    except nacl.exceptions.CryptoError as err:
        raise VaultCorrupt("stream header rejected") from err
    while True:
        piece = _read_exactly(src, _PIECE_OUT)
        if len(piece) < _PIECE_OUT - PIECE:
            raise VaultCorrupt("stream ends before its final piece")
        try:
            plain, tag = sodium.crypto_secretstream_xchacha20poly1305_pull(
                state, piece, ad
            )
        except nacl.exceptions.CryptoError as err:
            raise VaultCorrupt("stream piece failed to decrypt") from err
        if tag == _FINAL and len(piece) < _PIECE_OUT and not src.read(1):
            dst.write(plain)
            return
        if tag != _MESSAGE or len(piece) != _PIECE_OUT:
            raise VaultCorrupt("stream is cut short or has trailing data")
        dst.write(plain)


def _derive(password: str, salt: bytes, opslimit: int, memlimit: int) -> bytes:
    secret = unicodedata.normalize("NFC", password).encode("utf-8")
    try:
        return argon2id.kdf(
            _KEY_BYTES, secret, salt, opslimit=opslimit, memlimit=memlimit
        )
    except nacl.exceptions.RuntimeError as err:
        raise NotEnoughMemory from err


def _read_exactly(src: BinaryIO, size: int) -> bytes:
    """Up to `size` bytes, short only at end of file."""
    parts, left = [], size
    while left:
        chunk = src.read(left)
        if not chunk:
            break
        parts.append(chunk)
        left -= len(chunk)
    return b"".join(parts)


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _unb64(value: object, length: int) -> bytes:
    try:
        data = (
            base64.b64decode(value, validate=True) if isinstance(value, str) else None
        )
    except binascii.Error:
        data = None
    if data is None or len(data) != length:
        raise VaultCorrupt("the key record holds a malformed value")
    return data

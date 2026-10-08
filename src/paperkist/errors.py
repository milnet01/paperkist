"""The errors every Paperkist part raises. `ui` turns each into one message."""


class PaperkistError(Exception):
    """Base class for every expected Paperkist failure."""


class NotAVault(PaperkistError):
    """The folder holds no vault header."""


class VaultExists(PaperkistError):
    """A vault was to be created in a folder that is not empty."""


class WrongPassword(PaperkistError):
    """The key record would not unwrap with this password."""


class VaultCorrupt(PaperkistError):
    """A vault file failed to decrypt or parse."""


class NotEnoughMemory(PaperkistError):
    """Key derivation could not allocate the memory it needs."""


class VaultTooNew(PaperkistError):
    """A format number above what this release reads."""


class VaultInUse(PaperkistError):
    """Another Paperkist, or another Vault in this process, has it open."""


class DocumentMissing(PaperkistError):
    """No document with that id is in the vault."""

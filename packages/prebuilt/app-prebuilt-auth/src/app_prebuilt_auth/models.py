"""The complete authentication schema, independent of enabled login providers.

Importing app_prebuilt_auth registers every table on app-layer-base's metadata.
The host still applies schema changes through its migration process.
"""

from .api_key.models import Machine, MachineKey
from .google.models import GoogleLoginFlow
from .user.identities import ExternalIdentity
from .user.models import User, UserAccessEvent

__all__ = ["ExternalIdentity", "GoogleLoginFlow", "Machine", "MachineKey", "User", "UserAccessEvent"]

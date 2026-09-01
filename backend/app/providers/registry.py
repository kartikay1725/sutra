from typing import Optional, Dict
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.providers.base import RepositoryProvider
from app.providers.credentials import CredentialProvider
from app.providers.events import WebhookEventAdapter
from app.providers.checks import CheckProvider


class ProviderRegistry:
    """
    Central registry and resolver for substrate provider implementations.
    Routes operations dynamically to Local or GitHub provider instances
    based on the repository's configured provider_type.
    """

    def __init__(
        self,
        repository_providers: Dict[str, RepositoryProvider],
        credential_providers: Dict[str, CredentialProvider],
        webhook_adapters: Dict[str, WebhookEventAdapter],
        check_providers: Dict[str, CheckProvider],
        default_provider: str = "local",
    ):
        self._repository_providers = repository_providers
        self._credential_providers = credential_providers
        self._webhook_adapters = webhook_adapters
        self._check_providers = check_providers
        self._default_provider = default_provider

    def _get_provider_type(self, repository: Optional[Repository | str]) -> str:
        if isinstance(repository, Repository):
            return getattr(repository, "provider_type", None) or self._default_provider
        if isinstance(repository, str):
            return repository.lower()
        return self._default_provider

    def get_repository_provider(self, repository: Optional[Repository | str] = None) -> RepositoryProvider:
        ptype = self._get_provider_type(repository)
        provider = self._repository_providers.get(ptype)
        if not provider:
            provider = self._repository_providers.get(self._default_provider)
        if not provider:
            raise KeyError(f"No RepositoryProvider registered for type '{ptype}'")
        return provider

    def get_credential_provider(self, repository: Optional[Repository | str] = None) -> CredentialProvider:
        ptype = self._get_provider_type(repository)
        provider = self._credential_providers.get(ptype)
        if not provider:
            provider = self._credential_providers.get(self._default_provider)
        if not provider:
            raise KeyError(f"No CredentialProvider registered for type '{ptype}'")
        return provider

    def get_webhook_adapter(self, provider_type: str = "github") -> WebhookEventAdapter:
        adapter = self._webhook_adapters.get(provider_type.lower())
        if not adapter:
            raise KeyError(f"No WebhookEventAdapter registered for type '{provider_type}'")
        return adapter

    def get_check_provider(self, repository: Optional[Repository | str] = None) -> CheckProvider:
        ptype = self._get_provider_type(repository)
        provider = self._check_providers.get(ptype)
        if not provider:
            provider = self._check_providers.get(self._default_provider)
        if not provider:
            raise KeyError(f"No CheckProvider registered for type '{ptype}'")
        return provider

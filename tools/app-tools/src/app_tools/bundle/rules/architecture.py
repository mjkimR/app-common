"""app-common architecture rules for `devkit rules check`; the checks live in `app_tools.architecture`."""

from app_tools.architecture.rule import ArchitectureRule


class RouterRepoImportRule(ArchitectureRule):
    rule_id = "RULE-app-router-repo-import"


class ServiceCommitRule(ArchitectureRule):
    rule_id = "RULE-app-service-commit"


class HookSuperCallRule(ArchitectureRule):
    rule_id = "RULE-app-hook-super-call"


class AdapterDependencyRule(ArchitectureRule):
    rule_id = "RULE-app-adapter-dependency"


class ForbiddenImportRule(ArchitectureRule):
    rule_id = "RULE-app-forbidden-import"


class CommandSignatureRule(ArchitectureRule):
    rule_id = "RULE-app-command-signature"


class CommandTransactionRule(ArchitectureRule):
    rule_id = "RULE-app-command-transaction"


class ArchitectureConfigRule(ArchitectureRule):
    rule_id = "RULE-app-architecture-config"


class ParseErrorRule(ArchitectureRule):
    rule_id = "RULE-app-parse-error"


class HttpClientConstructionRule(ArchitectureRule):
    rule_id = "RULE-app-http-client-construction"


class SharedClientCloseRule(ArchitectureRule):
    rule_id = "RULE-app-shared-client-close"


class DirectCurrentTimeRule(ArchitectureRule):
    rule_id = "RULE-app-direct-current-time"


class DbFactoryInLayerRule(ArchitectureRule):
    rule_id = "RULE-app-db-factory-in-layer"


class UndeclaredDependencyRule(ArchitectureRule):
    rule_id = "RULE-app-undeclared-dependency"


class InvalidSuppressionRule(ArchitectureRule):
    rule_id = "RULE-app-invalid-suppression"

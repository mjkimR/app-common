"""Scaffold app-common features from the templates under ``templates/``."""

from app_tools.create_code.feature import create_feature
from app_tools.create_code.naming import FeatureResult
from app_tools.create_code.web_feature import create_web_feature

__all__ = ["FeatureResult", "create_feature", "create_web_feature"]

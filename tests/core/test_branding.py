"""Tests for the Star Warehouse AI identity contract."""

from app.core.branding import (
    APP_VERSION,
    CELERY_APP_NAME,
    HEALTH_VERSION,
    PRODUCT_NAME_EN,
    PRODUCT_NAME_ZH,
    SERVICE_SLUG,
    normalize_product_name,
)
from app.core.config import Settings


def test_branding_constants_define_v5_identity() -> None:
    """The public identity must be stable across runtime integrations."""
    assert PRODUCT_NAME_ZH == "星仓 AI 智能客服"
    assert PRODUCT_NAME_EN == "Star Warehouse AI"
    assert SERVICE_SLUG == "star-warehouse-ai"
    assert CELERY_APP_NAME == "star_warehouse_ai"
    assert APP_VERSION == "5.0.0"
    assert HEALTH_VERSION == "v5.0"


def test_normalize_product_name_migrates_known_v4_value() -> None:
    """A v4 environment should upgrade without displaying the retired name."""
    assert normalize_product_name(" E-commerce Smart Agent ") == PRODUCT_NAME_ZH
    assert Settings.normalize_legacy_project_name("E-commerce Smart Agent") == PRODUCT_NAME_ZH


def test_normalize_product_name_preserves_custom_deployment_name() -> None:
    """Operators may continue to supply an intentional custom display name."""
    assert normalize_product_name("Acme Support") == "Acme Support"

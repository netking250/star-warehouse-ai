"""Canonical product identity for Star Warehouse AI."""

PRODUCT_NAME_ZH = "星仓 AI 智能客服"
PRODUCT_NAME_EN = "Star Warehouse AI"
SERVICE_SLUG = "star-warehouse-ai"
CELERY_APP_NAME = "star_warehouse_ai"
APP_VERSION = "5.0.0"
HEALTH_VERSION = "v5.0"

# Retained for the v5 compatibility window so existing deployments can upgrade
# without exposing the retired brand in user-facing surfaces.
LEGACY_PRODUCT_NAMES = frozenset(
    {
        "E-commerce Smart Agent",
        "E-commerce-Smart-Agent",
        "Ecommerce Smart Agent",
        "电商智能客服",
    }
)


def normalize_product_name(value: str) -> str:
    """Return the canonical product name for a known legacy name."""
    return PRODUCT_NAME_ZH if value.strip() in LEGACY_PRODUCT_NAMES else value.strip()

"""Bedrock calculator-assisted estimating module manifest."""

from app.core.module_loader import ModuleManifest

manifest = ModuleManifest(
    name="oe_bedrock_calculators",
    version="0.1.0",
    display_name="Bedrock Calculators",
    description="Bedrock-specific calculator previews and BOQ authoring helpers.",
    author="OpenConstructionERP",
    category="business",
    depends=["oe_boq"],
    auto_install=True,
    enabled=True,
)

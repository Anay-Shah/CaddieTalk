import pytest

# CDK is only needed from M4 onwards, so it lives in the optional `infra` extra. Skip
# rather than fail when it isn't installed; CI installs it and does run these.
cdk = pytest.importorskip("aws_cdk", reason="install with: pip install -e '.[infra]'")

from aws_cdk.assertions import Template  # noqa: E402
from caddietalk_infra.stack import CaddieTalkStack  # noqa: E402


def test_stack_synthesizes():
    template = Template.from_stack(CaddieTalkStack(cdk.App(), "TestStack")).to_json()
    assert isinstance(template, dict)


def test_no_vpc_resources():
    """A NAT Gateway would cost roughly a third of the credit budget per month."""
    template = Template.from_stack(CaddieTalkStack(cdk.App(), "TestStack")).to_json()
    resource_types = {r["Type"] for r in template.get("Resources", {}).values()}
    assert "AWS::EC2::NatGateway" not in resource_types
    assert "AWS::EC2::VPC" not in resource_types

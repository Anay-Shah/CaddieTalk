"""The CaddieTalk stack.

Deliberately empty until M4. M1 through M3 are pure local Python and deploy nothing, so
this exists only to keep `cdk synth` wired into CI from the start.

M4 adds, in roughly this order: Budgets alerts, DynamoDB tables, the S3 bucket, Cognito,
the container image with the engine and caddie functions, the data API Lambdas, API
Gateway, and CloudWatch alarms.
"""

from aws_cdk import Stack
from constructs import Construct


class CaddieTalkStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

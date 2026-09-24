"""Cost guardrails, encoded once so no resource can quietly opt out of them.

The project runs on a ~$100 CAD AWS signup credit. Guardrails that rely on remembering to
apply them are not guardrails, so every value that protects the budget lives here and every
construct reads from here. See DECISIONS.md (D-005).
"""

from aws_cdk import Duration, RemovalPolicy
from aws_cdk import aws_logs as logs

# The default retention is "forever", which quietly accumulates cost.
LOG_RETENTION = logs.RetentionDays.TWO_WEEKS

# Lambda's default timeout is 15 minutes. Nothing here should ever run that long, and a
# short timeout caps the damage a runaway loop can do.
LAMBDA_TIMEOUT = Duration.seconds(30)

# Caps blast radius: a bug cannot fan out to hundreds of parallel invocations.
LAMBDA_RESERVED_CONCURRENCY = 5

# Memory for the container image function that runs NumPy/Shapely simulation.
ENGINE_MEMORY_MB = 3008

# The caddie function spends most of its time waiting on Bedrock, so it needs far less.
CADDIE_MEMORY_MB = 1024

# Generated speech is played once and never needed again.
AUDIO_EXPIRY = Duration.days(1)

# Dev stacks should be fully destroyable so nothing is left running by accident.
DEV_REMOVAL_POLICY = RemovalPolicy.DESTROY

# Budget alert thresholds in USD. Set before the first deploy — step zero of M4.
BUDGET_THRESHOLDS_USD = (10, 25, 50)

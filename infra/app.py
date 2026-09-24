#!/usr/bin/env python3
import aws_cdk as cdk
from caddietalk_infra.stack import CaddieTalkStack

app = cdk.App()
CaddieTalkStack(app, "CaddieTalkDev")
app.synth()

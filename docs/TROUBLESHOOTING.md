# Troubleshooting Guide: MCP Demo Application on ECS

This document captures issues encountered during deployment and their solutions.

## Issue 1: UI Service Cannot Connect to Agent Service via Service Connect

### Symptoms
- UI service logs show: `Failed to connect to agent at http://agent:3000`
- `ConnectionError` when UI tries to reach the Agent service
- Agent service is running and healthy
- Service Connect is enabled on all services

### Root Cause Analysis
The Envoy sidecar proxy was not properly intercepting traffic to `agent:3000`. Investigation revealed:

1. **Envoy was receiving cluster configuration** - Logs showed `cds: response indicates 2 added/updated cluster(s)` (agent and mcp-server)
2. **Egress listener was configured** - `lds: add/update listener 'egress'` appeared in logs
3. **But traffic wasn't being routed** - No connection attempts were visible in Envoy logs
4. **DNS resolution failing before Envoy** - The iptables rules that should intercept traffic weren't working

### Solution
**Trigger a service redeployment** by updating the Service Connect configuration.

1. Add `logConfiguration` to the UI service's Service Connect config:

```json
{
  "enabled": true,
  "namespace": "mcp-namespace.local",
  "services": [],
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/ui-service-connect",
      "awslogs-region": "us-west-2",
      "awslogs-stream-prefix": "envoy"
    }
  }
}
```

2. Update the service to trigger a new deployment:

```bash
aws ecs update-service \
  --cluster mcp-demo-cluster \
  --service ui-service \
  --service-connect-configuration file://config/ui-service-connect.json \
  --force-new-deployment \
  --profile smanubol-admin \
  --region us-west-2
```

### Why This Works
The redeployment creates a fresh Envoy sidecar container with properly initialized:
- iptables rules for traffic interception
- DNS resolution for Service Connect endpoints
- Proxy configuration for routing to backend services

### Verification
After redeployment, check Envoy logs for successful routing:
```bash
aws logs filter-log-events \
  --log-group-name /ecs/ui-service-connect \
  --limit 50 \
  --profile smanubol-admin \
  --region us-west-2
```

Look for:
- `cds: response indicates 2 added/updated cluster(s)` - Clusters configured
- `lds: add/update listener 'egress'` - Egress listener ready
- Connection logs showing traffic to agent:3000

---

## Issue 2: Agent Cannot Invoke Bedrock Model (AccessDeniedException)

### Symptoms
- Agent logs show: `AccessDeniedException` when calling Bedrock
- Error mentions `inference-profile/global.amazon.nova-*`
- UI receives error responses from agent

### Root Cause
The Agent task role had permissions for **foundation models** but was missing permissions for **inference profiles**.

The agent code uses an inference profile (e.g., `us.amazon.nova-lite-v1:0`) for cross-region inference, which requires separate IAM permissions.

### Solution
Update the Agent task role's IAM policy to include inference profile resources.

**Before (broken):**
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": [
    "arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-lite-v1:0",
    "arn:aws:bedrock:*::foundation-model/amazon.nova-*"
  ]
}
```

**After (working):**
```json
{
  "Effect": "Allow",
  "Action": [
    "bedrock:InvokeModel",
    "bedrock:InvokeModelWithResponseStream"
  ],
  "Resource": [
    "arn:aws:bedrock:us-west-2::foundation-model/amazon.nova-lite-v1:0",
    "arn:aws:bedrock:*::foundation-model/amazon.nova-*",
    "arn:aws:bedrock:*:ACCOUNT_ID:inference-profile/*",
    "arn:aws:bedrock:*::inference-profile/*"
  ]
}
```

### How to Apply
Option 1: Update CloudFormation stack (recommended for persistence)
```bash
aws cloudformation update-stack \
  --stack-name mcp-demo-infrastructure \
  --template-body file://cloudformation/infrastructure.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --profile smanubol-admin \
  --region us-west-2
```

Option 2: Update IAM policy directly (immediate fix)
```bash
# Get the current policy
aws iam get-role-policy \
  --role-name mcp-demo-infrastructure-agent-task-role \
  --policy-name BedrockAccess \
  --profile smanubol-admin

# Update with new policy including inference-profile resources
aws iam put-role-policy \
  --role-name mcp-demo-infrastructure-agent-task-role \
  --policy-name BedrockAccess \
  --policy-document file://updated-policy.json \
  --profile smanubol-admin
```

### Verification
Test the application by sending a query through the UI:
```
https://ui-7aced620c90b418699e2dcf91288ddb1.ecs.us-west-2.on.aws/
```

Check agent logs for successful Bedrock invocation:
```bash
aws logs filter-log-events \
  --log-group-name /ecs/agent \
  --filter-pattern "Agent response generated" \
  --limit 10 \
  --profile smanubol-admin \
  --region us-west-2
```

---

## Debugging Tips

### Enable Service Connect Logging
Add `logConfiguration` to all Service Connect configs for visibility into Envoy proxy behavior:

```json
{
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/SERVICE-service-connect",
      "awslogs-region": "us-west-2",
      "awslogs-stream-prefix": "envoy"
    }
  }
}
```

### Check Service Connect Status
```bash
aws ecs describe-services \
  --cluster mcp-demo-cluster \
  --services ui-service agent-service mcp-server-service \
  --query 'services[*].{name:serviceName,deployments:deployments[0].serviceConnectConfiguration}' \
  --profile smanubol-admin \
  --region us-west-2
```

### Verify Cloud Map Registration
```bash
aws servicediscovery list-instances \
  --service-id srv-vn5inmx45h4u6zqv \
  --profile smanubol-admin \
  --region us-west-2
```

### Force Service Redeployment
When Service Connect issues occur, a redeployment often resolves them:
```bash
aws ecs update-service \
  --cluster mcp-demo-cluster \
  --service SERVICE_NAME \
  --force-new-deployment \
  --profile smanubol-admin \
  --region us-west-2
```

---

## Summary of Fixes Applied

| Issue | Root Cause | Fix |
|-------|------------|-----|
| UI cannot connect to Agent | Envoy proxy not intercepting traffic | Redeploy UI service with updated Service Connect config |
| Agent cannot call Bedrock | Missing IAM permissions for inference profiles | Add `inference-profile/*` to task role policy |

---

Document Version: 1.0  
Last Updated: January 26, 2026

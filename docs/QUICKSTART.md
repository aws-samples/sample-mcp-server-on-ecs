# MCP on ECS - Quick Start Deployment Guide

Deploy a Model Context Protocol (MCP) application on Amazon ECS with Service Connect.

## Prerequisites

- AWS CLI v2 configured with credentials
- Docker with buildx support
- Git (to clone the repository)

## Step 1: Clone Repository and Set Variables

```bash
# Clone the repository
git clone https://github.com/aws-samples/ecs-mcp-blog.git
cd ecs-mcp-blog

# Set your variables (modify these for your environment)
export STACK_NAME=ecs-mcp-blog
export AWS_REGION=us-west-2
export AWS_PROFILE=default
```

## Step 2: Deploy Infrastructure

```bash
aws cloudformation deploy \
  --template-file cloudformation/infrastructure.yaml \
  --stack-name $STACK_NAME \
  --capabilities CAPABILITY_NAMED_IAM \
  --region $AWS_REGION \
  --profile $AWS_PROFILE
```

**Validate:** Confirm the stack completed successfully before proceeding.

```bash
# Should output CREATE_COMPLETE
aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $AWS_REGION \
  --profile $AWS_PROFILE \
  --query 'Stacks[0].StackStatus' \
  --output text
```

> If the status is not `CREATE_COMPLETE`, check the events for errors:
> ```bash
> aws cloudformation describe-stack-events \
>   --stack-name $STACK_NAME \
>   --region $AWS_REGION \
>   --profile $AWS_PROFILE \
>   --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
>   --output table
> ```

## Step 3: Get Stack Outputs

```bash
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile $AWS_PROFILE)
export ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
export CLUSTER_NAME=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`ECSClusterName`].OutputValue' --output text)
export S3_BUCKET=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`S3BucketName`].OutputValue' --output text)
export PRIVATE_SUBNETS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`PrivateSubnetIds`].OutputValue' --output text)
export PUBLIC_SUBNETS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`PublicSubnetIds`].OutputValue' --output text)
export MCP_SG=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`MCPServerSecurityGroupId`].OutputValue' --output text)
export AGENT_SG=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`AgentSecurityGroupId`].OutputValue' --output text)
export UI_SG=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`UISecurityGroupId`].OutputValue' --output text)
export EXECUTION_ROLE=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`TaskExecutionRoleArn`].OutputValue' --output text)
export INFRA_ROLE=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`ECSExpressInfrastructureRoleArn`].OutputValue' --output text)
export UI_TASK_ROLE=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`UITaskRoleArn`].OutputValue' --output text)
export UI_ECR=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`UIECRRepositoryUri`].OutputValue' --output text)
export UI_LOG_GROUP=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs[?OutputKey==`UILogGroupName`].OutputValue' --output text)
```

**Validate:** Ensure all critical variables are set. If any show `None` or are empty, the stack outputs may be missing.

```bash
# All values should be non-empty
echo "Cluster:    $CLUSTER_NAME"
echo "S3 Bucket:  $S3_BUCKET"
echo "ECR:        $ECR_REGISTRY"
echo "Priv Subs:  $PRIVATE_SUBNETS"
echo "Pub Subs:   $PUBLIC_SUBNETS"
echo "Infra Role: $INFRA_ROLE"
```

## Step 4: Login to ECR

```bash
aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | \
  docker login --username AWS --password-stdin $ECR_REGISTRY
```

> You should see `Login Succeeded`. If not, verify your AWS credentials and that the ECR registry URL is correct.

## Step 5: Upload Product Catalog

```bash
aws s3 cp sample-data/product-catalog.json s3://$S3_BUCKET/product-catalog.json \
  --region $AWS_REGION --profile $AWS_PROFILE
```

**Validate:**

```bash
# Should return product-catalog.json with size ~5 KiB
aws s3 ls s3://$S3_BUCKET/ --region $AWS_REGION --profile $AWS_PROFILE
```

## Step 6: Build and Push Docker Images

```bash
# MCP Server
docker buildx build --platform linux/amd64 \
  -t $ECR_REGISTRY/${STACK_NAME}-mcp-server:latest \
  ./mcp-server --push

# Agent
docker buildx build --platform linux/amd64 \
  -t $ECR_REGISTRY/${STACK_NAME}-agent:latest \
  ./agent --push

# UI
docker buildx build --platform linux/amd64 \
  -t $ECR_REGISTRY/${STACK_NAME}-ui:latest \
  ./ui --push
```

**Validate:** Confirm all three images exist in ECR.

```bash
# Each should return an imageDigest — if empty, the push failed
for repo in mcp-server agent ui; do
  echo "--- ${STACK_NAME}-${repo} ---"
  aws ecr describe-images \
    --repository-name ${STACK_NAME}-${repo} \
    --region $AWS_REGION \
    --profile $AWS_PROFILE \
    --query 'imageDetails[0].[imageTags[0],imageSizeInBytes]' \
    --output text
done
```

## Step 7: Create Service Connect Config Files

```bash
# MCP Server Service Connect
cat > config/${STACK_NAME}-mcp-server-service-connect.json << EOF
{
  "enabled": true,
  "namespace": "${STACK_NAME}.local",
  "services": [
    {
      "portName": "mcp-port",
      "discoveryName": "mcp-server",
      "clientAliases": [{"port": 8080, "dnsName": "mcp-server"}]
    }
  ],
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/${STACK_NAME}/mcp-server-service-connect",
      "awslogs-region": "${AWS_REGION}",
      "awslogs-stream-prefix": "envoy"
    }
  }
}
EOF

# Agent Service Connect
cat > config/${STACK_NAME}-agent-service-connect.json << EOF
{
  "enabled": true,
  "namespace": "${STACK_NAME}.local",
  "services": [
    {
      "portName": "agent-port",
      "discoveryName": "agent",
      "clientAliases": [{"port": 3000, "dnsName": "agent"}]
    }
  ],
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/${STACK_NAME}/agent-service-connect",
      "awslogs-region": "${AWS_REGION}",
      "awslogs-stream-prefix": "envoy"
    }
  }
}
EOF

# UI Service Connect
cat > config/${STACK_NAME}-ui-service-connect.json << EOF
{
  "enabled": true,
  "namespace": "${STACK_NAME}.local",
  "services": [],
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/${STACK_NAME}/ui-service-connect",
      "awslogs-region": "${AWS_REGION}",
      "awslogs-stream-prefix": "envoy"
    }
  }
}
EOF
```

## Step 8: Deploy ECS Services

Deploy services in order: MCP Server first (no dependencies), then Agent (depends on MCP Server), then UI (depends on Agent).

### MCP Server Service
```bash
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name mcp-server-service \
  --task-definition ${STACK_NAME}-mcp-server \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$PRIVATE_SUBNETS],securityGroups=[$MCP_SG],assignPublicIp=DISABLED}" \
  --service-connect-configuration file://config/${STACK_NAME}-mcp-server-service-connect.json \
  --region $AWS_REGION \
  --profile $AWS_PROFILE
```

### Agent Service
```bash
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name agent-service \
  --task-definition ${STACK_NAME}-agent \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$PRIVATE_SUBNETS],securityGroups=[$AGENT_SG],assignPublicIp=DISABLED}" \
  --service-connect-configuration file://config/${STACK_NAME}-agent-service-connect.json \
  --region $AWS_REGION \
  --profile $AWS_PROFILE
```

**Validate:** Wait for MCP Server and Agent to stabilize before deploying UI. Both services should show `runningCount: 1`.

```bash
echo "Waiting 60 seconds for tasks to start..."
sleep 60

aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services mcp-server-service agent-service \
  --region $AWS_REGION \
  --profile $AWS_PROFILE \
  --query 'services[].[serviceName,status,runningCount,desiredCount]' \
  --output table
```

> If `runningCount` is 0, check for task failures:
> ```bash
> # List stopped tasks to find failure reason
> aws ecs list-tasks --cluster $CLUSTER_NAME --service-name mcp-server-service \
>   --desired-status STOPPED --region $AWS_REGION --profile $AWS_PROFILE
> ```
> Then describe the stopped task to see the `stoppedReason`.

### UI Service (Express Mode)
```bash
# Create UI service with Express Mode (no Service Connect initially)
aws ecs create-express-gateway-service \
  --cluster $CLUSTER_NAME \
  --service-name ui-service \
  --execution-role-arn $EXECUTION_ROLE \
  --infrastructure-role-arn $INFRA_ROLE \
  --primary-container "{
    \"image\": \"$UI_ECR:latest\",
    \"containerPort\": 7860,
    \"awsLogsConfiguration\": {
      \"logGroup\": \"$UI_LOG_GROUP\",
      \"logStreamPrefix\": \"ecs\"
    },
    \"environment\": [
      {\"name\": \"AGENT_ENDPOINT\", \"value\": \"http://agent:3000\"}
    ]
  }" \
  --task-role-arn $UI_TASK_ROLE \
  --network-configuration subnets=$PUBLIC_SUBNETS,securityGroups=$UI_SG \
  --cpu "256" \
  --memory "512" \
  --scaling-target minTaskCount=1,maxTaskCount=4,autoScalingMetric=AVERAGE_CPU,autoScalingTargetValue=70 \
  --tags key=Project,value=ECS-MCP-Blog \
  --region $AWS_REGION \
  --profile $AWS_PROFILE
```

Now add Service Connect so the UI can reach the Agent via `http://agent:3000`:

```bash
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service ui-service \
  --service-connect-configuration file://config/${STACK_NAME}-ui-service-connect.json \
  --force-new-deployment \
  --region $AWS_REGION \
  --profile $AWS_PROFILE
```

> **Why two steps?** Express Mode doesn't support Service Connect on initial creation. The update adds the Envoy sidecar needed for service-to-service communication.

> **Deployment time:** Express Mode uses canary deployments with a 6-minute bake time. Wait 6-7 minutes after the update for traffic to shift to the new task.

## Step 9: Verify Deployment

Wait for all services to stabilize, then verify everything is running.

```bash
# Check all three services — runningCount should equal desiredCount for each
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services mcp-server-service agent-service ui-service \
  --region $AWS_REGION \
  --profile $AWS_PROFILE \
  --query 'services[].[serviceName,status,runningCount,desiredCount]' \
  --output table
```

Expected output:
```
---------------------------------------------------------
|                    DescribeServices                    |
+----------------------+--------+---+-------------------+
|  mcp-server-service  |  ACTIVE|  1|  1               |
|  agent-service       |  ACTIVE|  1|  1               |
|  ui-service          |  ACTIVE|  1|  1               |
+----------------------+--------+---+-------------------+
```

Get the public URL for the UI:

```bash
# Express Mode provisions an ALB — get the public endpoint
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services ui-service \
  --region $AWS_REGION \
  --profile $AWS_PROFILE \
  --query 'services[0].loadBalancers[0]'
```

> The public URL follows the pattern: `https://ui-<hash>.ecs.<region>.on.aws`
> You can also find it in the ECS console under the ui-service details.

## Step 10: Test the Application

Open the UI URL in your browser and try queries like:
- "Show me electronics under $100"
- "What laptops do you have?"
- "Find running shoes in stock"

If the UI loads but queries fail, check the Agent and MCP Server logs:

```bash
# Agent logs — look for MCP connection or Bedrock errors
aws logs tail /ecs/${STACK_NAME}/agent --since 10m --region $AWS_REGION --profile $AWS_PROFILE

# MCP Server logs — look for S3 or startup errors
aws logs tail /ecs/${STACK_NAME}/mcp-server --since 10m --region $AWS_REGION --profile $AWS_PROFILE
```

## Cleanup

```bash
# Delete UI service (Express Mode requires special API)
UI_SERVICE_ARN=$(aws ecs describe-services --cluster $CLUSTER_NAME --services ui-service --region $AWS_REGION --profile $AWS_PROFILE --query 'services[0].serviceArn' --output text)
aws ecs delete-express-gateway-service --service-arn $UI_SERVICE_ARN --region $AWS_REGION --profile $AWS_PROFILE

# Delete standard services
aws ecs delete-service --cluster $CLUSTER_NAME --service agent-service --force --region $AWS_REGION --profile $AWS_PROFILE
aws ecs delete-service --cluster $CLUSTER_NAME --service mcp-server-service --force --region $AWS_REGION --profile $AWS_PROFILE

# Wait for services to drain
echo "Waiting 90 seconds for services to drain..."
sleep 90

# Empty S3 bucket
aws s3 rm s3://$S3_BUCKET --recursive --profile $AWS_PROFILE

# Delete ECR repositories (must delete before CloudFormation)
aws ecr delete-repository --repository-name ${STACK_NAME}-mcp-server --force --region $AWS_REGION --profile $AWS_PROFILE
aws ecr delete-repository --repository-name ${STACK_NAME}-agent --force --region $AWS_REGION --profile $AWS_PROFILE
aws ecr delete-repository --repository-name ${STACK_NAME}-ui --force --region $AWS_REGION --profile $AWS_PROFILE

# Delete Express Mode orphan resources (ALB and security groups created at runtime)
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=${STACK_NAME}-vpc" --query "Vpcs[0].VpcId" --output text --region $AWS_REGION --profile $AWS_PROFILE)

# Delete orphan ALB (if exists)
ALB_ARN=$(aws elbv2 describe-load-balancers --region $AWS_REGION --profile $AWS_PROFILE --query "LoadBalancers[?contains(LoadBalancerName, 'ecs-express-gateway')].LoadBalancerArn" --output text)
[ -n "$ALB_ARN" ] && aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN --region $AWS_REGION --profile $AWS_PROFILE && sleep 30

# Delete orphan security groups
for SG in $(aws ec2 describe-security-groups --filters Name=vpc-id,Values=$VPC_ID --query "SecurityGroups[?contains(GroupName, 'ecs-express') || contains(GroupName, 'ui-service')].GroupId" --output text --region $AWS_REGION --profile $AWS_PROFILE); do
  aws ec2 delete-security-group --group-id $SG --region $AWS_REGION --profile $AWS_PROFILE 2>/dev/null || true
done

# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE

# Monitor deletion (optional)
aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE
echo "Stack deleted successfully."
```

> **Note:** Express Mode creates ALB and security groups at runtime that are not managed by CloudFormation. These must be deleted manually before the VPC can be removed.

**Validate cleanup:** Confirm the stack is gone.

```bash
# Should return an error indicating the stack does not exist
aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $AWS_REGION \
  --profile $AWS_PROFILE 2>&1 | head -1
```

## Troubleshooting

### Service Connect Issues
If UI cannot connect to Agent, redeploy with Service Connect:
```bash
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service ui-service \
  --service-connect-configuration file://config/${STACK_NAME}-ui-service-connect.json \
  --force-new-deployment \
  --region $AWS_REGION \
  --profile $AWS_PROFILE
```

### Tasks Failing to Start
Check the stopped task reason:
```bash
TASK_ARN=$(aws ecs list-tasks --cluster $CLUSTER_NAME --service-name mcp-server-service \
  --desired-status STOPPED --region $AWS_REGION --profile $AWS_PROFILE \
  --query 'taskArns[0]' --output text)

aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks $TASK_ARN \
  --region $AWS_REGION --profile $AWS_PROFILE \
  --query 'tasks[0].[stoppedReason,containers[].reason]' --output text
```

### View Logs
```bash
# MCP Server logs
aws logs tail /ecs/${STACK_NAME}/mcp-server --follow --region $AWS_REGION --profile $AWS_PROFILE

# Agent logs
aws logs tail /ecs/${STACK_NAME}/agent --follow --region $AWS_REGION --profile $AWS_PROFILE

# UI logs
aws logs tail /ecs/${STACK_NAME}/ui --follow --region $AWS_REGION --profile $AWS_PROFILE

# Service Connect (Envoy) logs — useful for connectivity issues
aws logs tail /ecs/${STACK_NAME}/mcp-server-service-connect --since 10m --region $AWS_REGION --profile $AWS_PROFILE
```

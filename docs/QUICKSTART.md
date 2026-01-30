# MCP on ECS - Quick Start Deployment Guide

Deploy a Model Context Protocol (MCP) application on Amazon ECS with Service Connect.

## Prerequisites

- AWS CLI configured
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

## Step 3: Get Stack Outputs

```bash
# Get all required values from CloudFormation
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

# Verify outputs
echo "Cluster: $CLUSTER_NAME"
echo "S3 Bucket: $S3_BUCKET"
```

## Step 4: Login to ECR

```bash
aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | \
  docker login --username AWS --password-stdin $ECR_REGISTRY
```

## Step 5: Upload Product Catalog

```bash
aws s3 cp sample-data/product-catalog.json s3://$S3_BUCKET/product-catalog.json \
  --region $AWS_REGION --profile $AWS_PROFILE
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

### UI Service (Express Mode)
```bash
# Step 1: Create UI service with Express Mode (no Service Connect initially)
aws ecs create-express-gateway-service \
  --cluster $CLUSTER_NAME \
  --service-name ui-service \
  --execution-role-arn $EXECUTION_ROLE \
  --infrastructure-role-arn $INFRA_ROLE \
  --primary-container "{
    \"image\": \"${UI_ECR}:latest\",
    \"containerPort\": 7860,
    \"awsLogsConfiguration\": {
      \"logGroup\": \"${UI_LOG_GROUP}\",
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

# Step 2: Add Service Connect (required for UI to reach Agent)
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service ui-service \
  --service-connect-configuration file://config/${STACK_NAME}-ui-service-connect.json \
  --force-new-deployment \
  --region $AWS_REGION \
  --profile $AWS_PROFILE
```

> **Note:** Express Mode doesn't support Service Connect on initial creation. The update step adds the Envoy sidecar needed for UI to communicate with Agent via `http://agent:3000`.

> **Deployment Time:** Express Mode uses canary deployments with a 6-minute bake time. Wait 6-7 minutes after the update for traffic to shift to the new task.

## Step 9: Verify Deployment

```bash
# Check service status
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services mcp-server-service agent-service ui-service \
  --region $AWS_REGION \
  --profile $AWS_PROFILE \
  --query 'services[].[serviceName,status,runningCount,desiredCount]' \
  --output table

# Get UI public URL (wait ~2 minutes for ALB provisioning)
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services ui-service \
  --region $AWS_REGION \
  --profile $AWS_PROFILE \
  --query 'services[0].deployments[0].serviceConnectResources' 
```

## Step 10: Test the Application

Open the UI URL in your browser and try queries like:
- "Show me electronics under $100"
- "What laptops do you have?"
- "Find running shoes in stock"

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

# Delete orphan ALB in our VPC (if exists)
ALB_ARN=$(aws elbv2 describe-load-balancers --region $AWS_REGION --profile $AWS_PROFILE --query "LoadBalancers[?VpcId=='${VPC_ID}' && contains(LoadBalancerName, 'ecs-express-gateway')].LoadBalancerArn" --output text)
[ -n "$ALB_ARN" ] && aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN --region $AWS_REGION --profile $AWS_PROFILE && sleep 30

# Delete orphan security groups
for SG in $(aws ec2 describe-security-groups --filters Name=vpc-id,Values=$VPC_ID --query "SecurityGroups[?contains(GroupName, 'ecs-express') || contains(GroupName, 'ui-service')].GroupId" --output text --region $AWS_REGION --profile $AWS_PROFILE); do
  aws ec2 delete-security-group --group-id $SG --region $AWS_REGION --profile $AWS_PROFILE 2>/dev/null || true
done

# Delete CloudFormation stack
aws cloudformation delete-stack --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE

# Wait for stack deletion
aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE

# Delete log groups (retained by CloudFormation)
for LOG_GROUP in /ecs/${STACK_NAME}/mcp-server /ecs/${STACK_NAME}/agent /ecs/${STACK_NAME}/ui /ecs/${STACK_NAME}/mcp-server-service-connect /ecs/${STACK_NAME}/agent-service-connect /ecs/${STACK_NAME}/ui-service-connect; do
  aws logs delete-log-group --log-group-name $LOG_GROUP --region $AWS_REGION --profile $AWS_PROFILE 2>/dev/null || true
done
```

> **Note:** Express Mode creates ALB and security groups at runtime that are not managed by CloudFormation. These must be deleted manually before the VPC can be removed.

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

### View Logs
```bash
# MCP Server logs
aws logs tail /ecs/${STACK_NAME}/mcp-server --follow --region $AWS_REGION --profile $AWS_PROFILE

# Agent logs
aws logs tail /ecs/${STACK_NAME}/agent --follow --region $AWS_REGION --profile $AWS_PROFILE

# UI logs
aws logs tail /ecs/${STACK_NAME}/ui --follow --region $AWS_REGION --profile $AWS_PROFILE
```

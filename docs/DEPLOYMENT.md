# AWS MCP ECS Infrastructure Deployment Guide

## Overview
This guide documents the complete deployment of a Model Context Protocol (MCP) architecture on AWS ECS with three services:
- **MCP Server**: FastMCP server providing product catalog search tools
- **Agent**: Strands agent orchestrating MCP tool calls with Amazon Bedrock
- **UI**: Gradio web interface for user interaction

## Architecture

```
Internet → ALB (Express Mode) → UI Service (Public Subnets)
                                    ↓ Service Connect
                                Agent Service (Private Subnets)
                                    ↓ Service Connect
                                MCP Server (Private Subnets)
                                    ↓
                                S3 Bucket (Product Catalog)
```

### Key Components
- **VPC**: 10.0.0.0/16 with public and private subnets across 2 AZs
- **ECS Cluster**: Fargate-based cluster `mcp-demo-cluster`
- **Service Connect**: Private service discovery via Cloud Map namespace `mcp-namespace.local`
- **ECS Express Mode**: Automated ALB provisioning with SSL/TLS for UI service
- **S3 Bucket**: `mcp-demo-product-catalog-976884845791` with product data

## Prerequisites

1. AWS CLI configured with appropriate credentials
2. Docker with buildx for multi-platform builds (required for Mac ARM → Linux AMD64)
3. AWS Account ID: 976884845791
4. Region: us-west-2
5. AWS Profile: `smanubol-admin` (or your configured profile)

## Deployment Steps

### 1. Infrastructure Setup (CloudFormation)

Deploy the foundational infrastructure:

```bash
aws cloudformation deploy \
  --template-file cloudformation/infrastructure.yaml \
  --stack-name mcp-demo-infrastructure \
  --capabilities CAPABILITY_NAMED_IAM \
  --region us-west-2 \
  --profile smanubol-admin \
  --parameter-overrides \
    VpcCIDR=10.0.0.0/16 \
    PublicSubnet1CIDR=10.0.1.0/24 \
    PublicSubnet2CIDR=10.0.2.0/24 \
    PrivateSubnet1CIDR=10.0.3.0/24 \
    PrivateSubnet2CIDR=10.0.4.0/24
```

**Resources Created:**
- VPC with Internet Gateway and NAT Gateway
- Public subnets: `subnet-079a9653710c9104c`, `subnet-069547a349f3a48ef`
- Private subnets: `subnet-075775f9f79a2f441`, `subnet-050caffc38662c0a5`
- ECS Cluster: `mcp-demo-cluster`
- Cloud Map namespace: `mcp-namespace.local` (ID: `ns-xrvosx2uvvlnyvdb`)
- S3 Bucket: `mcp-demo-product-catalog-976884845791`
- ECR Repositories: `mcp-server`, `agent`, `ui`
- Security Groups:
  - `sg-0a4e0cd1099bf0f94` (UI)
  - `sg-0a4f6d5c3dc3b7c15` (MCP Server)
  - `sg-09dba9bc4c7bb3b29` (Agent)
- IAM Roles:
  - `mcp-demo-infrastructure-ecs-task-execution-role` (ECS task execution)
  - `mcp-demo-infrastructure-mcp-server-task-role` (MCP Server task)
  - `mcp-demo-infrastructure-agent-task-role` (Agent task with Bedrock permissions)
  - `mcp-demo-infrastructure-ui-task-role` (UI task)
  - `mcp-demo-ecs-express-infrastructure-role` (ECS Express Mode infrastructure management)
- CloudWatch Log Groups: `/ecs/mcp-server`, `/ecs/agent`, `/ecs/ui`

### 2. ECR Login and Upload Product Catalog Data

```bash
# Login to ECR
aws ecr get-login-password --region us-west-2 --profile smanubol-admin | \
  docker login --username AWS --password-stdin 976884845791.dkr.ecr.us-west-2.amazonaws.com

# Upload product catalog
aws s3 cp sample-data/product-catalog.json \
  s3://mcp-demo-product-catalog-976884845791/product-catalog.json \
  --region us-west-2 \
  --profile smanubol-admin
```

### 3. Build and Push Docker Images

All images must be built for `linux/amd64` platform (ECS Fargate requirement).

#### MCP Server
```bash
cd mcp-server
docker buildx build --platform linux/amd64 \
  -t 976884845791.dkr.ecr.us-west-2.amazonaws.com/mcp-server:latest \
  . --push
```

**Image Details:**
- Base: Python 3.12-slim
- Key Dependencies: fastmcp 2.14.3, boto3
- Port: 8080
- Environment: `S3_BUCKET_NAME`, `AWS_REGION`

#### Agent Service
```bash
cd agent
docker buildx build --platform linux/amd64 \
  -t 976884845791.dkr.ecr.us-west-2.amazonaws.com/agent:latest \
  . --push
```

**Image Details:**
- Base: Python 3.12-slim
- Key Dependencies: strands-agents 1.22.0, Flask 3.1.2, mcp 1.25.0
- Port: 3000
- Environment: `MCP_SERVER_URL`, `AWS_REGION`, `BEDROCK_MODEL_ID`

#### UI Service
```bash
cd ui
docker buildx build --platform linux/amd64 \
  -t 976884845791.dkr.ecr.us-west-2.amazonaws.com/ui:latest \
  . --push
```

**Image Details:**
- Base: Python 3.12-slim
- Key Dependencies: Gradio 5.50.0, requests
- Port: 7860
- Environment: `AGENT_ENDPOINT`

### 4. Verify Task Definitions (Auto-Created by CloudFormation)

Task definitions are automatically created by the CloudFormation stack. Verify they exist:

```bash
aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?contains(OutputKey, `TaskDefinition`)].{Key:OutputKey,Value:OutputValue}' \
  --output table
```

**Expected Output:**
- MCP Server Task Definition ARN
- Agent Task Definition ARN  
- UI Task Definition ARN

**Note:** Task definitions reference the ECR images you just pushed with `:latest` tag.

### 5. Deploy ECS Services

#### Get CloudFormation Outputs
First, retrieve the necessary values from CloudFormation:

```bash
# Get subnet IDs
PRIVATE_SUBNETS=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`PrivateSubnetIds`].OutputValue' \
  --output text)

# Get security group IDs
MCP_SG=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`MCPServerSecurityGroupId`].OutputValue' \
  --output text)

AGENT_SG=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentSecurityGroupId`].OutputValue' \
  --output text)

UI_SG=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`UISecurityGroupId`].OutputValue' \
  --output text)

# Get public subnets for UI
PUBLIC_SUBNETS=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`PublicSubnetIds`].OutputValue' \
  --output text)

# Get cluster name
CLUSTER_NAME=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`ECSClusterName`].OutputValue' \
  --output text)

# Get task definition ARNs
MCP_TASK_DEF=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`MCPServerTaskDefinitionArn`].OutputValue' \
  --output text)

AGENT_TASK_DEF=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`AgentTaskDefinitionArn`].OutputValue' \
  --output text)

UI_TASK_DEF=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`UITaskDefinitionArn`].OutputValue' \
  --output text)
```

#### MCP Server Service (Private)
```bash
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name mcp-server-service \
  --task-definition $MCP_TASK_DEF \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$PRIVATE_SUBNETS],securityGroups=[$MCP_SG],assignPublicIp=DISABLED}" \
  --service-connect-configuration file://config/mcp-server-service-connect.json \
  --region us-west-2 \
  --profile smanubol-admin
```

**Service Details:**
- ARN: `arn:aws:ecs:us-west-2:976884845791:service/mcp-demo-cluster/mcp-server-service`
- Service Connect DNS: `mcp-server.mcp-namespace.local:8080`
- Network: Private subnets only

#### Agent Service (Private)
```bash
aws ecs create-service \
  --cluster $CLUSTER_NAME \
  --service-name agent-service \
  --task-definition $AGENT_TASK_DEF \
  --desired-count 1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[$PRIVATE_SUBNETS],securityGroups=[$AGENT_SG],assignPublicIp=DISABLED}" \
  --service-connect-configuration file://config/agent-service-connect.json \
  --region us-west-2 \
  --profile smanubol-admin
```

**Service Details:**
- ARN: `arn:aws:ecs:us-west-2:976884845791:service/mcp-demo-cluster/agent-service`
- Service Connect DNS: `agent.mcp-namespace.local:3000`
- Network: Private subnets only

#### UI Service (Public - ECS Express Mode)
```bash
# Get infrastructure role ARN
INFRA_ROLE=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`ECSExpressInfrastructureRoleArn`].OutputValue' \
  --output text)

EXECUTION_ROLE=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`TaskExecutionRoleArn`].OutputValue' \
  --output text)

UI_TASK_ROLE=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`UITaskRoleArn`].OutputValue' \
  --output text)

UI_ECR=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`UIECRRepositoryUri`].OutputValue' \
  --output text)

UI_LOG_GROUP=$(aws cloudformation describe-stacks \
  --stack-name mcp-demo-infrastructure \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'Stacks[0].Outputs[?OutputKey==`UILogGroupName`].OutputValue' \
  --output text)

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
  --tags key=Project,value=MCP-Blog key=Environment,value=dev \
  --region us-west-2 \
  --profile smanubol-admin
```

**Service Details:**
- ARN: `arn:aws:ecs:us-west-2:976884845791:service/mcp-demo-cluster/ui-service`
- Public URL: `https://ui-7aced620c90b418699e2dcf91288ddb1.ecs.us-west-2.on.aws`
- Network: Public subnets with internet-facing ALB
- Auto-scaling: 1-4 tasks based on CPU utilization (70% target)
- Health Check: `/health` endpoint
- Service Connect: Enabled for agent communication

## Service Communication Flow

1. **User → UI Service**
   - Public HTTPS via ALB (automatically provisioned by Express Mode)
   - URL: `https://ui-7aced620c90b418699e2dcf91288ddb1.ecs.us-west-2.on.aws`

2. **UI → Agent Service**
   - Service Connect DNS: `http://agent:3000`
   - Private communication within VPC

3. **Agent → MCP Server**
   - Service Connect DNS: `http://mcp-server:8080`
   - Private communication within VPC

4. **MCP Server → S3**
   - AWS SDK via IAM role
   - Bucket: `s3://mcp-demo-product-catalog-976884845791`

## Key Features

### ECS Express Mode
- **Automated Infrastructure**: ALB, target groups, security groups, and auto-scaling policies automatically provisioned
- **SSL/TLS**: Automatic HTTPS endpoint with managed certificate
- **Cost Optimization**: Shared ALB across multiple Express Mode services
- **Simplified Deployment**: Only requires container image, execution role, and infrastructure role

### Service Connect
- **Private Service Discovery**: Cloud Map namespace for internal DNS resolution
- **No Load Balancer Needed**: Direct container-to-container communication
- **Simplified Configuration**: Short DNS names (`agent:3000` instead of full FQDN)

### Security
- **Least Privilege IAM**: Separate task roles with minimal permissions
- **Network Isolation**: Private subnets for backend services
- **Security Groups**: Restrictive ingress/egress rules
- **No Public IPs**: Backend services only accessible via Service Connect

## Verification

### Check Service Status
```bash
aws ecs describe-services \
  --cluster mcp-demo-cluster \
  --services mcp-server-service agent-service ui-service \
  --region us-west-2 \
  --profile smanubol-admin \
  --query 'services[].[serviceName,status,desiredCount,runningCount]'
```

### Check Running Tasks
```bash
aws ecs list-tasks \
  --cluster mcp-demo-cluster \
  --region us-west-2 \
  --profile smanubol-admin
```

### View Logs
```bash
# MCP Server logs
aws logs tail /ecs/mcp-server --follow --region us-west-2 --profile smanubol-admin

# Agent logs
aws logs tail /ecs/agent --follow --region us-west-2 --profile smanubol-admin

# UI logs
aws logs tail /ecs/ui --follow --region us-west-2 --profile smanubol-admin
```

### Test UI
Access the public URL in your browser:
```
https://ui-7aced620c90b418699e2dcf91288ddb1.ecs.us-west-2.on.aws
```

## Updating Services (Force New Deployment)

When you make code changes and rebuild images, force a new deployment:

```bash
# Rebuild and push updated images
cd mcp-server
docker buildx build --platform linux/amd64 -t 976884845791.dkr.ecr.us-west-2.amazonaws.com/mcp-server:latest . --push

cd ../agent
docker buildx build --platform linux/amd64 -t 976884845791.dkr.ecr.us-west-2.amazonaws.com/agent:latest . --push

cd ../ui
docker buildx build --platform linux/amd64 -t 976884845791.dkr.ecr.us-west-2.amazonaws.com/ui:latest . --push

# Force new deployments
aws ecs update-service --cluster mcp-demo-cluster --service mcp-server-service --force-new-deployment --region us-west-2 --profile smanubol-admin
aws ecs update-service --cluster mcp-demo-cluster --service agent-service --force-new-deployment --region us-west-2 --profile smanubol-admin
aws ecs update-service --cluster mcp-demo-cluster --service ui-service --force-new-deployment --region us-west-2 --profile smanubol-admin
```

### Update Service Connect Configuration (if needed)

```bash
aws ecs update-service \
  --cluster mcp-demo-cluster \
  --service mcp-server-service \
  --service-connect-configuration file://config/mcp-server-service-connect.json \
  --force-new-deployment \
  --region us-west-2 \
  --profile smanubol-admin

aws ecs update-service \
  --cluster mcp-demo-cluster \
  --service agent-service \
  --service-connect-configuration file://config/agent-service-connect.json \
  --force-new-deployment \
  --region us-west-2 \
  --profile smanubol-admin

aws ecs update-service \
  --cluster mcp-demo-cluster \
  --service ui-service \
  --service-connect-configuration file://config/ui-service-connect.json \
  --force-new-deployment \
  --region us-west-2 \
  --profile smanubol-admin
```

## Troubleshooting

### Service Not Starting
1. Check task definition is registered correctly
2. Verify IAM roles have necessary permissions
3. Check security group rules allow required traffic
4. Review CloudWatch logs for container errors

### Service Connect Issues
1. Verify Cloud Map namespace exists: `mcp-namespace.local`
2. Check service connect configuration in service definition
3. Ensure all services are in the same namespace
4. Verify DNS resolution within containers

### Express Mode Deployment Failures
1. Ensure infrastructure role has all required permissions:
   - Elastic Load Balancing (all actions)
   - EC2 (security groups, VPC, subnets, route tables)
   - Application Auto Scaling
   - CloudWatch (alarms, logs)
2. Check CloudFormation events for detailed error messages
3. Verify subnets are in public availability zones for internet-facing ALB

## Resource Cleanup

To delete all resources:

```bash
# IMPORTANT: UI service uses Express Mode and requires delete-express-gateway-service API
# Standard delete-service will NOT work for Express Mode services

# Delete UI service (Express Mode)
aws ecs delete-express-gateway-service \
  --service-arn arn:aws:ecs:us-west-2:976884845791:service/mcp-demo-cluster/ui-service \
  --region us-west-2 \
  --profile smanubol-admin

# Delete Agent and MCP Server services (standard services)
aws ecs delete-service --cluster mcp-demo-cluster --service agent-service --force --region us-west-2 --profile smanubol-admin
aws ecs delete-service --cluster mcp-demo-cluster --service mcp-server-service --force --region us-west-2 --profile smanubol-admin

# Wait for services to drain
sleep 60

# Delete ECR images (required before CloudFormation can delete repos)
aws ecr delete-repository --repository-name mcp-server --force --region us-west-2 --profile smanubol-admin
aws ecr delete-repository --repository-name agent --force --region us-west-2 --profile smanubol-admin
aws ecr delete-repository --repository-name ui --force --region us-west-2 --profile smanubol-admin

# Empty S3 bucket
aws s3 rm s3://mcp-demo-product-catalog-976884845791 --recursive --profile smanubol-admin

# Delete Express Mode orphan security group (created by ECS Express Mode, not CloudFormation)
# Find the security group named: <cluster>-ui-service-<vpc-id>
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=tag:Name,Values=mcp-demo-infrastructure-vpc" \
  --query "Vpcs[0].VpcId" --output text --region us-west-2 --profile smanubol-admin)
ORPHAN_SG=$(aws ec2 describe-security-groups --filters Name=vpc-id,Values=$VPC_ID \
  --query "SecurityGroups[?contains(GroupName, 'ui-service')].GroupId" --output text \
  --region us-west-2 --profile smanubol-admin)
[ -n "$ORPHAN_SG" ] && aws ec2 delete-security-group --group-id $ORPHAN_SG --region us-west-2 --profile smanubol-admin

# Delete CloudFormation stack (deletes all infrastructure)
aws cloudformation delete-stack --stack-name mcp-demo-infrastructure --region us-west-2 --profile smanubol-admin
```

**Note:** Express Mode services have `ResourceManagementType=ECS` and manage their own ALB infrastructure. The `delete-express-gateway-service` API properly cleans up the ALB, target groups, and auto-scaling policies created by Express Mode.

**Known Cleanup Issue:** ECS Express Mode creates a security group named `<cluster>-<service>-<vpc-id>` at runtime (not managed by CloudFormation). This must be deleted manually before the VPC can be removed.

## Cost Considerations

- **Fargate**: Pay per vCPU and memory per second
- **ALB**: Hourly charge + LCU (Load Balancer Capacity Units)
- **NAT Gateway**: Hourly charge + data processing
- **CloudWatch Logs**: Storage and ingestion
- **S3**: Storage and requests
- **Data Transfer**: Outbound data transfer charges

**Estimated Monthly Cost** (1 task per service, minimal traffic):
- Fargate: ~$30-40
- ALB: ~$20-25
- NAT Gateway: ~$35-40
- CloudWatch Logs: ~$5-10
- S3: <$1
- **Total**: ~$90-115/month

## Additional Notes

- All Docker images must be built for `linux/amd64` platform
- Service Connect uses short DNS names for simplified configuration
- Express Mode automatically manages ALB lifecycle
- Infrastructure role requires broad permissions for Express Mode automation
- Health check endpoint must return HTTP 200 for service to be healthy
- Auto-scaling based on CPU utilization (70% target)

## References

- [ECS Express Mode Documentation](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-overview.html)
- [ECS Service Connect](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-connect.html)
- [AWS Cloud Map](https://docs.aws.amazon.com/cloud-map/)
- [Fargate Task Definitions](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-definition-parameters.html)

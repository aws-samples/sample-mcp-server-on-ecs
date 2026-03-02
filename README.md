# MCP on Amazon ECS with Service Connect

This project demonstrates how to deploy Model Context Protocol (MCP) servers on Amazon ECS Fargate using ECS Service Connect for service-to-service communication. You build and deploy a three-tier application where a Gradio web interface sends natural language queries to an AI agent, which uses MCP tools to search a product catalog stored in Amazon S3.

## Architecture

```
Internet → ALB (Express Mode) → UI Service (Gradio)
                                    ↓ Service Connect
                                Agent Service (Strands + Bedrock)
                                    ↓ Service Connect
                                MCP Server (FastMCP)
                                    ↓
                                S3 Bucket (Product Catalog)
```

### Components

- **MCP Server**: FastMCP server providing product catalog search tools via HTTP/SSE transport
- **Agent**: Strands agent orchestrating MCP tool calls with Amazon Bedrock (Nova Lite model)
- **UI**: Gradio web interface for natural language product queries

### AWS Services Used

- Amazon ECS Fargate with Service Connect
- Amazon Bedrock (Nova Lite model)
- Application Load Balancer (ECS Express Mode)
- AWS Cloud Map for service discovery
- Amazon S3 for product data
- Amazon ECR for container images
- AWS CloudFormation for infrastructure provisioning
- Amazon CloudWatch for logging and monitoring

## Prerequisites

- **AWS CLI v2 ≥ 2.32.0** — run `aws --version` to check
- **Docker ≥ 20.10** with buildx support — run `docker --version` to check
- **Git** — to clone the repository
- **jq** — run `jq --version` to check
- **Amazon Bedrock model access** — enable the Amazon Nova Lite model in your AWS account via the [Bedrock console](https://console.aws.amazon.com/bedrock/home#/modelaccess)

## Directory Structure

```
├── cloudformation/
│   └── infrastructure.yaml      # VPC, ECS cluster, IAM roles, ECR repos
├── mcp-server/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/mcp_server.py        # FastMCP server with S3 integration
├── agent/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/agent.py             # Strands agent with Bedrock
├── ui/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                   # Gradio chat interface
├── sample-data/
│   └── product-catalog.json     # Sample product data
└── docs/
    └── TROUBLESHOOTING.md       # Common issues and solutions
```


## Deployment

**Estimated deployment time:** 25-30 minutes

### Step 1: Clone Repository and Set Variables

```bash
git clone https://github.com/aws-samples/ecs-mcp-blog.git
cd ecs-mcp-blog

# Set your variables (modify these for your environment)
export STACK_NAME=ecs-mcp-blog
export AWS_REGION=us-west-2
export AWS_PROFILE=default
```

### Step 2: Deploy Infrastructure

Deploy the AWS CloudFormation stack that creates the VPC, Amazon ECS cluster, IAM roles, and Amazon ECR repositories.

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

### Step 3: Get Stack Outputs

```bash
# Get AWS Account ID
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile $AWS_PROFILE)
export ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Get all AWS CloudFormation outputs in one call
OUTPUTS=$(aws cloudformation describe-stacks --stack-name $STACK_NAME --region $AWS_REGION --profile $AWS_PROFILE --query 'Stacks[0].Outputs')

# Parse outputs into environment variables
export CLUSTER_NAME=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="ECSClusterName") | .OutputValue')
export S3_BUCKET=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="S3BucketName") | .OutputValue')
export PRIVATE_SUBNETS=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="PrivateSubnetIds") | .OutputValue')
export PUBLIC_SUBNETS=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="PublicSubnetIds") | .OutputValue')
export MCP_SG=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="MCPServerSecurityGroupId") | .OutputValue')
export AGENT_SG=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="AgentSecurityGroupId") | .OutputValue')
export UI_SG=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="UISecurityGroupId") | .OutputValue')
export EXECUTION_ROLE=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="TaskExecutionRoleArn") | .OutputValue')
export INFRA_ROLE=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="ECSExpressInfrastructureRoleArn") | .OutputValue')
export UI_TASK_ROLE=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="UITaskRoleArn") | .OutputValue')
export UI_ECR=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="UIECRRepositoryUri") | .OutputValue')
export UI_LOG_GROUP=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="UILogGroupName") | .OutputValue')
export VPC_ID=$(echo $OUTPUTS | jq -r '.[] | select(.OutputKey=="VpcId") | .OutputValue')

# Verify key outputs — all values should be non-empty
echo "Cluster:    $CLUSTER_NAME"
echo "S3 Bucket:  $S3_BUCKET"
echo "ECR:        $ECR_REGISTRY"
echo "Priv Subs:  $PRIVATE_SUBNETS"
echo "Pub Subs:   $PUBLIC_SUBNETS"
echo "Infra Role: $INFRA_ROLE"
```

> If any value shows `null` or is empty, the stack may not have completed successfully. Re-run the validation in Step 2.

### Step 4: Login to Amazon ECR

```bash
aws ecr get-login-password --region $AWS_REGION --profile $AWS_PROFILE | \
  docker login --username AWS --password-stdin $ECR_REGISTRY
```

### Step 5: Upload Product Catalog

```bash
aws s3 cp sample-data/product-catalog.json s3://$S3_BUCKET/product-catalog.json \
  --region $AWS_REGION --profile $AWS_PROFILE
```

**Validate:**

```bash
# Should return product-catalog.json with size ~5 KiB
aws s3 ls s3://$S3_BUCKET/ --region $AWS_REGION --profile $AWS_PROFILE
```

### Step 6: Build and Push Docker Images

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

### Step 7: Create Service Connect Config Files

```bash
mkdir -p config

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

### Step 8: Deploy Amazon ECS Services

Deploy the MCP Server and Agent as standard Amazon ECS services, and the UI using ECS Express Mode.

#### MCP Server Service

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

#### Agent Service

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

**Validate:** Wait for MCP Server and Agent to stabilize before deploying UI.

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

> Both services should show `runningCount: 1`. If `runningCount` is 0, check for task failures:
> ```bash
> TASK_ARN=$(aws ecs list-tasks --cluster $CLUSTER_NAME --service-name mcp-server-service \
>   --desired-status STOPPED --region $AWS_REGION --profile $AWS_PROFILE \
>   --query 'taskArns[0]' --output text)
> aws ecs describe-tasks --cluster $CLUSTER_NAME --tasks $TASK_ARN \
>   --region $AWS_REGION --profile $AWS_PROFILE \
>   --query 'tasks[0].[stoppedReason,containers[].reason]' --output text
> ```

#### UI Service (Express Mode)

The UI service uses ECS Express Mode, which provisions an Application Load Balancer automatically. Deploy it in three steps:

**Create the UI service:**

```bash
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
```

**Wait for the service to stabilize (~4 minutes):**

```bash
aws ecs wait services-stable \
  --cluster $CLUSTER_NAME \
  --services ui-service \
  --region $AWS_REGION \
  --profile $AWS_PROFILE
```

**Add Service Connect (required for UI to reach Agent):**

```bash
aws ecs update-service \
  --cluster $CLUSTER_NAME \
  --service ui-service \
  --service-connect-configuration file://config/${STACK_NAME}-ui-service-connect.json \
  --force-new-deployment \
  --region $AWS_REGION \
  --profile $AWS_PROFILE
```

> **Note:** Express Mode does not support Service Connect on initial creation. The update step adds the Envoy sidecar needed for UI to communicate with Agent via `http://agent:3000`.

> **Deployment Time:** Express Mode uses canary deployments with a 6-minute bake time. Wait 6-7 minutes after the update for traffic to shift to the new task.

### Step 9: Verify Deployment

```bash
# Check service status
aws ecs describe-services \
  --cluster $CLUSTER_NAME \
  --services mcp-server-service agent-service ui-service \
  --region $AWS_REGION \
  --profile $AWS_PROFILE \
  --query 'services[].[serviceName,status,runningCount,desiredCount]' \
  --output table

# Get UI public URL via Express Mode API
UI_SERVICE_ARN=$(aws ecs describe-services --cluster $CLUSTER_NAME --services ui-service \
  --region $AWS_REGION --profile $AWS_PROFILE \
  --query 'services[0].serviceArn' --output text)

UI_ENDPOINT=$(aws ecs describe-express-gateway-service \
  --service-arn $UI_SERVICE_ARN \
  --region $AWS_REGION --profile $AWS_PROFILE \
  --query 'service.activeConfigurations[0].ingressPaths[0].endpoint' --output text)

echo "UI URL: https://${UI_ENDPOINT}/"
```

### Step 10: Test the Application

Open the UI URL in your browser and try queries like:
- "Show me electronics under $100"
- "What laptops do you have?"
- "Find running shoes in stock"


## Cleanup

> **Important:** This deployment creates billable AWS resources. Follow these steps to remove all resources and avoid ongoing charges.

### Delete the UI Service

Express Mode requires a separate API for deletion.

```bash
UI_SERVICE_ARN=$(aws ecs describe-services --cluster $CLUSTER_NAME --services ui-service \
  --region $AWS_REGION --profile $AWS_PROFILE \
  --query 'services[0].serviceArn' --output text)

aws ecs delete-express-gateway-service \
  --service-arn $UI_SERVICE_ARN \
  --region $AWS_REGION \
  --profile $AWS_PROFILE
```

### Delete Standard Services

```bash
aws ecs delete-service --cluster $CLUSTER_NAME --service agent-service --force \
  --region $AWS_REGION --profile $AWS_PROFILE

aws ecs delete-service --cluster $CLUSTER_NAME --service mcp-server-service --force \
  --region $AWS_REGION --profile $AWS_PROFILE
```

### Wait for Services to Drain

Express Mode needs extra time to release the ALB and security groups it created at runtime.

```bash
echo "Waiting 120 seconds for services and Express Mode resources to drain..."
sleep 120
```

### Delete Express Mode Orphan Resources

Express Mode creates an ALB and security groups at runtime that are not managed by AWS CloudFormation. Remove them before deleting the VPC.

```bash
# Delete orphan ALB in the VPC (if it exists)
ALB_ARN=$(aws elbv2 describe-load-balancers --region $AWS_REGION --profile $AWS_PROFILE \
  --query "LoadBalancers[?VpcId=='${VPC_ID}' && contains(LoadBalancerName, 'ecs-express-gateway')].LoadBalancerArn" \
  --output text)
[ -n "$ALB_ARN" ] && aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN \
  --region $AWS_REGION --profile $AWS_PROFILE && sleep 30
```

```bash
# Delete orphan security groups created by ECS Express Mode
for SG in $(aws ec2 describe-security-groups --filters Name=vpc-id,Values=$VPC_ID \
  --query "SecurityGroups[?GroupName != 'default'].GroupId" --output text \
  --region $AWS_REGION --profile $AWS_PROFILE); do
  aws ec2 delete-security-group --group-id $SG --region $AWS_REGION --profile $AWS_PROFILE 2>/dev/null || true
done
```

### Empty Amazon S3 Buckets

Versioned buckets require deleting all object versions and delete markers before AWS CloudFormation can remove them.

```bash
# Empty product catalog bucket
aws s3 rm s3://$S3_BUCKET --recursive --profile $AWS_PROFILE
aws s3api delete-objects --bucket $S3_BUCKET \
  --delete "$(aws s3api list-object-versions --bucket $S3_BUCKET \
    --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' --output json --profile $AWS_PROFILE)" \
  --region $AWS_REGION --profile $AWS_PROFILE 2>/dev/null || true
aws s3api delete-objects --bucket $S3_BUCKET \
  --delete "$(aws s3api list-object-versions --bucket $S3_BUCKET \
    --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' --output json --profile $AWS_PROFILE)" \
  --region $AWS_REGION --profile $AWS_PROFILE 2>/dev/null || true
```

```bash
# Empty access logs bucket
ACCESS_LOGS_BUCKET="${STACK_NAME}-access-logs-${AWS_ACCOUNT_ID}"
aws s3 rm s3://$ACCESS_LOGS_BUCKET --recursive --profile $AWS_PROFILE 2>/dev/null || true
aws s3api delete-objects --bucket $ACCESS_LOGS_BUCKET \
  --delete "$(aws s3api list-object-versions --bucket $ACCESS_LOGS_BUCKET \
    --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' --output json --profile $AWS_PROFILE)" \
  --region $AWS_REGION --profile $AWS_PROFILE 2>/dev/null || true
aws s3api delete-objects --bucket $ACCESS_LOGS_BUCKET \
  --delete "$(aws s3api list-object-versions --bucket $ACCESS_LOGS_BUCKET \
    --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' --output json --profile $AWS_PROFILE)" \
  --region $AWS_REGION --profile $AWS_PROFILE 2>/dev/null || true
```

### Delete Amazon ECR Repositories

Amazon ECR repositories must be emptied before AWS CloudFormation can delete them.

```bash
aws ecr delete-repository --repository-name ${STACK_NAME}-mcp-server --force \
  --region $AWS_REGION --profile $AWS_PROFILE
aws ecr delete-repository --repository-name ${STACK_NAME}-agent --force \
  --region $AWS_REGION --profile $AWS_PROFILE
aws ecr delete-repository --repository-name ${STACK_NAME}-ui --force \
  --region $AWS_REGION --profile $AWS_PROFILE
```

### Delete the AWS CloudFormation Stack

```bash
aws cloudformation delete-stack --stack-name $STACK_NAME \
  --region $AWS_REGION --profile $AWS_PROFILE

aws cloudformation wait stack-delete-complete --stack-name $STACK_NAME \
  --region $AWS_REGION --profile $AWS_PROFILE

echo "Stack deleted successfully."
```

**Validate cleanup:** Confirm the stack is gone.

```bash
# Should return an error indicating the stack does not exist
aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --region $AWS_REGION \
  --profile $AWS_PROFILE 2>&1 | head -1
```

### Delete Retained Log Groups

Amazon CloudWatch log groups are retained by AWS CloudFormation by design. Remove them manually.

```bash
for LOG_GROUP in /ecs/${STACK_NAME}/mcp-server /ecs/${STACK_NAME}/agent /ecs/${STACK_NAME}/ui \
  /ecs/${STACK_NAME}/mcp-server-service-connect /ecs/${STACK_NAME}/agent-service-connect \
  /ecs/${STACK_NAME}/ui-service-connect; do
  aws logs delete-log-group --log-group-name $LOG_GROUP \
    --region $AWS_REGION --profile $AWS_PROFILE 2>/dev/null || true
done
```

### Manual VPC Cleanup (if needed)

If the AWS CloudFormation stack deletion fails on the VPC resource (for example, due to lingering ENIs or dependencies), you can manually delete the VPC:

1. Open the [VPC console](https://console.aws.amazon.com/vpc/).
2. Select the VPC tagged with your stack name.
3. Choose **Delete VPC** to remove the VPC and its associated subnets, route tables, and internet gateways.


## Troubleshooting

### Service Connect Issues

If the UI cannot connect to the Agent, redeploy with Service Connect:

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

For detailed troubleshooting guidance, including root cause analysis for common issues, see [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md).

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

## Conclusion

You have deployed a three-tier MCP application on Amazon ECS Fargate with ECS Service Connect handling service-to-service communication. The architecture uses Amazon Bedrock for AI inference, FastMCP for tool serving, and Gradio for the web interface. To extend this project, you can add more MCP tools to the server, swap the AI model, or integrate additional data sources through Amazon S3.

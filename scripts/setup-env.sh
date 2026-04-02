#!/bin/bash
# setup-env.sh - Export CloudFormation stack outputs as environment variables
# Usage: source scripts/setup-env.sh

# Verify required variables
check_var() { eval "[ -n \"\${$1}\" ]"; }
for var in STACK_NAME AWS_REGION AWS_PROFILE; do
    if ! check_var "$var"; then
        echo "ERROR: $var is not set. Run: export $var=<value>"
        return 1 2>/dev/null || exit 1
    fi
done

# Account and ECR registry
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile $AWS_PROFILE)
export ECR_REGISTRY="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# Fetch all stack outputs
OUTPUTS=$(aws cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --profile "$AWS_PROFILE" \
    --query 'Stacks[0].Outputs' 2>/dev/null)

if [ -z "$OUTPUTS" ] || [ "$OUTPUTS" = "null" ]; then
    echo "ERROR: Stack '$STACK_NAME' not found or has no outputs."
    return 1 2>/dev/null || exit 1
fi

get_output() { echo "$OUTPUTS" | jq -r ".[] | select(.OutputKey==\"$1\") | .OutputValue"; }

export CLUSTER_NAME=$(get_output ECSClusterName)
export S3_BUCKET=$(get_output S3BucketName)
export PRIVATE_SUBNETS=$(get_output PrivateSubnetIds)
export PUBLIC_SUBNETS=$(get_output PublicSubnetIds)
export MCP_SG=$(get_output MCPServerSecurityGroupId)
export AGENT_SG=$(get_output AgentSecurityGroupId)
export UI_SG=$(get_output UISecurityGroupId)
export EXECUTION_ROLE=$(get_output TaskExecutionRoleArn)
export INFRA_ROLE=$(get_output ECSExpressInfrastructureRoleArn)
export UI_TASK_ROLE=$(get_output UITaskRoleArn)
export UI_ECR=$(get_output UIECRRepositoryUri)
export UI_LOG_GROUP=$(get_output UILogGroupName)
export VPC_ID=$(get_output VpcId)

# Verify
echo "✅ Environment variables set:"
echo "   Cluster:    $CLUSTER_NAME"
echo "   S3 Bucket:  $S3_BUCKET"
echo "   ECR:        $ECR_REGISTRY"
echo "   Priv Subs:  $PRIVATE_SUBNETS"
echo "   Pub Subs:   $PUBLIC_SUBNETS"
echo "   Infra Role: $INFRA_ROLE"

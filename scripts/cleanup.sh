#!/bin/bash
# cleanup.sh - Remove all resources created by the ECS MCP Blog deployment
set -o pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

FAILED_STEPS=()

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "\n${GREEN}==>${NC} $1"; }

record_failure() { FAILED_STEPS+=("$1"); }

# Check required variables
check_variables() {
    local missing=()
    [ -z "$STACK_NAME" ] && missing+=("STACK_NAME")
    [ -z "$AWS_REGION" ] && missing+=("AWS_REGION")
    [ -z "$AWS_PROFILE" ] && missing+=("AWS_PROFILE")
    
    if [ ${#missing[@]} -ne 0 ]; then
        log_error "Missing required environment variables: ${missing[*]}"
        echo ""
        echo "Please set the variables used during deployment:"
        echo "  export STACK_NAME=ecs-mcp-blog"
        echo "  export AWS_REGION=us-west-2"
        echo "  export AWS_PROFILE=default"
        exit 1
    fi
}

# Get stack outputs
get_stack_outputs() {
    log_step "Retrieving stack outputs..."
    
    OUTPUTS=$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" --profile "$AWS_PROFILE" \
        --query 'Stacks[0].Outputs' 2>/dev/null)
    
    if [ -z "$OUTPUTS" ] || [ "$OUTPUTS" = "null" ]; then
        log_warn "Stack '$STACK_NAME' not found or has no outputs. Some cleanup steps may fail."
        return 1
    fi
    
    CLUSTER_NAME=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="ECSClusterName") | .OutputValue')
    S3_BUCKET=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="S3BucketName") | .OutputValue')
    VPC_ID=$(echo "$OUTPUTS" | jq -r '.[] | select(.OutputKey=="VpcId") | .OutputValue')
    AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text --profile "$AWS_PROFILE")
    
    log_info "Cluster: $CLUSTER_NAME"
    log_info "S3 Bucket: $S3_BUCKET"
    log_info "VPC: $VPC_ID"
}

# Delete ECS services in parallel
delete_ecs_services() {
    log_step "Deleting ECS services (parallel)..."
    
    # Delete UI service (Express Mode)
    (
        UI_SERVICE_ARN=$(aws ecs describe-services --cluster "$CLUSTER_NAME" --services ui-service \
            --region "$AWS_REGION" --profile "$AWS_PROFILE" \
            --query 'services[0].serviceArn' --output text 2>/dev/null)
        
        if [ -n "$UI_SERVICE_ARN" ] && [ "$UI_SERVICE_ARN" != "None" ]; then
            log_info "Deleting UI service (Express Mode)..."
            aws ecs delete-express-gateway-service --service-arn "$UI_SERVICE_ARN" \
                --region "$AWS_REGION" --profile "$AWS_PROFILE" 2>/dev/null
        fi
    ) &
    
    # Delete Agent service
    (
        log_info "Deleting Agent service..."
        aws ecs delete-service --cluster "$CLUSTER_NAME" --service agent-service --force \
            --region "$AWS_REGION" --profile "$AWS_PROFILE" 2>/dev/null
    ) &
    
    # Delete MCP Server service
    (
        log_info "Deleting MCP Server service..."
        aws ecs delete-service --cluster "$CLUSTER_NAME" --service mcp-server-service --force \
            --region "$AWS_REGION" --profile "$AWS_PROFILE" 2>/dev/null
    ) &
    
    wait
    log_info "Service deletion initiated"
}

# Wait for services to drain
wait_for_drain() {
    log_step "Waiting for services to drain (90s)..."
    sleep 90
}

# Delete Express Mode orphan resources
delete_express_mode_resources() {
    log_step "Deleting Express Mode orphan resources..."
    
    # Delete ALB
    ALB_ARN=$(aws elbv2 describe-load-balancers --region "$AWS_REGION" --profile "$AWS_PROFILE" \
        --query "LoadBalancers[?VpcId=='${VPC_ID}' && contains(LoadBalancerName, 'ecs-express-gateway')].LoadBalancerArn" \
        --output text 2>/dev/null)
    
    if [ -n "$ALB_ARN" ] && [ "$ALB_ARN" != "None" ]; then
        log_info "Deleting Express Mode ALB..."
        aws elbv2 delete-load-balancer --load-balancer-arn "$ALB_ARN" \
            --region "$AWS_REGION" --profile "$AWS_PROFILE" 2>/dev/null || record_failure "Delete ALB"
        sleep 30
    fi
    
    # Delete orphan security groups
    log_info "Deleting orphan security groups..."
    for SG in $(aws ec2 describe-security-groups --filters "Name=vpc-id,Values=$VPC_ID" \
        --query "SecurityGroups[?GroupName != 'default'].GroupId" --output text \
        --region "$AWS_REGION" --profile "$AWS_PROFILE" 2>/dev/null); do
        aws ec2 delete-security-group --group-id "$SG" \
            --region "$AWS_REGION" --profile "$AWS_PROFILE" 2>/dev/null || true
    done
}

# Empty S3 bucket (handles versioning)
empty_s3_bucket() {
    local bucket=$1
    log_info "Emptying bucket: $bucket"
    
    aws s3 rm "s3://$bucket" --recursive --profile "$AWS_PROFILE" > /dev/null 2>&1 || true
    
    # Delete versions
    aws s3api delete-objects --bucket "$bucket" \
        --delete "$(aws s3api list-object-versions --bucket "$bucket" \
            --query '{Objects: Versions[].{Key:Key,VersionId:VersionId}}' \
            --output json --profile "$AWS_PROFILE" 2>/dev/null)" \
        --region "$AWS_REGION" --profile "$AWS_PROFILE" > /dev/null 2>&1 || true
    
    # Delete markers
    aws s3api delete-objects --bucket "$bucket" \
        --delete "$(aws s3api list-object-versions --bucket "$bucket" \
            --query '{Objects: DeleteMarkers[].{Key:Key,VersionId:VersionId}}' \
            --output json --profile "$AWS_PROFILE" 2>/dev/null)" \
        --region "$AWS_REGION" --profile "$AWS_PROFILE" > /dev/null 2>&1 || true
}

# Empty all S3 buckets
empty_s3_buckets() {
    log_step "Emptying S3 buckets..."
    
    [ -n "$S3_BUCKET" ] && empty_s3_bucket "$S3_BUCKET"
    
    ACCESS_LOGS_BUCKET="${STACK_NAME}-access-logs-${AWS_ACCOUNT_ID}"
    empty_s3_bucket "$ACCESS_LOGS_BUCKET"
}

# Delete ECR repositories
delete_ecr_repos() {
    log_step "Deleting ECR repositories..."
    
    for repo in mcp-server agent ui; do
        log_info "Deleting ${STACK_NAME}-${repo}..."
        aws ecr delete-repository --repository-name "${STACK_NAME}-${repo}" --force \
            --region "$AWS_REGION" --profile "$AWS_PROFILE" 2>/dev/null || record_failure "Delete ECR: $repo"
    done
}

# Delete CloudFormation stack
delete_stack() {
    log_step "Deleting CloudFormation stack..."
    
    aws cloudformation delete-stack --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" --profile "$AWS_PROFILE" || { record_failure "Delete stack"; return 1; }
    
    log_info "Waiting for stack deletion (this may take several minutes)..."
    aws cloudformation wait stack-delete-complete --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" --profile "$AWS_PROFILE" || record_failure "Stack deletion wait"
}

# Delete retained log groups
delete_log_groups() {
    log_step "Deleting CloudWatch log groups..."
    
    for suffix in mcp-server agent ui mcp-server-service-connect agent-service-connect ui-service-connect; do
        aws logs delete-log-group --log-group-name "/ecs/${STACK_NAME}/${suffix}" \
            --region "$AWS_REGION" --profile "$AWS_PROFILE" 2>/dev/null || true
    done
}

# Verify resources are deleted
verify_cleanup() {
    log_step "Verifying resource cleanup..."
    local remaining=()

    # Check CloudFormation stack
    if aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
        --region "$AWS_REGION" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
        remaining+=("CloudFormation stack: $STACK_NAME")
    fi

    # Check ECS services
    for svc in ui-service agent-service mcp-server-service; do
        local status
        status=$(aws ecs describe-services --cluster "$CLUSTER_NAME" --services "$svc" \
            --region "$AWS_REGION" --profile "$AWS_PROFILE" \
            --query 'services[0].status' --output text 2>/dev/null)
        if [ -n "$status" ] && [ "$status" != "None" ] && [ "$status" != "INACTIVE" ]; then
            remaining+=("ECS service: $svc ($status)")
        fi
    done

    # Check S3 buckets
    for bucket in "$S3_BUCKET" "${STACK_NAME}-access-logs-${AWS_ACCOUNT_ID}"; do
        if aws s3api head-bucket --bucket "$bucket" --profile "$AWS_PROFILE" 2>/dev/null; then
            remaining+=("S3 bucket: $bucket")
        fi
    done

    # Check ECR repositories
    for repo in mcp-server agent ui; do
        if aws ecr describe-repositories --repository-names "${STACK_NAME}-${repo}" \
            --region "$AWS_REGION" --profile "$AWS_PROFILE" > /dev/null 2>&1; then
            remaining+=("ECR repository: ${STACK_NAME}-${repo}")
        fi
    done

    # Check log groups
    for suffix in mcp-server agent ui mcp-server-service-connect agent-service-connect ui-service-connect; do
        if aws logs describe-log-groups --log-group-name-prefix "/ecs/${STACK_NAME}/${suffix}" \
            --region "$AWS_REGION" --profile "$AWS_PROFILE" \
            --query 'logGroups[0].logGroupName' --output text 2>/dev/null | grep -q "/ecs/"; then
            remaining+=("Log group: /ecs/${STACK_NAME}/${suffix}")
        fi
    done

    echo ""
    if [ ${#remaining[@]} -eq 0 ]; then
        log_info "✅ All resources successfully deleted!"
    else
        log_warn "⚠️  The following resources still exist:"
        for r in "${remaining[@]}"; do
            echo "  - $r"
        done
    fi
}

# Print summary
print_summary() {
    echo ""
    if [ ${#FAILED_STEPS[@]} -eq 0 ]; then
        log_info "Cleanup completed successfully!"
    else
        log_warn "Cleanup completed with errors:"
        for step in "${FAILED_STEPS[@]}"; do
            echo "  - $step"
        done
        echo ""
        echo "Manual cleanup may be required. Check the AWS Console for:"
        echo "  - VPC: https://console.aws.amazon.com/vpc/"
        echo "  - ECS: https://console.aws.amazon.com/ecs/"
        echo "  - S3: https://console.aws.amazon.com/s3/"
    fi
}

# Main
main() {
    echo "=========================================="
    echo "  ECS MCP Blog - Cleanup Script"
    echo "=========================================="
    
    check_variables
    
    echo ""
    echo "This will delete ALL resources for stack: $STACK_NAME"
    echo "Region: $AWS_REGION | Profile: $AWS_PROFILE"
    echo ""
    read -p "Are you sure you want to continue? (y/N) " -n 1 -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Cleanup cancelled."
        exit 0
    fi
    
    get_stack_outputs
    delete_ecs_services
    wait_for_drain
    delete_express_mode_resources
    empty_s3_buckets
    delete_ecr_repos
    delete_stack
    delete_log_groups
    verify_cleanup
    print_summary
}

main

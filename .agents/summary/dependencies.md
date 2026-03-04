# Dependencies Documentation

## Python Dependencies

### MCP Server (`mcp-server/requirements.txt`)
| Package | Purpose |
|---------|---------|
| `fastmcp` | MCP protocol server implementation |
| `boto3` | AWS SDK for S3 access |
| `starlette` | ASGI framework (FastMCP dependency) |

### Agent (`agent/requirements.txt`)
| Package | Purpose |
|---------|---------|
| `strands-agents` | AI agent framework |
| `flask` | REST API framework |
| `mcp` | MCP client library |
| `boto3` | AWS SDK for Bedrock |
| `requests` | HTTP client for health checks |

### UI (`ui/requirements.txt`)
| Package | Purpose |
|---------|---------|
| `gradio` | Web interface framework |
| `requests` | HTTP client for Agent API |

---

## AWS Service Dependencies

| Service | Purpose | Required Permissions |
|---------|---------|---------------------|
| Amazon ECS Fargate | Container hosting | Task execution |
| Amazon ECR | Container registry | Push/pull images |
| Amazon Bedrock | AI inference | InvokeModel |
| Amazon S3 | Data storage | GetObject |
| AWS Cloud Map | Service discovery | Auto-managed by ECS |
| CloudWatch Logs | Logging | CreateLogStream, PutLogEvents |
| AWS KMS | Encryption | Encrypt, Decrypt |

---

## Infrastructure Dependencies

### CloudFormation Stack Outputs
| Output | Used By |
|--------|---------|
| `ECSClusterName` | Service deployment |
| `S3BucketName` | MCP Server config |
| `PrivateSubnetIds` | Agent, MCP Server networking |
| `PublicSubnetIds` | UI networking |
| `*SecurityGroupId` | Service networking |
| `TaskExecutionRoleArn` | ECS task execution |
| `*TaskRoleArn` | Service-specific permissions |
| `*ECRRepositoryUri` | Docker image push |
| `*LogGroupName` | CloudWatch logging |

---

## Container Base Images

All services use: `python:3.12-slim`

### System Packages
- `curl` - Health checks
- `ca-certificates` - HTTPS connections

---

## External Dependencies

| Dependency | Version Requirement | Notes |
|------------|---------------------|-------|
| AWS CLI | ≥ 2.32.0 | ECS Express Mode support |
| Docker | ≥ 20.10 | buildx support required |
| jq | Any | JSON parsing in scripts |
| Git | Any | Repository cloning |

---

## Model Dependencies

| Model | Provider | Usage |
|-------|----------|-------|
| Amazon Nova Lite | Amazon Bedrock | Natural language processing |

**Model ID**: `global.amazon.nova-2-lite-v1:0`

**Required**: Enable model access in [Bedrock console](https://console.aws.amazon.com/bedrock/home#/modelaccess)

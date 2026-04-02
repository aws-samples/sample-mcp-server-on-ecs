# Codebase Information

## Project Overview
- **Name**: MCP on Amazon ECS with Service Connect
- **Type**: Three-tier AI-powered product catalog application
- **Primary Languages**: Python (100%)
- **Infrastructure**: AWS CloudFormation (YAML)

## Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | Gradio | Web chat interface |
| Agent | Strands Agents + Flask | AI orchestration with Amazon Bedrock |
| Backend | FastMCP | MCP server with Streamable HTTP transport |
| AI Model | Amazon Bedrock (Nova Lite) | Natural language processing |
| Infrastructure | AWS ECS Fargate | Container orchestration |
| Networking | ECS Service Connect | Service-to-service communication |
| Storage | Amazon S3 | Product catalog JSON storage |
| IaC | AWS CloudFormation | Infrastructure provisioning |

## Directory Structure

```
aws-mcp-ecs-blog/
├── cloudformation/
│   └── infrastructure.yaml      # VPC, ECS cluster, IAM, ECR repos
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
├── config/
│   └── *.json                   # ECS Service Connect configs
├── docs/
│   └── TROUBLESHOOTING.md       # Common issues and solutions
└── images/
    └── architecture-diagram.png # Solution architecture
```

## Service Ports

| Service | Port | Protocol |
|---------|------|----------|
| UI | 7860 | HTTP |
| Agent | 3000 | HTTP/REST |
| MCP Server | 8080 | HTTP |

## Dependencies

### MCP Server
- `fastmcp` - MCP protocol implementation
- `boto3` - AWS SDK for S3 access
- `starlette` - ASGI framework

### Agent
- `strands-agents` - AI agent framework
- `flask` - REST API framework
- `mcp` - MCP client library
- `boto3` - AWS SDK for Bedrock

### UI
- `gradio` - Web interface framework
- `requests` - HTTP client

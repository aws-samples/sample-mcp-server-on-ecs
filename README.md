# MCP on Amazon ECS with Service Connect

Deploy Model Context Protocol (MCP) servers on Amazon ECS Fargate using ECS Service Connect for service-to-service communication.

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
- **MCP Server**: FastMCP server providing product catalog search tools
- **Agent**: Strands agent orchestrating MCP tool calls with Amazon Bedrock
- **UI**: Gradio web interface for natural language product queries

### AWS Services
- Amazon ECS Fargate with Service Connect
- Amazon Bedrock (Nova Lite model)
- Application Load Balancer (ECS Express Mode)
- AWS Cloud Map for service discovery
- Amazon S3 for product data
- Amazon ECR for container images

## Quick Start

See [docs/QUICKSTART.md](docs/QUICKSTART.md) for step-by-step deployment instructions.

**Estimated deployment time:** 25-30 minutes

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
    ├── QUICKSTART.md            # Deployment guide
    ├── DEPLOYMENT.md            # Detailed reference
    └── TROUBLESHOOTING.md       # Common issues and solutions
```

## Prerequisites

- AWS CLI configured with appropriate permissions
- Docker with buildx support
- Amazon Bedrock model access enabled (Nova Lite)

## Documentation

- [QUICKSTART.md](docs/QUICKSTART.md) - Step-by-step deployment
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Detailed deployment reference
- [TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) - Common issues and fixes

## Security

See [CONTRIBUTING](CONTRIBUTING.md#security-issue-notifications) for more information.

## License

This library is licensed under the MIT-0 License. See the LICENSE file.

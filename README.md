# AWS MCP ECS Blog - Product Catalog Search

This project demonstrates how to deploy MCP (Model Context Protocol) servers on Amazon ECS Fargate using ECS Service Connect for service-to-service communication.

## Architecture

The infrastructure includes:
- VPC with public and private subnets across 2 AZs
- ECS Cluster with Fargate capacity provider
- Two ECS services: MCP Server and Agent
- AWS Cloud Map for service discovery
- S3 bucket for product catalog data
- ECR repositories for container images

## Directory Structure

```
aws-mcp-ecs-blog/
├── README.md
├── cloudformation/
│   └── infrastructure.yaml      # Base infrastructure template
├── mcp-server/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       └── mcp_server.py
├── agent/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       └── agent.py
├── sample-data/
│   └── product-catalog.json
├── config/
│   ├── mcp-server-task-def.json
│   ├── agent-task-def.json
│   ├── mcp-server-service-connect.json
│   └── agent-service-connect.json
└── docs/
    └── deployment-guide.md
```

## Deployment

1. Deploy the base infrastructure:
```bash
aws cloudformation deploy \
  --template-file cloudformation/infrastructure.yaml \
  --stack-name mcp-demo-infrastructure \
  --capabilities CAPABILITY_IAM
```

2. Build and push container images to ECR

3. Deploy ECS services using the task definitions in `config/`

## License

MIT License

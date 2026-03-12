# Documentation Index

> **For AI Assistants**: This file serves as your primary reference for understanding this codebase. Use the summaries below to identify which detailed documentation files to consult for specific questions.

## Quick Reference

| Question Type | Consult |
|---------------|---------|
| "How does the system work?" | [architecture.md](architecture.md) |
| "What does X service do?" | [components.md](components.md) |
| "What's the API for X?" | [interfaces.md](interfaces.md) |
| "What's the data format?" | [data_models.md](data_models.md) |
| "How do I deploy/cleanup?" | [workflows.md](workflows.md) |
| "What packages are used?" | [dependencies.md](dependencies.md) |
| "Basic project info?" | [codebase_info.md](codebase_info.md) |

---

## Project Summary

This is a **three-tier AI-powered product catalog** deployed on AWS ECS Fargate:
1. **UI** (Gradio) → User-facing chat interface
2. **Agent** (Strands + Bedrock) → AI orchestration
3. **MCP Server** (FastMCP) → Product data access via MCP protocol

All services communicate via **ECS Service Connect** (Envoy sidecars + Cloud Map).

---

## Documentation Files

### [codebase_info.md](codebase_info.md)
**Tags**: `#overview` `#structure` `#tech-stack`

Basic project information including directory structure, technology stack, service ports, and Python dependencies per service.

### [architecture.md](architecture.md)
**Tags**: `#architecture` `#diagrams` `#security` `#networking`

System architecture with Mermaid diagrams showing:
- Overall system topology (VPC, subnets, services)
- Request flow sequence diagram
- Security architecture and controls
- Design patterns (three-tier, service mesh, MCP)

### [components.md](components.md)
**Tags**: `#components` `#services` `#functions` `#endpoints`

Detailed documentation for each service:
- UI Service: Gradio chat function
- Agent Service: REST endpoints, Strands Agent setup
- MCP Server: MCP tools, catalog loading
- Infrastructure: CloudFormation resources

### [interfaces.md](interfaces.md)
**Tags**: `#api` `#rest` `#mcp` `#service-connect` `#aws`

API specifications including:
- Agent REST API (POST /chat, GET /health, POST /reset)
- MCP Server tools (search_products, get_product_details, check_availability)
- Service Connect configuration format
- AWS service integrations (Bedrock, S3, ECR)

### [data_models.md](data_models.md)
**Tags**: `#data` `#schema` `#json` `#models`

Data structures including:
- Product catalog JSON schema
- Catalog cache structure
- API request/response models
- Conversation state format

### [workflows.md](workflows.md)
**Tags**: `#workflows` `#deployment` `#cleanup` `#troubleshooting`

Process documentation with flowcharts:
- Deployment workflow (10 steps)
- Query processing workflow
- Catalog loading workflow
- Cleanup workflow
- Error recovery procedures

### [dependencies.md](dependencies.md)
**Tags**: `#dependencies` `#python` `#aws` `#docker`

Dependency information:
- Python packages per service
- AWS service dependencies with required permissions
- CloudFormation stack outputs
- External tool requirements (AWS CLI, Docker, jq)

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `cloudformation/infrastructure.yaml` | All AWS resources |
| `mcp-server/app/mcp_server.py` | MCP tools implementation |
| `agent/app/agent.py` | AI agent with Bedrock |
| `ui/app.py` | Gradio chat interface |
| `sample-data/product-catalog.json` | Sample product data |
| `docs/TROUBLESHOOTING.md` | Issue resolution guide |
| `README.md` | Full deployment instructions |

---

## Common Tasks

### Add a new MCP tool
1. Edit `mcp-server/app/mcp_server.py`
2. Add function with `@mcp.tool()` decorator
3. Rebuild and push Docker image
4. Force service redeployment

### Modify AI behavior
1. Edit `agent/app/agent.py`
2. Update `system_prompt` in `create_agent()`
3. Rebuild and push Docker image

### Change product data
1. Edit `sample-data/product-catalog.json`
2. Upload to S3: `aws s3 cp sample-data/product-catalog.json s3://$S3_BUCKET/`
3. MCP Server auto-refreshes on next request

### Debug Service Connect issues
1. Check Envoy logs in CloudWatch
2. Verify Cloud Map namespace
3. Force redeployment with `--force-new-deployment`

# AGENTS.md - AI Assistant Guide

> This file provides context for AI coding assistants working with this codebase.

## Project Overview

Three-tier AI-powered product catalog on AWS ECS Fargate:
- **UI** (Gradio :7860) → Chat interface
- **Agent** (Flask :3000) → AI orchestration with Amazon Bedrock
- **MCP Server** (FastMCP :8080) → Product data via MCP protocol

Services communicate via ECS Service Connect (Envoy + Cloud Map).

## Directory Structure

```
├── cloudformation/infrastructure.yaml   # All AWS resources (VPC, ECS, IAM, S3, ECR)
├── mcp-server/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/mcp_server.py               # FastMCP server - MCP tools here
├── agent/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/agent.py                    # Strands Agent - AI logic here
├── ui/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app.py                          # Gradio UI - chat function here
├── sample-data/product-catalog.json    # Product data (upload to S3)
├── config/*.json                       # ECS Service Connect configs
└── docs/TROUBLESHOOTING.md             # Issue resolution
```

## Key Code Locations

| Task | File | Function/Section |
|------|------|------------------|
| Add MCP tool | `mcp-server/app/mcp_server.py` | Add `@mcp.tool()` decorated function |
| Modify AI behavior | `agent/app/agent.py` | Edit `system_prompt` in `create_agent()` |
| Change UI | `ui/app.py` | Edit `chat()` or Gradio config |
| Add AWS resource | `cloudformation/infrastructure.yaml` | Add to Resources section |
| Fix IAM permissions | `cloudformation/infrastructure.yaml` | Find `*TaskRole` policies |

## Coding Patterns

### MCP Tool Pattern
```python
@mcp.tool()
def tool_name(param: str, optional_param: Optional[int] = None) -> str:
    """Docstring becomes tool description for AI."""
    # Implementation
    return json.dumps(result, indent=2)
```

### Flask Endpoint Pattern
```python
@app.route("/endpoint", methods=["POST"])
def endpoint():
    data = request.get_json()
    # Validate, process, return jsonify({...})
```

### Environment Variables
- Services use `os.getenv("VAR", "default")` pattern
- Defaults configured for ECS Service Connect DNS names
- Override via Dockerfile ENV or ECS task definition

## Testing Locally

No test suite exists. To test manually:

```bash
# MCP Server (requires S3 bucket)
cd mcp-server && pip install -r requirements.txt
S3_BUCKET=your-bucket python -m app.mcp_server

# Agent (requires MCP Server running)
cd agent && pip install -r requirements.txt
MCP_SERVER_ENDPOINT=http://localhost:8080 python app/agent.py

# UI (requires Agent running)
cd ui && pip install -r requirements.txt
AGENT_ENDPOINT=http://localhost:3000 python app.py
```

## Build & Deploy Changes

```bash
# Rebuild single service
docker buildx build --platform linux/amd64 \
  -t $ECR_REGISTRY/${STACK_NAME}-SERVICE:latest \
  ./SERVICE --push

# Force redeploy
aws ecs update-service --cluster $CLUSTER_NAME \
  --service SERVICE-service --force-new-deployment
```

## Common Issues

| Issue | Solution |
|-------|----------|
| UI can't reach Agent | Redeploy UI with `--force-new-deployment` |
| Bedrock AccessDenied | Add `inference-profile/*` to Agent task role |
| Catalog not loading | Check S3 bucket name and IAM permissions |
| Service Connect DNS fails | Check Cloud Map namespace, redeploy service |

## File Purposes

| File | When to Modify |
|------|----------------|
| `mcp_server.py` | Adding/changing product search capabilities |
| `agent.py` | Changing AI behavior, adding endpoints |
| `app.py` | UI changes, error handling |
| `infrastructure.yaml` | AWS resources, IAM, networking |
| `product-catalog.json` | Sample data for testing |
| `TROUBLESHOOTING.md` | Documenting new issues |

## Detailed Documentation

For comprehensive information, see `.agents/summary/index.md` which links to:
- `architecture.md` - System diagrams
- `components.md` - Service details
- `interfaces.md` - API specs
- `data_models.md` - Data schemas
- `workflows.md` - Deployment steps
- `dependencies.md` - Package info

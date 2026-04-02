# Interfaces Documentation

## API Interfaces

### Agent Service REST API

**Base URL**: `http://agent:3000`

#### POST /chat
Process a natural language query through the AI agent.

**Request**:
```json
{
  "message": "Find laptops under $1000",
  "conversation_id": "optional-uuid"
}
```

**Response**:
```json
{
  "success": true,
  "response": "I found 2 laptops under $1000...",
  "conversation_id": "uuid",
  "tools_used": ["search_products"]
}
```

#### GET /health
Health check endpoint.

**Response**:
```json
{
  "status": "healthy",
  "mcp_server_connected": true,
  "mcp_server_endpoint": "http://mcp-server:8080",
  "bedrock_model": "global.amazon.nova-2-lite-v1:0",
  "bedrock_accessible": true,
  "tools_available": ["search_products", "get_product_details", "check_availability"]
}
```

#### POST /reset
Reset conversation history.

**Request**:
```json
{
  "conversation_id": "uuid-to-reset"
}
```

---

### MCP Server Tools (via Streamable HTTP)

**Streamable HTTP Endpoint**: `http://mcp-server:8080/mcp/`

#### search_products
```json
{
  "query": "wireless headphones",
  "category": "Electronics",
  "max_price": 200,
  "min_price": 50,
  "in_stock_only": true,
  "features": "noise cancellation"
}
```

#### get_product_details
```json
{
  "product_id": "P001"
}
```

#### check_availability
```json
{
  "product_id": "P001"
}
```

---

## Service Connect Configuration

### Namespace
`${STACK_NAME}.local`

### Service Discovery Names
| Service | DNS Name | Port |
|---------|----------|------|
| MCP Server | `mcp-server` | 8080 |
| Agent | `agent` | 3000 |

### Config File Structure
```json
{
  "enabled": true,
  "namespace": "${STACK_NAME}.local",
  "services": [
    {
      "portName": "port-name",
      "discoveryName": "service-name",
      "clientAliases": [{"port": 8080, "dnsName": "service-name"}]
    }
  ],
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/${STACK_NAME}/service-connect",
      "awslogs-region": "${AWS_REGION}",
      "awslogs-stream-prefix": "envoy"
    }
  }
}
```

---

## AWS Service Integrations

### Amazon Bedrock
- **Action**: `bedrock:InvokeModel`
- **Model**: `global.amazon.nova-2-lite-v1:0`
- **Region**: Configurable via `AWS_REGION`

### Amazon S3
- **Action**: `s3:GetObject`
- **Bucket**: Created by CloudFormation
- **Key**: `product-catalog.json`

### Amazon ECR
- **Repositories**: `${STACK_NAME}-mcp-server`, `${STACK_NAME}-agent`, `${STACK_NAME}-ui`
- **Tag Immutability**: Enabled

### CloudWatch Logs
- **Log Groups**: `/ecs/${STACK_NAME}/{service}`
- **Encryption**: KMS customer-managed key

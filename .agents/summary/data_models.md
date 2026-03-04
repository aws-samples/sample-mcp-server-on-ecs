# Data Models Documentation

## Product Catalog Schema

### Product Object
```json
{
  "id": "P001",
  "name": "ProBook 15 Laptop",
  "category": "Electronics",
  "price": 899.99,
  "in_stock": true,
  "features": [
    "15.6-inch Full HD display",
    "Intel Core i7 processor",
    "16GB RAM, 512GB SSD"
  ]
}
```

### Field Definitions
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique product identifier (e.g., "P001") |
| `name` | string | Yes | Product display name |
| `category` | string | Yes | Product category (Electronics, Sports, Clothing) |
| `price` | number | Yes | Price in USD |
| `in_stock` | boolean | Yes | Availability status |
| `features` | string[] | Yes | List of product features |

### Categories
- Electronics
- Sports
- Clothing

---

## Catalog Cache Structure

```python
catalog_cache = {
    "products": [],           # List of product objects
    "loaded": False,          # Whether catalog has been loaded
    "last_refresh": None      # ISO timestamp of last S3 fetch
}
```

---

## API Request/Response Models

### Chat Request
```json
{
  "message": "string (required)",
  "conversation_id": "string (optional, UUID)"
}
```

### Chat Response
```json
{
  "success": true,
  "response": "string",
  "conversation_id": "string",
  "tools_used": ["string"]
}
```

### Health Response (Agent)
```json
{
  "status": "healthy|unhealthy",
  "mcp_server_connected": true,
  "mcp_server_endpoint": "string",
  "bedrock_model": "string",
  "bedrock_accessible": true,
  "tools_available": ["string"]
}
```

### Health Response (MCP Server)
```json
{
  "status": "healthy",
  "catalog_loaded": true,
  "product_count": 10,
  "last_refresh": "ISO timestamp",
  "s3_bucket": "string",
  "catalog_file": "string"
}
```

---

## Conversation State

```python
conversations: dict = {
    "conversation_id": [
        {"role": "user", "content": "..."},
        {"role": "assistant", "content": "..."}
    ]
}
```

Stored in-memory on Agent service. Reset via `POST /reset`.

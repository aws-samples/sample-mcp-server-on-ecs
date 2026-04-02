# Architecture Documentation

## System Architecture

```mermaid
graph TB
    subgraph Internet
        User[User Browser]
    end
    
    subgraph AWS["AWS Cloud"]
        subgraph VPC["VPC (10.0.0.0/16)"]
            subgraph Public["Public Subnets"]
                ALB[Application Load Balancer]
                UI[UI Service<br/>Gradio :7860]
            end
            
            subgraph Private["Private Subnets"]
                Agent[Agent Service<br/>Flask :3000]
                MCP[MCP Server<br/>FastMCP :8080]
            end
        end
        
        Bedrock[Amazon Bedrock<br/>Nova Lite]
        S3[(Amazon S3<br/>Product Catalog)]
        CloudMap[AWS Cloud Map<br/>Service Discovery]
    end
    
    User -->|HTTPS| ALB
    ALB -->|HTTP| UI
    UI -->|Service Connect| Agent
    Agent -->|Service Connect| MCP
    Agent -->|InvokeModel| Bedrock
    MCP -->|GetObject| S3
    
    CloudMap -.->|DNS| UI
    CloudMap -.->|DNS| Agent
    CloudMap -.->|DNS| MCP
```

## Request Flow

```mermaid
sequenceDiagram
    participant U as User
    participant UI as UI Service
    participant A as Agent Service
    participant B as Amazon Bedrock
    participant M as MCP Server
    participant S3 as Amazon S3
    
    U->>UI: Natural language query
    UI->>A: POST /chat {message}
    A->>B: InvokeModel (Nova Lite)
    B-->>A: Tool call decision
    A->>M: MCP tool request (Streamable HTTP)
    M->>S3: GetObject (catalog)
    S3-->>M: Product data
    M-->>A: Tool response
    A->>B: Tool result
    B-->>A: Final response
    A-->>UI: JSON response
    UI-->>U: Formatted answer
```

## Design Patterns

### Three-Tier Architecture
- **Presentation**: Gradio UI handles user interaction
- **Business Logic**: Strands Agent orchestrates AI reasoning
- **Data Access**: MCP Server abstracts S3 data operations

### Service Mesh (ECS Service Connect)
- Envoy sidecar proxies handle service discovery
- AWS Cloud Map provides DNS-based routing
- Traffic stays within VPC for security

### MCP Protocol
- Streamable HTTP transport for stateless request/response communication
- Tool-based abstraction for data operations
- Stateless request handling with in-memory catalog cache

## Security Architecture

```mermaid
graph LR
    subgraph Public
        ALB[ALB]
    end
    
    subgraph Private
        UI[UI SG]
        Agent[Agent SG]
        MCP[MCP SG]
    end
    
    ALB -->|:7860| UI
    UI -->|:3000| Agent
    Agent -->|:8080| MCP
```

### Security Controls
- **Network Isolation**: Private subnets for Agent and MCP Server
- **Security Groups**: Per-service ingress rules
- **IAM Roles**: Least-privilege task roles
- **KMS Encryption**: CloudWatch Logs and ECR repos
- **S3 TLS Enforcement**: Bucket policy denying non-HTTPS

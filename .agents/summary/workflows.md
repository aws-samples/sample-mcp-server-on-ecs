# Workflows Documentation

## Deployment Workflow

```mermaid
flowchart TD
    A[Clone Repository] --> B[Set Environment Variables]
    B --> C[Deploy CloudFormation Stack]
    C --> D[Get Stack Outputs]
    D --> E[Login to ECR]
    E --> F[Upload Product Catalog to S3]
    F --> G[Build & Push Docker Images]
    G --> H[Create Service Connect Configs]
    H --> I[Deploy MCP Server Service]
    I --> J[Deploy Agent Service]
    J --> K[Wait for Services to Stabilize]
    K --> L[Deploy UI Service - Express Mode]
    L --> M[Update UI with Service Connect]
    M --> N[Verify Deployment]
```

## Query Processing Workflow

```mermaid
flowchart TD
    A[User Query] --> B[UI: chat function]
    B --> C[POST to Agent /chat]
    C --> D[Agent: Create MCP Client]
    D --> E[Agent: Create Strands Agent]
    E --> F[Agent: Call Bedrock]
    F --> G{Tool Call Needed?}
    G -->|Yes| H[MCP: Execute Tool]
    H --> I[Return Tool Result]
    I --> F
    G -->|No| J[Format Response]
    J --> K[Return to UI]
    K --> L[Display to User]
```

## Catalog Loading Workflow

```mermaid
flowchart TD
    A[MCP Server Starts] --> B[load_catalog_from_s3]
    B --> C[S3 GetObject]
    C --> D{Success?}
    D -->|Yes| E[Parse JSON]
    E --> F[Update catalog_cache]
    F --> G[Set loaded=true]
    D -->|No| H[Log Error]
    H --> I[catalog_cache.loaded=false]
    
    J[Tool Request] --> K{catalog_cache.loaded?}
    K -->|No| B
    K -->|Yes| L[Return cached data]
```

## Cleanup Workflow

```mermaid
flowchart TD
    A[Start Cleanup] --> B[Delete UI Service - Express Mode API]
    B --> C[Delete Agent Service]
    C --> D[Delete MCP Server Service]
    D --> E[Wait 120s for Drain]
    E --> F[Delete Express Mode ALB]
    F --> G[Delete Orphan Security Groups]
    G --> H[Empty S3 Buckets]
    H --> I[Delete ECR Repositories]
    I --> J[Delete CloudFormation Stack]
    J --> K[Delete Retained Log Groups]
```

## Service Connect Initialization

```mermaid
sequenceDiagram
    participant ECS as ECS Service
    participant Envoy as Envoy Sidecar
    participant CM as Cloud Map
    
    ECS->>Envoy: Start sidecar container
    Envoy->>CM: Register service
    CM-->>Envoy: Namespace config
    Envoy->>Envoy: Configure iptables
    Envoy->>Envoy: Setup egress listener
    Note over Envoy: Ready to intercept traffic
    ECS->>ECS: Start application container
```

## Error Recovery Workflows

### Service Connect Failure
1. Check Envoy logs for cluster configuration
2. Verify Cloud Map namespace registration
3. Force service redeployment with `--force-new-deployment`
4. Wait for new task with fresh Envoy sidecar

### Bedrock Access Failure
1. Check Agent task role IAM policy
2. Verify inference-profile permissions
3. Update IAM policy via CloudFormation or direct API
4. No service restart needed (IAM changes immediate)

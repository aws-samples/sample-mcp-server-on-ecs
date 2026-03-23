#!/bin/bash
# generate-service-connect-configs.sh - Create Service Connect JSON configs
# Usage: ./scripts/generate-service-connect-configs.sh

for var in STACK_NAME AWS_REGION; do
    if [ -z "${!var}" ]; then
        echo "ERROR: $var is not set. Run: source scripts/setup-env.sh"
        exit 1
    fi
done

mkdir -p config

cat > config/${STACK_NAME}-mcp-server-service-connect.json << EOF
{
  "enabled": true,
  "namespace": "${STACK_NAME}.local",
  "services": [
    {
      "portName": "mcp-port",
      "discoveryName": "mcp-server",
      "clientAliases": [{"port": 8080, "dnsName": "mcp-server"}]
    }
  ],
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/${STACK_NAME}/mcp-server-service-connect",
      "awslogs-region": "${AWS_REGION}",
      "awslogs-stream-prefix": "envoy"
    }
  }
}
EOF

cat > config/${STACK_NAME}-agent-service-connect.json << EOF
{
  "enabled": true,
  "namespace": "${STACK_NAME}.local",
  "services": [
    {
      "portName": "agent-port",
      "discoveryName": "agent",
      "clientAliases": [{"port": 3000, "dnsName": "agent"}]
    }
  ],
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/${STACK_NAME}/agent-service-connect",
      "awslogs-region": "${AWS_REGION}",
      "awslogs-stream-prefix": "envoy"
    }
  }
}
EOF

cat > config/${STACK_NAME}-ui-service-connect.json << EOF
{
  "enabled": true,
  "namespace": "${STACK_NAME}.local",
  "services": [],
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/${STACK_NAME}/ui-service-connect",
      "awslogs-region": "${AWS_REGION}",
      "awslogs-stream-prefix": "envoy"
    }
  }
}
EOF

echo "✅ Service Connect configs created:"
ls -1 config/${STACK_NAME}-*-service-connect.json

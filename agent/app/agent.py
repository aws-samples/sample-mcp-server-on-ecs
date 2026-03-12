"""
Strands Agent - AI-Powered Product Catalog Assistant
Runs on ECS Fargate and orchestrates conversations between users,
Amazon Bedrock Foundation Models, and an MCP server for product search.
"""

import os
import logging
import traceback
import uuid
from typing import Optional

from flask import Flask, request, jsonify
from mcp.client.sse import sse_client
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp import MCPClient

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("strands-agent")

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================
MCP_SERVER_ENDPOINT = os.getenv("MCP_SERVER_ENDPOINT", "http://mcp-server:8080")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "global.amazon.nova-2-lite-v1:0")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "3000"))

# =============================================================================
# FLASK APP SETUP
# =============================================================================
app = Flask(__name__)

# =============================================================================
# GLOBAL STATE
# =============================================================================
conversations: dict = {}  # Store conversation histories by ID
available_tools: list = []  # Cache of available MCP tools


# =============================================================================
# MCP CLIENT SETUP
# =============================================================================
def create_mcp_client() -> MCPClient:
    """Create MCP client with SSE transport for the product catalog server."""
    sse_url = f"{MCP_SERVER_ENDPOINT}/sse"
    logger.info(f"Creating MCP client for: {sse_url}")
    return MCPClient(lambda: sse_client(sse_url))


# =============================================================================
# STRANDS AGENT SETUP
# =============================================================================
def create_agent(mcp_client: MCPClient, conversation_id: Optional[str] = None) -> Agent:
    """
    Create a Strands Agent with Bedrock model and MCP tools.
    
    Args:
        mcp_client: Initialized MCP client with tools
        conversation_id: Optional conversation ID for history management
    
    Returns:
        Configured Strands Agent
    """
    # Configure Bedrock model
    model = BedrockModel(
        model_id=BEDROCK_MODEL_ID,
        region_name=AWS_REGION,
        temperature=0.3,  # Lower temperature for factual product queries
        max_tokens=2048
    )
    
    # Get tools from MCP client
    tools = mcp_client.list_tools_sync()
    
    # Create agent with system prompt for product catalog assistance
    system_prompt = """You are a helpful product catalog assistant. You help users find products, 
check availability, and get product details using the available tools.

When users ask about products:
1. Use search_products to find products matching their criteria
2. Use get_product_details to get detailed information about specific products
3. Use check_availability to check if products are in stock

Always provide clear, helpful responses with product names, prices, and relevant details.
Format prices as currency (e.g., $79.99) and highlight key features."""

    # Get conversation history if exists
    messages = []
    if conversation_id and conversation_id in conversations:
        messages = conversations[conversation_id]
    
    agent = Agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        messages=messages
    )
    
    return agent


# =============================================================================
# REST API ENDPOINTS
# =============================================================================
@app.route("/chat", methods=["POST"])
def chat():
    """
    Process a chat message through the Strands Agent.
    
    Request Body:
        message: User's natural language query
        conversation_id: Optional conversation ID for context
    
    Returns:
        Agent's response with tools used
    """
    logger.info(f"POST /chat - received request")
    
    try:
        # Parse request
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body must be JSON"
            }), 400
        
        message = data.get("message")
        if not message:
            return jsonify({
                "success": False,
                "error": "Missing required field: message"
            }), 400
        
        conversation_id = data.get("conversation_id") or str(uuid.uuid4())
        
        logger.info(f"Processing message: {message[:100]}... (conversation: {conversation_id})")
        
        # Create MCP client and agent within context
        mcp_client = create_mcp_client()
        tools_used = []
        
        with mcp_client:
            agent = create_agent(mcp_client, conversation_id)
            
            # Process the message
            logger.info("Calling Strands Agent...")
            response = agent(message)
            
            # Extract tools used from agent's last turn
            if hasattr(agent, 'messages') and agent.messages:
                for msg in agent.messages:
                    if hasattr(msg, 'content'):
                        for content in msg.get('content', []):
                            if isinstance(content, dict) and content.get('toolUse'):
                                tool_name = content['toolUse'].get('name')
                                if tool_name and tool_name not in tools_used:
                                    tools_used.append(tool_name)
            
            # Store conversation history
            conversations[conversation_id] = agent.messages
            
            logger.info(f"Agent response generated. Tools used: {tools_used}")
        
        return jsonify({
            "success": True,
            "response": str(response),
            "conversation_id": conversation_id,
            "tools_used": tools_used
        })
        
    except ConnectionError as e:
        logger.error(f"MCP server connection failed: {e}")
        return jsonify({
            "success": False,
            "error": "MCP server unavailable"
        }), 503
    except Exception as e:
        logger.error(f"Chat error: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500



@app.route("/health", methods=["GET"])
def health():
    """
    Health check endpoint.
    
    Returns:
        Health status including MCP server and Bedrock connectivity
    """
    logger.info("GET /health")
    
    mcp_connected = False
    tools_available = []
    bedrock_accessible = False
    
    # Check MCP server connectivity
    try:
        import requests
        response = requests.get(f"{MCP_SERVER_ENDPOINT}/health", timeout=5)
        mcp_connected = response.status_code == 200
        
        # Try to list tools if connected
        if mcp_connected:
            mcp_client = create_mcp_client()
            with mcp_client:
                tools = mcp_client.list_tools_sync()
                # MCPAgentTool objects have mcp_tool.name, not direct .name
                tools_available = [t.mcp_tool.name if hasattr(t, 'mcp_tool') else str(t) for t in tools]
    except Exception as e:
        logger.warning(f"MCP server health check failed: {e}")
    
    # Check Bedrock accessibility
    try:
        import boto3
        bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        # Simple check - just verify client creation works
        bedrock_accessible = True
    except Exception as e:
        logger.warning(f"Bedrock access check failed: {e}")
    
    status = "healthy" if (mcp_connected and bedrock_accessible) else "unhealthy"
    
    return jsonify({
        "status": status,
        "mcp_server_connected": mcp_connected,
        "mcp_server_endpoint": MCP_SERVER_ENDPOINT,
        "bedrock_model": BEDROCK_MODEL_ID,
        "bedrock_accessible": bedrock_accessible,
        "tools_available": tools_available
    })


@app.route("/reset", methods=["POST"])
def reset():
    """
    Reset conversation history for a given conversation ID.
    
    Request Body:
        conversation_id: Conversation ID to reset
    
    Returns:
        Success status
    """
    logger.info("POST /reset")
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({
                "success": False,
                "error": "Request body must be JSON"
            }), 400
        
        conversation_id = data.get("conversation_id")
        if not conversation_id:
            return jsonify({
                "success": False,
                "error": "Missing required field: conversation_id"
            }), 400
        
        # Remove conversation from history
        if conversation_id in conversations:
            del conversations[conversation_id]
            logger.info(f"Reset conversation: {conversation_id}")
            return jsonify({
                "success": True,
                "message": f"Conversation {conversation_id} reset successfully"
            })
        else:
            return jsonify({
                "success": True,
                "message": f"Conversation {conversation_id} not found (already cleared)"
            })
            
    except Exception as e:
        logger.error(f"Reset error: {e}\n{traceback.format_exc()}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =============================================================================
# ERROR HANDLERS
# =============================================================================
@app.errorhandler(400)
def bad_request(error):
    """Handle bad request errors."""
    return jsonify({
        "success": False,
        "error": "Bad request"
    }), 400


@app.errorhandler(404)
def not_found(error):
    """Handle not found errors."""
    return jsonify({
        "success": False,
        "error": "Resource not found"
    }), 404


@app.errorhandler(500)
def internal_error(error):
    """Handle internal server errors."""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "success": False,
        "error": "Internal server error"
    }), 500


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main():
    """Main entry point for the Strands Agent."""
    logger.info("=" * 60)
    logger.info("Starting Strands Agent")
    logger.info(f"MCP Server Endpoint: {MCP_SERVER_ENDPOINT}")
    logger.info(f"Bedrock Model: {BEDROCK_MODEL_ID}")
    logger.info(f"AWS Region: {AWS_REGION}")
    logger.info(f"Listening on {HOST}:{PORT}")
    logger.info("=" * 60)
    
    # Verify MCP server connection on startup
    try:
        import requests
        response = requests.get(f"{MCP_SERVER_ENDPOINT}/health", timeout=5)
        if response.status_code == 200:
            logger.info("Successfully connected to MCP server")
            
            # List available tools
            mcp_client = create_mcp_client()
            with mcp_client:
                tools = mcp_client.list_tools_sync()
                tool_names = [t.name for t in tools]
                logger.info(f"Available tools from MCP server: {tool_names}")
                global available_tools
                available_tools = tool_names
        else:
            logger.warning(f"MCP server returned status {response.status_code}")
    except Exception as e:
        logger.warning(f"Initial MCP server connection failed: {e}")
        logger.info("Agent will retry connection on incoming requests")
    
    # Verify Bedrock access
    try:
        import boto3
        bedrock = boto3.client("bedrock-runtime", region_name=AWS_REGION)
        logger.info("Bedrock client initialized successfully")
    except Exception as e:
        logger.warning(f"Bedrock client initialization failed: {e}")
        logger.info("Bedrock access will be verified on first request")
    
    # Run Flask app
    app.run(host=HOST, port=PORT, debug=False)


if __name__ == "__main__":
    main()

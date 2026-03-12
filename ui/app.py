"""
Gradio UI for AWS Product Catalog Search
Connects to Strands Agent backend via HTTP for natural language product queries.
"""

import gradio as gr
import os
import requests
import logging
import uuid

# Configuration
AGENT_ENDPOINT = os.getenv('AGENT_ENDPOINT', 'http://agent:3000')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Logging setup
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('gradio-ui')


def chat(message: str, history: list) -> str:
    """
    Send message to Strands Agent and return response.
    
    Args:
        message: User's query
        history: Chat history in OpenAI format (list of dicts with 'role' and 'content')
    
    Returns:
        Agent's response string
    """
    if not message.strip():
        return "Please enter a question about products."
    
    try:
        logger.info(f"Sending query to agent: {message}")
        
        # Call Strands Agent
        response = requests.post(
            f"{AGENT_ENDPOINT}/chat",
            json={
                "message": message,
                "conversation_id": str(uuid.uuid4())
            },
            timeout=60,
            headers={'Content-Type': 'application/json'}
        )
        
        response.raise_for_status()
        data = response.json()
        
        if data.get('success'):
            agent_response = data.get('response', 'No response from agent')
            logger.info("Received successful response from agent")
            return agent_response
        else:
            error_msg = data.get('error', 'Unknown error from agent')
            logger.warning(f"Agent returned error: {error_msg}")
            return f"❌ Agent error: {error_msg}"
    
    except requests.exceptions.Timeout:
        logger.error("Request to agent timed out")
        return "⏱️ Request timed out. The agent is taking longer than expected. Please try again."
    
    except requests.exceptions.ConnectionError:
        logger.error(f"Failed to connect to agent at {AGENT_ENDPOINT}")
        return "❌ Cannot connect to agent service. Please check if the agent is running."
    
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error from agent: {e}")
        status_code = e.response.status_code if e.response else 'Unknown'
        return f"❌ Agent returned an error (HTTP {status_code}). Please try again."
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error: {str(e)}")
        return "❌ Failed to communicate with the agent. Please try again."
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return "❌ An unexpected error occurred. Please try again."


# Custom CSS for AWS-themed styling
custom_css = """
.gradio-container {
    max-width: 900px !important;
    margin: auto !important;
}
footer {
    display: none !important;
}
"""

# Create Gradio ChatInterface
demo = gr.ChatInterface(
    fn=chat,
    title="🔍 AWS Product Catalog Search",
    description="Powered by Amazon Bedrock & Strands Agents | Ask questions about products in natural language",
    examples=[
        "Show me wireless headphones under $100",
        "Find running shoes in stock",
        "What laptops do you have?",
        "Show me electronics between $500 and $1000",
        "Are there any yoga mats available?"
    ]
)

if __name__ == "__main__":
    logger.info(f"Starting Gradio UI on 0.0.0.0:7860")
    logger.info(f"Agent endpoint: {AGENT_ENDPOINT}")
    
    # Launch Gradio directly - it handles / and returns 200
    demo.launch(server_name="0.0.0.0", server_port=7860)

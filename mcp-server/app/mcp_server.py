"""
MCP Server for Product Catalog Search
Runs on ECS Fargate and provides product search functionality via MCP protocol.
Reads product data from S3 bucket.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastmcp import FastMCP
from starlette.responses import JSONResponse

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mcp-server")

# =============================================================================
# ENVIRONMENT VARIABLES
# =============================================================================
S3_BUCKET = os.getenv("S3_BUCKET", "")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")
CATALOG_FILE = os.getenv("CATALOG_FILE", "product-catalog.json")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8080"))

# =============================================================================
# GLOBAL STATE
# =============================================================================
catalog_cache: dict = {"products": [], "loaded": False, "last_refresh": None}
s3_client = boto3.client("s3", region_name=AWS_REGION)

# =============================================================================
# S3 CATALOG FUNCTIONS
# =============================================================================
def load_catalog_from_s3() -> bool:
    """Load product catalog from S3 bucket into memory cache."""
    global catalog_cache
    
    logger.info(f"Loading catalog from s3://{S3_BUCKET}/{CATALOG_FILE}")
    
    try:
        response = s3_client.get_object(Bucket=S3_BUCKET, Key=CATALOG_FILE)
        content = response["Body"].read().decode("utf-8")
        data = json.loads(content)
        
        catalog_cache["products"] = data.get("products", [])
        catalog_cache["loaded"] = True
        catalog_cache["last_refresh"] = datetime.utcnow().isoformat()
        
        logger.info(f"Catalog loaded successfully: {len(catalog_cache['products'])} products")
        return True
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"S3 ClientError ({error_code}): {e}")
        return False
    except NoCredentialsError:
        logger.error("AWS credentials not found")
        return False
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in catalog file: {e}")
        return False
    except Exception as e:
        logger.exception(f"Unexpected error loading catalog: {e}")
        return False


def refresh_catalog() -> dict:
    """Refresh the catalog from S3 and return status."""
    success = load_catalog_from_s3()
    return {
        "success": success,
        "product_count": len(catalog_cache["products"]),
        "last_refresh": catalog_cache["last_refresh"]
    }


def get_catalog() -> list:
    """Get cached catalog, loading from S3 if not yet loaded."""
    if not catalog_cache["loaded"]:
        load_catalog_from_s3()
    return catalog_cache["products"]

# =============================================================================
# MCP SERVER SETUP
# =============================================================================
mcp = FastMCP("Product Catalog MCP Server")

# =============================================================================
# HTTP HEALTH CHECK ENDPOINT
# =============================================================================
@mcp.custom_route("/health", methods=["GET"])
async def health_endpoint(request):
    """HTTP health check endpoint for ECS/Docker health checks."""
    status = {
        "status": "healthy",
        "catalog_loaded": catalog_cache["loaded"],
        "product_count": len(catalog_cache["products"]),
        "last_refresh": catalog_cache["last_refresh"],
        "s3_bucket": S3_BUCKET,
        "catalog_file": CATALOG_FILE
    }
    return JSONResponse(status)

# =============================================================================
# MCP TOOLS
# =============================================================================
@mcp.tool()
def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    max_price: Optional[float] = None,
    min_price: Optional[float] = None,
    in_stock_only: bool = False,
    features: Optional[str] = None
) -> str:
    """
    Search products in the catalog with optional filters.
    
    Args:
        query: Free-text search across product name and features (e.g. "wireless headphones", "running shoes", "laptop")
        category: Filter by category (Electronics, Sports, Clothing)
        max_price: Maximum price filter
        min_price: Minimum price filter
        in_stock_only: Only return products that are in stock
        features: Filter by feature text (partial match)
    
    Returns:
        List of matching products
    """
    logger.info(f"search_products called: query={query}, category={category}, max_price={max_price}, "
                f"min_price={min_price}, in_stock_only={in_stock_only}, features={features}")
    
    products = get_catalog()
    results = []
    
    for product in products:
        # Free-text query filter (searches name + features)
        if query:
            searchable = product.get("name", "").lower() + " " + " ".join(product.get("features", [])).lower()
            query_terms = query.lower().split()
            if not all(term in searchable for term in query_terms):
                continue
        
        # Category filter
        if category and product.get("category", "").lower() != category.lower():
            continue
        
        # Price filters
        price = product.get("price", 0)
        if max_price is not None and price > max_price:
            continue
        if min_price is not None and price < min_price:
            continue
        
        # Stock filter
        if in_stock_only and not product.get("in_stock", False):
            continue
        
        # Features filter (partial match)
        if features:
            product_features = " ".join(product.get("features", [])).lower()
            if features.lower() not in product_features:
                continue
        
        results.append(product)
    
    logger.info(f"search_products returning {len(results)} results")
    return json.dumps(results, indent=2)


@mcp.tool()
def get_product_details(product_id: str) -> str:
    """
    Get detailed information for a specific product.
    
    Args:
        product_id: Product ID (e.g., "P001")
    
    Returns:
        Product object with all fields, or error dict if not found
    """
    logger.info(f"get_product_details called: product_id={product_id}")
    
    if not product_id:
        return json.dumps({"error": "product_id is required"})
    
    products = get_catalog()
    
    for product in products:
        if product.get("id") == product_id:
            logger.info(f"Found product: {product.get('name')}")
            return json.dumps(product, indent=2)
    
    logger.warning(f"Product not found: {product_id}")
    return json.dumps({"error": f"Product not found: {product_id}"})


@mcp.tool()
def check_availability(product_id: str) -> str:
    """
    Check if a product is in stock.
    
    Args:
        product_id: Product ID (e.g., "P001")
    
    Returns:
        Dict with in_stock status and product name
    """
    logger.info(f"check_availability called: product_id={product_id}")
    
    if not product_id:
        return json.dumps({"error": "product_id is required"})
    
    products = get_catalog()
    
    for product in products:
        if product.get("id") == product_id:
            return json.dumps({
                "product_id": product_id,
                "name": product.get("name"),
                "in_stock": product.get("in_stock", False)
            })
    
    return json.dumps({"error": f"Product not found: {product_id}"})


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================
def main():
    """Main entry point for the MCP server."""
    logger.info(f"Starting MCP Server on {HOST}:{PORT}")
    logger.info(f"S3 Bucket: {S3_BUCKET}")
    logger.info(f"Catalog File: {CATALOG_FILE}")
    
    # Pre-load catalog on startup
    load_catalog_from_s3()
    
    # Run the MCP server with SSE transport
    mcp.run(transport="sse", host=HOST, port=PORT)


if __name__ == "__main__":
    main()

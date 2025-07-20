from fastapi import FastAPI, Request, HTTPException

app = FastAPI()

# A simple check for the API key header
async def check_api_key(request: Request):
    if "x-internal-api-key" not in request.headers:
        raise HTTPException(status_code=401, detail="X-Internal-API-Key header missing")

@app.get("/orders/{order_id}")
async def get_order(order_id: str, request: Request):
    """
    Mocks the internal order service.
    It checks for an API key and returns a fake order with a product ID.
    """
    await check_api_key(request)
    return {
        "order_id": order_id,
        "customer_id": "c-456",
        "product_id": "p-987" # This is the key the MCP server will parse
    }

@app.get("/products/{product_id}")
async def get_product(product_id: str, request: Request):
    """
    Mocks the internal product service.
    It checks for an API key and returns the final product details.
    """
    await check_api_key(request)
    if product_id == "p-987":
        return {
            "product_name": "Quantum Widget",
            "price": 99.99,
            "in_stock": True
        }
    raise HTTPException(status_code=404, detail="Product not found")

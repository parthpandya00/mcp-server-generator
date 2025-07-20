#!/bin/bash
# A script to manage the full lifecycle of generating and testing an MCP server.
set -e

# --- Configuration ---
GENERATOR_IMAGE="mcp-generator"
GENERATOR_CONTAINER="mcp-generator-instance"
GENERATOR_HOST="http://localhost:8000"

MOCK_SERVER_IMAGE="mcp-mock-server"
MOCK_SERVER_CONTAINER="mcp-mock-instance"

MCP_SERVER_IMAGE="my-mcp-server"
MCP_SERVER_CONTAINER="my-mcp-server-instance"
MCP_SERVER_HOST="http://localhost:8002"

API_KEY="your-secret-key-here"

# --- Cleanup Function ---
cleanup() {
  echo "🧹 Cleaning up all running Docker containers..."
  docker stop $GENERATOR_CONTAINER $MOCK_SERVER_CONTAINER $MCP_SERVER_CONTAINER > /dev/null 2>&1 || true
  echo "✔️ Cleanup complete."
}
trap cleanup EXIT


# --- Helper function to create the request.json file ---
setup() {
  echo "✅ Creating the sample request.json file..."
  cat > request.json << EOF
{
  "openapi_spec": {
    "openapi": "3.0.3",
    "info": { "title": "Order Processing Service" },
    "paths": { "/orders/{order_id}/details": { "get": {
      "summary": "Get enriched order details", "operationId": "get_enriched_order_details",
      "parameters": [{ "name": "order_id", "in": "path", "required": true, "schema": { "type": "string" }}],
      "security": [{ "InternalApiKeyAuth": [] }],
      "x-mcp-source": { "type": "http", "steps": [
        { "step_id": "fetch_order", "method": "get", "url": "http://host.docker.internal:8001/orders/\${path_params.order_id}" },
        { "step_id": "get_product_details", "method": "get", "url": "http://host.docker.internal:8001/products/\${fetch_order.product_id}" }
      ]}
    }}},
    "components": { "securitySchemes": {
      "InternalApiKeyAuth": { "type": "apiKey", "in": "header", "name": "X-Internal-API-Key" }
    }}
  },
  "direct_credentials": {}
}
EOF
  echo "✔️ request.json created successfully."
}

# --- Main Workflow Functions ---
build_prerequisites() {
    echo "🛠️ Building prerequisite images (generator and mock server)..."
    docker build -t $GENERATOR_IMAGE -f docker/Dockerfile .
    docker build -t $MOCK_SERVER_IMAGE -f examples/Dockerfile ./examples
    echo "✔️ Prerequisite images built."
}

start_prerequisites() {
    echo "🚀 Starting prerequisite servers (generator and mock server)..."
    docker run -d --rm -p 8000:8000 --name $GENERATOR_CONTAINER $GENERATOR_IMAGE
    docker run -d --rm -p 8001:8001 --name $MOCK_SERVER_CONTAINER $MOCK_SERVER_IMAGE
    echo "⏳ Waiting for servers to be ready..."
    sleep 5
    echo "✔️ Prerequisite servers are running."
}

generate_and_run_mcp() {
    echo "📄 Generating the MCP server Dockerfile..."
    curl -s -X POST "$GENERATOR_HOST/generate-dockerfile" -H "Content-Type: application/json" --data @request.json -o Dockerfile

    echo "🛠️ Building the generated MCP server image..."
    docker build -t $MCP_SERVER_IMAGE .

    echo "🚀 Running the generated MCP server..."
    docker run -d --rm -p 8002:8000 --name $MCP_SERVER_CONTAINER --add-host=host.docker.internal:host-gateway $MCP_SERVER_IMAGE
    echo "⏳ Waiting for MCP server to be ready..."
    sleep 5
    echo "✔️ Generated MCP server is running on $MCP_SERVER_HOST."
}

run_tests() {
    echo "🧪 Running end-to-end tests..."
    echo
    echo "--- [REST Test] ---"
    curl -X GET "$MCP_SERVER_HOST/orders/123/details" -H "X-Internal-API-Key: $API_KEY"; echo
    echo
    echo "--- [RPC Test] ---"
    curl -X POST "$MCP_SERVER_HOST/rpc" -H "Content-Type: application/json" -H "X-Internal-API-Key: $API_KEY" -d '{"jsonrpc": "2.0", "method": "get_enriched_order_details", "params": {"order_id": "123"}, "id": 1}'; echo
    echo
    echo "✔️ Tests complete."
}

e2e_test() {
    setup
    build_prerequisites
    start_prerequisites
    generate_and_run_mcp
    run_tests
}


# --- Main script logic to route commands ---
case "$1" in
  setup) setup ;;
  build) build_prerequisites ;;
  start) start_prerequisites ;;
  generate) generate_and_run_mcp ;;
  test) run_tests ;;
  e2e_test) e2e_test ;;
  stop) cleanup ;;
  *) echo "Usage: $0 {setup|build|start|generate|test|e2e_test|stop}" && exit 1 ;;
esac
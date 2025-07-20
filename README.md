
-----

# MCP Server Generator 🚀

This project is a FastAPI application that generates custom, dockerized MCP (Message-oriented Communication Protocol) servers from an OpenAPI specification. It simplifies the creation of data ingestion and orchestration services by allowing you to define complex, multi-step workflows in a standard API document.

## Overview

The primary goal of this project is to automate the creation of specialized servers that can:

  * Ingest data from various sources like external APIs, databases, or object stores.
  * Orchestrate multi-step workflows (e.g., call API A, use its response to call API B).
  * Expose this data to clients through multiple communication protocols (REST, JSON-RPC, SSE, Stdio).

Instead of writing boilerplate code for each new data integration, you simply define the logic in an OpenAPI spec, and this generator builds the ready-to-deploy server for you.

-----

## How It Works

The generator acts as a "compiler" for your data ingestion logic. The process is decoupled into a build-time step (generation) and a run-time step (execution).

1.  **You Define the Logic**: You create an OpenAPI specification and use a custom extension, `x-mcp-source`, to describe the data sources and multi-step workflows for each API endpoint.
2.  **Generate the Server**: You send this OpenAPI spec to the running **Generator Server**.
3.  **The Generator Builds the Plan**: The generator doesn't write new Python code. Instead, it creates:
      * A **`Dockerfile`** that packages a pre-written, generic, and highly configurable MCP server.
      * An **`MCP_CONFIG`** JSON object, which is a simplified, optimized "instruction set" derived from your spec's `x-mcp-source` blocks. This config is embedded directly into the `Dockerfile` as an environment variable.
4.  **Run Your Custom Server**: You build the generated `Dockerfile`. When the container starts, the generic MCP server reads the `MCP_CONFIG` from its environment and dynamically configures itself to execute your specific workflows.

-----

## Capabilities

### Ingestion Channels

  * **External APIs**: Query any RESTful API. Supports multi-step, chained requests where the output of one step is the input for the next.
  * **Databases (Future)**: Placeholder for querying SQL/NoSQL databases.
  * **Object Stores (Future)**: Placeholder for fetching objects from services like AWS S3.

### Communication Transports

The generated server can communicate with clients using multiple protocols simultaneously.

| Feature | Stdio | Web (SSE) | StreamableHTTP |
| :--- | :--- | :--- | :--- |
| **Protocol** | JSON-RPC | JSON-RPC over SSE | JSON-RPC over HTTP |
| **Connection** | Persistent | Persistent | Request/Response |
| **Multiple Clients** | No | Yes | Yes |
| **Browser Compatible** | No | Yes | Yes |

### Authentication

The generated server acts as a pass-through proxy for authentication, forwarding credentials to the downstream services.

  * **API Key** (in Header or Query)
  * **Bearer Token**
  * **Basic Auth**
  * **OAuth2** (by forwarding the final Bearer token)

-----

## Getting Started

You only need **Docker** installed.

#### 1\. Build the Generator Image

From the project's root directory, build the Docker image for the generator application itself.

```bash
docker build -t mcp-generator -f docker/Dockerfile .
```

#### 2\. Run the Generator Server

This command starts the generator server in the background on `http://localhost:8000`.

```bash
docker run -d --rm -p 8000:8000 --name mcp-generator-instance mcp-generator
```

-----

## Usage with `manage.sh`

The `manage.sh` script is the easiest way to interact with the project. It automates the entire end-to-end workflow.

First, make the script executable:

```bash
chmod +x manage.sh
```

### Main Command

To run the full end-to-end test—which sets up files, builds and runs the mock server and generator, then generates, builds, runs, and tests your MCP server—use this single command:

```bash
./manage.sh e2e_test
```

### Individual Commands

You can also run each step manually, which is useful for debugging.

  * `./manage.sh setup`
    Creates the example `request.json` and all the necessary files for the mock server in the `examples/` directory.

  * `./manage.sh build`
    Builds the Docker images for the generator and the mock server.

  * `./manage.sh start`
    Starts the generator and mock server containers in the background.

  * `./manage.sh generate`
    Calls the running generator to create the `Dockerfile` for the MCP server, then builds and runs it.

  * `./manage.sh test`
    Runs `curl` requests against your running MCP server to verify its REST and RPC endpoints.

  * `./manage.sh stop`
    Stops and removes all Docker containers started by the script.
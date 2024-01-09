# TigerGraph Natural Language Query Service

# Getting Started

## Clone The Repository and Setup Environment
```sh
git clone https://github.com/tigergraph/natural_language_service.git

cd natural_language_service

mkdir configs

touch db_config.json
touch llm_config.json
```

## Build the Dockerfile
```sh
docker build -t nlqs:0.1 .
```

### Optional: Configure Logging Level in Dockerfile
To configure the logging level of the service, edit the `Dockerfile`. By default, the logging level is set to `"INFO"`.

```dockerfile
ENV LOGLEVEL="INFO"
```
This line can be changed to support different logging levels. The levels are described below:

* **CRITICAL**: A serious error
* **ERROR**: Failing to perform functions
* **WARNING**: Indication of unexpected problems, e.g. failure to map a user's question to the graph schema
* **INFO**: Confriming that the service is performing as expected.
* **DEBUG**: Detailed information, e.g. the functions retrieved during the GenerateFunction step, etc.
* **DEBUG_PII**: Finer-grained information that could potentially include PII, such as a user's question, the complete function call (with parameters), and the LLM's natural language response.
* **NOTSET**: All messages are processed

## Create LLM provider configuration file
In the `config/llm_config.json` file, copy your provider's JSON config template below, and fill out the appropriate fields.

### OpenAI
In addition to the `OPENAI_API_KEY`, `llm_model` and `model_name` can be edited to match your specific configuration details.

```json
{
    "model_name": "GPT-4",
    "embedding_service": {
        "embedding_model_service": "openai",
        "authentication_configuration": {
            "OPENAI_API_KEY": "YOUR_OPENAI_API_KEY_HERE"
        }
    },
    "completion_service": {
        "llm_service": "openai",
        "llm_model": "gpt-4-0613",
        "authentication_configuration": {
            "OPENAI_API_KEY": "YOUR_OPENAI_API_KEY_HERE"
        },
        "model_kwargs": {
            "temperature": 0
        },
        "prompt_path": "./app/prompts/open_ai_davinci-003/"
    }
}
```
### GCP
Follow the GCP authentication information found here: https://cloud.google.com/docs/authentication/application-default-credentials#GAC
```json
{
    "model_name": "GCP-text-bison",
    "embedding_service": {
        "embedding_model_service": "vertexai",
        "authentication_configuration": {}
    },
    "completion_service": {
        "llm_service": "vertexai",
        "llm_model": "text-bison",
        "model_kwargs": {
            "temperature": 0
        },
        "prompt_path": "./app/prompts/gcp_vertexai_palm/"
    }
}
```

### Azure
In addition to the `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and `azure_deployment`, `llm_model` and `model_name` can be edited to match your specific configuration details.
```json
{
    "model_name": "GPT35Turbo",
    "embedding_service": {
        "embedding_model_service": "azure",
        "azure_deployment":"YOUR_EMBEDDING_DEPLOYMENT_HERE",
        "authentication_configuration": {
            "OPENAI_API_TYPE": "azure",
            "OPENAI_API_VERSION": "2022-12-01",
            "AZURE_OPENAI_ENDPOINT": "YOUR_AZURE_ENDPOINT_HERE",
            "AZURE_OPENAI_API_KEY": "YOUR_AZURE_API_KEY_HERE"
        }
    },
    "completion_service": {
        "llm_service": "azure",
        "azure_deployment": "YOUR_COMPLETION_DEPLOYMENT_HERE",
        "openai_api_version": "2023-07-01-preview",
        "llm_model": "gpt-35-turbo-instruct",
        "authentication_configuration": {
            "OPENAI_API_TYPE": "azure",
            "AZURE_OPENAI_ENDPOINT": "YOUR_AZURE_ENDPOINT_HERE",
            "AZURE_OPENAI_API_KEY": "YOUR_AZURE_API_KEY_HERE"
        },
        "model_kwargs": {
            "temperature": 0
        },
        "prompt_path": "./app/prompts/azure_open_ai_gpt35_turbo_instruct/"
    }
}
```

## Create DB configuration file
Copy the below into `configs/db_config.json` and edit the `hostname` and `getToken` fields to match your database's configuration. Set the timeout, memory threshold, and thread limit parameters as desired to control how much of the database's resources are consumed when answering a question.
```json
{
    "hostname": "DATABASE_HOSTNAME_HERE",
    "getToken": true,
    "default_timeout": 300,
    "default_mem_threshold": 5000,
    "default_thread_limit": 8
}
```
## Run the Docker Image
```sh
docker run -d -v $(pwd)/configs/openai_gpt4_config.json:/llm_config.json -v $(pwd)/configs/db_config.json:/db_config.json --name nlqs -p 80:80 nlqs:0.1
```

## Open Swagger Doc Page
Navigate to `http://localhost/docs` when the Docker container is running.

## Using pyTigerGraph
First, update pyTigerGraph to utilize the latest build:
```sh
pip install -U git+https://github.com/tigergraph/pyTigerGraph.git
```

Then, the endpoints are availble when configured with a `TigerGraphConnection`:

```py
from pyTigerGraph import TigerGraphConnection

# create a connection to the database
conn = TigerGraphConnection(host="DATABASE_HOST_HERE", graphname="GRAPH_NAME_HERE", username="USERNAME_HERE", password="PASSWORD_HERE")

### ==== CONFIGURE INQUIRYAI HOST ====
conn.ai.configureInquiryAIHost("http://localhost:8000")

### ==== RETRIEVE TOP-K DOCS FROM LIBRARY ====
# `top_k` parameter optional
conn.ai.retrieveDocs("How many papers are there?", top_k = 5)

### ==== RUN A NATURAL LANGUAGE QUERY ====
print(conn.ai.query("How many papers are there?"))

# prints: {'natural_language_response': 'There are 736389 papers.', 'answered_question': True, 'query_sources': {'function_call': "getVertexCount('Paper')", 'result': 736389}}

### ==== REGISTER A CUSTOM QUERY ====
# Prompt for PageRank query - could be read in as JSON file.
pr_prompt = {
    "function_header": "tg_pagerank",
    "description": "Determines the importance or influence of each vertex based on its connections to other vertices.",
    "docstring": "The PageRank algorithm measures the influence of each vertex on every other vertex. PageRank influence is defined recursively: a vertex’s influence is based on the influence of the vertices which refer to it. A vertex’s influence tends to increase if either of these conditions are met:\n* It has more referring vertices\n* Its referring vertices have higher influence\nTo run this algorithm, use `runInstalledQuery('tg_pagerank', params={'v_type': 'INSERT_V_TYPE_HERE', 'e_type': 'INSERT_E_TYPE_HERE', 'top_k': INSERT_TOP_K_HERE})`, where the parameters are:\n* 'v_type': The vertex type to run the algorithm on.\n* 'e_type': The edge type to run the algorithm on.\n* 'top_k': The number of top scoring vertices to return to the user.",
    "param_types": {
        "v_type": "str",
        "e_type": "str",
        "top_k": "int"
    }
}

# Register Query
conn.ai.registerCustomQuery(pr_prompt["function_header"], pr_prompt["description"], pr_prompt["docstring"], pr_prompt["param_types"])

# Run Query
print(conn.ai.query("What are the 5 most influential papers by citations?"))

# prints: {'natural_language_response': 'The top 5 most cited papers are:\n\n1. [Title of paper with Vertex_ID 428523]\n2. [Title of paper with Vertex_ID 384889]\n3. [Title of paper with Vertex_ID 377502]\n4. [Title of paper with Vertex_ID 61855]\n5. [Title of paper with Vertex_ID 416200]', 'answered_question': True, 'query_sources': {'function_call': "runInstalledQuery('tg_pagerank', params={'v_type': 'Paper', 'e_type': 'CITES', 'top_k': 5})", 'result': [{'@@top_scores_heap': [{'Vertex_ID': '428523', 'score': 392.8731}, {'Vertex_ID': '384889', 'score': 251.8021}, {'Vertex_ID': '377502', 'score': 149.1018}, {'Vertex_ID': '61855', 'score': 129.7406}, {'Vertex_ID': '416200', 'score': 129.2286}]}]}}
```

# Testing

This documentation outlines the steps to run the provided shell script for testing different language model services. The script takes command-line arguments to specify the language model service, schema, and the usage of Weights and Biases (WandB) logging.

## Prerequisites

1. **Python**: Ensure that Python is installed on your system.

2. **Dependencies**: Make sure to install the necessary Python packages by running the following command in your terminal:

    ```bash
    pip install -r requirements.txt
    ```


3. **Configuration Files**: Prepare the required JSON configuration files for each language model service. The configuration files should be appropriately named and contain the necessary parameters for the corresponding language model.

## Usage

Run the provided shell script with the following format:

```bash
./run_tests.sh [llm_service] [schema] [use_wandb]
```

- `llm_service`: Specify the language model service to test. Possible values are:
  - `azure_gpt35`
  - `openai_gpt35`
  - `openai_gpt4`
  - `gcp_textbison`
  - `all` (to execute all services)

- `schema` (Optional): Specify the schema for testing. Default is set to `all`.

- `use_wandb` (Optional): Specify whether to use Weights and Biases for logging. Default is set to `true`.

## Examples

1. Run tests for Azure GPT-3.5 Turbo with default settings:

    ```bash
    ./run_tests.sh azure_gpt35
    ```

2. Run tests for OpenAI GPT-4 with a specific schema:

    ```bash
    ./run_tests.sh openai_gpt4 OGB_MAG
    ```

3. Run tests for all language model services without Weights and Biases logging:

    ```bash
    ./run_tests.sh all all false
    ```

## Notes

- If the specified `llm_service` is not recognized, the script will exit with an error message.

- Ensure that the required Python scripts and configuration files are correctly located according to the script's expectations.

- It is recommended to review and update the `script_mapping` array in the shell script if new language model services or configurations are added. Each entry in this array should consist of a Python script name followed by the corresponding configuration file.

- Adjust the `LOGLEVEL` and other environment variables in the script as needed for debugging or customization.
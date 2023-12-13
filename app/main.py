from typing import Union, Annotated, List, Dict
from fastapi import FastAPI, Header, Depends, HTTPException, status
import os
from pyTigerGraph import TigerGraphConnection
import json

from fastapi.security import HTTPBasic, HTTPBasicCredentials

from app.agent import TigerGraphAgent
from app.llm_services import OpenAI, AzureOpenAI, AWS_SageMaker_Endpoint, GoogleVertexAI
from app.embedding_utils.embedding_services import AzureOpenAI_Ada002, OpenAI_Embedding, VertexAI_PaLM_Embedding
from app.embedding_utils.embedding_stores import FAISS_EmbeddingStore

from app.tools import MapQuestionToSchemaException
from app.schemas.schemas import NaturalLanguageQuery, NaturalLanguageQueryResponse, GSQLQueryInfo

LLM_SERVICE = os.getenv("LLM_CONFIG")
DB_CONFIG = os.getenv("DB_CONFIG")

with open(LLM_SERVICE, "r") as f:
    llm_config = json.load(f)

app = FastAPI()

security = HTTPBasic()

if llm_config["embedding_service"]["embedding_model_service"].lower() == "openai":
    embedding_service = OpenAI_Embedding(llm_config["embedding_service"])
elif llm_config["embedding_service"]["embedding_model_service"].lower() == "azure":
    embedding_service = AzureOpenAI_Ada002(llm_config["embedding_service"])
elif llm_config["embedding_service"]["embedding_model_service"].lower() == "vertexai":
    embedding_service = VertexAI_PaLM_Embedding(llm_config["embedding_service"])
else:
    raise Exception("Embedding service not implemented")


embedding_store = FAISS_EmbeddingStore(embedding_service)


@app.get("/")
def read_root():
    return {"config": llm_config["model_name"]}


@app.post("/{graphname}/registercustomquery")
def register_query(graphname, query_info: GSQLQueryInfo, credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    vec = embedding_service.embed_query(query_info.docstring)
    res = embedding_store.add_embeddings([(query_info.docstring, vec)], [{"function_header": query_info.function_header, 
                                                                          "description": query_info.description,
                                                                          "param_types": query_info.param_types,
                                                                          "custom_query": True}])
    return res

# TODO: RUD of CRUD with custom queries

@app.post("/{graphname}/retrievedocs")
def retrieve_docs(graphname, query: NaturalLanguageQuery, credentials: Annotated[HTTPBasicCredentials, Depends(security)], top_k:int = 3):
    # TODO: Better polishing of this response
    return str(embedding_store.retrieve_similar(embedding_service.embed_query(query.query), top_k=top_k))


@app.post("/{graphname}/query")
def retrieve_answer(graphname, query: NaturalLanguageQuery, credentials: Annotated[HTTPBasicCredentials, Depends(security)]) -> NaturalLanguageQueryResponse:
    with open(DB_CONFIG, "r") as config_file:
        config = json.load(config_file)
        
    conn = TigerGraphConnection(
        host=config["hostname"],
        username = credentials.username,
        password = credentials.password,
        graphname = graphname,
    )

    try:
        apiToken = conn._post(conn.restppUrl+"/requesttoken", authMode="pwd", data=str({"graph": conn.graphname}), resKey="results")["token"]
    except:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )

    conn = TigerGraphConnection(
        host=config["hostname"],
        username = credentials.username,
        password = credentials.password,
        graphname = graphname,
        apiToken = apiToken
    )

    conn.customizeHeader(timeout=config["default_timeout"]*1000)

    if llm_config["completion_service"]["llm_service"].lower() == "openai":
        agent = TigerGraphAgent(OpenAI(llm_config["completion_service"]), conn, embedding_service, embedding_store)
    elif llm_config["completion_service"]["llm_service"].lower() == "azure":
        agent = TigerGraphAgent(AzureOpenAI(llm_config["completion_service"]), conn, embedding_service, embedding_store)
    elif llm_config["completion_service"]["llm_service"].lower() == "sagemaker":
        agent = TigerGraphAgent(AWS_SageMaker_Endpoint(llm_config["completion_service"]), conn, embedding_service, embedding_store)
    elif llm_config["completion_service"]["llm_service"].lower() == "vertexai":
        agent = TigerGraphAgent(GoogleVertexAI(llm_config["completion_service"]), conn, embedding_service, embedding_store)
    else:
        raise Exception("LLM Completion Service Not Supported")

    resp = NaturalLanguageQueryResponse

    try:
        steps = agent.question_for_agent(query.query)
        try:
            function_call = steps["intermediate_steps"][-1][-1].split("Function ")[1].split(" produced")[0]
            res = steps["intermediate_steps"][-1][-1].split("the result ")[-1]
            resp.natural_language_response = steps["output"]
            resp.query_sources = {"function_call": function_call,
                                "result": json.loads(res)}
            resp.answered_question = True
        except Exception as e:
            resp.natural_language_response = steps["output"]
            resp.query_sources = {"agent_history": str(steps)}
            resp.answered_question = False
    except MapQuestionToSchemaException as e:
        resp.natural_language_response = ""
        resp.query_sources = {}
        resp.answered_question = False
    except Exception as e:
        resp.natural_language_response = ""
        resp.query_sources = {}
        resp.answered_question = False
    return resp
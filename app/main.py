from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
import logging

from app.api.definition import router as definition_router
from app.api.runtime import router as runtime_router
from app.core.exceptions import (
    BusinessException,
    business_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
)

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Workflow Service",
    description="Generic multi-step approval workflow microservice",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(definition_router)
app.include_router(runtime_router)

app.add_exception_handler(BusinessException, business_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


@app.get("/health", tags=["ops"])
async def health():
    return {"status": "ok", "service": "workflow-service"}
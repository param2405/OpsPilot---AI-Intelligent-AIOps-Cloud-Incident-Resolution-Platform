from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])
    service: str
    environment: str
    version: str


class DatabaseCheck(BaseModel):
    connected: bool
    detail: str


class ReadinessResponse(BaseModel):
    status: str = Field(examples=["ready", "unavailable"])
    service: str
    environment: str
    version: str
    database: DatabaseCheck

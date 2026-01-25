from typing import List, Literal, Optional
from pydantic import BaseModel


class IngestResponse(BaseModel):
    success: bool
    ingestionId: str
    message: str
    filesUploaded: int
    dataType: str


class FileInfo(BaseModel):
    fileName: str
    fileSize: int
    status: str


class IngestionRecord(BaseModel):
    ingestionId: str
    dataType: str
    filesCount: int
    fileNames: List[str]
    totalSizeBytes: int
    uploadedBy: str
    uploadedAt: str
    status: str


class IngestionHistoryResponse(BaseModel):
    records: List[IngestionRecord]
    total: int

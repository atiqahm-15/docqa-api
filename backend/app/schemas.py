from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    chunk_count: int


class DocumentListItem(BaseModel):
    document_id: str
    filename: str
    uploaded_at: str
    chunk_count: int


class DocumentListResponse(BaseModel):
    documents: list[DocumentListItem]


class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None
    document_id: str | None = None


class SourceCitation(BaseModel):
    filename: str
    page: int
    snippet: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceCitation]
    session_id: str


class ChatMessageItem(BaseModel):
    role: str
    content: str


class ChatHistoryResponse(BaseModel):
    session_id: str
    messages: list[ChatMessageItem]

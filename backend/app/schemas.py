from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=4)


class AuthResponse(BaseModel):
    token: str
    email: str


class LogoutResponse(BaseModel):
    logged_out: bool = True


class AuthMeResponse(BaseModel):
    email: str
    authenticated: bool = True
    display_name: str = ""
    role_title: str = "Workspace operator"
    avatar_url: Optional[str] = None
    bio: str = ""
    timezone: str = ""
    notifications_enabled: bool = False
    created_at: str = ""
    updated_at: str = ""


class AdminProfileUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=80)
    role_title: Optional[str] = Field(default=None, max_length=80)
    avatar_url: Optional[str] = Field(default=None, max_length=500)
    bio: Optional[str] = Field(default=None, max_length=500)
    timezone: Optional[str] = Field(default=None, max_length=80)
    notifications_enabled: Optional[bool] = None


class UserAuthConfigResponse(BaseModel):
    enabled: bool
    client_id: Optional[str] = None
    guest_mode: bool = True


class UserProfileResponse(BaseModel):
    id: int
    email: str
    name: str
    username: str = ""
    picture_url: Optional[str] = None
    bio: str = ""
    ai_nickname: str = "HajiHaz AI"
    personality: Literal["balanced", "direct", "warm", "strategic", "creative"] = "balanced"
    theme: Literal["dark", "light", "system"] = "dark"
    memory_enabled: bool = True
    ai_mode: Literal["auto", "general", "memory", "reasoning", "coding", "creative"] = "auto"
    answer_mode: Literal["balanced", "concise", "detailed", "strategic", "founder"] = "balanced"
    notifications_enabled: bool = False
    authenticated: bool = True


class UserGoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=20)
    session_id: Optional[str] = Field(default=None, max_length=64)


class UserProfileUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=80)
    username: Optional[str] = Field(default=None, max_length=40)
    picture_url: Optional[str] = Field(default=None, max_length=500)
    bio: Optional[str] = Field(default=None, max_length=500)
    ai_nickname: Optional[str] = Field(default=None, max_length=80)
    personality: Optional[Literal["balanced", "direct", "warm", "strategic", "creative"]] = None
    theme: Optional[Literal["dark", "light", "system"]] = None
    memory_enabled: Optional[bool] = None
    ai_mode: Optional[Literal["auto", "general", "memory", "reasoning", "coding", "creative"]] = None
    answer_mode: Optional[Literal["balanced", "concise", "detailed", "strategic", "founder"]] = None
    notifications_enabled: Optional[bool] = None


class UserAuthResponse(BaseModel):
    token: str
    user: UserProfileResponse
    claimed_session_id: Optional[str] = None


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=4)
    new_password: str = Field(min_length=8)


class PasswordChangeResponse(BaseModel):
    updated: bool = True
    email: str


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    history: List[ChatTurn] = Field(default_factory=list)
    session_id: Optional[str] = Field(default=None, max_length=64)
    answer_mode: Literal["balanced", "concise", "detailed", "strategic", "founder"] = "balanced"
    memory_enabled: bool = True
    ai_mode: Literal["auto", "general", "memory", "reasoning", "coding", "creative"] = "auto"


class ChatCitation(BaseModel):
    title: str
    excerpt: str
    url: Optional[str] = None
    kind: str = "knowledge"
    source: Optional[str] = None
    group_name: str = ""


class ChatResponse(BaseModel):
    answer: str
    citations: List[ChatCitation]
    mode: str
    notice: Optional[str] = None
    session_id: Optional[str] = None
    conversation_title: Optional[str] = None
    intent: Optional[str] = None
    source_strategy: Optional[str] = None
    memory_confidence: float = 0.0


class ChatMessageResponse(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    mode: str = ""
    notice: Optional[str] = None
    citations: List[ChatCitation] = Field(default_factory=list)
    created_at: str


class ChatSessionSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0
    answer_mode: str = "balanced"


class ChatSessionResponse(BaseModel):
    session: ChatSessionSummary
    messages: List[ChatMessageResponse]


class DocumentCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=10, max_length=60000)
    tags: List[str] = Field(default_factory=list)
    source: str = "manual"
    group_name: str = ""
    core_persona: bool = False
    source_url: Optional[str] = None


class DocumentUpdate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    content: str = Field(min_length=10, max_length=60000)
    tags: List[str] = Field(default_factory=list)
    source: str = "manual"
    group_name: str = ""
    core_persona: bool = False
    source_url: Optional[str] = None


class DocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    tags: List[str]
    source: str
    group_name: str = ""
    core_persona: bool = False
    source_url: Optional[str] = None
    source_key: str = ""
    source_enabled: bool = True
    last_synced_at: Optional[str] = None
    sync_status: str = "ready"
    sync_error: str = ""
    updated_at: str


class DocumentDeleteResponse(BaseModel):
    id: int
    deleted: bool = True


class DocumentCorePersonaRequest(BaseModel):
    core_persona: bool


class DocumentImportRequest(BaseModel):
    documents: List[DocumentCreate] = Field(default_factory=list)
    skip_duplicates: bool = True


class DocumentImportResponse(BaseModel):
    imported: int
    skipped: int
    documents: List[DocumentResponse]


class UrlImportRequest(BaseModel):
    url: str = Field(min_length=8, max_length=400)
    tags: List[str] = Field(default_factory=list)
    group_name: str = ""


class SourceHealthItem(BaseModel):
    source_key: str = ""
    source: str
    source_label: str = ""
    group_name: str
    documents: int
    last_updated: str
    last_synced_at: Optional[str] = None
    total_characters: int = 0
    health: str
    detail: str
    source_url: Optional[str] = None
    enabled: bool = True
    syncable: bool = False
    sync_status: str = "ready"
    sync_error: str = ""


class MonitoringAlert(BaseModel):
    id: int
    level: str
    title: str
    detail: str
    source: str
    created_at: str


class MonitoringHealthCheck(BaseModel):
    id: int
    name: str
    status: str
    detail: str
    created_at: str


class MonitoringRequestLog(BaseModel):
    id: int
    method: str
    path: str
    status_code: int
    duration_ms: float
    error_message: str = ""
    created_at: str


class AdminDebugResponse(BaseModel):
    uptime_seconds: int
    log_path: str
    log_tail: List[str]
    recent_logs: List[MonitoringRequestLog]
    recent_alerts: List[MonitoringAlert]
    recent_health_checks: List[MonitoringHealthCheck]
    source_health: List[SourceHealthItem]
    resource_metrics: dict
    metric_history: List[dict]
    backups: List[dict]
    analytics: dict
    secret_audit: dict
    last_checked_at: str


class AdminStatsResponse(BaseModel):
    documents: int
    chunks: int
    groups: int = 0
    sources: int = 0
    active_sources: int = 0
    ai_provider: str
    provider_ready: bool
    anthropic_configured: bool
    ollama_configured: bool
    web_search_enabled: bool


class AdminRuntimePulseResponse(BaseModel):
    provider: str
    provider_label: str
    status: Literal["live", "degraded", "offline"]
    status_label: str
    reason: str
    checked_at: str
    uptime_seconds: int


class AdminUserCreateRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class AdminUserResponse(BaseModel):
    email: str
    display_name: str = ""
    role_title: str = "Workspace operator"
    avatar_url: Optional[str] = None
    created_at: str
    updated_at: str
    is_current: bool = False


class BackupCreateRequest(BaseModel):
    note: str = "manual backup"


class BackupRunResponse(BaseModel):
    id: int
    archive_name: str
    archive_path: str
    size_bytes: int
    status: str
    note: str
    created_at: str
    download_ready: bool = True


class BackupCleanupResponse(BaseModel):
    removed: List[str]
    remaining: List[BackupRunResponse]


class SourceActionResponse(BaseModel):
    source: SourceHealthItem
    action: str


class SecretAuditCheckResponse(BaseModel):
    name: str
    ok: bool
    detail: str


class SecretAuditResponse(BaseModel):
    status: str
    issues: List[str]
    checks: List[SecretAuditCheckResponse]


class MetricSnapshotResponse(BaseModel):
    id: int
    cpu_load_1: float
    cpu_load_5: float
    cpu_load_15: float
    memory_used_bytes: int
    memory_total_bytes: int
    disk_used_bytes: int
    disk_total_bytes: int
    ollama_reachable: bool
    notes: str
    created_at: str


class ResourceMetricsResponse(BaseModel):
    hostname: str
    cpu_load_1: float
    cpu_load_5: float
    cpu_load_15: float
    memory_used_bytes: int
    memory_total_bytes: int
    memory_percent: float
    disk_used_bytes: int
    disk_total_bytes: int
    disk_percent: float
    database_size_bytes: int
    log_size_bytes: int
    uploads_size_bytes: int
    backup_size_bytes: int
    ollama_reachable: bool
    uptime_seconds: int
    captured_at: str


class RouteCountResponse(BaseModel):
    route: str
    count: int


class DailyUsageResponse(BaseModel):
    day: str
    count: int


class UsageAnalyticsResponse(BaseModel):
    window_days: int
    total_requests: int
    by_mode: dict
    top_routes: List[RouteCountResponse]
    daily_requests: List[DailyUsageResponse]
    average_citations: float
    average_prompt_length: float
    average_answer_length: float


class AdminOpsOverviewResponse(BaseModel):
    metrics: ResourceMetricsResponse
    metric_history: List[MetricSnapshotResponse]
    analytics: UsageAnalyticsResponse
    backups: List[BackupRunResponse]
    secret_audit: SecretAuditResponse
    log_tail: List[str]


class HealthResponse(BaseModel):
    status: str
    app: str

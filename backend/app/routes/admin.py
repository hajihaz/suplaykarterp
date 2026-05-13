from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.core.security import get_current_admin
from app.schemas import (
    AdminDebugResponse,
    AdminOpsOverviewResponse,
    AdminRuntimePulseResponse,
    AdminStatsResponse,
    AdminUserCreateRequest,
    AdminUserResponse,
    BackupCleanupResponse,
    BackupCreateRequest,
    BackupRunResponse,
    DocumentCorePersonaRequest,
    DocumentCreate,
    DocumentDeleteResponse,
    DocumentImportRequest,
    DocumentImportResponse,
    DocumentResponse,
    DocumentUpdate,
    SourceActionResponse,
    SourceHealthItem,
    UrlImportRequest,
)
from app.services.anthropic_client import ai_service
from app.services.ingestion import import_documents_from_file, import_documents_from_url
from app.services.monitoring import build_runtime_debug, record_alert, record_health_check
from app.services.operations import (
    backup_file_path,
    build_usage_analytics,
    cleanup_backups,
    create_backup,
    list_backups,
    operational_overview,
    prune_operational_data,
    run_watchdog_checks,
)
from app.services.rag import (
    add_document,
    delete_document,
    export_documents,
    get_document,
    import_documents,
    list_documents,
    list_sources,
    reindex_source,
    set_document_core_persona,
    set_source_enabled,
    source_health,
    stats,
    sync_source,
    update_document,
)
from app.core.security import create_admin_user, list_admin_users


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/runtime-pulse", response_model=AdminRuntimePulseResponse)
def runtime_pulse_route(_: str = Depends(get_current_admin)) -> AdminRuntimePulseResponse:
    return AdminRuntimePulseResponse(**ai_service.runtime_pulse())


@router.get("/documents", response_model=List[DocumentResponse])
def get_documents(_: str = Depends(get_current_admin)) -> List[DocumentResponse]:
    return [DocumentResponse(**document) for document in list_documents()]


@router.post("/documents", response_model=DocumentResponse)
def create_document(payload: DocumentCreate, _: str = Depends(get_current_admin)) -> DocumentResponse:
    document_id = add_document(
        payload.title,
        payload.content,
        payload.tags,
        payload.source,
        payload.group_name,
        payload.core_persona,
        payload.source_url,
    )
    document = get_document(document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Document was created but could not be loaded.")
    return DocumentResponse(**document)


@router.post("/documents/import", response_model=DocumentImportResponse)
def import_documents_route(payload: DocumentImportRequest, _: str = Depends(get_current_admin)) -> DocumentImportResponse:
    if not payload.documents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No documents were supplied for import.")
    result = import_documents(
        [
            {
                "title": document.title,
                "content": document.content,
                "tags": document.tags,
                "source": document.source,
                "group_name": document.group_name,
                "core_persona": document.core_persona,
                "source_url": document.source_url,
            }
            for document in payload.documents
        ],
        skip_duplicates=payload.skip_duplicates,
    )
    return DocumentImportResponse(
        imported=result["imported"],
        skipped=result["skipped"],
        documents=[DocumentResponse(**document) for document in result["documents"]],
    )


@router.post("/documents/import/files", response_model=DocumentImportResponse)
async def import_document_files_route(
    files: List[UploadFile] = File(default_factory=list),
    group_name: str = Form(default=""),
    tags_csv: str = Form(default=""),
    skip_duplicates: bool = Form(default=True),
    _: str = Depends(get_current_admin),
) -> DocumentImportResponse:
    if not files:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No files were uploaded.")

    base_tags = [tag.strip() for tag in tags_csv.split(",") if tag.strip()]
    documents: List[dict] = []
    try:
        for upload in files:
            content = await upload.read()
            documents.extend(import_documents_from_file(upload.filename or "upload", content, group_name, base_tags))
    except ValueError as exc:
        record_alert("warning", "File import rejected", str(exc), source="admin.import.files")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        record_alert("error", "File import failed", str(exc), source="admin.import.files")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File import failed.") from exc

    if not documents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No readable documents were found in the uploaded files.")
    if len(documents) > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many documents were produced from the uploaded files.")

    result = import_documents(documents, skip_duplicates=skip_duplicates)
    return DocumentImportResponse(
        imported=result["imported"],
        skipped=result["skipped"],
        documents=[DocumentResponse(**document) for document in result["documents"]],
    )


@router.post("/documents/import/url", response_model=DocumentImportResponse)
async def import_document_url_route(payload: UrlImportRequest, _: str = Depends(get_current_admin)) -> DocumentImportResponse:
    try:
        documents = await import_documents_from_url(payload.url, payload.group_name, payload.tags)
    except ValueError as exc:
        record_alert("warning", "URL import rejected", str(exc), source="admin.import.url")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        record_alert("error", "URL import failed", str(exc), source="admin.import.url")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Website import failed.") from exc

    result = import_documents(documents, skip_duplicates=True)
    return DocumentImportResponse(
        imported=result["imported"],
        skipped=result["skipped"],
        documents=[DocumentResponse(**item) for item in result["documents"]],
    )


@router.put("/documents/{document_id}", response_model=DocumentResponse)
def update_document_route(
    document_id: int,
    payload: DocumentUpdate,
    _: str = Depends(get_current_admin),
) -> DocumentResponse:
    document = update_document(
        document_id,
        payload.title,
        payload.content,
        payload.tags,
        payload.source,
        payload.group_name,
        payload.core_persona,
        payload.source_url,
    )
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return DocumentResponse(**document)


@router.delete("/documents/{document_id}", response_model=DocumentDeleteResponse)
def delete_document_route(document_id: int, _: str = Depends(get_current_admin)) -> DocumentDeleteResponse:
    deleted = delete_document(document_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return DocumentDeleteResponse(id=document_id)


@router.post("/documents/{document_id}/core-persona", response_model=DocumentResponse)
def set_document_core_persona_route(
    document_id: int,
    payload: DocumentCorePersonaRequest,
    _: str = Depends(get_current_admin),
) -> DocumentResponse:
    document = set_document_core_persona(document_id, payload.core_persona)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return DocumentResponse(**document)


@router.get("/stats", response_model=AdminStatsResponse)
def get_stats(_: str = Depends(get_current_admin)) -> AdminStatsResponse:
    rag_stats = stats()
    ai_status = ai_service.status()
    return AdminStatsResponse(
        documents=rag_stats["documents"],
        chunks=rag_stats["chunks"],
        groups=rag_stats["groups"],
        sources=rag_stats["sources"],
        active_sources=rag_stats["active_sources"],
        ai_provider=ai_status["provider"],
        provider_ready=ai_status["provider_ready"],
        anthropic_configured=ai_status["anthropic_configured"],
        ollama_configured=ai_status["ollama_configured"],
        web_search_enabled=ai_status["web_search_enabled"],
    )


@router.get("/admin-users", response_model=List[AdminUserResponse])
def get_admin_users(current_email: str = Depends(get_current_admin)) -> List[AdminUserResponse]:
    return [AdminUserResponse(**user) for user in list_admin_users(current_email)]


@router.post("/admin-users", response_model=AdminUserResponse)
def create_admin_user_route(payload: AdminUserCreateRequest, _: str = Depends(get_current_admin)) -> AdminUserResponse:
    user = create_admin_user(payload.email, payload.password)
    return AdminUserResponse(**user)


@router.get("/documents/export")
def export_documents_route(
    export_format: str = "json",
    _: str = Depends(get_current_admin),
) -> Response:
    if export_format not in {"json", "csv", "markdown"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported export format.")
    content, media_type, filename = export_documents(export_format)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return Response(content=content, media_type=media_type, headers=headers)


@router.get("/debug", response_model=AdminDebugResponse)
def debug_route(_: str = Depends(get_current_admin)) -> AdminDebugResponse:
    rag_stats = stats()
    ai_status = ai_service.status()
    overview = operational_overview()
    checks = [
        ("database", True, f"{rag_stats['documents']} documents and {rag_stats['chunks']} chunks available."),
        (
            "provider",
            bool(ai_status["provider_ready"]),
            f"Provider={ai_status['provider']} web_search={ai_status['web_search_enabled']} ollama={ai_status['ollama_configured']}",
        ),
    ]
    for name, ok, detail in checks:
        record_health_check(name, ok, detail)
    payload = build_runtime_debug(ai_status, rag_stats, source_health())
    payload["resource_metrics"] = overview["metrics"]
    payload["metric_history"] = overview["metric_history"]
    payload["backups"] = overview["backups"]
    payload["analytics"] = overview["analytics"]
    payload["secret_audit"] = overview["secret_audit"]
    return AdminDebugResponse(**payload)


@router.get("/ops/overview", response_model=AdminOpsOverviewResponse)
def ops_overview_route(_: str = Depends(get_current_admin)) -> AdminOpsOverviewResponse:
    payload = operational_overview()
    return AdminOpsOverviewResponse(**payload)


@router.get("/sources", response_model=List[SourceHealthItem])
def get_sources(_: str = Depends(get_current_admin)) -> List[SourceHealthItem]:
    return [SourceHealthItem(**item) for item in list_sources()]


@router.post("/sources/{source_key:path}/enable", response_model=SourceActionResponse)
def enable_source_route(source_key: str, _: str = Depends(get_current_admin)) -> SourceActionResponse:
    source = set_source_enabled(source_key, True)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return SourceActionResponse(source=SourceHealthItem(**source), action="enabled")


@router.post("/sources/{source_key:path}/disable", response_model=SourceActionResponse)
def disable_source_route(source_key: str, _: str = Depends(get_current_admin)) -> SourceActionResponse:
    source = set_source_enabled(source_key, False)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return SourceActionResponse(source=SourceHealthItem(**source), action="disabled")


@router.post("/sources/{source_key:path}/reindex", response_model=SourceActionResponse)
def reindex_source_route(source_key: str, _: str = Depends(get_current_admin)) -> SourceActionResponse:
    source = reindex_source(source_key)
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return SourceActionResponse(source=SourceHealthItem(**source), action="reindexed")


@router.post("/sources/{source_key:path}/sync", response_model=SourceActionResponse)
async def sync_source_route(source_key: str, _: str = Depends(get_current_admin)) -> SourceActionResponse:
    try:
        source = await sync_source(source_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if source is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
    return SourceActionResponse(source=SourceHealthItem(**source), action="synced")


@router.get("/backups", response_model=List[BackupRunResponse])
def get_backups(_: str = Depends(get_current_admin)) -> List[BackupRunResponse]:
    return [BackupRunResponse(**item) for item in list_backups()]


@router.post("/backups/create", response_model=BackupRunResponse)
def create_backup_route(payload: BackupCreateRequest, _: str = Depends(get_current_admin)) -> BackupRunResponse:
    backup = create_backup(payload.note)
    return BackupRunResponse(**backup)


@router.post("/backups/cleanup", response_model=BackupCleanupResponse)
def cleanup_backups_route(_: str = Depends(get_current_admin)) -> BackupCleanupResponse:
    result = cleanup_backups()
    return BackupCleanupResponse(
        removed=result["removed"],
        remaining=[BackupRunResponse(**item) for item in result["remaining"]],
    )


@router.get("/backups/{backup_id}/download")
def download_backup_route(backup_id: int, _: str = Depends(get_current_admin)) -> FileResponse:
    archive_path = backup_file_path(backup_id)
    if archive_path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup archive not found.")
    return FileResponse(archive_path, filename=archive_path.name, media_type="application/zip")


@router.get("/analytics")
def analytics_route(_: str = Depends(get_current_admin)) -> dict:
    return build_usage_analytics()


@router.post("/maintenance")
def maintenance_route(_: str = Depends(get_current_admin)) -> dict:
    metrics = run_watchdog_checks()
    pruning = prune_operational_data()
    backups = cleanup_backups()
    return {
        "metrics": metrics,
        "pruned": pruning,
        "removed_backups": backups["removed"],
    }

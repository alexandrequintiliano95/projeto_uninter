# Elaborado com apoio de IA (Claude Code) e revisado pelo autor.
from fastapi import APIRouter

router = APIRouter(tags=["Saúde"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

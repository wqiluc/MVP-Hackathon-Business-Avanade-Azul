from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def check_health():
    return {
        "status": "online",
        "service": "AeroShield AI BFA",
        "version": "2.0.0"
    }

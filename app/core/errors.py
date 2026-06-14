from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

class KioskError(Exception):
    def __init__(self, message_en: str, message_ta: str, status_code: int = 400):
        self.message_en = message_en
        self.message_ta = message_ta
        self.status_code = status_code

async def kiosk_exception_handler(request: Request, exc: KioskError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "message": {
                "en": exc.message_en,
                "ta": exc.message_ta
            }
        }
    )

async def global_exception_handler(request: Request, exc: Exception):
    # Log the real error for the developer
    print(f"[ERROR] Global Catch: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "message": {
                "en": "An unexpected error occurred. Please try again.",
                "ta": "எதிர்பாராத பிழை ஏற்பட்டது. மீண்டும் முயற்சிக்கவும்."
            }
        }
    )

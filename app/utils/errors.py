from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

class AppException(Exception):
    """应用异常基类"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(self.message)

class ValidationException(AppException):
    """验证异常"""
    def __init__(self, message: str):
        super().__init__(400, message)

class NotFoundException(AppException):
    """资源不存在异常"""
    def __init__(self, message: str):
        super().__init__(404, message)

class InternalErrorException(AppException):
    """内部错误异常"""
    def __init__(self, message: str):
        super().__init__(500, message)

class UnauthorizedException(AppException):
    """未授权异常"""
    def __init__(self, message: str):
        super().__init__(401, message)

async def exception_handler(request: Request, exc: AppException):
    """异常处理函数"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.message
        }
    )

async def generic_exception_handler(request: Request, exc: Exception):
    """通用异常处理函数"""
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": f"内部服务器错误: {str(exc)}"
        }
    )
from wf_fastapi.encoders import jsonable_encoder
from wf_fastapi.exceptions import RequestValidationError
from wf_fastapi.utils import is_body_allowed_for_status_code
from wf_starlette.exceptions import HTTPException
from wf_starlette.requests import Request
from wf_starlette.responses import JSONResponse, Response
from wf_starlette.status import HTTP_422_UNPROCESSABLE_ENTITY


async def http_exception_handler(request: Request, exc: HTTPException) -> Response:
    headers = getattr(exc, "headers", None)
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=headers)
    return JSONResponse(
        {"detail": exc.detail}, status_code=exc.status_code, headers=headers
    )


async def request_validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())},
    )

"""인증 SDK 예외 클래스 모듈.

인증 및 권한 검증 과정에서 발생할 수 있는 예외를 정의합니다.
각 예외는 대응하는 HTTP 상태 코드와 매핑됩니다.
"""


class AuthSDKError(Exception):
    """인증 SDK 기본 예외 클래스.

    모든 인증 SDK 예외의 부모 클래스입니다.

    Attributes:
        message: 오류 메시지
        status_code: HTTP 상태 코드
    """

    def __init__(
        self, message: str = "인증 SDK 오류가 발생했습니다", status_code: int = 500
    ) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class AuthenticationError(AuthSDKError):
    """인증 실패 예외 (HTTP 401).

    토큰이 없거나 유효하지 않은 경우 발생합니다.
    """

    def __init__(self, message: str = "인증에 실패했습니다") -> None:
        super().__init__(message=message, status_code=401)


class PermissionDeniedError(AuthSDKError):
    """권한 부족 예외 (HTTP 403).

    인증은 성공했으나 요청한 리소스에 대한 권한이 없는 경우 발생합니다.
    """

    def __init__(self, message: str = "접근 권한이 없습니다") -> None:
        super().__init__(message=message, status_code=403)


class TokenExpiredError(AuthenticationError):
    """토큰 만료 예외.

    JWT 토큰의 exp 클레임이 현재 시간을 초과한 경우 발생합니다.
    """

    def __init__(self, message: str = "토큰이 만료되었습니다") -> None:
        super().__init__(message=message)


class InvalidTokenError(AuthenticationError):
    """유효하지 않은 토큰 예외.

    JWT 토큰의 형식이 잘못되었거나 서명 검증에 실패한 경우 발생합니다.
    """

    def __init__(self, message: str = "유효하지 않은 토큰입니다") -> None:
        super().__init__(message=message)


class AuthServiceUnavailableError(AuthSDKError):
    """인증 서비스 불가 예외 (HTTP 503).

    인증 서비스에 연결할 수 없거나 응답하지 않는 경우 발생합니다.
    """

    def __init__(self, message: str = "인증 서비스에 연결할 수 없습니다") -> None:
        super().__init__(message=message, status_code=503)

class AppError(Exception):
    """Ошибка, которую можно безопасно показать клиенту."""

    status_code = 500
    code = "internal_error"
    message = "Внутренняя ошибка сервиса"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        self.detail = message or self.message


class UnsupportedFileTypeError(AppError):
    status_code = 415
    code = "unsupported_file_type"
    message = "Поддерживаются только JPEG, PNG и WEBP"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"
    message = "Файл слишком большой"


class PhotoNotFoundError(AppError):
    status_code = 404
    code = "photo_not_found"
    message = "Фотография не найдена"


class DependencyUnavailableError(AppError):
    status_code = 503
    code = "dependency_unavailable"
    message = "Внешняя зависимость временно недоступна"

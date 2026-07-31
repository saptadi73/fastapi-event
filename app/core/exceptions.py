from dataclasses import dataclass


@dataclass
class AppException(Exception):
    code: str
    message: str


class NotFoundException(AppException):
    pass


class ValidationException(AppException):
    pass


class ConflictException(AppException):
    pass


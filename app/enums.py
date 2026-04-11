from enum import Enum


class CodeTaskStatus(Enum):
    """
    Статусы задач по генерации кода:
        pending     — задача создана, ещё не начата
        processing  — идёт генерация или исправление кода
        validating  — код отправлен в lua-sandbox на проверку
        done        — код прошёл валидацию
        failed      — исчерпаны попытки или критическая ошибка
    """

    pending = "PENDING"
    processing = "PROCESSING"
    validating = "VALIDATING"
    done = "DONE"
    failed = "FAILED"

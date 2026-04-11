"""
validator.py — изолированный сервис валидации Lua-кода.

Запускается как отдельный FastAPI-сервис внутри lua-sandbox Docker контейнера.
Принимает Lua-код от бэкенда и проверяет его в два шага:
    1. Синтаксическая проверка через luac (быстро, без исполнения)
    2. Исполнение с mock wf-окружением через lua (проверка runtime ошибок)

Эндпоинты:
    POST /validate  — валидация кода
    GET  /health    — проверка доступности lua и luac

Изоляция в Docker контейнере защищает хост от потенциально опасного кода.
"""

import os
import subprocess
import tempfile

import uvicorn
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Lua Sandbox Validator")

# Таймаут исполнения Lua-кода в секундах.
# Защищает от бесконечных циклов в сгенерированном коде.
LUA_TIMEOUT = 5


# Имитирует реальное окружение платформы чтобы код можно было исполнить
# без реальных данных. Используется при втором шаге валидации.
#
# wf.vars и wf.initVariables возвращают nil для любого ключа через метатаблицы —
# это позволяет коду обращаться к переменным без ошибок даже без реальных данных.
WF_MOCK = """
-- Mock окружение платформы MWS Octapi
wf = {
    vars = setmetatable({}, {
        __index = function(t, k)
            -- Возвращаем пустую таблицу для любого ключа
            -- чтобы цепочки вида wf.vars.foo.bar не падали с nil error
            return setmetatable({}, {
                __index = function(t2, k2) return nil end,
                __len = function() return 0 end,
            })
        end
    }),
    initVariables = setmetatable({}, {
        __index = function(t, k) return nil end
    })
}

-- Mock утилиты платформы
_utils = {
    array = {
        -- Создаёт новый пустой массив
        new = function()
            local arr = {}
            return arr
        end,
        -- Помечает существующую переменную как массив
        markAsArray = function(arr)
            return arr
        end
    }
}
"""


class ValidateRequest(BaseModel):
    code: str


class ValidateResponse(BaseModel):
    ok: bool
    error: str = ""


class HealthResponse(BaseModel):
    status: str
    lua: bool
    luac: bool


def validate(lua_code: str) -> tuple[bool, str]:
    """
    Валидирует Lua-код в два шага.

    Шаг 1 — Синтаксическая проверка (luac -p):
        Быстрая проверка синтаксиса без исполнения кода.
        Ловит опечатки, незакрытые блоки, неверные операторы.

    Шаг 2 — Исполнение с mock-окружением (lua):
        Запускает код с имитацией wf.vars и _utils.
        Ловит runtime ошибки: обращение к nil, неверные типы и т.д.

    Args:
        lua_code: чистый Lua-код без обёртки lua{...}lua

    Returns:
        (True, "")              — код прошёл оба шага
        (False, "описание")     — код не прошёл, описание ошибки
    """

    # --- Шаг 1: синтаксическая проверка ---
    with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False) as f:
        f.write(lua_code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["luac", "-p", tmp_path],  # -p = parse only, не создаёт .out файл
            capture_output=True,
            text=True,
            timeout=LUA_TIMEOUT,
        )
        if result.returncode != 0:
            return False, f"Синтаксическая ошибка: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "Timeout при синтаксической проверке"
    finally:
        os.unlink(tmp_path)

    # --- Шаг 2: исполнение с mock-окружением ---
    # Prepend mock перед кодом пользователя чтобы wf и _utils были доступны
    full_code = WF_MOCK + "\n" + lua_code

    with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False) as f:
        f.write(full_code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["lua", tmp_path],
            capture_output=True,
            text=True,
            timeout=LUA_TIMEOUT,  # защита от бесконечных циклов
        )
        if result.returncode != 0:
            return False, f"Ошибка исполнения: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return False, "Timeout при исполнении кода"
    finally:
        os.unlink(tmp_path)

    return True, ""


@app.post("/validate", response_model=ValidateResponse)
def validate_endpoint(body: ValidateRequest):
    """
    Валидирует Lua-код.

    Request:  {"code": "<lua код без обёртки lua{...}lua>"}
    Response: {"ok": true, "error": ""}
              {"ok": false, "error": "описание ошибки"}
    """
    ok, error = validate(body.code)
    return ValidateResponse(ok=ok, error=error)


@app.get("/health", response_model=HealthResponse)
def health():
    """
    Проверяет доступность lua и luac интерпретаторов.

    Используется бэкендом и Docker healthcheck.

    Response: {"status": "ok", "lua": true, "luac": true}
    """
    lua_ok = subprocess.run(["lua", "-v"], capture_output=True).returncode == 0
    luac_ok = subprocess.run(["luac", "-v"], capture_output=True).returncode == 0
    return HealthResponse(status="ok", lua=lua_ok, luac=luac_ok)


if __name__ == "__main__":
    uvicorn.run("validator:app", host="0.0.0.0", port=8081)

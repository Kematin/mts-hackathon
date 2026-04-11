import json


class OllamaFormatter:
    @classmethod
    def extract_json(cls, raw: str) -> str:
        """
        Извлекает чистый JSON из сырого ответа модели.

        Модель иногда оборачивает ответ в markdown-блок ```json ... ```
        несмотря на инструкции в промпте. Эта функция чистит обёртку.

        Алгоритм:
            1. Убираем строки начинающиеся с ```
            2. Ищем первый { и последний } — берём всё между ними

        Args:
            raw: сырой текст ответа модели

        Returns:
            Строка с валидным JSON

        Raises:
            ValueError: если JSON не найден в ответе
        """
        # Убираем markdown-блоки если модель всё же добавила их
        if "```" in raw:
            lines = raw.splitlines()
            filtered = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(filtered)

        # Ищем первый { и последний } — берём всё между ними
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"JSON не найден в ответе модели: {raw!r}")

        return raw[start : end + 1]

    @classmethod
    def extract_lua_snippets(cls, code_json: str) -> list[str]:
        """
        Извлекает все Lua-сниппеты из JSON-ответа модели.

        Модель возвращает JSON вида:
            {"key": "lua{<код>}lua", "key2": "lua{<код>}lua"}

        Функция извлекает только внутренний код между lua{ и }lua
        чтобы передать его в валидатор без обёртки.

        Returns:
            Список строк с Lua-кодом (без lua{...}lua обёртки)
        """
        snippets = []
        try:
            data = json.loads(code_json)
            for value in data.values():
                if (
                    isinstance(value, str)
                    and value.startswith("lua{")
                    and value.endswith("}lua")
                ):
                    # Вырезаем код между lua{ и }lua (4 символа с начала, 4 с конца)
                    inner = value[4:-4]
                    snippets.append(inner)
        except Exception:
            pass
        return snippets

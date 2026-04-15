#тут был дядя некит....
FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    lua5.4 \
    && rm -rf /var/lib/apt/lists/*

RUN ln -sf /usr/bin/lua5.4 /usr/bin/lua && \
    ln -sf /usr/bin/luac5.4 /usr/bin/luac

WORKDIR /app

RUN pip install fastapi --no-cache-dir && pip install uvicorn --no-cache-dir

COPY lua-sandbox/validator.py .

EXPOSE $SANDBOX_PORT

CMD ["python", "validator.py"]

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .analysis import AnalysisError, analyze

app = FastAPI(title="standalone1 baseline", version="0.1.0")

# 程序上限 200 节点，合法请求体很小；1 MiB 只是兜底，防止超大载荷占用解析资源。
MAX_BODY_BYTES = 1024 * 1024


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "standalone1"}


@app.post("/api/analysis/count")
async def analysis_count(request: Request):
    body = await request.body()
    if len(body) > MAX_BODY_BYTES:
        return JSONResponse(
            status_code=422,
            content={"code": "invalid_json", "path": "$"},
        )
    try:
        count = analyze(body)
    except AnalysisError as exc:
        # 输入仅作为数据被解释，绝不作为代码执行；所有失败统一 422 + code/path。
        return JSONResponse(
            status_code=422,
            content={"code": exc.code, "path": exc.path},
        )
    return {"count": count}

// POST /api/analysis/count 的调用封装。
// 成功返回十进制字符串 count；422 时抛出携带 code/path 的 AnalysisRequestError。

export class AnalysisRequestError extends Error {
  readonly code: string
  readonly path: string
  constructor(code: string, path: string) {
    super(`请求被拒绝（${code}）：${path}`)
    this.name = 'AnalysisRequestError'
    this.code = code
    this.path = path
  }
}

/**
 * 提交计数请求。
 * @param n 十进制字符串，取值 1..10^18
 * @param program 已解析的程序树（op/seq/repeat/double/triangle 任意嵌套）
 */
export async function countOperations(n: string, program: unknown): Promise<string> {
  const response = await fetch('/api/analysis/count', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ n, program }),
  })
  let data: unknown = null
  try {
    data = await response.json()
  }
  catch {
    data = null
  }
  if (response.status === 422 && isErrorBody(data)) {
    throw new AnalysisRequestError(data.code, data.path)
  }
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }
  if (!isSuccessBody(data)) {
    throw new Error('无效的计数响应')
  }
  return data.count
}

function isErrorBody(data: unknown): data is { code: string; path: string } {
  return (
    typeof data === 'object' && data !== null
    && typeof (data as { code?: unknown }).code === 'string'
    && typeof (data as { path?: unknown }).path === 'string'
  )
}

function isSuccessBody(data: unknown): data is { count: string } {
  return (
    typeof data === 'object' && data !== null
    && typeof (data as { count?: unknown }).count === 'string'
  )
}

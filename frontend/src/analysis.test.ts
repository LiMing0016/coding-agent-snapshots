import { afterEach, describe, expect, it, vi } from 'vitest'
import { AnalysisRequestError, countOperations } from './analysis'

afterEach(() => vi.unstubAllGlobals())

function stubResponse(response: { ok?: boolean; status?: number; body: unknown }) {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: response.ok ?? response.status === 200,
    status: response.status ?? 200,
    json: async () => response.body,
  }))
}

describe('成功响应', () => {
  it('以 JSON 发送 n 与 program 并返回十进制字符串', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ count: '5050' }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const program = { type: 'triangle' }
    const result = await countOperations('100', program)
    expect(result).toBe('5050')
    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('/api/analysis/count')
    expect(init.method).toBe('POST')
    expect(init.headers['content-type']).toBe('application/json')
    expect(JSON.parse(init.body)).toEqual({ n: '100', program })
  })
})

describe('422 错误', () => {
  it('解析出 code 与 path 抛出 AnalysisRequestError', async () => {
    stubResponse({
      status: 422,
      body: { code: 'type_error', path: '$.program.times' },
    })
    const error = await countOperations('1', { type: 'op' }).catch((e) => e)
    expect(error).toBeInstanceOf(AnalysisRequestError)
    expect(error.code).toBe('type_error')
    expect(error.path).toBe('$.program.times')
  })

  it('先序节点路径完整透传', async () => {
    stubResponse({
      status: 422,
      body: { code: 'node_limit', path: '$.program.items[199]' },
    })
    await expect(countOperations('1', { type: 'seq', items: [] }))
      .rejects.toThrow(AnalysisRequestError)
  })
})

describe('其他异常', () => {
  it('非 422 的失败状态码抛 HTTP 错误', async () => {
    stubResponse({ status: 503, body: {} })
    await expect(countOperations('1', { type: 'op' }))
      .rejects.toThrow('HTTP 503')
  })

  it('成功响应缺少 count 字符串时报错', async () => {
    stubResponse({ status: 200, body: { value: 1 } })
    await expect(countOperations('1', { type: 'op' }))
      .rejects.toThrow('无效的计数响应')
  })

  it('响应体不是 JSON 时不崩溃', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error('bad json')
      },
    }))
    await expect(countOperations('1', { type: 'op' }))
      .rejects.toThrow('HTTP 500')
  })
})

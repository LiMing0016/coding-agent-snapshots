import { afterEach, expect, it, vi } from 'vitest'
import { getHealth } from './health'
afterEach(() => vi.unstubAllGlobals())
it('accepts a valid service response', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok: true, json: async () => ({status:'ok',service:'standalone3'})}))
  expect(await getHealth()).toBe('后端连接正常')
})
it('reports HTTP failures', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ok: false, status: 503}))
  await expect(getHealth()).rejects.toThrow('HTTP 503')
})

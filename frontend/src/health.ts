export async function getHealth(): Promise<string> {
  const response = await fetch('/api/health')
  if (!response.ok) throw new Error(`HTTP ${response.status}`)
  const data = await response.json()
  if (data.status !== 'ok' || data.service !== 'standalone3') throw new Error('无效的健康检查响应')
  return '后端连接正常'
}

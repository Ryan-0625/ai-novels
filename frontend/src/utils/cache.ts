/**
 * 浏览器缓存工具（带版本控制）
 *
 * 使用 localStorage，自动清除过期或版本不匹配的缓存
 */
const CACHE_PREFIX = 'ainovels_cache_'
const CACHE_VERSION_KEY = CACHE_PREFIX + 'version'
const CURRENT_VERSION = '1.0'

interface CacheEntry<T> {
  version: string
  timestamp: number
  ttl: number
  data: T
}

/** 获取缓存版本号 */
function getStoredVersion(): string {
  try {
    return localStorage.getItem(CACHE_VERSION_KEY) || ''
  } catch {
    return ''
  }
}

/** 设置缓存版本号 */
function setStoredVersion(v: string): void {
  try {
    localStorage.setItem(CACHE_VERSION_KEY, v)
  } catch { /* ignore */ }
}

/**
 * 清除过期/版本不匹配的缓存
 * 在应用启动时调用
 */
export function clearStaleCaches(): void {
  try {
    const stored = getStoredVersion()
    if (stored !== CURRENT_VERSION) {
      for (let i = localStorage.length - 1; i >= 0; i--) {
        const key = localStorage.key(i)
        if (key?.startsWith(CACHE_PREFIX)) {
          localStorage.removeItem(key)
        }
      }
      setStoredVersion(CURRENT_VERSION)
    }
  } catch { /* ignore */ }
}

/**
 * 从缓存中获取数据
 * @returns 缓存命中且未过期时返回数据，否则返回 null
 */
export function getCached<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(CACHE_PREFIX + key)
    if (!raw) return null
    const entry: CacheEntry<T> = JSON.parse(raw)
    if (entry.version !== CURRENT_VERSION) {
      localStorage.removeItem(CACHE_PREFIX + key)
      return null
    }
    if (Date.now() - entry.timestamp > entry.ttl) {
      localStorage.removeItem(CACHE_PREFIX + key)
      return null
    }
    return entry.data
  } catch {
    try { localStorage.removeItem(CACHE_PREFIX + key) } catch { /* ignore */ }
    return null
  }
}

/**
 * 将数据写入缓存
 * @param ttlMs 过期时间（毫秒），默认 5 分钟
 */
export function setCache<T>(key: string, data: T, ttlMs: number = 5 * 60 * 1000): void {
  try {
    const entry: CacheEntry<T> = {
      version: CURRENT_VERSION,
      timestamp: Date.now(),
      ttl: ttlMs,
      data,
    }
    localStorage.setItem(CACHE_PREFIX + key, JSON.stringify(entry))
  } catch { /* ignore */ }
}

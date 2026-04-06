import api from '@/services/api'
import { getRetryQueue, removeFromRetryQueue, incrementRetryCount, getBlobsForQueue, removeBlobsForQueue } from '@/services/offlineCache'
import type { ConflictResponse } from '@/types'

const INITIAL_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 30000
const MAX_RETRIES = 10

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export interface ConflictEvent {
  queueItemId: number
  request: { method: string; url: string; data: unknown }
  conflict: ConflictResponse
}

type ConflictHandler = (event: ConflictEvent) => void

let _onConflict: ConflictHandler | null = null

export function setConflictHandler(handler: ConflictHandler): void {
  _onConflict = handler
}

export interface ReplayResult {
  processed: number
  failed: number
  conflicted: boolean
}

export async function processRetryQueue(): Promise<ReplayResult> {
  const queue = await getRetryQueue()
  let backoff = INITIAL_BACKOFF_MS
  let processed = 0
  let failed = 0

  for (const item of queue) {
    if (item.retryCount >= MAX_RETRIES) {
      await removeFromRetryQueue(item.id)
      failed++
      continue
    }

    try {
      const headers: Record<string, string> = {
        ...(item.headers || {}),
        'Idempotency-Key': item.idempotencyKey,
      }

      let requestData: unknown = item.data

      // Reconstruct FormData with blobs if this was a multipart request
      if (item.data && typeof item.data === 'object' && (item.data as any)._formData) {
        const formData = new FormData()
        const fields = (item.data as any).fields || {}
        for (const [k, v] of Object.entries(fields)) {
          formData.append(k, v as string)
        }
        if ((item.data as any)._hasBlobs) {
          const blobs = await getBlobsForQueue(item.queueId)
          for (const b of blobs) {
            formData.append(b.fieldName, b.blob, b.filename)
          }
        }
        requestData = formData
        headers['Content-Type'] = 'multipart/form-data'
      }

      await api.request({
        method: item.method,
        url: item.url,
        data: requestData,
        headers,
      })

      await removeBlobsForQueue(item.queueId)
      await removeFromRetryQueue(item.id)
      processed++
      backoff = INITIAL_BACKOFF_MS
    } catch (error: any) {
      const status = error?.response?.status

      if (status === 409) {
        // Version conflict — pause queue and notify UI
        const conflictData = error.response.data?.detail as ConflictResponse
        if (_onConflict) {
          _onConflict({
            queueItemId: item.id,
            request: { method: item.method, url: item.url, data: item.data },
            conflict: conflictData,
          })
        }
        return { processed, failed, conflicted: true }
      }

      if (status >= 500) {
        // Server error — back off and stop
        await incrementRetryCount(item.id)
        await sleep(backoff)
        backoff = Math.min(backoff * 2, MAX_BACKOFF_MS)
        return { processed, failed, conflicted: false }
      }

      if (status >= 400 && status < 500) {
        // Client error (not conflict) — discard
        await removeFromRetryQueue(item.id)
        failed++
      }
    }
  }

  return { processed, failed, conflicted: false }
}

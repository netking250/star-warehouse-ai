import { normalizeTransportError, TransportError } from './api'

export interface SseReaderOptions {
  signal?: AbortSignal
  route?: string
}

/** Parse one SSE block into its combined data payload. */
export function parseSseBlock(block: string): string | null {
  const dataLines = block
    .split(/\r?\n/)
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).replace(/^ /, ''))
  return dataLines.length > 0 ? dataLines.join('\n') : null
}

/** Read a browser SSE body while preserving event boundaries across network chunks. */
export async function* readSseData(
  body: ReadableStream<Uint8Array> | null,
  options: SseReaderOptions = {}
): AsyncGenerator<string> {
  const route = options.route ?? 'stream'
  if (!body) {
    throw new TransportError({
      kind: 'NETWORK',
      route,
      message: 'The streaming response body is unavailable.',
    })
  }

  const reader = body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  const cancelReader = (): void => {
    void reader.cancel().catch(() => undefined)
  }

  options.signal?.addEventListener('abort', cancelReader, { once: true })
  try {
    while (true) {
      if (options.signal?.aborted) {
        throw new TransportError({ kind: 'ABORTED', route })
      }
      const { done, value } = await reader.read()
      if (done) break
      if (value) buffer += decoder.decode(value, { stream: true })

      const blocks = buffer.split(/\r?\n\r?\n/)
      buffer = blocks.pop() ?? ''
      for (const block of blocks) {
        const data = parseSseBlock(block)
        if (data !== null) yield data
      }
    }

    buffer += decoder.decode()
    const finalData = parseSseBlock(buffer)
    if (finalData !== null) yield finalData
  } catch (error) {
    throw normalizeTransportError(error, {
      route,
      signal: options.signal,
    })
  } finally {
    options.signal?.removeEventListener('abort', cancelReader)
    reader.releaseLock()
  }
}

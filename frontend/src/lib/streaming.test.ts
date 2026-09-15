import { describe, expect, it } from 'vitest'
import { parseSseBlock, readSseData } from './streaming'

function streamFromChunks(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk))
      controller.close()
    },
  })
}

describe('SSE transport', () => {
  it('parses data blocks split across arbitrary network chunks', async () => {
    const events: string[] = []
    for await (const event of readSseData(
      streamFromChunks(['data: {"token":"Hel', 'lo"}\r\n\r\ndata: [DONE]\r\n\r\n']),
      { route: '/chat' }
    )) {
      events.push(event)
    }
    expect(events).toEqual(['{"token":"Hello"}', '[DONE]'])
  })

  it('combines multiline data fields without inventing replay semantics', () => {
    expect(parseSseBlock('event: message\ndata: first\ndata: second')).toBe('first\nsecond')
  })
})

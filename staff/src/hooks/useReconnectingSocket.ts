import { useEffect, useRef, useState } from 'react'

/**
 * WebSocket with exponential backoff reconnect (1s -> 15s).
 * Pass url=null to stay disconnected. Returns whether the socket is open.
 */
export function useReconnectingSocket(
  url: string | null,
  onMessage: (data: unknown) => void,
  onOpen?: () => void,
): boolean {
  const [connected, setConnected] = useState(false)
  const handler = useRef(onMessage)
  handler.current = onMessage
  const openHandler = useRef(onOpen)
  openHandler.current = onOpen

  useEffect(() => {
    if (!url) {
      setConnected(false)
      return
    }
    let ws: WebSocket | null = null
    let timer: number | undefined
    let attempt = 0
    let stopped = false

    const connect = () => {
      ws = new WebSocket(url)
      ws.onopen = () => {
        attempt = 0
        setConnected(true)
        openHandler.current?.()
      }
      ws.onmessage = (ev: MessageEvent<string>) => {
        try {
          handler.current(JSON.parse(ev.data) as unknown)
        } catch {
          /* ignore malformed frames */
        }
      }
      ws.onclose = () => {
        setConnected(false)
        if (stopped) return
        const delay = Math.min(15000, 1000 * 2 ** attempt)
        attempt += 1
        timer = window.setTimeout(connect, delay)
      }
      ws.onerror = () => ws?.close()
    }
    connect()

    return () => {
      stopped = true
      window.clearTimeout(timer)
      if (ws) {
        ws.onclose = null
        ws.close()
      }
      setConnected(false)
    }
  }, [url])

  return connected
}

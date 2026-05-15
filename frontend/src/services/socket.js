import { useEffect, useRef, useState } from "react";
import { io } from "socket.io-client";

const SOCKET_URL = "/ws";

/**
 * React hook for Socket.IO real-time ticket events.
 * Returns: { connected, lastEvent }
 *
 * Calls onTicketEvent(event, data) when a ticket event arrives.
 * Events: ticket:created, ticket:updated, ticket:resolved, ticket:deleted
 */
export function useSocket(onTicketEvent) {
  const [connected, setConnected] = useState(false);
  const socketRef = useRef(null);
  const callbackRef = useRef(onTicketEvent);
  callbackRef.current = onTicketEvent;

  useEffect(() => {
    const socket = io(SOCKET_URL, {
      transports: ["websocket", "polling"],
      reconnection: true,
      reconnectionDelay: 2000,
      reconnectionAttempts: 10,
    });

    socketRef.current = socket;

    socket.on("connect", () => setConnected(true));
    socket.on("disconnect", () => setConnected(false));

    const events = ["ticket:created", "ticket:updated", "ticket:resolved", "ticket:deleted"];
    for (const event of events) {
      socket.on(event, (data) => {
        callbackRef.current?.(event, data);
      });
    }

    return () => {
      socket.disconnect();
      socketRef.current = null;
    };
  }, []);

  return { connected };
}

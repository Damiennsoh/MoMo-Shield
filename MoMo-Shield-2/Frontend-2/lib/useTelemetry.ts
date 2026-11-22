'use client';

import { useEffect, useRef } from 'react';
import { fetchRecentEvents, telemetryWsUrl, type AssessmentResult } from './api';
import { useStore } from './useStore';
import { playAlertTone } from './sound';

const RECONNECT_MS = 3000;
const MAX_BACKOFF_MS = 15000;

/**
 * Subscribes the FraudOps dashboard to the Intelligence Core:
 * hydrates recent assessments over REST, then streams live ones over WS.
 */
export function useTelemetry(): void {
  const ingestAssessment = useStore((s) => s.ingestAssessment);
  const hydrateAssessments = useStore((s) => s.hydrateAssessments);
  const setConnection = useStore((s) => s.setConnection);
  const ingestRef = useRef(ingestAssessment);
  const hydrateRef = useRef(hydrateAssessments);
  const setConnRef = useRef(setConnection);
  ingestRef.current = ingestAssessment;
  hydrateRef.current = hydrateAssessments;
  setConnRef.current = setConnection;

  useEffect(() => {
    let stopped = false;
    let ws: WebSocket | null = null;
    let retry = 0;
    let retryTimer: number | undefined;

    const connect = () => {
      if (stopped) return;
      try {
        ws = new WebSocket(telemetryWsUrl());
      } catch {
        scheduleRetry();
        return;
      }
      ws.onopen = () => {
        retry = 0;
        setConnRef.current(true, true);
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as AssessmentResult;
          if (data && typeof data.risk_score === 'number') {
            ingestRef.current(data);
            if (data.risk_tier === 'HIGH') {
              void playAlertTone();
            }
          }
        } catch {
          /* ignore malformed frames */
        }
      };
      ws.onclose = () => {
        setConnRef.current(false, true);
        scheduleRetry();
      };
      ws.onerror = () => ws?.close();
    };

    const scheduleRetry = () => {
      if (stopped) return;
      const delay = Math.min(RECONNECT_MS * 2 ** retry, MAX_BACKOFF_MS);
      retry += 1;
      retryTimer = window.setTimeout(connect, delay);
    };

    // Hydrate history first; failure still leaves the WS path usable.
    fetchRecentEvents(50)
      .then((events) => {
        if (!stopped && events.length) hydrateRef.current(events);
        setConnRef.current(false, true);
      })
      .catch(() => setConnRef.current(false, false));

    connect();
    return () => {
      stopped = true;
      window.clearTimeout(retryTimer);
      ws?.close();
    };
  }, []);
}

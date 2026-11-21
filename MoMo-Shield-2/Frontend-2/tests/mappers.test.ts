import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  assessmentToAlert,
  assessmentToSignalEvent,
  buildLabEvent,
} from '../lib/mappers.ts';
import type { AssessmentResult } from '../lib/api.ts';

function makeResult(overrides: Partial<AssessmentResult> = {}): AssessmentResult {
  return {
    event_id: 'evt-1',
    msisdn: '+233244001122',
    event_type: 'sms',
    risk_score: 80,
    risk_tier: 'HIGH',
    triggered_rules: ['GH18: New device binding detected'],
    glance_status: 'HIGH (7 reports)',
    llm_intent: 'credential harvesting',
    action_taken: 'BLOCKED',
    latency_ms: 12.5,
    timestamp: '2026-11-21T10:00:00.000Z',
    ...overrides,
  };
}

test('masks msisdn in signal events', () => {
  const event = assessmentToSignalEvent(makeResult());
  assert.equal(event.msisdn, '+23324 ••• 1122');
  assert.equal(event.kind, 'SMS');
  assert.equal(event.risk, 'high');
  assert.equal(event.score, 80);
});

test('maps event types to kinds', () => {
  assert.equal(assessmentToSignalEvent(makeResult({ event_type: 'voice' })).kind, 'VOICE');
  assert.equal(assessmentToSignalEvent(makeResult({ event_type: 'ussd' })).kind, 'USSD');
  assert.equal(assessmentToSignalEvent(makeResult({ event_type: 'transaction' })).kind, 'USSD');
});

test('LOW tier produces no alert', () => {
  assert.equal(assessmentToAlert(makeResult({ risk_tier: 'LOW', action_taken: 'ALLOWED' })), undefined);
});

test('MEDIUM tier produces active alert', () => {
  const alert = assessmentToAlert(makeResult({ risk_tier: 'MEDIUM', action_taken: 'WARNED' }));
  assert.ok(alert);
  assert.equal(alert.status, 'active');
  assert.deepEqual(alert.rules, ['GH18: New device binding detected']);
});

test('BLOCKED action maps to blocked status', () => {
  const alert = assessmentToAlert(makeResult());
  assert.equal(alert?.status, 'blocked');
});

test('buildLabEvent builds valid sandbox payload', () => {
  const evt = buildLabEvent({ msisdn: '+233240000310', channel: 'voice', text: 'hello' });
  assert.equal(evt.event_type, 'voice');
  assert.equal(evt.msisdn, '+233240000310');
  assert.equal(evt.payload.text, 'hello');
  assert.ok(evt.event_id.startsWith('lab-'));
});

test('buildLabEvent maps sms channel', () => {
  const evt = buildLabEvent({ msisdn: '+233240000310', channel: 'sms', text: 'hi' });
  assert.equal(evt.event_type, 'sms');
});

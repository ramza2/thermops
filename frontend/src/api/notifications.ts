import { fetchApi, postApi, putApi } from "@/api/client";
import type {
  AlertRule,
  Incident,
  NotificationChannel,
  NotificationDelivery,
  NotificationEvent,
  NotificationRecipient,
  NotificationSummary,
} from "@/types/notification";

export async function getNotificationSummary(): Promise<NotificationSummary> {
  return fetchApi("/notifications/summary");
}

export async function listNotificationChannels(): Promise<NotificationChannel[]> {
  return fetchApi("/notifications/channels");
}

export async function createNotificationChannel(body: Record<string, unknown>): Promise<NotificationChannel> {
  return postApi("/notifications/channels", body);
}

export async function updateNotificationChannel(channelId: string, body: Record<string, unknown>): Promise<NotificationChannel> {
  return putApi(`/notifications/channels/${encodeURIComponent(channelId)}`, body);
}

export async function testNotificationChannel(channelId: string): Promise<Record<string, unknown>> {
  return postApi(`/notifications/channels/${encodeURIComponent(channelId)}/test`, {});
}

export async function listNotificationRecipients(): Promise<NotificationRecipient[]> {
  return fetchApi("/notifications/recipients");
}

export async function createNotificationRecipient(body: Record<string, unknown>): Promise<NotificationRecipient> {
  return postApi("/notifications/recipients", body);
}

export async function listAlertRules(): Promise<AlertRule[]> {
  return fetchApi("/notifications/alert-rules");
}

export async function createAlertRule(body: Record<string, unknown>): Promise<AlertRule> {
  return postApi("/notifications/alert-rules", body);
}

export async function updateAlertRule(ruleId: string, body: Record<string, unknown>): Promise<AlertRule> {
  return putApi(`/notifications/alert-rules/${encodeURIComponent(ruleId)}`, body);
}

export async function listNotificationEvents(): Promise<NotificationEvent[]> {
  return fetchApi("/notifications/events");
}

export async function postTestNotificationEvent(body: Record<string, unknown>): Promise<Record<string, unknown>> {
  return postApi("/notifications/events/test", body);
}

export async function listIncidents(): Promise<Incident[]> {
  return fetchApi("/notifications/incidents");
}

export async function acknowledgeIncident(incidentId: string, body?: Record<string, unknown>): Promise<Incident> {
  return postApi(`/notifications/incidents/${encodeURIComponent(incidentId)}/acknowledge`, body || {});
}

export async function resolveIncident(incidentId: string, body?: Record<string, unknown>): Promise<Incident> {
  return postApi(`/notifications/incidents/${encodeURIComponent(incidentId)}/resolve`, body || {});
}

export async function listNotificationDeliveries(): Promise<NotificationDelivery[]> {
  return fetchApi("/notifications/deliveries");
}

export async function retryNotificationDelivery(deliveryId: string): Promise<NotificationDelivery> {
  return postApi(`/notifications/deliveries/${encodeURIComponent(deliveryId)}/retry`, {});
}

export interface NotificationChannel {
  channel_id: string;
  channel_name: string;
  channel_type: string;
  enabled_yn: boolean;
  config_json?: Record<string, unknown>;
  has_secret?: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface NotificationRecipient {
  recipient_id: string;
  recipient_name: string;
  recipient_type: string;
  address_masked?: string;
  enabled_yn: boolean;
}

export interface AlertRule {
  alert_rule_id: string;
  rule_name: string;
  rule_description?: string;
  enabled_yn: boolean;
  event_source: string;
  event_type: string;
  min_severity: string;
  condition_json?: Record<string, unknown>;
  dedup_window_minutes: number;
  suppress_yn: boolean;
  create_incident_yn: boolean;
  channel_ids_json: string[];
  recipient_ids_json: string[];
  message_template?: string;
}

export interface NotificationEvent {
  event_id: string;
  event_source: string;
  event_type: string;
  severity: string;
  title: string;
  message?: string;
  resource_type?: string;
  resource_id?: string;
  occurred_at?: string;
}

export interface Incident {
  incident_id: string;
  event_id?: string;
  severity: string;
  status: string;
  title: string;
  summary?: string;
  resource_type?: string;
  resource_id?: string;
  occurrence_count: number;
  first_occurred_at?: string;
  last_occurred_at?: string;
  acknowledged_at?: string;
  resolved_at?: string;
}

export interface NotificationDelivery {
  delivery_id: string;
  event_id: string;
  incident_id?: string;
  channel_id?: string;
  recipient_id?: string;
  delivery_status: string;
  severity: string;
  title: string;
  destination_masked?: string;
  error_message?: string;
  sent_at?: string;
  created_at?: string;
}

export interface NotificationSummary {
  open_incident_count: number;
  severity_counts: Record<string, number>;
  total_event_count: number;
  failed_delivery_count: number;
}

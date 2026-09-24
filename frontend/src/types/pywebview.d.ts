interface PyWebViewApi {
  get_config(): Promise<Record<string, unknown>>;
  save_config(config: Record<string, unknown>): Promise<void>;
  get_multi_instance_state(): Promise<Record<string, unknown>>;
  set_multi_instance_enabled(enabled: boolean): Promise<{ success: boolean; error?: string }>;
  get_biome_data(): Promise<Record<string, string>>;
  get_full_biome_data(): Promise<Record<string, unknown>>;
  get_full_aura_data(): Promise<Record<string, unknown>>;
  get_aura_detail?(auraName: string): Promise<Record<string, unknown>>;
  get_biome_detail?(biomeName: string): Promise<Record<string, unknown>>;
  ensure_media_thumbnail?(url: string, maxDim?: number): Promise<Record<string, unknown>>;
  reset_config_to_defaults?(): Promise<Record<string, unknown>>;
  get_remote_bot_status?(): Promise<{ running: boolean; enabled: boolean; core?: boolean }>;
  restart_remote_bot?(): Promise<Record<string, unknown>>;
  get_rare_biome_custom(): Promise<Record<string, unknown>>;
  set_biome_detection(enabled: boolean): Promise<void>;
  get_macro_version(): Promise<string>;
  get_active_modules(): Promise<{ modules: Record<string, { active: boolean; enabled: boolean }>; incompatibilities: string[] }>;
  get_macro_logs(): Promise<{ lines: string[] }>;
  send_webhook_status(message: string, color: number): Promise<void>;
  send_webhook(biome: string, message_type: string, event_type: "start" | "end", screenshot_path?: string): Promise<void>;
  preview_biome_webhook(biome: string, event_type: "start" | "end", custom_title?: string, custom_description?: string, color_override?: string): Promise<string>;
  apply_update(url: string, version: string): Promise<void>;
  check_obby_path_exists(): Promise<boolean>;
  open_appdata(): Promise<{ success: boolean; error?: string }>;
  check_winocr_status(): Promise<{ installed: boolean; version: string | null }>;
  create_calibration_window(key: string, mode: "point" | "region"): Promise<void>;
  take_calibration_screenshot(): Promise<[string, number, number]>;
  emit_calibration_result(data: Record<string, unknown>): Promise<void>;
  close_window(): Promise<void>;
  minimize_window(): Promise<void>;
  toggle_maximize(): Promise<void>;
}
declare global {
  interface Window { pywebview?: { api: PyWebViewApi } }
}
export {};

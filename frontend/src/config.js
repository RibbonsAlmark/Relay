const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  LIST_ALL: `${BASE_URL}/list_all`,
  CREATE_SOURCE: `${BASE_URL}/create_source`,
  PLAY_DATA: (uuid) => `${BASE_URL}/play_data/${uuid}`,
  
  // 必须定义为函数，才能接收 uuid 参数
  HEARTBEAT: (uuid) => `${BASE_URL}/heartbeat/${uuid}`, 
  LOAD_RANGE: (uuid) => `${BASE_URL}/load_range/${uuid}`,
  GET_INFO: (uuid) => `${BASE_URL}/get_info/${uuid}`,
  ENABLE_STREAMING: (uuid) => `${BASE_URL}/enable_streaming_mode/${uuid}`,
  ENABLE_ALIGNMENT: (uuid) => `${BASE_URL}/enable_alignment_mode/${uuid}`,
  REFRESH_UI: (uuid) => `${BASE_URL}/refresh_ui/${uuid}`,
};

export const RERUN_CONFIG = {
  VIEWER_BASE: import.meta.env.VITE_RERUN_VIEWER_BASE || 'http://localhost:9092/',
  STREAMING_MODE: import.meta.env.VITE_RERUN_STREAMING_MODE === 'true',
  STREAMING_BATCH_SIZE: 100, // 默认流式加载批次大小
  STREAMING_BUFFER_THRESHOLD: 50, // 流式加载触发阈值
  STREAMING_MAX_CACHED_FRAMES: 1000, // 最大缓存帧数
  STREAMING_KEEP_WINDOW_RATIO: 2.0, // 保留窗口系数 (Window Size = Batch Size * Ratio)
};
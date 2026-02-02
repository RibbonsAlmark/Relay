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
  CLEAR_QUEUES: (uuid) => `${BASE_URL}/clear_queues/${uuid}`,
  SEND_SENTINEL: (uuid) => `${BASE_URL}/send_sentinel/${uuid}`,
};

export const RERUN_CONFIG = {
  VIEWER_BASE: import.meta.env.VITE_RERUN_VIEWER_BASE || 'http://localhost:9092/',
  STREAMING_MODE: import.meta.env.VITE_RERUN_STREAMING_MODE === 'true',
  
  // --- 流式加载核心配置 (自动计算) ---
  STREAMING_BATCH_SIZE: 100, // 基础加载单位 (帧数)
  
  // 系数配置
  // 1. 播放时的预加载阈值系数 (2.0 表示剩余 200 帧时就触发加载，防止网络延迟导致播放卡顿)
  _BUFFER_COEFF: 1.0,
  // 2. 暂停/卡顿时的预加载阈值系数 (5.0 表示暂停时预加载 500 帧，保证流畅启动)
  _PAUSED_BUFFER_COEFF: 1.0, 

  // 内存管理配置
  STREAMING_MEMORY_LIMIT_MB: 2000, // 内存阈值 (MB)，超过此值触发清理
  STREAMING_SAFE_WINDOW_RADIUS: 500, // 缓存清理时的保留窗口半径 (帧数)

  get STREAMING_BUFFER_THRESHOLD() {
    return Math.ceil(this.STREAMING_BATCH_SIZE * this._BUFFER_COEFF);
  },
  
  get STREAMING_PAUSED_BUFFER_THRESHOLD() {
    const maxCoeff = Math.max(this._BUFFER_COEFF, this._PAUSED_BUFFER_COEFF);
    return Math.ceil(this.STREAMING_BATCH_SIZE * maxCoeff);
  },

  // 辅助方法：根据播放状态获取当前应该使用的阈值
  getStreamingThreshold(isPlaying) {
      return isPlaying ? this.STREAMING_BUFFER_THRESHOLD : this.STREAMING_PAUSED_BUFFER_THRESHOLD;
  }
};
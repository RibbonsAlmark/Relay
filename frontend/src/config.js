const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export const API_ENDPOINTS = {
  LIST_ALL: `${BASE_URL}/list_all`,
  CREATE_SOURCE: `${BASE_URL}/create_source`,
  PLAY_DATA: (uuid) => `${BASE_URL}/play_data/${uuid}`,
  
  // 必须定义为函数，才能接收 uuid 参数
  HEARTBEAT: (uuid) => `${BASE_URL}/heartbeat/${uuid}`, 
};
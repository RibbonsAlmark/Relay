// 从环境变量读取基础地址
const BASE_URL = import.meta.env.VITE_API_BASE_URL;

export const API_ENDPOINTS = {
  LIST_ALL: `${BASE_URL}/list_all`,
  CREATE_SOURCE: `${BASE_URL}/create_source`,
  PLAY_DATA: (uuid) => `${BASE_URL}/play_data/${uuid}`,
};
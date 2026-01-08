import { defineStore } from 'pinia'

export const useRerunStore = defineStore('rerun', {
  state: () => ({
    appId: '',
    currentSource: '',
    recordingUuid: '', // 存储 API 返回的 UUID
    dbStructure: {},   // 👈 必须添加这个，用于存储 list_all 返回的数据库结构
    collection: '',    // 建议初始值留空，由用户选择或接口填充
    dataset: ''
  }),
  actions: {
    // 确保传入三个参数：AppID, URL, UUID
    setRerunInfo(appId, source, uuid) {
      this.appId = appId
      this.currentSource = source
      this.recordingUuid = uuid
    },
    // 👈 添加这个 action，用于更新数据库结构
    setDbStructure(structure) {
      this.dbStructure = { ...structure } // 使用解构确保触发 Vue 响应式
    }
  }
})
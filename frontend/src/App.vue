<template>
  <div id="app" :class="{ 'is-dragging': isDragging }">
    <!-- <div class="controls">
      <div class="input-group">
        <label>数据库：</label>
        <input 
          v-model="selectedDB" 
          list="db-options" 
          placeholder="点击选择"
          @focus="handleDBFocus"
          @input="onDBChange"
        >
        <datalist id="db-options">
          <option v-for="dbName in Object.keys(rerunStore.dbStructure)" :key="dbName" :value="dbName" />
        </datalist>
      </div>

      <div class="input-group">
        <label>数据集：</label>
        <input 
          v-model="selectedDataset" 
          list="dataset-options" 
          placeholder="点击选择"
          :disabled="!selectedDB"
          @focus="handleDSFocus"
        >
        <datalist id="dataset-options">
          <option v-for="ds in availableDatasets" :key="ds" :value="ds" />
        </datalist>
      </div>

      <div class="btn-group">
        <button 
          type="button"
          class="generate-btn" 
          @click.stop.prevent="handleCreateSource" 
          :disabled="loading || !selectedDB || !selectedDataset"
        >
          {{ loading ? '...' : '生成数据源URL' }}
        </button>

        <button 
          type="button"
          class="play-btn" 
          @click.stop.prevent="handlePlayData" 
          :disabled="!recordingUuid || playing"
        >
          {{ playing ? '传输中...' : '开始数据传输' }}
        </button>
      </div>

      <div v-if="currentSource" class="result-container">
        <span class="tag">Rerun URL</span>
        <div class="result-box" @click="copyToClipboard" title="点击复制 URL">
          <span class="url-text">{{ currentSource }}</span>
          <span class="copy-icon">{{ copied ? '✅' : '📋' }}</span>
        </div>
      </div>
    </div> -->

    
    <RerunViewer 
      v-if="isInitialized" 
      ref="rerunViewerRef"
      :source="currentSource" 
    />

    <FloatingButton 
      :on-reload="handleManualReload"
      @drag-start="isDragging = true"
      @drag-end="isDragging = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed, watch, nextTick } from 'vue';
import { storeToRefs } from 'pinia';
import RerunViewer from './components/RerunViewer.vue';
import FloatingButton from './components/FloatingButton.vue';
import { useRerunStore } from './stores/rerun';
import { API_ENDPOINTS, RERUN_CONFIG } from './config';
import { ElNotification } from 'element-plus'; 

const rerunStore = useRerunStore();
const { recordingUuid, currentSource } = storeToRefs(rerunStore);

// const selectedDB = ref('');
// const selectedDataset = ref('');
// const loading = ref(false);
const playing = ref(false);
// const copied = ref(false);

// 流式加载状态管理
// 有效帧范围列表，元素为 [start, end)
// 例如: [[0, 100], [200, 300]]
const loadedRanges = ref([]); 
const pendingRanges = ref(new Set()); // 记录正在加载中的区间字符串 "start-end"
const maxFrameIdx = ref(0); // 数据集最大帧数
const currentPlaybackFrame = ref(0); // 当前播放帧索引
const isDragging = ref(false); // 控制 iframe 穿透


// 直接在 setup 顶层运行，不要等到 onMounted
const params = new URLSearchParams(window.location.search);
const urlParam = params.get('rerun_url');
const uuidParam = params.get('source_uuid');

const isInitialized = ref(false);
const rerunViewerRef = ref(null); // 引用 RerunViewer 组件实例

let heartbeatTimer = null; // 用于存储定时器引用

if (urlParam && uuidParam) {
  rerunStore.setRerunInfo(null, urlParam.trim().replace(/\s+/g, '+'), uuidParam);
} else {
  // 如果没有参数，也给 Store 塞个空值，防止组件内部报错
  rerunStore.setRerunInfo(null, "", "");
}

// 标记初始化完成
isInitialized.value = true;

// // 核心联动：根据选中的数据库计算数据集列表
// const availableDatasets = computed(() => {
//   if (!selectedDB.value || !rerunStore.dbStructure) return [];
//   return rerunStore.dbStructure[selectedDB.value] || [];
// });

// // 解决无法重选的问题：点击输入框时清空内容以弹出完整列表
// const handleDBFocus = () => {
//   selectedDB.value = '';
// };

// const handleDSFocus = () => {
//   selectedDataset.value = '';
// };

// // 当数据库内容改变时，清空已选的数据集
// const onDBChange = () => {
//   selectedDataset.value = '';
// };

// --- 核心函数：发送心跳 ---
const sendHeartbeat = async () => {
  if (!recordingUuid.value) return;

  try {
    // 这里的 API_ENDPOINTS.HEARTBEAT 对应后端 manager.keep_alive 的路由
    const response = await fetch(API_ENDPOINTS.HEARTBEAT(recordingUuid.value), {
      method: 'POST'
    });
    
    if (response.ok) {
      console.log(`[Heartbeat] 续命成功: ${recordingUuid.value}`);
    } else {
      console.warn("[Heartbeat] 续命失败，后端可能已回收资源");
    }
  } catch (e) {
    console.error("[Heartbeat] 网络错误:", e);
  }
};

// --- 开启心跳循环 ---
const startHeartbeatLoop = () => {
  stopHeartbeatLoop(); // 先清理旧的
  console.log("启动心跳监控...");
  // 每 60 秒发送一次心跳 (过期时间 180s，60s 非常安全)
  heartbeatTimer = setInterval(sendHeartbeat, 60000);
};

// --- 停止心跳循环 ---
const stopHeartbeatLoop = () => {
  if (heartbeatTimer) {
    clearInterval(heartbeatTimer);
    heartbeatTimer = null;
  }
};

// --- 监听 recordingUuid 的变化 ---
// 当获取到新的录制 ID 时，立即发送一次心跳并开启循环
watch(recordingUuid, (newId) => {
  if (newId) {
    sendHeartbeat(); // 立即执行一次
    startHeartbeatLoop();
  } else {
    stopHeartbeatLoop();
  }
});

// --- 全局消息监听处理 ---
const handleGlobalMessage = async (event) => {
  // 监听打分完成消息
  if (event.data?.type === "RERUN_RATING_COMPLETE") {
    console.log("收到打分完成消息:", event.data);
    
    // 1. 校验 UUID 是否匹配当前会话
    if (event.data.recording_uuid === recordingUuid.value) {
      console.log("UUID 匹配，正在请求刷新 UI...");
      
      try {
        // 2. 构造刷新请求，附带当前已加载的区间
        // 注意：loadedRanges 是 Ref 对象，需要取 .value
        const payload = {
          recording_uuid: recordingUuid.value,
          loaded_ranges: loadedRanges.value
        };

        const res = await fetch(API_ENDPOINTS.REFRESH_UI(recordingUuid.value), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify(payload)
        });

        if (res.ok) {
          console.log("[UI Refresh] 刷新请求发送成功");
          ElNotification({
            title: '评分同步',
            message: '评分已更新，正在刷新界面...',
            type: 'success',
            duration: 2000
          });
        } else {
          console.warn("[UI Refresh] 刷新请求失败", res.status);
        }
      } catch (e) {
        console.error("[UI Refresh] 网络异常", e);
      }
    } else {
      console.log(`UUID 不匹配 (期望: ${recordingUuid.value}, 收到: ${event.data.recording_uuid})，忽略消息`);
    }
  }
};

// 页面初始化：加载后端数据库结构
onMounted(async () => {
  // 注册全局消息监听
  window.addEventListener('message', handleGlobalMessage);

  // 1. 解析 URL 参数 (例如: ?rerun_url=rrd://localhost:9876&source_uuid=123-456)
  const params = new URLSearchParams(window.location.search);
  const urlParam = params.get('rerun_url'); // 对应你说的 rerun url
  const uuidParam = params.get('source_uuid'); // 对应你说的 source uuid

  // 2. 如果存在参数，直接存入 Store
  // 这会自动触发 RerunViewer 的更新，因为 currentSource 是响应式的
  if (urlParam || uuidParam) {
    rerunStore.setRerunInfo(
      null,        // app_id (如果没有就不传)
      urlParam,    // connect_url -> 对应 currentSource
      uuidParam    // recording_uuid
    );
    console.log('Detected params:', { urlParam, uuidParam });
  }

  // // 3. 数据库结构加载逻辑
  // try {
  //   const response = await fetch(API_ENDPOINTS.LIST_ALL);
  //   const result = await response.json();
  //   if (result.status === 'success') {
  //     rerunStore.setDbStructure(result.data);
  //   }
  // } catch (e) {
  //   console.error('API Error:', e);
  // }

  // 如果 URL 里直接带了 UUID，触发心跳
  if (recordingUuid.value) {
    sendHeartbeat();
    startHeartbeatLoop();
  }

  if (recordingUuid.value) {
    console.log("正在监控 Rerun 加载进度...");
    
    // 如果是直连模式 (URL带参数)，需要额外获取一次 Session 信息 (主要是 max_frame_idx)
    if (RERUN_CONFIG.STREAMING_MODE) {
        try {
            // 1. 获取 Session 信息
            const res = await fetch(API_ENDPOINTS.GET_INFO(recordingUuid.value));
            if (res.ok) {
                const info = await res.json();
                if (info.max_frame_idx) {
                    maxFrameIdx.value = info.max_frame_idx;
                    console.log(`[Stream] 初始化获取最大帧数: ${maxFrameIdx.value}`);
                }
            }
            
            // 2. 显式通知后端开启流式模式 (以防 Session 不是通过 create_source 创建的)
            await fetch(API_ENDPOINTS.ENABLE_STREAMING(recordingUuid.value), { method: 'POST' });
            
            // 3. 显式通知后端开启对齐模式 (推荐流式模式下开启以减少抖动)
            await fetch(API_ENDPOINTS.ENABLE_ALIGNMENT(recordingUuid.value), { method: 'POST' });
            
            console.log("[Stream] 已通知后端开启流式模式 & 对齐模式");
            
        } catch (e) {
            console.warn("[Stream] 初始化 Session 失败", e);
        }
    }
    
    // 关键改变：等资源下载完，而不是等固定秒数
    await waitForRerunReady(); 
    
    console.log("检测到 Viewer 已就绪，正在启动数据流...");

    ElNotification({
      title: '加载成功',
      message: 'Rerun Viewer 已就绪，正在启动数据传输流...',
      type: 'success',
      position: 'bottom-right',
      duration: 3000 // 3秒后自动关闭
    });

    if (RERUN_CONFIG.STREAMING_MODE) {
        // 如果开启了流式模式，这里不再自动调用 handlePlayData
        // 而是通过监听 rerun_time_update 事件，在后续逻辑中动态触发 load_range
        console.log("【流式模式】已就绪，正在预加载初始数据...");
        // 预加载第一批数据
        await handleLoadRange(0, RERUN_CONFIG.STREAMING_BATCH_SIZE);
        
        // 强制跳转到第0帧，确保播放器指针归位
        jumpToTime("frame_idx", 0);
    } else {
        // 经典模式：一次性全量加载
        await handlePlayData(); 
    }
  }
});

onUnmounted(() => {
  stopHeartbeatLoop();
  window.removeEventListener('message', handleGlobalMessage);
});

const waitForRerunReady = () => {
  return new Promise((resolve) => {
    window.addEventListener("message", (event) => { 
        // 安全起见，建议检查 event.origin 
        const data = event.data;

        // 1. 监听 Rerun 就绪信号
        if (data && data.type === "rerun_ready") { 
            console.log("Rerun viewer 已准备好接收数据！"); 
            resolve();
        } 
        
        // 2. 监听时间轴更新信号
        if (data && data.type === "rerun_time_update") { 
            onTimeUpdate(data);
        }
    }); 
  });
};

// 辅助函数：获取 iframe window
const getRerunWindow = () => {
    // 通过组件 ref 获取，比 querySelector 更安全
    return rerunViewerRef.value?.getWindow();
};

// 让 Rerun Viewer 跳转到指定时间点
const jumpToTime = (timeline, timeVal) => {
    const win = getRerunWindow();
    if (win) {
        console.log(`[Stream] 调用 Rerun Jump: ${timeline} -> ${timeVal}`);
        win.postMessage({
            type: "rerun_set_time",
            recording_id: recordingUuid.value,
            timeline: timeline,
            time: timeVal
        }, "*");
    } else {
        console.warn("[Stream] 无法获取 iframe window，跳转失败");
    }
};

// 调用 Rerun 内部接口清理数据
const callRerunDrop = (start, end) => {
    const win = getRerunWindow();
    if (win) {
        console.log(`[Stream] 调用 Rerun Drop: [${start}, ${end})`);
        
        // 使用 postMessage 发送指令，绕过跨域限制
        win.postMessage({
            type: "rerun_drop_time_range", // 固定指令类型
            recording_id: recordingUuid.value, // 必须匹配
            timeline: "frame_idx", // 时间轴名称
            start: start,
            end: end
        }, "*"); // 允许发送给任意源
    } else {
        console.warn("[Stream] 无法获取 iframe window，数据清理失败");
    }
};

// --- 缓存清理逻辑 (基于距离的最远驱逐策略) ---
const handleCacheCleanup = () => {
    let totalCached = 0;
    for (const range of loadedRanges.value) {
        totalCached += (range[1] - range[0]);
    }
    
    const MAX_CACHED = RERUN_CONFIG.STREAMING_MAX_CACHED_FRAMES || 1000;
    if (totalCached <= MAX_CACHED) return;
    
    console.log(`[Stream] 缓存超标 (${totalCached} > ${MAX_CACHED})，执行窗口清理策略...`);
    
    const currentFrame = currentPlaybackFrame.value;
    // 动态计算窗口大小：BatchSize * 系数
    const BATCH_SIZE = RERUN_CONFIG.STREAMING_BATCH_SIZE || 100;
    const RATIO = RERUN_CONFIG.STREAMING_KEEP_WINDOW_RATIO || 5.0;
    const KEEP_WINDOW = Math.ceil(BATCH_SIZE * RATIO);
    
    const halfWindow = Math.floor(KEEP_WINDOW / 2);
    
    // 计算保留窗口范围 [keepStart, keepEnd]
    const keepStart = Math.max(0, currentFrame - halfWindow);
    const keepEnd = currentFrame + halfWindow;

    let newRanges = [];

    // 简单窗口保留策略：遍历所有区间，只保留在窗口内的部分
    for (const range of loadedRanges.value) {
        let [start, end] = range;
        
        // 标记该区间是否原本包含第0帧
        const originallyContainsFirstFrame = (start === 0);
        // 标记该区间是否原本包含最后一帧 (注意: maxFrameIdx 是开区间上限，所以有效帧是 maxFrameIdx-1)
        // 但这里 range 是 [start, end)，如果 end == maxFrameIdx.value，说明包含了最后一帧
        const originallyContainsLastFrame = (maxFrameIdx.value > 0 && end === maxFrameIdx.value);
        
        // 1. 裁剪头部：[start, keepStart)
        if (start < keepStart) {
            let dropEnd = Math.min(end, keepStart);
            
            // 关键修复：如果本来包含第0帧，那么绝对不能删掉 [0, 1]
            // 我们把删除范围限制在 [1, keepStart)
            if (originallyContainsFirstFrame) {
                 // 如果 dropEnd <= 1，说明整个删除请求都在保护区内，直接取消删除
                 if (dropEnd <= 1) {
                     // do nothing
                 } else {
                     // 否则，从 1 开始删
                     callRerunDrop(1, dropEnd);
                     // 此时 start 逻辑上变为了 dropEnd，但我们还需要保留 [0, 1]
                     // 这里为了简单，我们先把 start 移到 dropEnd，
                     // 然后单独把 [0, 1] 加回 newRanges (如果不连续的话)
                     start = dropEnd;
                 }
            } else {
                // 普通情况，照常删除
                if (start < dropEnd) {
                    callRerunDrop(start, dropEnd);
                    start = dropEnd;
                }
            }
        }
        
        // 2. 裁剪尾部：[keepEnd, end)
        if (end > keepEnd) {
            const dropStart = Math.max(start, keepEnd);
            
            // 关键修复：如果本来包含最后一帧，那么绝对不能删掉 [maxFrameIdx-1, maxFrameIdx]
            if (originallyContainsLastFrame) {
                // 保护区是 [maxFrameIdx-1, maxFrameIdx]
                const protectedStart = maxFrameIdx.value - 1;
                
                // 如果 dropStart >= protectedStart，说明删除请求全在保护区内（或之后），直接取消删除
                if (dropStart >= protectedStart) {
                    // do nothing
                } else {
                    // 否则，删到 protectedStart 为止: [dropStart, protectedStart)
                    // 也就是保留了 [protectedStart, end)
                    callRerunDrop(dropStart, protectedStart);
                    end = dropStart; // 逻辑上 end 变为了 dropStart
                }
            } else {
                if (dropStart < end) {
                    callRerunDrop(dropStart, end);
                    end = dropStart;
                }
            }
        }
        
        // 3. 保留有效部分
        if (start < end) {
            newRanges.push([start, end]);
        }
        
        // 4. 补回第0帧 (如果之前因为窗口原因没包含进去)
        if (originallyContainsFirstFrame) {
            // 检查 newRanges 里有没有 [0, 1] 或者覆盖了 0 的区间
            // 由于上面 start 可能被移到了 keepStart (比如 500)，所以 [0, 1] 肯定不在 newRanges 的当前 push 里
            // 我们需要手动加回去
            // 只有当当前的 start > 1 时才需要加，因为如果 start 还是 0 (说明窗口覆盖了头部)，那已经加进去了
            if (start > 1) {
                newRanges.push([0, 1]);
            }
        }

        // 5. 补回最后一帧 (如果之前因为窗口原因没包含进去)
        if (originallyContainsLastFrame) {
             const lastFrameStart = maxFrameIdx.value - 1;
             // 如果当前的 end 被裁剪到了 lastFrameStart 之前 (或者等于)，说明最后一帧被切掉了
             // 我们需要手动加回去 [lastFrameStart, maxFrameIdx]
             if (end <= lastFrameStart) {
                 newRanges.push([lastFrameStart, maxFrameIdx.value]);
             }
        }
    }
    
    // 重新排序，因为补回的首尾帧可能会打乱顺序
    newRanges.sort((a, b) => a[0] - b[0]);
    
    loadedRanges.value = newRanges;
};

const handleLoadRange = async (startIndex, count) => {
  if (!recordingUuid.value) return;
  
  // 越界检查
  if (maxFrameIdx.value > 0 && startIndex >= maxFrameIdx.value) {
      console.log(`[Stream] 请求起始点 ${startIndex} 超出最大帧数 ${maxFrameIdx.value}，停止加载`);
      return;
  }
  
  let endIndex = startIndex + count;
  
  // 截断 EndIndex
  if (maxFrameIdx.value > 0 && endIndex > maxFrameIdx.value) {
      endIndex = maxFrameIdx.value;
      console.log(`[Stream] 截断加载范围至末尾: ${endIndex}`);
  }
  
  // 检查是否与正在进行的请求重叠
  // 简单策略：如果请求完全一致，或者已经被包含在 pending 中，则跳过
  // 为了简化，我们用 "start-end" 字符串作为 key
  const requestKey = `${startIndex}-${endIndex}`;
  if (pendingRanges.value.has(requestKey)) {
      console.log(`[Stream] 请求 ${requestKey} 已在队列中，跳过`);
      return;
  }
  
  pendingRanges.value.add(requestKey);
  
  try {
    console.log(`[Stream] 请求加载范围: [${startIndex}, ${endIndex})`);
    
    const response = await fetch(API_ENDPOINTS.LOAD_RANGE(recordingUuid.value), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        start_index: startIndex, 
        end_index: endIndex 
      })
    });

    if (response.ok) {
      console.log(`[Stream] 范围 [${startIndex}, ${endIndex}) 请求成功`);
      
      // 更新有效帧范围列表 (合并重叠区间)
      const newRange = [startIndex, endIndex];
      const ranges = [...loadedRanges.value, newRange];
      
      // 按起始位置排序
      ranges.sort((a, b) => a[0] - b[0]);
      
      const merged = [];
      if (ranges.length > 0) {
        let current = ranges[0];
        for (let i = 1; i < ranges.length; i++) {
          const next = ranges[i];
          // 如果当前区间与下一个区间重叠或相邻 (例如 [0,100] 和 [100,200])，则合并
          if (current[1] >= next[0]) {
            current[1] = Math.max(current[1], next[1]);
          } else {
            merged.push(current);
            current = next;
          }
        }
        merged.push(current);
      }
      
      loadedRanges.value = merged;
      console.log("[Stream] 当前有效帧范围:", loadedRanges.value);
      
      // 触发缓存清理检查
      handleCacheCleanup();
      
    } else {
      console.warn(`[Stream] 范围加载请求失败: ${response.status}`);
    }
  } catch (e) {
    console.error(`[Stream] 网络错误:`, e);
  } finally {
    pendingRanges.value.delete(requestKey);
  }
};

// --- 流式加载核心逻辑 ---
const onTimeUpdate = (data) => {
    // 这里实现流式加载的触发逻辑
    let currentTime = data.time; // 当前播放时间 (秒)
    let isPlaying = data.is_playing;
    
    // Rerun 的时间可能是秒，也可能是帧索引。
    // 假设这里的 time 对应 frame_idx，如果不确定单位，需要根据 time_str 或业务逻辑转换。
    // 如果 currentTime 是秒，需要根据 FPS 转换为 frame_idx。
    // 这里暂且假设 currentTime 就是 frame_idx (因为我们在后端用 set_time("frame_idx", ...))
    const currentFrameIdx = Math.floor(currentTime);
    
    // 更新全局状态，供清理逻辑使用
    currentPlaybackFrame.value = currentFrameIdx;

    if (isPlaying) {
      handleStreamingPlayback(currentFrameIdx);
    } else {
      handleStreamingJump(currentFrameIdx);
    }
};

// 场景 1: 正常播放中的流式加载
const handleStreamingPlayback = (currentFrameIdx) => {
    // 策略：不再只看最后一个区间，而是关注“当前播放区间”的剩余量
    // if (loadedRanges.value.length === 0) return;
    
    const BUFFER_THRESHOLD = RERUN_CONFIG.STREAMING_BUFFER_THRESHOLD || 50;
    
    // 1. 找到包含当前帧的区间
    let activeRangeIndex = -1;
    for (let i = 0; i < loadedRanges.value.length; i++) {
        const range = loadedRanges.value[i];
        if (currentFrameIdx >= range[0] && currentFrameIdx < range[1]) {
            activeRangeIndex = i;
            break;
        }
    }
    
    if (activeRangeIndex !== -1) {
        // 我们在某个区间内
        const currentRange = loadedRanges.value[activeRangeIndex];
        const currentRangeEnd = currentRange[1];
        
        // 检查是否接近当前区间的末尾
        if (currentRangeEnd - currentFrameIdx < BUFFER_THRESHOLD) {
            // 准备加载的位置是当前区间的末尾
            const loadStart = currentRangeEnd;
            
            // 检查后面是否还有区间 (处理空隙)
            const nextRange = loadedRanges.value[activeRangeIndex + 1];
            let loadCount = RERUN_CONFIG.STREAMING_BATCH_SIZE;
            
            // 检查是否已经在加载这个位置了 (避免重复触发)
            // 我们检查 [loadStart, loadStart + 1] 是否在 pending 队列的某个请求范围内
            // 由于 pending key 是 "start-end"，我们需要遍历 check
            let isAlreadyLoading = false;
            for (const key of pendingRanges.value) {
                const [pStart, pEnd] = key.split('-').map(Number);
                if (loadStart >= pStart && loadStart < pEnd) {
                    isAlreadyLoading = true;
                    break;
                }
            }
            
            if (isAlreadyLoading) {
                // console.log(`[Stream] 位置 ${loadStart} 正在加载中，跳过`);
                return;
            }

            if (nextRange) {
                // 如果后面还有区间，计算空隙大小
                if (loadStart < nextRange[0]) {
                    const gapSize = nextRange[0] - loadStart;
                    // 如果空隙比标准块小，就只加载空隙大小，避免重复加载下一块的数据
                    if (gapSize < loadCount) {
                        loadCount = gapSize;
                    }
                    // 触发加载
                    handleLoadRange(loadStart, loadCount);
                }
                // 如果没有空隙 (loadStart == nextRange[0])，说明数据连续，无需加载，自然播放过去即可
            } else {
                // 后面没有区间了，正常往后加载
                handleLoadRange(loadStart, loadCount);
            }
        }
    } else {
        // 当前帧不在任何已加载区间内
        // 这通常发生在播放指针刚跳出区间，或者处于空隙中
        // 尝试立即加载当前位置
        handleLoadRange(currentFrameIdx, RERUN_CONFIG.STREAMING_BATCH_SIZE);
    }
};

// 场景 2: 用户拖拽/跳转导致的流式加载
const handleStreamingJump = (currentFrameIdx) => {
    // 策略：检查当前帧是否落在任何已加载的区间内
    // 如果不在，说明用户跳到了未加载区域，立即加载
    
    const isCovered = loadedRanges.value.some(range => 
        currentFrameIdx >= range[0] && currentFrameIdx < range[1]
    );
    
    if (!isCovered) {
        console.log(`[Stream] 检测到跳转至未加载区域: ${currentFrameIdx}`);
        // 从跳转点开始加载
        handleLoadRange(currentFrameIdx, RERUN_CONFIG.STREAMING_BATCH_SIZE);
    }
};

// const handleCreateSource = async () => {
//   loading.value = true;
//   try {
//     const response = await fetch(API_ENDPOINTS.CREATE_SOURCE, {
//       method: 'POST',
//       headers: { 'Content-Type': 'application/json' },
//       body: JSON.stringify({ 
//         dataset: selectedDB.value, 
//         collection: selectedDataset.value,
//         alignment_mode: true // 强制开启对齐模式 (保证同一帧数据打包)
//       })
//     });
//     const data = await response.json();
//     if (data.connect_url) {
//       rerunStore.setRerunInfo(data.app_id, data.connect_url, data.recording_uuid);
//     }
    
//     // 保存最大帧数
//     if (data.max_frame_idx) {
//         maxFrameIdx.value = data.max_frame_idx;
//         console.log(`[Stream] 数据集最大帧数: ${maxFrameIdx.value}`);
//     }
    
//   } catch (e) {
//     alert('请求失败，请检查后端');
//   } finally {
//     loading.value = false;
//   }
// };

const handlePlayData = async () => {
  if (!recordingUuid.value) return;
  playing.value = true;
  try {
    const response = await fetch(API_ENDPOINTS.PLAY_DATA(recordingUuid.value), { method: 'POST' });
    if (response.ok) {
        // 数据真正开始流动的反馈
        ElNotification({
          title: '传输中',
          message: '数据流已连接，正在同步 Frame 序列',
          type: 'info',
          position: 'bottom-right',
          duration: 2000
        });
    }
  } catch (e) {
    ElNotification({
      title: '传输失败',
      message: '无法启动后端数据传输，请检查网络或后端状态',
      type: 'error',
      position: 'bottom-right'
    });
  } finally {
    playing.value = false;
  }
};

// const copyToClipboard = async () => {
//   if (!currentSource.value) return;
//   try {
//     if (navigator.clipboard && window.isSecureContext) {
//       await navigator.clipboard.writeText(currentSource.value);
//     } else {
//       const textArea = document.createElement("textarea");
//       textArea.value = currentSource.value;
//       document.body.appendChild(textArea);
//       textArea.select();
//       document.execCommand('copy');
//       document.body.removeChild(textArea);
//     }
//     copied.value = true;
//     setTimeout(() => copied.value = false, 2000);
//   } catch (err) {
//     console.error('Copy failed');
//   }
// };

// 手动触发重新加载
const handleManualReload = () => {
  if (!recordingUuid.value) return;
  
  const startFrame = currentPlaybackFrame.value;
  const count = RERUN_CONFIG.STREAMING_BATCH_SIZE || 100;
  
  console.log(`[Manual Reload] 用户手动触发加载: Start=${startFrame}, Count=${count}`);
  
  handleLoadRange(startFrame, count);
  
  ElNotification({
    title: '重新加载',
    message: `正在尝试重新加载帧 ${startFrame} 及其后续数据...`,
    type: 'info',
    position: 'bottom-left',
    duration: 2000
  });
};
</script>

<style scoped>
#app { 
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
  color: white; 
  background: #1a1a1a; 
  
  /* 关键修改：让 #app 撑满视口高度 */
  height: 100vh; 
  display: flex;
  flex-direction: column;
  overflow: hidden; /* 防止出现双滚动条 */
}

:deep(.rerun-container) {
  flex: 1; /* 占据剩余全部高度 */
}

.controls { 
  display: flex; 
  align-items: center; 
  gap: 15px; 
  background: #252525; padding: 12px 18px; border-radius: 8px; border: 1px solid #333;
}

.input-group { display: flex; align-items: center; gap: 8px; }
.input-group label { font-size: 13px; color: #999; white-space: nowrap; }

/* 保持你喜欢的扁平化 input 样式 */
input { 
  background: #333; 
  color: #fff; 
  border: 1px solid #444; 
  padding: 8px 12px; 
  border-radius: 4px; 
  width: 160px; 
  outline: none; 
  transition: border-color 0.2s;
}
input:focus { border-color: #4CAF50; }
input:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-group { display: flex; gap: 10px; }
.generate-btn, .play-btn { 
  padding: 8px 16px; border: none; border-radius: 4px; 
  cursor: pointer; font-weight: 600; font-size: 13px; transition: 0.2s;
}

.generate-btn { background: #4CAF50; color: white; }
.generate-btn:hover { background: #45a049; }

.generate-btn:disabled { background: #2a2a2a; color: #666; cursor: not-allowed; }

.play-btn { background: #2196F3; color: white; }
.play-btn:hover { background: #1e88e5; }
.play-btn:disabled { background: #2a2a2a; color: #666; cursor: not-allowed; border: 1px solid #444; }

.result-container { margin-left: auto; display: flex; align-items: center; gap: 10px; }
.tag { font-size: 10px; background: rgba(76, 175, 80, 0.1); color: #4CAF50; padding: 2px 8px; border: 1px solid rgba(76, 175, 80, 0.3); border-radius: 4px; }
.result-box { display: flex; align-items: center; gap: 12px; background: #111; padding: 6px 12px; border-radius: 4px; border: 1px solid #333; cursor: pointer; }
.url-text { font-family: 'Fira Code', monospace; font-size: 12px; color: #888; }
.copy-icon { font-size: 12px; }

/* 关键修复：拖拽时禁用 iframe 响应，防止鼠标事件被吞噬 */
.is-dragging :deep(iframe) {
  pointer-events: none;
}
</style>
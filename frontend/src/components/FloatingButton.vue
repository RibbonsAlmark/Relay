<template>
  <div 
    class="floating-controls"
    :style="{ 
      transform: `translate(${
        btnX + (isDocked && dockSide === 'left' ? -25 : (isDocked && dockSide === 'right' ? 25 : 0))
      }px, ${
        btnY + (isDocked && dockSide === 'top' ? -25 : (isDocked && dockSide === 'bottom' ? 25 : 0))
      }px)`,
      opacity: isDocked ? 0.5 : 1
    }"
    @mousedown="startDrag"
    @mouseenter="handleMouseEnter"
    @mouseleave="handleMouseLeave"
  >
    <button 
      class="reload-btn" 
      @click="handleClick" 
      title="重新加载当前位置数据"
    >
      <!-- 使用 SVG 图标代替 Emoji -->
      <svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
        <polyline points="23 4 23 10 17 10"></polyline>
        <polyline points="1 20 1 14 7 14"></polyline>
        <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path>
      </svg>
    </button>
    
    <!-- 悬浮提示文字 -->
    <span class="btn-tooltip">重载后续100帧</span>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  onReload: {
    type: Function,
    required: true
  }
});

// --- 悬浮球拖拽逻辑 ---
const btnX = ref(20);
const btnY = ref(window.innerHeight - 80); // 初始位置在左下角附近
const isDragging = ref(false);
const isDocked = ref(false);
const dockSide = ref(''); // 'left', 'right', 'top', 'bottom'
let dragStartX = 0;
let dragStartY = 0;
let initialBtnX = 0;
let initialBtnY = 0;
let hasMoved = false; // 用于区分点击和拖拽

// 初始化位置：右下角
onMounted(() => {
  const screenWidth = window.innerWidth;
  const screenHeight = window.innerHeight;
  btnX.value = screenWidth - 100;
  btnY.value = screenHeight - 100;
  
  window.addEventListener('mousemove', onDrag);
  window.addEventListener('mouseup', endDrag);
});

onUnmounted(() => {
  window.removeEventListener('mousemove', onDrag);
  window.removeEventListener('mouseup', endDrag);
});

const startDrag = (e) => {
  e.preventDefault(); // 防止选中文本等默认行为
  isDragging.value = true;
  // 通知父组件开始拖拽（可选，如果父组件需要知道）
  emit('drag-start');
  
  hasMoved = false;
  dragStartX = e.clientX;
  dragStartY = e.clientY;
  initialBtnX = btnX.value;
  initialBtnY = btnY.value;
  isDocked.value = false; // 拖动开始时取消停靠状态
  dockSide.value = '';
};

const onDrag = (e) => {
  if (!isDragging.value) return;
  
  const dx = e.clientX - dragStartX;
  const dy = e.clientY - dragStartY;
  
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
    hasMoved = true;
  }
  
  // 限制在屏幕范围内
  let newX = initialBtnX + dx;
  let newY = initialBtnY + dy;
  
  const maxX = window.innerWidth - 50;
  const maxY = window.innerHeight - 50;
  
  newX = Math.max(0, Math.min(newX, maxX));
  newY = Math.max(0, Math.min(newY, maxY));
  
  btnX.value = newX;
  btnY.value = newY;
};

const endDrag = () => {
  if (!isDragging.value) return;
  
  isDragging.value = false;
  emit('drag-end'); // 通知父组件拖拽结束
  
  // 自动吸附逻辑
  if (hasMoved) {
    const screenWidth = window.innerWidth;
    const screenHeight = window.innerHeight;
    const threshold = 10; // 距离边缘多少像素触发吸附
    
    const distLeft = btnX.value;
    const distRight = screenWidth - 50 - btnX.value;
    const distTop = btnY.value;
    const distBottom = screenHeight - 50 - btnY.value;
    
    const minDist = Math.min(distLeft, distRight, distTop, distBottom);
    
    if (minDist < threshold) {
      isDocked.value = true;
      if (minDist === distLeft) {
        btnX.value = 0;
        dockSide.value = 'left';
      } else if (minDist === distRight) {
        btnX.value = screenWidth - 50;
        dockSide.value = 'right';
      } else if (minDist === distTop) {
        btnY.value = 0;
        dockSide.value = 'top';
      } else if (minDist === distBottom) {
        btnY.value = screenHeight - 50;
        dockSide.value = 'bottom';
      }
    }
  }
};

const handleMouseEnter = () => {
  if (isDocked.value) {
    isDocked.value = false; // 鼠标移入时取消透明度和偏移
    // 注意：这里不清除 dockSide，以便移出时能恢复原来的停靠位置
  }
};

const handleMouseLeave = () => {
  // 如果之前是停靠状态，移出时恢复停靠（透明+偏移）
  // 只有当位置确实还在边缘时才恢复
  const screenWidth = window.innerWidth;
  const screenHeight = window.innerHeight;
  
  const isAtEdge = 
    (dockSide.value === 'left' && btnX.value <= 0) ||
    (dockSide.value === 'right' && btnX.value >= screenWidth - 60) ||
    (dockSide.value === 'top' && btnY.value <= 0) ||
    (dockSide.value === 'bottom' && btnY.value >= screenHeight - 60);

  if (isAtEdge) {
    isDocked.value = true;
  } else {
      // 如果位置已经变了（比如被拖走了），重置 dockSide
      dockSide.value = '';
  }
};

const handleClick = () => {
  if (!hasMoved) {
    props.onReload();
  }
};

const emit = defineEmits(['drag-start', 'drag-end']);
</script>

<style scoped>
.floating-controls {
  position: absolute;
  z-index: 1000;
  top: 0;
  left: 0;
  transition: opacity 0.3s ease, transform 0.1s linear; /* transform 用 linear 避免拖拽延迟感 */
  touch-action: none; /* 防止触摸屏滚动 */
}

.reload-btn {
  width: 50px;
  height: 50px;
  border-radius: 50%;
  border: none;
  background-color: rgba(60, 60, 60, 0.7); /* 透明灰 */
  color: rgba(255, 255, 255, 0.9);
  font-size: 24px;
  cursor: grab;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  user-select: none;
  backdrop-filter: blur(4px); /* 增加毛玻璃效果 */
}

.reload-btn:active {
  cursor: grabbing;
  transform: scale(0.95);
}

.reload-btn:hover {
  background-color: rgba(80, 80, 80, 0.9); /* hover 时稍微变亮且不透明度增加 */
  transform: scale(1.05);
}

/* 提示文字样式 */
.btn-tooltip {
  position: absolute;
  top: -30px; /* 位于按钮上方 */
  left: 50%;
  transform: translateX(-50%);
  background-color: rgba(0, 0, 0, 0.8);
  color: white;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  white-space: nowrap;
  pointer-events: none; /* 防止遮挡鼠标事件 */
  opacity: 0;
  transition: opacity 0.2s ease, top 0.2s ease;
}

/* 鼠标移入整个控件区域时显示提示 */
.floating-controls:hover .btn-tooltip {
  opacity: 1;
  top: -35px; /* 稍微上浮一点的动画效果 */
}
</style>
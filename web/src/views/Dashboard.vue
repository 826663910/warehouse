<template>
  <div class="page-container" v-loading="loading">
    <!-- 欢迎条 -->
    <div class="welcome-card">
      <div>
        <h2>你好，{{ userStore.username }}</h2>
        <p>{{ todayText }}，这里是今天的库存概况，祝工作顺利！</p>
      </div>
      <div class="welcome-right">
        <el-button type="primary" round :icon="Plus" @click="$router.push('/orders/edit?type=1')">快速入库</el-button>
        <el-button type="warning" round :icon="Minus" @click="$router.push('/orders/edit?type=2')">快速出库</el-button>
      </div>
    </div>

    <!-- 统计卡片 -->
    <div class="stat-grid">
      <div v-for="s in stats" :key="s.label" class="stat-card" :style="{ '--c': s.color }">
        <div class="stat-icon">
          <el-icon :size="24"><component :is="s.icon" /></el-icon>
        </div>
        <div class="stat-info">
          <div class="stat-value">{{ s.value }}</div>
          <div class="stat-label">{{ s.label }}</div>
        </div>
      </div>
    </div>

    <div class="dash-row">
      <!-- 出入库趋势 -->
      <div class="chart-card">
        <div class="card-head">
          <span class="card-title">近 7 日出入库趋势</span>
        </div>
        <div ref="chartRef" class="chart-box"></div>
      </div>

      <!-- 低库存预警 -->
      <div class="panel-card">
        <div class="card-head">
          <span class="card-title">低库存预警</span>
          <el-tag v-if="warningList.length" type="danger" effect="light" size="small">
            {{ warningList.length }} 项
          </el-tag>
        </div>
        <div v-if="!warningList.length" class="empty-box">
          <el-icon :size="34" color="#c0c8d8"><CircleCheck /></el-icon>
          <p>库存状态良好，暂无预警</p>
        </div>
        <div v-else class="warning-list">
          <div v-for="w in warningList" :key="w.id" class="warning-item">
            <div class="w-info">
              <div class="w-name">{{ w.name }}<span v-if="w.type" class="w-type">{{ w.type }}</span></div>
              <div class="w-sub">
                预警值 {{ w.warning }} {{ w.unit }} · 编码 {{ w.code }}
              </div>
            </div>
            <div class="w-stock">
              <span class="w-num">{{ w.stock }}</span>
              <span class="w-unit">{{ w.unit }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 最近流水 -->
    <div class="page-card mt-card">
      <div class="card-head">
        <span class="card-title">最近出入库记录</span>
        <el-button link type="primary" @click="$router.push('/record')">查看全部 →</el-button>
      </div>
      <el-table :data="recentRecords" size="small">
        <el-table-column label="时间" width="160">
          <template #default="{ row }">{{ fmtDateTime(row.transaction_date) }}</template>
        </el-table-column>
        <el-table-column prop="name" label="物料" min-width="140" />
        <el-table-column prop="type" label="型号" width="120">
          <template #default="{ row }">{{ row.type || '—' }}</template>
        </el-table-column>
        <el-table-column label="单据类型" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="ORDER_TYPES[row.order_type]?.tag || 'info'" effect="light" size="small">
              {{ ORDER_TYPES[row.order_type]?.label || `未知(${row.order_type})` }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="变更" width="90" align="center">
          <template #default="{ row }">
            <span :class="`change-num change-${row.order_type}`">
              {{ row.change_quantity > 0 ? '+' : '' }}{{ row.change_quantity }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="结存" width="90" align="center">
          <template #default="{ row }">{{ row.after_quantity }} {{ row.unit }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import * as echarts from 'echarts'
import { Plus, Minus } from '@element-plus/icons-vue'
import { userStore } from '@/store/user'
import { listInventory, listSupplier, listCategory, listRecords } from '@/api'
import { fmtDate, fmtDateTime, ORDER_TYPES } from '@/utils/format'

const loading = ref(false)
const chartRef = ref(null)
let chart = null

const inventoryList = ref([])
const supplierList = ref([])
const categoryList = ref([])
const recordList = ref([])

const todayText = computed(() => {
  const d = new Date()
  const week = ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]
  return `${fmtDate(d)} 星期${week}`
})

const totalStock = computed(() => inventoryList.value.reduce((s, i) => s + (i.stock || 0), 0))

const warningList = computed(() =>
  inventoryList.value
    .filter((i) => i.warning != null && i.warning > 0 && i.stock != null && i.stock <= i.warning)
    .slice(0, 8)
)

const stats = computed(() => [
  { label: '物料种类', value: inventoryList.value.length.toLocaleString(), icon: 'Box', color: '#2f6bff' },
  { label: '库存总量', value: totalStock.value.toLocaleString(), icon: 'Coin', color: '#f2a93b' },
  { label: '供应商数量', value: supplierList.value.length.toLocaleString(), icon: 'OfficeBuilding', color: '#10b981' },
  { label: '物料分类', value: categoryList.value.length.toLocaleString(), icon: 'FolderOpened', color: '#8b5cf6' }
])

const recentRecords = computed(() =>
  [...recordList.value].sort((a, b) => new Date(b.transaction_date) - new Date(a.transaction_date)).slice(0, 8)
)

function buildTrendData(records) {
  // 生成近7天日期序列（本地）
  const days = []
  for (let i = 6; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    days.push(fmtDate(d))
  }
  // 按 order_type 拆 4 类，每天累加；退货/报废都是减库存，取绝对值参与对比
  const map = { 1: {}, 2: {}, 3: {}, 4: {} }
  days.forEach((d) => {
    map[1][d] = 0
    map[2][d] = 0
    map[3][d] = 0
    map[4][d] = 0
  })
  records.forEach((r) => {
    const key = String(r.transaction_date).slice(0, 10)
    if (!(key in map[1])) return
    const t = Number(r.order_type)
    if (!map[t]) return
    const v = Number(r.change_quantity) || 0
    // 入库（1）原样累加；出库/退货/报废（2/3/4）展示总量趋势，取绝对值
    map[t][key] += Math.abs(v)
  })
  return {
    days,
    inData: days.map((d) => map[1][d]),
    outData: days.map((d) => map[2][d]),
    retData: days.map((d) => map[3][d]),
    scrData: days.map((d) => map[4][d])
  }
}

function renderChart() {
  if (!chartRef.value) return
  const { days, inData, outData, retData, scrData } = buildTrendData(recordList.value)
  chart = echarts.init(chartRef.value)
  chart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['入库', '出库', '退货', '报废'], right: 8, top: 0 },
    grid: { left: 10, right: 14, top: 36, bottom: 4, containLabel: true },
    xAxis: {
      type: 'category',
      data: days,
      axisLine: { lineStyle: { color: '#e3e8f0' } },
      axisLabel: { color: '#8a94a6' }
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { type: 'dashed', color: '#eef1f7' } },
      axisLabel: { color: '#8a94a6' }
    },
    series: [
      {
        name: '入库',
        type: 'bar',
        data: inData,
        barWidth: 8,
        itemStyle: { borderRadius: [4, 4, 0, 0], color: '#2f6bff' }
      },
      {
        name: '出库',
        type: 'bar',
        data: outData,
        barWidth: 8,
        itemStyle: { borderRadius: [4, 4, 0, 0], color: '#f56c6c' }
      },
      {
        name: '退货',
        type: 'bar',
        data: retData,
        barWidth: 8,
        itemStyle: { borderRadius: [4, 4, 0, 0], color: '#e6a23c' }
      },
      {
        name: '报废',
        type: 'bar',
        data: scrData,
        barWidth: 8,
        itemStyle: { borderRadius: [4, 4, 0, 0], color: '#909399' }
      }
    ]
  })
}

function handleResize() {
  chart && chart.resize()
}

async function load() {
  loading.value = true
  try {
    const [inv, sup, cat, rec] = await Promise.all([
      // 仪表盘要全量做统计，取大分页；接口返回 { total, items }
      listInventory({ limit: 10000, offset: 0 }),
      listSupplier(),
      listCategory(),
      listRecords({ limit: 10000, offset: 0 })
    ])
    inventoryList.value = inv.items || []
    supplierList.value = sup
    categoryList.value = cat
    recordList.value = rec.items || []
    await nextTick()
    renderChart()
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart && chart.dispose()
})
</script>

<style scoped>
.welcome-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: linear-gradient(120deg, #1b2a52, #2f4a9e 60%, #2f6bff);
  border-radius: 12px;
  padding: 22px 26px;
  color: #fff;
  margin-bottom: 16px;
  box-shadow: 0 8px 24px rgba(47, 107, 255, 0.25);
}
.welcome-card h2 {
  margin: 0;
  font-size: 20px;
}
.welcome-card p {
  margin: 6px 0 0;
  opacity: 0.8;
  font-size: 13px;
}
.welcome-right :deep(.el-button.is-round) {
  font-weight: 500;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 16px;
}
.stat-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #fff;
  border-radius: 12px;
  padding: 18px 20px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
  border-left: 4px solid var(--c);
}
.stat-icon {
  width: 50px;
  height: 50px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--c);
  background: color-mix(in srgb, var(--c) 12%, #fff);
}
.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #1f2d3d;
  line-height: 1.2;
}
.stat-label {
  font-size: 13px;
  color: #8a94a6;
  margin-top: 2px;
}

.dash-row {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: 14px;
  margin-bottom: 14px;
}
.chart-card,
.panel-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 1px 4px rgba(15, 23, 42, 0.06);
}
.chart-box {
  height: 300px;
}
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.card-title {
  font-size: 15px;
  font-weight: 600;
  color: #223049;
}
.mt-card {
  padding: 16px;
}

.warning-list {
  max-height: 260px;
  overflow: auto;
}
.warning-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 9px 6px;
  border-bottom: 1px dashed #f0f2f7;
}
.warning-item:last-child {
  border-bottom: none;
}
.w-name {
  font-weight: 600;
  font-size: 13px;
  color: #2a3348;
}
.w-type {
  margin-left: 6px;
  font-weight: 400;
  font-size: 12px;
  color: #a0a8b8;
}
.w-sub {
  font-size: 12px;
  color: #a0a8b8;
  margin-top: 2px;
}
.w-num {
  font-size: 18px;
  font-weight: 800;
  color: #f56c6c;
}
.w-unit {
  font-size: 12px;
  color: #a0a8b8;
}
.empty-box {
  text-align: center;
  color: #c0c8d8;
  padding: 46px 0;
}
.empty-box p {
  margin: 10px 0 0;
  font-size: 13px;
}

/* 变更数量按 order_type 配色，与「单据类型」tag 一致 */
.change-num {
  font-weight: 700;
}
.change-1 { color: #2f9e44; }   /* 入库 */
.change-2 { color: #f56c6c; }   /* 出库 */
.change-3 { color: #e6a23c; }   /* 退货 */
.change-4 { color: #909399; }   /* 报废 */

@media (max-width: 1100px) {
  .stat-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .dash-row {
    grid-template-columns: 1fr;
  }
}
</style>

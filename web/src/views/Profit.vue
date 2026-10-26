<template>
  <div class="page-container">
    <div class="page-card">
      <!-- 筛选栏：只按业务日期范围过滤（后端按 stock_orders.transaction_date 筛） -->
      <div class="toolbar">
        <el-date-picker
          v-model="query.range"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
          @change="load"
        />
        <el-button type="primary" :icon="Search" @click="load">查询</el-button>
        <el-button :icon="RefreshLeft" @click="handleReset">重置</el-button>
        <div class="spacer"></div>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <!-- 口径说明：这三条决定数字对不对，必须让用户看见 -->
      <div class="note">
        <span class="note-title">统计口径</span>
        只统计<b>已审核的出库单</b>；成本取自<b>出库审核那一刻的成本快照</b>（不是当前库存均价），
        所以历史月份的毛利不会随之后进货而变动；退货与报废不计入收入。
      </div>

      <!-- 汇总卡片：整个筛选区间的合计 -->
      <div class="cards">
        <div class="card">
          <div class="card-label">总收入</div>
          <div class="card-value">¥ {{ fmtMoney(total.revenue) }}</div>
        </div>
        <div class="card">
          <div class="card-label">总成本</div>
          <div class="card-value">¥ {{ fmtMoney(total.cost) }}</div>
        </div>
        <div class="card" :class="profitClass(total.profit)">
          <div class="card-label">毛利</div>
          <div class="card-value">¥ {{ fmtMoney(total.profit) }}</div>
        </div>
        <div class="card" :class="profitClass(total.profit)">
          <div class="card-label">毛利率</div>
          <div class="card-value">{{ fmtRate(total.profit_rate) }}</div>
        </div>
      </div>

      <!-- 趋势图：柱=收入/成本（左轴金额），折线=毛利率（右轴 %） -->
      <div v-if="items.length" ref="chartRef" class="chart"></div>
      <div v-else-if="!loading" class="empty-tip">该时间范围内没有已审核的出库单</div>

      <!-- 按月明细 -->
      <el-table v-if="items.length" v-loading="loading" :data="items" stripe>
        <el-table-column label="月份" width="110" align="center">
          <template #default="{ row }"><span class="row-month">{{ row.month }}</span></template>
        </el-table-column>
        <el-table-column label="收入" align="right">
          <template #default="{ row }">¥ {{ fmtMoney(row.revenue) }}</template>
        </el-table-column>
        <el-table-column label="成本" align="right">
          <template #default="{ row }">¥ {{ fmtMoney(row.cost) }}</template>
        </el-table-column>
        <el-table-column label="毛利" align="right">
          <template #default="{ row }">
            <span :class="profitTextClass(row.profit)">¥ {{ fmtMoney(row.profit) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="毛利率" align="right">
          <template #default="{ row }">
            <span :class="profitTextClass(row.profit)">{{ fmtRate(row.profit_rate) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { nextTick, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { Refresh, RefreshLeft, Search } from '@element-plus/icons-vue'
import { getProfitTrend } from '@/api'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const items = ref([])                 // 按月明细
const total = ref({ revenue: 0, cost: 0, profit: 0, profit_rate: null })

// 筛选条件从 URL 还原：刷新 / 分享链接能回到同一个视图
const query = reactive({
  range: route.query.start_day && route.query.end_day
    ? [String(route.query.start_day), String(route.query.end_day)]
    : []
})

const chartRef = ref(null)
let chart = null

// 把日期范围写回 URL；用 replace 避免后退时要点很多次
function syncQuery() {
  const [start_day, end_day] = query.range || []
  const q = {}
  if (start_day) q.start_day = start_day
  if (end_day) q.end_day = end_day
  const unchanged =
    String(route.query.start_day ?? '') === String(q.start_day ?? '') &&
    String(route.query.end_day ?? '') === String(q.end_day ?? '')
  if (!unchanged) router.replace({ path: '/profit', query: q })
}

async function load() {
  syncQuery()
  loading.value = true
  try {
    const [start_day, end_day] = query.range || []
    // 不传日期 = 全部时间；后端要求 start_day / end_day 成对，所以只取都有值的时候传
    const res = await getProfitTrend(
      start_day && end_day ? { start_day, end_day } : {}
    )
    items.value = res.items || []
    total.value = res.total || { revenue: 0, cost: 0, profit: 0, profit_rate: null }
    await nextTick()
    renderChart()
  } finally {
    loading.value = false
  }
}

function handleReset() {
  query.range = []
  load()
}

function renderChart() {
  if (!chartRef.value) return
  // 重新 init 前必须 dispose，否则 echarts 会警告"该 dom 上已有实例"
  if (chart) chart.dispose()
  chart = echarts.init(chartRef.value)

  const months = items.value.map((r) => r.month)
  // 右轴配置抽成函数：把 show 参数提出来，好让「毛利率」图例关掉时右轴一起收起。
  // 不做这一步的话，隐藏毛利率后右轴还挂在图上，点击看上去就像"没反应"。
  const yAxis = (showRate) => [
    {
      type: 'value',
      name: '金额',
      nameTextStyle: { color: '#8a94a6', fontSize: 11 },
      splitLine: { lineStyle: { type: 'dashed', color: '#eef1f7' } },
      axisLabel: { color: '#8a94a6' }
    },
    {
      type: 'value',
      name: '毛利率',
      show: showRate,        // ← 跟着图例联动
      nameTextStyle: { color: '#8a94a6', fontSize: 11 },
      axisLabel: { color: '#8a94a6', formatter: '{value}%' },
      splitLine: { show: false }
    }
  ]

  chart.setOption({
    tooltip: {
      trigger: 'axis',
      // 自定义 formatter：金额加 ¥，毛利率加 %（右轴的值要单独格式化）
      formatter: (params) => {
        const lines = params.map((p) => {
          const v = p.value === null || p.value === undefined ? '—' : p.value
          const text = p.seriesName === '毛利率' ? `${Number(v).toFixed(1)}%` : `¥ ${fmtMoney(v)}`
          return `${p.marker}${p.seriesName}：${text}`
        })
        return [params[0].axisValue, ...lines].join('<br/>')
      }
    },
    legend: { data: ['收入', '成本', '毛利率'], right: 8, top: 0 },
    grid: { left: 10, right: 14, top: 36, bottom: 4, containLabel: true },
    xAxis: {
      type: 'category',
      data: months,
      axisLine: { lineStyle: { color: '#e3e8f0' } },
      axisLabel: { color: '#8a94a6' }
    },
    yAxis: yAxis(true),
    series: [
      {
        name: '收入',
        type: 'bar',
        data: items.value.map((r) => r.revenue),
        barWidth: 14,
        itemStyle: { borderRadius: [4, 4, 0, 0], color: '#2f6bff' }
      },
      {
        name: '成本',
        type: 'bar',
        data: items.value.map((r) => r.cost),
        barWidth: 14,
        itemStyle: { borderRadius: [4, 4, 0, 0], color: '#e6a23c' }
      },
      {
        name: '毛利率',
        type: 'line',
        yAxisIndex: 1,     // 走右轴
        data: items.value.map((r) => r.profit_rate),
        smooth: true,
        symbolSize: 6,
        lineStyle: { width: 2, color: '#2f9e44' },
        itemStyle: { color: '#2f9e44' },
        // 收入为 0 时后端给 null，connectNulls=false 让折线在此断开而不是画成 0
        connectNulls: false
      }
    ]
  })

  // 图例点击 = 显示/隐藏对应系列（echarts 默认行为）。
  // 这里额外把右轴一起收放，让"点毛利率"有明确视觉反馈。
  chart.on('legendselectchanged', (p) => {
    chart.setOption({ yAxis: yAxis(p.selected['毛利率'] !== false) })
  })
}

function handleResize() {
  chart && chart.resize()
}

function fmtMoney(n) {
  return Number(n || 0).toLocaleString('zh-CN', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  })
}

function fmtRate(n) {
  return n === null || n === undefined ? '—' : `${Number(n).toFixed(1)}%`
}

// 盈利绿 / 亏损红 / 零灰
function profitClass(v) {
  if (v > 0) return 'is-profit'
  if (v < 0) return 'is-loss'
  return ''
}
function profitTextClass(v) {
  return v > 0 ? 'num-profit' : v < 0 ? 'num-loss' : 'num-zero'
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
.toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.spacer {
  flex: 1;
}
.note {
  margin: 14px 0;
  padding: 10px 14px;
  border-radius: 8px;
  background: #f6f8fb;
  border: 1px solid #e8ecf3;
  font-size: 12px;
  line-height: 1.6;
  color: #8a94a6;
}
.note-title {
  display: inline-block;
  margin-right: 6px;
  font-weight: 600;
  color: #2a3348;
}
.cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.card {
  flex: 1 1 180px;
  padding: 14px 16px;
  border-radius: 8px;
  background: #f6f8fb;
  border: 1px solid #e8ecf3;
}
.card-label {
  font-size: 12px;
  color: #8a94a6;
  margin-bottom: 4px;
}
.card-value {
  font-size: 22px;
  font-weight: 700;
  color: #2a3348;
}
/* 毛利 / 毛利率两张卡片跟着盈亏变色 */
.card.is-profit {
  background: #f0f9eb;
  border-color: #d9ecce;
}
.card.is-profit .card-value {
  color: #2f9e44;
}
.card.is-loss {
  background: #fef0f0;
  border-color: #f7d4d4;
}
.card.is-loss .card-value {
  color: #f56c6c;
}
.chart {
  width: 100%;
  height: 320px;
  margin-bottom: 16px;
}
.empty-tip {
  padding: 40px 0;
  text-align: center;
  font-size: 13px;
  color: #b0b7c3;
  border: 1px dashed #e4e8f0;
  border-radius: 8px;
  margin-bottom: 16px;
}
.row-month {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  color: #2a3348;
}
.num-profit {
  font-weight: 700;
  color: #2f9e44;
}
.num-loss {
  font-weight: 700;
  color: #f56c6c;
}
.num-zero {
  font-weight: 700;
  color: #909399;
}
</style>

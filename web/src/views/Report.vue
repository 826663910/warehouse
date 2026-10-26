<template>
  <div class="page-container">
    <div class="page-card">
      <!-- 筛选栏 -->
      <div class="toolbar">
        <el-input
          v-model="query.keyword"
          placeholder="物料名称 / 型号"
          :prefix-icon="Search"
          clearable
          style="width: 200px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-select
          v-model="query.direction"
          placeholder="统计方向"
          clearable
          style="width: 140px"
          @change="handleSearch"
        >
          <el-option label="只统计入库" :value="1" />
          <el-option label="只统计出库" :value="2" />
        </el-select>
        <el-date-picker
          v-model="query.range"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
          style="width: 260px"
          @change="handleSearch"
        />
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button :icon="RefreshLeft" @click="handleReset">重置</el-button>
        <div class="spacer"></div>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <!-- 汇总区：左边「流水笔数」卡片，右边「分类汇总」面板，两者并排同一排。
           分类汇总必须按【单位赛道】分开——斤 + 米 + 个 加不出有意义的数；
           同一赛道内物料共享同一个基础单位，才能统一换算到该赛道目标单位（公斤/米/升/个） -->
      <div v-if="summary" class="summary-block">
        <div class="summary-card summary-card-count">
          <div class="summary-label">流水笔数</div>
          <div class="summary-value">{{ summary.tx_count }}</div>
          <div class="summary-sub">{{ summary.item_count }} 个物料</div>
        </div>

        <div v-if="catRows.length" class="cat-panel">
          <div class="cat-head">
            <span class="cat-title">分类汇总</span>
            <span class="cat-tip">按单位类型分行，各行单位不同，不可跨行相加</span>
          </div>
          <el-table :data="catRows" size="small" stripe>
            <el-table-column label="单位类型" width="100" align="center">
              <template #default="{ row }">{{ CATEGORY_LABELS[row.category] || row.category || '自定义' }}</template>
            </el-table-column>
            <el-table-column label="单位" width="70" align="center">
              <template #default="{ row }">{{ row.unit || '—' }}</template>
            </el-table-column>
            <el-table-column label="物料数" width="80" align="center">
              <template #default="{ row }">{{ row.item_count }}</template>
            </el-table-column>
            <el-table-column label="入库" align="right">
              <template #default="{ row }"><span class="num-in">+{{ fmtQty(row.total_in) }}</span></template>
            </el-table-column>
            <el-table-column label="出库" align="right">
              <template #default="{ row }"><span class="num-out">{{ fmtQty(row.total_out) }}</span></template>
            </el-table-column>
            <el-table-column label="退货" align="right">
              <template #default="{ row }"><span class="num-ret">{{ fmtQty(row.total_ret) }}</span></template>
            </el-table-column>
            <el-table-column label="报废" align="right">
              <template #default="{ row }"><span class="num-scr">{{ fmtQty(row.total_scr) }}</span></template>
            </el-table-column>
            <el-table-column label="净变化" align="right">
              <template #default="{ row }">
                <span :class="netClass(row.net_change)">
                  {{ row.net_change > 0 ? '+' : '' }}{{ fmtQty(row.net_change) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- 报表表格：每行 = 一个物料在筛选范围内的汇总 -->
      <el-table v-loading="loading" :data="list" stripe>
        <el-table-column label="编码" width="90" align="center">
          <template #default="{ row }"><span class="row-code">{{ row.code }}</span></template>
        </el-table-column>
        <el-table-column label="物料名称" min-width="200">
          <template #default="{ row }">
            <div class="item-name">{{ row.name || '—' }}</div>
            <div v-if="row.type" class="item-type">{{ row.type }}</div>
          </template>
        </el-table-column>
        <el-table-column label="笔数" width="80" align="center">
          <template #default="{ row }">{{ row.tx_count }}</template>
        </el-table-column>
        <!-- 总量用 *_display（后端已按【本行物料的显示单位】换算）；缺失时退回基础单位原值 -->
        <el-table-column label="入库总量" width="120" align="right">
          <template #default="{ row }">
            <span class="num-in">+{{ fmtQty(disp(row, 'total_in')) }}</span>
            <span class="unit-text">{{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column label="出库总量" width="120" align="right">
          <template #default="{ row }">
            <span class="num-out">{{ fmtQty(disp(row, 'total_out')) }}</span>
            <span class="unit-text">{{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column label="退货总量" width="110" align="right">
          <template #default="{ row }">
            <span class="num-ret">{{ fmtQty(disp(row, 'total_ret')) }}</span>
            <span class="unit-text">{{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column label="报废总量" width="110" align="right">
          <template #default="{ row }">
            <span class="num-scr">{{ fmtQty(disp(row, 'total_scr')) }}</span>
            <span class="unit-text">{{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column label="净变化" width="120" align="right">
          <template #default="{ row }">
            <span :class="netClass(disp(row, 'net_change'))">
              {{ disp(row, 'net_change') > 0 ? '+' : '' }}{{ fmtQty(disp(row, 'net_change')) }}
            </span>
            <span class="unit-text">{{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column label="最近交易" width="170">
          <template #default="{ row }">{{ fmtDateTimeFull(row.last_date) }}</template>
        </el-table-column>
      </el-table>

      <div class="table-footer">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next, jumper"
          background
          @change="load"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, RefreshLeft, Search } from '@element-plus/icons-vue'
import { getReport } from '@/api'
import { fmtDateTimeFull } from '@/utils/format'

const PAGE_SIZES = [10, 20, 50]
const DEFAULT_PAGE_SIZE = 20

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const list = ref([])        // 当前页数据（后端已按物料聚合、分页）
const total = ref(0)        // 物料数（后端 count distinct inventory_id）
const summary = ref(null)   // 筛选范围全局汇总（后端按赛道分组聚合，与分页无关）

// 分类汇总行：每行一个单位赛道（重量 / 长度 / 体积 / 数量 / 自定义）
const catRows = computed(() => summary.value?.by_category ?? [])

// 单位赛道中文名（后端存的是 weight / length / volume / count / other）
const CATEGORY_LABELS = {
  weight: '重量',
  length: '长度',
  volume: '体积',
  count: '数量',
  other: '自定义'
}

// 筛选条件与分页都从 URL 还原：刷新、后退、分享链接都能回到同一个列表视图
function readFilters() {
  const q = route.query
  const num = (v) => {
    if (v === undefined || v === '') return null
    const n = Number(v)
    return Number.isNaN(n) ? null : n
  }
  // direction: 1=只统计入库 2=只统计出库，与后端约定一致
  return {
    keyword: typeof q.keyword === 'string' ? q.keyword : '',
    direction: num(q.direction),
    range: q.start_day && q.end_day ? [String(q.start_day), String(q.end_day)] : []
  }
}

const query = reactive(readFilters())
const page = ref(Math.max(1, Number(route.query.page) || 1))
const pageSize = ref(
  PAGE_SIZES.includes(Number(route.query.pageSize)) ? Number(route.query.pageSize) : DEFAULT_PAGE_SIZE
)

// 把当前筛选/分页写回 URL；用 replace 是为了不新增历史记录，否则后退要点很多次
function syncQuery() {
  const q = {}
  const keyword = query.keyword.trim()
  const [start_day, end_day] = query.range || []
  if (keyword) q.keyword = keyword
  if (query.direction !== null && query.direction !== undefined) q.direction = String(query.direction)
  if (start_day) q.start_day = start_day
  if (end_day) q.end_day = end_day
  if (page.value > 1) q.page = String(page.value)
  if (pageSize.value !== DEFAULT_PAGE_SIZE) q.pageSize = String(pageSize.value)

  const keys = ['keyword', 'direction', 'start_day', 'end_day', 'page', 'pageSize']
  const unchanged = keys.every((k) => String(route.query[k] ?? '') === String(q[k] ?? ''))
  if (!unchanged) router.replace({ path: '/report', query: q })
}

async function load() {
  syncQuery()
  loading.value = true
  try {
    // 过滤与聚合全部由后端完成，返回 { total: 物料数, items: 每物料一行 }
    const [start_day, end_day] = query.range || []
    const res = await getReport({
      start_day: start_day || undefined,
      end_day: end_day || undefined,
      keyword: query.keyword.trim() || undefined,
      direction: query.direction ?? undefined,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value
    })
    list.value = res.items || []
    total.value = res.total || 0
    summary.value = res.summary || null
  } finally {
    loading.value = false
  }
}

function handleSearch() {
  page.value = 1
  load()
}

function handleReset() {
  query.keyword = ''
  query.direction = null
  query.range = []
  page.value = 1
  load()
}

// 净变化配色：正绿、负红、零灰
function netClass(v) {
  if (v > 0) return 'num-in'
  if (v < 0) return 'num-out'
  return 'num-zero'
}

// 显示用总量：优先后端换算好的 *_display（本行物料的显示单位），缺失时退回基础单位原值
function disp(row, key) {
  return Number(row[`${key}_display`] ?? row[key]) || 0
}

// 去掉浮点尾巴（2.5000000001 → 2.5，40 → 40）
function fmtQty(n) {
  return Number(Number(n ?? 0).toFixed(3))
}

onMounted(load)
</script>

<style scoped>
/* 汇总区：「流水笔数」卡片 + 「分类汇总」面板并排同一排 */
.summary-block {
  display: flex;
  gap: 12px;
  align-items: stretch;
  margin-bottom: 14px;
}
/* 分类汇总面板：占满剩余宽度 */
.cat-panel {
  flex: 1;
  min-width: 0;   /* 关键：不让 el-table 的最小内容宽度撑破 flex 容器 */
  padding: 12px 14px;
  border-radius: 8px;
  background: #f6f8fb;
  border: 1px solid #e8ecf3;
}
.cat-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
  margin-bottom: 8px;
}
.cat-title {
  font-weight: 600;
  font-size: 14px;
  color: #2a3348;
}
.cat-tip {
  font-size: 12px;
  color: #a0a8b8;
}
.summary-card {
  flex: 1;
  padding: 12px 16px;
  border-radius: 8px;
  background: #f6f8fb;
  border: 1px solid #e8ecf3;
}
/* 笔数卡片：定宽 + 内容垂直居中，与右侧分类汇总等高。
   必须写在 .summary-card 之后才能覆盖它的 flex: 1 */
.summary-card-count {
  flex: 0 0 190px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}
.summary-card.card-in {
  background: #f0f9eb;
  border-color: #d9ecce;
}
.summary-card.card-out {
  background: #fef0f0;
  border-color: #f7d4d4;
}
.summary-label {
  font-size: 12px;
  color: #8a94a6;
  margin-bottom: 4px;
}
.summary-value {
  font-size: 22px;
  font-weight: 700;
  color: #2a3348;
}
.card-in .summary-value {
  color: #2f9e44;
}
.card-out .summary-value {
  color: #f56c6c;
}
/* 退货：橙（warning） */
.card-ret {
  background: #fdf6ec;
  border-color: #f5dab1;
}
.card-ret .summary-value {
  color: #e6a23c;
}
/* 报废：灰（info） */
.card-scr {
  background: #f4f4f5;
  border-color: #d9d9dc;
}
.card-scr .summary-value {
  color: #909399;
}
.summary-sub {
  font-size: 12px;
  color: #a0a8b8;
  margin-top: 2px;
}

.item-name {
  font-weight: 500;
  color: #2a3348;
}
.item-type {
  font-size: 12px;
  color: #a0a8b8;
}
/* 物料编码：等宽小灰字，与流水页风格统一 */
.row-code {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  color: #9aa3b2;
}
.num-in {
  font-weight: 700;
  color: #2f9e44;
}
.num-out {
  font-weight: 700;
  color: #f56c6c;
}
.num-ret {
  font-weight: 700;
  color: #e6a23c;
}
.num-scr {
  font-weight: 700;
  color: #909399;
}
.num-zero {
  font-weight: 700;
  color: #909399;
}
.unit-text {
  font-size: 12px;
  color: #9aa3b2;
  margin-left: 2px;
}
</style>

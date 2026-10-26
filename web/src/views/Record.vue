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
        <!-- 方向：按数量增减（1=入库/增加 2=出库/减少）-->
        <el-select v-model="query.direction" placeholder="方向" clearable style="width: 130px" @change="handleSearch">
          <el-option label="入库（增加）" :value="1" />
          <el-option label="出库（减少）" :value="2" />
        </el-select>
        <!-- 单据类型：基于来源单据的 order_type 筛（1=入库 2=出库 3=退货 4=报废）-->
        <el-select v-model="query.order_type" placeholder="单据类型" clearable style="width: 130px" @change="handleSearch">
          <el-option v-for="(v, k) in ORDER_TYPES" :key="k" :label="v.label" :value="Number(k)" />
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

      <el-table v-loading="loading" :data="list" stripe @row-click="handleRowClick">
        <el-table-column label="发生时间" width="170">
          <template #default="{ row }">{{ fmtDateTimeFull(row.transaction_date) }}</template>
        </el-table-column>
        <el-table-column label="物料名称" min-width="180">
          <template #default="{ row }">
            <span v-if="row.code" class="row-code">{{ row.code }}</span>{{ row.name || '—' }}
          </template>
        </el-table-column>
        <el-table-column prop="type" label="型号" min-width="120">
          <template #default="{ row }">{{ row.type || '—' }}</template>
        </el-table-column>
        <el-table-column label="单据类型" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="ORDER_TYPES[row.order_type]?.tag || 'info'" effect="light" size="small">
              {{ ORDER_TYPES[row.order_type]?.label || `未知(${row.order_type})` }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="原先库存" width="90" align="center">
          <template #default="{ row }">
            <!-- 库里存基础单位，*_display 是后端临时换算出来的显示单位 -->
            {{ row.before_display ?? row.before_quantity }}<span class="unit-text">{{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column label="变更数量" width="110" align="center">
          <template #default="{ row }">
            <span :class="`change-num change-${row.order_type}`">
              {{ changeQty(row) > 0 ? '+' : '' }}{{ changeQty(row) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="剩余库存" width="90" align="center">
          <template #default="{ row }">
            <b>{{ row.after_display ?? row.after_quantity }}</b><span class="unit-text">{{ row.unit }}</span>
          </template>
        </el-table-column>
        <!-- 金额的语义随单据类型变，列头用中性词 + tooltip 说明，每行副标签标清"这是什么钱" -->
        <el-table-column width="170" align="right">
          <template #header>
            金额
            <el-tooltip
              content="入库=采购金额；出库=销售金额；退货=退货金额；报废=报废损失。副标签里能看到 售价/成本/毛利 等详细分拆"
              placement="top"
            >
              <el-icon class="col-hint"><QuestionFilled /></el-icon>
            </el-tooltip>
          </template>
          <template #default="{ row }">
            <template v-if="displayAmount(row) != null">
              <div class="cost-amount">¥ {{ fmtMoney(displayAmount(row)) }}</div>
              <div class="cost-unit">{{ costUnitLabel(row) }}</div>
            </template>
            <span v-else class="text-muted">—</span>
          </template>
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
import { onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Refresh, RefreshLeft, Search, QuestionFilled } from '@element-plus/icons-vue'
import { listRecords } from '@/api'
import { fmtDateTimeFull, ORDER_TYPES } from '@/utils/format'

const PAGE_SIZES = [10, 20, 50]
const DEFAULT_PAGE_SIZE = 20

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const list = ref([])        // 当前页数据（后端已分页、已过滤）
const total = ref(0)        // 符合条件的总条数（后端返回）

// 筛选条件与分页都从 URL 还原：刷新、后退、分享链接都能回到同一个列表视图
function readFilters() {
  const q = route.query
  const num = (v) => {
    if (v === undefined || v === '') return null
    const n = Number(v)
    return Number.isNaN(n) ? null : n
  }
  // direction: 1=入库 2=出库，与后端约定一致
  // order_type: 1=入库单 2=出库单 3=退货单 4=报废单（来源单据类型）
  return {
    keyword: typeof q.keyword === 'string' ? q.keyword : '',
    direction: num(q.direction),
    order_type: num(q.order_type),
    range: q.start_day && q.end_day ? [String(q.start_day), String(q.end_day)] : []
  }
}

const query = reactive(readFilters())
const page = ref(Math.max(1, Number(route.query.page) || 1))
const pageSize = ref(
  PAGE_SIZES.includes(Number(route.query.pageSize)) ? Number(route.query.pageSize) : DEFAULT_PAGE_SIZE
)

// 只把"真的选了值"的传给后端：0 是有效值，不能因为 falsy 被丢掉
function toParam(v) {
  return v === null || v === undefined || v === '' ? undefined : v
}

// 把当前筛选/分页写回 URL；用 replace 是为了不新增历史记录，否则后退要点很多次
function syncQuery() {
  const q = {}
  const keyword = query.keyword.trim()
  const [start_day, end_day] = query.range || []
  if (keyword) q.keyword = keyword
  if (toParam(query.direction) !== undefined) q.direction = String(query.direction)
  if (toParam(query.order_type) !== undefined) q.order_type = String(query.order_type)
  if (start_day) q.start_day = start_day
  if (end_day) q.end_day = end_day
  if (page.value > 1) q.page = String(page.value)
  if (pageSize.value !== DEFAULT_PAGE_SIZE) q.pageSize = String(pageSize.value)

  const keys = ['keyword', 'direction', 'order_type', 'start_day', 'end_day', 'page', 'pageSize']
  const unchanged = keys.every((k) => String(route.query[k] ?? '') === String(q[k] ?? ''))
  if (!unchanged) router.replace({ path: '/record', query: q })
}

async function load() {
  syncQuery()
  loading.value = true
  try {
    // 过滤与分页全部由后端完成，返回 { total, items }
    const [start_day, end_day] = query.range || []
    const res = await listRecords({
      start_day: start_day || undefined,
      end_day: end_day || undefined,
      keyword: query.keyword.trim() || undefined,
      direction: toParam(query.direction),
      order_type: toParam(query.order_type),
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value
    })
    list.value = res.items || []
    total.value = res.total || 0
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
  query.direction = ''
  query.order_type = null
  query.range = []
  page.value = 1
  load()
}

// 整行点击 = 跳来源单据详情；正在选中文字时不跳，避免复制时间/名称时误触
function handleRowClick(row) {
  if (window.getSelection()?.toString()) return
  if (!row.order_id) return
  router.push({ name: 'order-detail', params: { id: row.order_id } })
}

// 显示单位数量：后端临时换算的 *_display；老流水没有就退回库里的基础单位原值。
// ⚠️ 金额必须用【显示单位】：unit_price / unit_cost 都是「每显示单位」的价
function changeQty(row) {
  return Number(row.change_display ?? row.change_quantity) || 0
}

// 主金额：出库/退货 = 销售/退货金额（订单侧的钱）；入库/报废 = 成本侧（采购金额/损失）
// 出库/退货需要订单明细的 unit_price（后端 join 了 stock_order_details 出来）
function displayAmount(row) {
  if (row.order_type === 2 || row.order_type === 3) {
    const up = Number(row.unit_price)
    if (!up) return null  // 老数据没有 unit_price（订单明细已删等）→ 显示 —，不强行算
    return Math.abs(changeQty(row)) * up
  }
  return Math.abs(changeQty(row)) * (Number(row.unit_cost) || 0)
}

// 副标签按单据类型标注"这些钱分别是啥"，让看的人不用猜
function costUnitLabel(row) {
  const u = `¥ ${fmtMoney(row.unit_cost)}`
  const up = `¥ ${fmtMoney(row.unit_price || 0)}`
  if (row.order_type === 1) return `采购价 ${u}`   // 入库：付给供应商的钱
  if (row.order_type === 2) {
    // 出库：售价 vs 成本，多算一笔毛利（负数=亏损）
    const qty = Math.abs(changeQty(row))
    const profit = qty * ((Number(row.unit_price) || 0) - (Number(row.unit_cost) || 0))
    const tag = profit >= 0 ? '毛利' : '亏损'
    return `售价 ${up} / 成本 ${u} · ${tag} ¥ ${fmtMoney(Math.abs(profit))}`
  }
  if (row.order_type === 3) return `退货价 ${up} / 成本 ${u}`  // 退货：拿回的钱 vs 原结转成本
  if (row.order_type === 4) return `损失单价 ${u}`             // 报废：按成本核销
  return `单价 ${u}`
}

function fmtMoney(n) {
  return Number(n || 0).toFixed(2)
}

onMounted(load)
</script>

<style scoped>
/* 整行可点进单据详情，给出手型反馈 */
:deep(.el-table__row) {
  cursor: pointer;
}
.change-num {
  font-weight: 700;
}
/* 变更数量按 order_type 配色，与「单据类型」tag 一致 */
.change-1 { color: #2f9e44; }   /* 入库 */
.change-2 { color: #f56c6c; }   /* 出库 */
.change-3 { color: #e6a23c; }   /* 退货 */
.change-4 { color: #909399; }   /* 报废 */
.unit-text {
  font-size: 12px;
  color: #9aa3b2;
  margin-left: 2px;
}
/* 成本快照：金额 + 单价两行 */
.cost-amount {
  font-weight: 600;
  color: #d98800;
}
.cost-unit {
  font-size: 12px;
  color: #9aa3b2;
}
/* 列头的 "?" 提示图标 */
.col-hint {
  font-size: 13px;
  color: #9aa3b2;
  cursor: help;
  vertical-align: -2px;
  margin-left: 2px;
}
.text-muted {
  color: #c0c4cc;
}
/* 物料编码前缀：等宽小灰字，与库存列表的展示风格统一 */
.row-code {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  color: #9aa3b2;
  margin-right: 4px;
}
</style>

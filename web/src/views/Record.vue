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
        <el-select v-model="query.direction" placeholder="类型" clearable style="width: 130px" @change="handleSearch">
          <el-option label="入库（增加）" :value="1" />
          <el-option label="出库（减少）" :value="2" />
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

      <el-table v-loading="loading" :data="list" stripe>
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
            {{ row.before_quantity }}<span class="unit-text">{{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column label="变更数量" width="110" align="center">
          <template #default="{ row }">
            <span :class="`change-num change-${row.order_type}`">
              {{ row.change_quantity > 0 ? '+' : '' }}{{ row.change_quantity }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="剩余库存" width="90" align="center">
          <template #default="{ row }">
            <b>{{ row.after_quantity }}</b><span class="unit-text">{{ row.unit }}</span>
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
import { Refresh, RefreshLeft, Search } from '@element-plus/icons-vue'
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
  if (start_day) q.start_day = start_day
  if (end_day) q.end_day = end_day
  if (page.value > 1) q.page = String(page.value)
  if (pageSize.value !== DEFAULT_PAGE_SIZE) q.pageSize = String(pageSize.value)

  const keys = ['keyword', 'direction', 'start_day', 'end_day', 'page', 'pageSize']
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
  query.range = []
  page.value = 1
  load()
}

onMounted(load)
</script>

<style scoped>
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
/* 物料编码前缀：等宽小灰字，与库存列表的展示风格统一 */
.row-code {
  font-family: Consolas, 'Courier New', monospace;
  font-size: 12px;
  color: #9aa3b2;
  margin-right: 4px;
}
</style>

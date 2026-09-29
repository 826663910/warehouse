<template>
  <div class="page-container">
    <div class="page-card">
      <!-- 筛选栏 -->
      <div class="toolbar">
        <el-input
          v-model="query.order_no"
          placeholder="单据号"
          :prefix-icon="Search"
          clearable
          style="width: 200px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-select v-model="query.order_type" placeholder="单据类型" clearable style="width: 130px" @change="handleSearch">
          <el-option v-for="(v, k) in ORDER_TYPES" :key="k" :label="v.label" :value="Number(k)" />
        </el-select>
        <el-select v-model="query.status" placeholder="单据状态" clearable style="width: 130px" @change="handleSearch">
          <el-option v-for="(v, k) in ORDER_STATUS" :key="k" :label="v.label" :value="Number(k)" />
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
        <el-dropdown @command="newOrder">
          <el-button type="primary" :icon="Plus">
            新建单据<el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item v-for="(v, k) in ORDER_TYPES" :key="k" :command="Number(k)">
                <el-tag size="small" :type="v.tag" effect="light">{{ v.label }}</el-tag>
                <span class="drop-label">创建{{ v.label }}单</span>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <!-- 单据列表：整行可点进详情，操作列的按钮已各自阻止冒泡 -->
      <el-table v-loading="loading" :data="list" stripe @row-click="handleRowClick">
        <el-table-column label="单据号" width="200">
          <template #default="{ row }">
            <span class="order-no">{{ row.order_no }}</span>
          </template>
        </el-table-column>
        <el-table-column label="类型" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="ORDER_TYPES[row.order_type]?.tag" effect="dark" size="small">
              {{ ORDER_TYPES[row.order_type]?.label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="业务日期" width="165">
          <template #default="{ row }">{{ fmtDateTimeFull(row.transaction_date) }}</template>
        </el-table-column>
        <el-table-column label="供应商" min-width="130">
          <template #default="{ row }">{{ supplierName(row.supplier_id) }}</template>
        </el-table-column>
        <el-table-column label="制单人" width="100">
          <template #default="{ row }">{{ row.created_by }}</template>
        </el-table-column>
        <el-table-column prop="remark" label="备注" min-width="150">
          <template #default="{ row }">
            <el-tooltip :content="row.remark || ''" :disabled="!row.remark">
              <span class="remark">{{ row.remark || '—' }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <el-tag :type="ORDER_STATUS[row.status]?.tag" effect="light" size="small">
              {{ ORDER_STATUS[row.status]?.label || `未知(${row.status})` }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="View" @click.stop="openDetail(row)">详情</el-button>
            <el-button
              v-if="row.status === 1"
              type="warning"
              link
              :icon="EditPen"
              @click.stop="$router.push(`/orders/edit/${row.id}`)"
            >编辑</el-button>
            <el-button
              v-if="row.status === 1"
              type="success"
              link
              :icon="CircleCheck"
              @click.stop="handleReview(row)"
            >审核</el-button>
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
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, RefreshLeft, Plus, ArrowDown, View, EditPen, CircleCheck } from '@element-plus/icons-vue'
import { listOrders, reviewOrder, listSupplier } from '@/api'
import { ORDER_TYPES, ORDER_STATUS, fmtDateTimeFull } from '@/utils/format'

const PAGE_SIZES = [10, 20, 50]
const DEFAULT_PAGE_SIZE = 20

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const list = ref([])
const total = ref(0)
const suppliers = ref([])

// 筛选条件与分页都从 URL 还原：刷新、后退、分享链接都能回到同一个列表视图
function readFilters() {
  const q = route.query
  const num = (v) => {
    if (v === undefined || v === '') return null
    const n = Number(v)
    return Number.isNaN(n) ? null : n
  }
  return {
    order_no: typeof q.order_no === 'string' ? q.order_no : '',
    order_type: num(q.order_type),
    status: num(q.status),
    range: q.start_day && q.end_day ? [String(q.start_day), String(q.end_day)] : []
  }
}

const query = reactive(readFilters())
const page = ref(Math.max(1, Number(route.query.page) || 1))
const pageSize = ref(
  PAGE_SIZES.includes(Number(route.query.pageSize)) ? Number(route.query.pageSize) : DEFAULT_PAGE_SIZE
)

const supplierMap = computed(() => {
  const m = new Map()
  suppliers.value.forEach((s) => m.set(s.id, s.name))
  return m
})

function supplierName(id) {
  return id ? supplierMap.value.get(id) || `#${id}` : '—'
}

// 只把"真的选了值"的传给后端：0 是有效值，不能因为 falsy 被丢掉
function toParam(v) {
  return v === null || v === undefined || v === '' ? undefined : v
}

// 把当前筛选/分页写回 URL；用 replace 是为了不新增历史记录，否则后退要点很多次
function syncQuery() {
  const q = {}
  const keyword = query.order_no.trim()
  if (keyword) q.order_no = keyword
  if (toParam(query.order_type) !== undefined) q.order_type = String(query.order_type)
  if (toParam(query.status) !== undefined) q.status = String(query.status)
  if (query.range?.[0]) q.start_day = query.range[0]
  if (query.range?.[1]) q.end_day = query.range[1]
  if (page.value > 1) q.page = String(page.value)
  if (pageSize.value !== DEFAULT_PAGE_SIZE) q.pageSize = String(pageSize.value)

  const keys = ['order_no', 'order_type', 'status', 'start_day', 'end_day', 'page', 'pageSize']
  const unchanged = keys.every((k) => String(route.query[k] ?? '') === String(q[k] ?? ''))
  if (!unchanged) router.replace({ path: '/orders', query: q })
}

async function load() {
  syncQuery()
  loading.value = true
  try {
    // 过滤与分页全部由后端完成，返回 { total, items }
    const res = await listOrders({
      order_no: query.order_no.trim() || undefined,
      order_type: toParam(query.order_type),
      status: toParam(query.status),
      start_day: query.range?.[0] || undefined,
      end_day: query.range?.[1] || undefined,
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
  query.order_no = ''
  query.order_type = null
  query.status = null
  query.range = []
  page.value = 1
  load()
}

function newOrder(type) {
  router.push({ path: '/orders/edit', query: { type } })
}

// 详情单开一页：跳到独立路由，URL 可分享、可前进后退
function openDetail(row) {
  router.push({ name: 'order-detail', params: { id: row.id } })
}

// 整行点击 = 进详情；正在选中文字时不跳，避免复制单据号/备注时误触
function handleRowClick(row) {
  if (window.getSelection()?.toString()) return
  openDetail(row)
}

async function handleReview(row) {
  try {
    await ElMessageBox.confirm(
      `审核后库存将立即生效且不可再编辑，确定审核单据「${row.order_no}」吗？`,
      '审核确认',
      { type: 'warning', confirmButtonText: '确定审核', cancelButtonText: '再想想' }
    )
  } catch (e) {
    return
  }
  await reviewOrder(row.id)
  ElMessage.success('审核成功，库存已更新')
  load()
}

onMounted(async () => {
  suppliers.value = await listSupplier()
  load()
})
</script>

<style scoped>
.order-no {
  font-family: Consolas, 'Courier New', monospace;
  font-weight: 600;
  color: #2a3348;
}
.remark {
  color: #6b7488;
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}
.drop-label {
  margin-left: 8px;
}
/* 整行可点，给出鼠标反馈（操作列按钮自己是 pointer，不受影响） */
:deep(.el-table__row) {
  cursor: pointer;
}
</style>

<template>
  <div class="page-container">
    <div class="page-card">
      <!-- 检索栏 -->
      <div class="toolbar">
        <el-input
          v-model="query.name"
          placeholder="物料名称 / 助记码 / 编码"
          :prefix-icon="Search"
          clearable
          style="width: 220px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-input
          v-model="query.type"
          placeholder="型号"
          :prefix-icon="Search"
          clearable
          style="width: 180px"
          @keyup.enter="handleSearch"
          @clear="handleSearch"
        />
        <el-select
          v-model="query.status"
          placeholder="状态"
          style="width: 110px"
          @change="handleSearch"
        >
          <el-option label="启用" :value="1" />
          <el-option label="禁用" :value="0" />
          <el-option label="全部" :value="-1" />
        </el-select>
        <el-button type="primary" :icon="Search" @click="handleSearch">查询</el-button>
        <el-button :icon="RefreshLeft" @click="handleReset">重置</el-button>
        <div class="spacer"></div>
        <!-- 新增/编辑走独立整页 /inventory/edit/:id?，不再是弹窗 -->
        <el-button type="primary" :icon="Plus" @click="$router.push('/inventory/edit')">新增物料</el-button>
        <el-button :icon="Refresh" @click="load">刷新</el-button>
      </div>

      <!-- 跨页面来源的筛选：来自供应商 / 分类页跳转等，需要明显且可一键清除 -->
      <div v-if="activeSupplierFilter || activeCategoryFilter" class="filter-chips">
        <el-tag v-if="activeSupplierFilter" type="info" effect="plain" closable @close="clearSupplierFilter">
          <el-icon class="chip-icon"><OfficeBuilding /></el-icon>
          仅看「{{ supplierName(query.supplier_id) }}」的物料
        </el-tag>
        <el-tag v-if="activeCategoryFilter" type="info" effect="plain" closable @close="clearCategoryFilter">
          <el-icon class="chip-icon"><FolderOpened /></el-icon>
          仅看「{{ categoryName(query.category_id) }}」分类的物料
        </el-tag>
      </div>

      <!-- 库存列表 -->
      <el-table
        ref="tableRef"
        v-loading="loading"
        :data="list"
        stripe
        :default-sort="defaultSort"
        @sort-change="handleSortChange"
      >
        <el-table-column prop="code" label="物料编码" width="90" align="center" />
        <el-table-column label="物料名称" min-width="180">
          <template #default="{ row }">
            <div class="inv-name">{{ row.name }}</div>
          </template>
        </el-table-column>
        <el-table-column label="助记码 · 分类 · 供应商" min-width="180" align="left">
          <template #default="{ row }">
            <span v-if="row.mnemonic_code" class="mnemonic-tag">[{{ row.mnemonic_code }}]</span>
            <template v-if="row.category_path"> · {{ row.category_path }}</template>
            <template v-if="row.supplier_name"> · 供: {{ row.supplier_name }}</template>
            <span v-if="!row.mnemonic_code && !row.category_path && !row.supplier_name" class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="型号" min-width="150">
          <template #default="{ row }">{{ row.type || '—' }}</template>
        </el-table-column>
        <el-table-column prop="stock" label="当前库存" width="110" align="center" sortable="custom">
          <template #default="{ row }">
            <span :class="isLowStock(row) ? 'stock-low' : 'stock-normal'">{{ row.stock_display ?? row.stock }}</span>
          </template>
        </el-table-column>
        <el-table-column label="单位" width="90" align="center">
          <template #default="{ row }">
            <!-- 显示单位和存储单位不一致时，tooltip 提示底层按什么记 -->
            <el-tooltip
              v-if="row.unit_base && row.unit_base !== row.unit"
              :content="`库存按「${row.unit_base}」存储`"
              placement="top"
            >
              <span class="unit-with-base">{{ row.unit }}</span>
            </el-tooltip>
            <span v-else>{{ row.unit }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成本均价" width="110" align="center">
          <template #default="{ row }">
            <span v-if="row.avg_cost" class="cost-value">¥ {{ fmtMoney(row.avg_cost) }}</span>
            <span v-else class="text-muted">—</span>
          </template>
        </el-table-column>
        <el-table-column label="预警值" width="90" align="center">
          <template #default="{ row }">
            {{ row.warning != null ? (row.warning_display ?? row.warning) : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="物料状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.status === 0 ? 'info' : 'success'" effect="light" size="small">
              {{ row.status === 0 ? '禁用' : '启用' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="库存状态" width="110" align="center">
          <template #default="{ row }">
            <el-tag :type="isLowStock(row) ? 'danger' : 'success'" effect="light" size="small">
              {{ isLowStock(row) ? '库存偏低' : '正常' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="200" align="center" fixed="right">
          <template #default="{ row }">
            <el-button type="primary" link :icon="Edit" @click="$router.push(`/inventory/edit/${row.id}`)">编辑</el-button>
            <el-button type="success" link :icon="Tickets" @click="quickOrder(row, 1)">入库</el-button>
            <el-button type="warning" link :icon="Tickets" @click="quickOrder(row, 2)">出库</el-button>
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
import { Plus, Refresh, RefreshLeft, Search, Edit, Tickets, OfficeBuilding, FolderOpened } from '@element-plus/icons-vue'
import {
  listInventory,
  listSupplier,
  listCategory
} from '@/api'

const PAGE_SIZES = [10, 20, 50]
const DEFAULT_PAGE_SIZE = 20
// 与后端 SORTABLE_FIELDS 白名单保持一致，URL 里的非法值直接丢掉
const SORT_FIELDS = ['id', 'code', 'name', 'type', 'stock', 'warning']

const route = useRoute()
const router = useRouter()
const loading = ref(false)
const list = ref([])        // 当前页数据（后端已分页、已过滤）
const total = ref(0)        // 符合条件的总条数（后端返回）
const supplierList = ref([])
const categoryList = ref([])

const tableRef = ref(null)

// 筛选、排序、分页都从 URL 还原：刷新、后退、分享链接都能回到同一个列表视图
const query = reactive({
  name: typeof route.query.name === 'string' ? route.query.name : '',
  type: typeof route.query.type === 'string' ? route.query.type : '',
  // supplier_id 为供应商页跳转过来用的跨页筛选条件；非法 / 缺失都视作无筛选
  supplier_id: (() => {
    const n = Number(route.query.supplier_id)
    return Number.isInteger(n) && n > 0 ? n : null
  })(),
  // category_id 为分类页跳转过来用的跨页筛选条件；非法 / 缺失都视作无筛选
  category_id: (() => {
    const n = Number(route.query.category_id)
    return Number.isInteger(n) && n > 0 ? n : null
  })(),
  // 状态筛选：1 启用（默认）/ 0 禁用 / -1 全部；URL 里的非法值回退到启用
  status: (() => {
    const n = Number(route.query.status)
    return [0, 1, -1].includes(n) ? n : 1
  })()
})
const page = ref(Math.max(1, Number(route.query.page) || 1))
const pageSize = ref(
  PAGE_SIZES.includes(Number(route.query.pageSize)) ? Number(route.query.pageSize) : DEFAULT_PAGE_SIZE
)
// 排序状态：由 el-table 的 sort-change 驱动，实际排序在后端做（翻页后顺序才正确）
const sortState = reactive({
  prop: SORT_FIELDS.includes(route.query.sort_by) ? route.query.sort_by : '',
  order: ['asc', 'desc'].includes(route.query.order) ? route.query.order : ''
})
function isLowStock(row) {
  return row.warning != null && row.stock != null && row.stock <= row.warning && row.warning > 0
}

function fmtMoney(n) {
  return Number(n || 0).toFixed(2)
}

// 当前是否在按供应商筛选；用 computed 让 chip / 标题 / 列表 自动响应
const activeSupplierFilter = computed(() => query.supplier_id != null)
// 当前是否在按分类筛选
const activeCategoryFilter = computed(() => query.category_id != null)

function supplierName(id) {
  return supplierList.value.find((s) => s.id === id)?.name || `#${id}`
}

function categoryName(id) {
  return categoryList.value.find((c) => c.id === id)?.name || `#${id}`
}

// 点 chip 的 ×：清掉跨页来源筛选，回到普通列表
function clearSupplierFilter() {
  query.supplier_id = null
  page.value = 1
  load()
}

function clearCategoryFilter() {
  query.category_id = null
  page.value = 1
  load()
}

// 表头排序箭头跟随 URL 里的排序状态，刷新后视觉和实际一致
const defaultSort = computed(() => {
  if (!sortState.prop || !sortState.order) return {}
  return { prop: sortState.prop, order: sortState.order === 'asc' ? 'ascending' : 'descending' }
})

// 把当前筛选/排序/分页写回 URL；用 replace 是为了不新增历史记录，否则后退要点很多次
function syncQuery() {
  const q = {}
  const keyword = query.name.trim()
  const type = query.type.trim()
  if (keyword) q.name = keyword
  if (type) q.type = type
  if (query.supplier_id != null) q.supplier_id = String(query.supplier_id)
  if (query.category_id != null) q.category_id = String(query.category_id)
  if (query.status !== 1) q.status = String(query.status)
  if (sortState.prop) {
    q.sort_by = sortState.prop
    if (sortState.order) q.order = sortState.order
  }
  if (page.value > 1) q.page = String(page.value)
  if (pageSize.value !== DEFAULT_PAGE_SIZE) q.pageSize = String(pageSize.value)

  const keys = ['name', 'type', 'supplier_id', 'category_id', 'status', 'sort_by', 'order', 'page', 'pageSize']
  const unchanged = keys.every((k) => String(route.query[k] ?? '') === String(q[k] ?? ''))
  if (!unchanged) router.replace({ path: '/inventory', query: q })
}

async function load() {
  syncQuery()
  loading.value = true
  try {
    // 过滤与分页全部由后端完成：name 参数同时匹配 物料名称 / 助记码 / 编码
    const res = await listInventory({
      name: query.name.trim() || undefined,
      type: query.type.trim() || undefined,
      supplier_id: query.supplier_id ?? undefined,
      category_id: query.category_id ?? undefined,
      status: query.status,
      sort_by: sortState.prop || undefined,
      order: sortState.order || undefined,
      limit: pageSize.value,
      offset: (page.value - 1) * pageSize.value
    })
    list.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

async function loadOptions() {
  const [sups, cats] = await Promise.all([listSupplier(), listCategory()])
  supplierList.value = sups
  categoryList.value = cats
}

function handleSearch() {
  page.value = 1
  load()
}

function handleReset() {
  query.name = ''
  query.type = ''
  query.supplier_id = null
  query.category_id = null
  query.status = 1
  page.value = 1
  sortState.prop = ''
  sortState.order = ''
  // default-sort 只在挂载时生效，重置排序要手动清表头箭头
  // clearSort 是静默的（不会触发 sort-change），所以后面照常 load()
  tableRef.value?.clearSort()
  load()
}

// 点表头排序：order 为 ascending / descending / null（第三次点击取消排序）
function handleSortChange({ prop, order }) {
  sortState.prop = order ? prop : ''
  sortState.order = order === 'ascending' ? 'asc' : order === 'descending' ? 'desc' : ''
  page.value = 1
  load()
}

function quickOrder(row, orderType) {
  router.push({ path: `/orders/edit`, query: { type: orderType, inventory_id: row.id } })
}

onMounted(async () => {
  await loadOptions()
  await load()
})
</script>

<style scoped>
.inv-name {
  font-weight: 500;
  color: #2a3348;
}
.mnemonic-tag {
  display: inline-block;
  padding: 1px 8px;
  font-size: 12px;
  font-family: Consolas, monospace;
  color: #4a5a76;
  background: #f0f3f9;
  border-radius: 4px;
  letter-spacing: 0.5px;
}
.text-muted {
  color: #c0c4cc;
}
.cost-value {
  font-weight: 600;
  color: #d98800;
}
.stock-normal {
  font-weight: 600;
  color: #2f9e44;
}
.stock-low {
  font-weight: 700;
  color: #f56c6c;
}
/* 显示单位 ≠ 存储单位时，加虚线下划线提示可看 tooltip */
.unit-with-base {
  border-bottom: 1px dashed #c0c4cc;
  cursor: help;
}

/* 跨页面来源的筛选 chip：来自供应商页跳转等，让用户看清楚「现在只看哪家的物料」 */
.filter-chips {
  margin-bottom: 12px;
}
.filter-chips :deep(.el-tag) {
  font-size: 13px;
}
.chip-icon {
  margin-right: 4px;
  vertical-align: -2px;
}
</style>

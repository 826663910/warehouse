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
        <el-button type="primary" :icon="Plus" @click="openCreate">新增物料</el-button>
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
            <span :class="isLowStock(row) ? 'stock-low' : 'stock-normal'">{{ row.stock }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="unit" label="单位" width="70" align="center" />
        <el-table-column label="预警值" width="90" align="center">
          <template #default="{ row }">{{ row.warning ?? '—' }}</template>
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
            <el-button type="primary" link :icon="Edit" @click="openEdit(row)">编辑</el-button>
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

    <!-- 新增 / 编辑物料弹窗 -->
    <el-dialog
      v-model="dialog.visible"
      :title="dialog.mode === 'create' ? '新增物料' : '编辑物料'"
      width="600px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="物料名称" prop="name">
              <el-input v-model="form.name" placeholder="如：减速机" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="型号" prop="type">
              <el-input v-model="form.type" placeholder="如：XK-100" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="助记码" prop="mnemonic_code">
              <el-input
                v-model="form.mnemonic_code"
                placeholder="留空则自动生成拼音首字母"
                clearable
                :disabled="dialog.mode === 'create'"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属分类" prop="category_id">
              <el-select v-model="form.category_id" placeholder="请选择末级分类" style="width: 100%">
                <el-option
                  v-for="c in categoryOptions"
                  :key="c.id"
                  :label="c.name"
                  :value="c.id"
                />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="供应商" prop="supplier_id">
              <el-select v-model="form.supplier_id" placeholder="请选择供应商" style="width: 100%">
                <el-option v-for="s in supplierList" :key="s.id" :label="s.name" :value="s.id" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位" prop="unit">
              <el-input v-model="form.unit" placeholder="如：台 / 个 / kg" clearable />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="初始库存" prop="stock">
              <el-input-number v-model="form.stock" :min="0" :precision="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="预警数量" prop="warning">
              <el-input-number
                v-model="form.warning"
                :min="0"
                :precision="0"
                placeholder="不填则不预警"
                style="width: 100%"
              />
              <div class="form-hint">库存 ≤ 预警值 时高亮提醒</div>
            </el-form-item>
          </el-col>
          <el-col v-if="dialog.mode === 'edit'" :span="12">
            <el-form-item label="物料状态">
              <el-switch
                v-model="form.status"
                :active-value="1"
                :inactive-value="0"
                active-text="启用"
                inactive-text="禁用"
              />
              <div class="form-hint">禁用后不出现在单据的物料搜索中</div>
            </el-form-item>
          </el-col>
        </el-row>
      </el-form>
      <template #footer>
        <el-button @click="dialog.visible = false">取 消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保 存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus, Refresh, RefreshLeft, Search, Edit, Tickets, OfficeBuilding, FolderOpened } from '@element-plus/icons-vue'
import {
  listInventory,
  getInventory,
  createInventory,
  updateInventory,
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
const saving = ref(false)
const list = ref([])        // 当前页数据（后端已分页、已过滤）
const total = ref(0)        // 符合条件的总条数（后端返回）
const supplierList = ref([])
const categoryList = ref([])
const formRef = ref(null)
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
const dialog = reactive({ visible: false, mode: 'create' })

const form = reactive({
  id: null,
  name: '',
  type: '',
  mnemonic_code: '',
  category_id: null,
  supplier_id: null,
  unit: '个',
  stock: 0,
  warning: null,
  status: 1
})

const rules = {
  name: [{ required: true, message: '请输入物料名称', trigger: 'blur' }],
  category_id: [{ required: true, message: '请选择末级分类', trigger: 'change' }],
  supplier_id: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  unit: [{ required: true, message: '请输入单位', trigger: 'blur' }]
}

/* 只允许选择末级分类 */
const categoryOptions = computed(() => {
  const hasChild = new Set(categoryList.value.filter((c) => c.parent_id !== 0).map((c) => c.parent_id))
  return categoryList.value
    .filter((c) => !hasChild.has(c.id))
    .map((c) => ({
      id: c.id,
      name: `${c.name}${c.parent_id ? '' : ''}`,
      full: c
    }))
})

function isLowStock(row) {
  return row.warning != null && row.stock != null && row.stock <= row.warning && row.warning > 0
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

function resetForm() {
  form.id = null
  form.name = ''
  form.type = ''
  form.mnemonic_code = ''
  form.category_id = null
  form.supplier_id = null
  form.unit = '个'
  form.stock = 0
  form.warning = null
  form.status = 1
}

function openCreate() {
  dialog.mode = 'create'
  resetForm()
  dialog.visible = true
}

async function openEdit(row) {
  dialog.mode = 'edit'
  resetForm()
  const detail = await getInventory(row.id)
  form.id = detail.id
  form.name = detail.name
  form.type = detail.type || ''
  form.mnemonic_code = detail.mnemonic_code || ''
  form.category_id = detail.category_id ?? null
  form.supplier_id = detail.supplier_id ?? null
  form.unit = detail.unit || '个'
  form.stock = detail.stock ?? 0
  form.warning = detail.warning ?? null
  form.status = detail.status ?? 1
  dialog.visible = true
}

async function submit() {
  try {
    await formRef.value.validate()
  } catch (e) {
    return
  }
  if (!categoryOptions.value.some((o) => o.id === form.category_id)) {
    ElMessage.warning('请选择末级分类（无子分类的类别）')
    return
  }
  saving.value = true
  try {
    const payload = {
      name: form.name,
      type: form.type || null,
      mnemonic_code: form.mnemonic_code || null,
      category_id: form.category_id,
      supplier_id: form.supplier_id,
      unit: form.unit,
      stock: form.stock,
      warning: form.warning
    }
    if (dialog.mode === 'create') {
      await createInventory(payload)
      ElMessage.success('新增成功')
    } else {
      // 编辑模式额外带 status；创建不用传，后端 schema 里 server_default=1 兜底
      await updateInventory(form.id, { ...payload, status: form.status })
      ElMessage.success('保存成功')
    }
    dialog.visible = false
    load()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
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
.stock-normal {
  font-weight: 600;
  color: #2f9e44;
}
.stock-low {
  font-weight: 700;
  color: #f56c6c;
}
.form-hint {
  font-size: 12px;
  color: #a0a8b8;
  line-height: 1.4;
  margin-top: 2px;
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

<template>
  <div class="page-container">
    <div class="page-card">
      <div class="head-bar">
        <div>
          <span class="head-title">{{ isEdit ? '编辑出入库单据' : '新建出入库单据' }}</span>
          <el-tag v-if="isEdit" class="ml8" type="info" effect="plain">{{ orderNo }}</el-tag>
        </div>
        <el-button :icon="Back" @click="$router.push('/orders')">返回列表</el-button>
      </div>

      <!-- 类型选择 -->
      <div class="type-block">
        <div class="type-label">单据类型</div>
        <div class="type-group">
          <div
            v-for="(v, k) in ORDER_TYPES"
            :key="k"
            class="type-item"
            :class="{ active: form.order_type === Number(k) }"
            :style="form.order_type === Number(k) ? { borderColor: typeColor(Number(k)), background: typeBg(Number(k)) } : {}"
            @click="form.order_type = Number(k)"
          >
            <el-icon :size="18" :color="form.order_type === Number(k) ? typeColor(Number(k)) : '#8a94a6'">
              <component :is="typeIcon(Number(k))" />
            </el-icon>
            <div>
              <div class="type-name">{{ v.label }}</div>
              <div class="type-desc">{{ typeDesc(Number(k)) }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 单据信息 -->
      <el-row :gutter="14" class="info-row">
        <el-col :span="6">
          <div class="field-label">业务日期</div>
          <el-date-picker v-model="form.date" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-col>
        <el-col v-if="form.order_type === 1" :span="6">
          <div class="field-label">供应商 <span class="required">*</span></div>
          <el-select v-model="form.supplier_id" placeholder="请选择供应商" style="width: 100%">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-col>
        <el-col :span="form.order_type === 1 ? 12 : 18">
          <div class="field-label">备注</div>
          <el-input v-model="form.remark" placeholder="选填，单据整体备注" clearable />
        </el-col>
      </el-row>
    </div>

    <!-- 明细卡片 -->
    <div class="page-card mt-card">
      <div class="card-head">
        <span class="head-title">物料明细</span>
        <el-select
          v-model="pickerId"
          class="picker-select"
          filterable
          remote
          clearable
          :remote-method="searchRemote"
          :loading="picking"
          placeholder="名称/助记码/编码，空格后接型号"
          @change="addPicked"
          @clear="onSelectClear"
        >
          <el-option v-for="o in pickerOptions" :key="o.id" :label="`${o.code} · ${o.name}`" :value="o.id">
            <div class="opt-line">
              <span class="opt-name">
                <b>{{ o.code }}</b> {{ o.name }}<span v-if="o.type" class="opt-type">{{ o.type }}</span>
              </span>
              <span class="opt-stock">库存 {{ o.stock ?? 0 }} {{ o.unit }}</span>
            </div>
          </el-option>
          <!-- 下拉底部回显分词结果，让用户看清空格是怎么被解析的 -->
          <template #footer>
            <div class="picker-hint">
              <template v-if="!parsedKw.name">
                名称 / 助记码 / 编码 直接输入；按型号筛则空格后接型号
              </template>
              <template v-else-if="parsedKw.type">
                名称、助记码、编码含「{{ parsedKw.name }}」且型号含「{{ parsedKw.type }}」
              </template>
              <template v-else>
                名称、助记码、编码、型号 任意命中「{{ parsedKw.name }}」
              </template>
            </div>
          </template>
        </el-select>
      </div>

      <el-table :data="lines" size="small" empty-text="请在上方搜索添加物料" style="width: 100%">
        <el-table-column label="#" type="index" width="45" align="center" />
        <el-table-column label="物料编码" width="95">
          <template #default="{ row }"><span class="mono">{{ row.code }}</span></template>
        </el-table-column>
        <el-table-column label="物料名称" min-width="170">
          <template #default="{ row }">
            <div class="row-name">{{ row.name }}</div>
            <div v-if="row.type" class="row-type">{{ row.type }}</div>
          </template>
        </el-table-column>
        <el-table-column label="单位" width="60" align="center">
          <template #default="{ row }">{{ row.unit }}</template>
        </el-table-column>
        <el-table-column label="当前库存" width="95" align="center">
          <template #default="{ row }">
            <span :class="row.stock < row.quantity ? 'text-danger' : ''">{{ row.stock ?? '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="160" align="center">
          <template #default="{ row }">
            <el-input-number v-model="row.quantity" :min="1" :precision="0" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="单价 (¥)" width="150" align="center">
          <template #default="{ row }">
            <el-input-number v-model="row.price" :min="0" :precision="2" :step="1" size="small" />
          </template>
        </el-table-column>
        <el-table-column label="金额" width="110" align="right">
          <template #default="{ row }">¥ {{ fmtMoney(row.quantity * (row.price || 0)) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="70" align="center">
          <template #default="{ $index }">
            <el-button link type="danger" :icon="Delete" @click="lines.splice($index, 1)" />
          </template>
        </el-table-column>
      </el-table>

      <!-- 合计 / 保存 -->
      <div class="foot-bar">
        <div class="sums">
          <span>共 <b>{{ lines.length }}</b> 项物料</span>
          <span>总数量：<b>{{ totalQty }}</b></span>
          <span v-if="form.order_type === 1">
            单据金额：<b class="sum-amount">¥ {{ fmtMoney(totalAmount) }}</b>
          </span>
        </div>
        <div class="ops">
          <el-button :icon="RefreshLeft" @click="resetForm">重置</el-button>
          <el-button type="primary" size="large" :loading="saving" :icon="DocumentChecked" @click="submit">
            {{ isEdit ? '保存修改' : '保存草稿' }}
          </el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back, Delete, RefreshLeft, DocumentChecked } from '@element-plus/icons-vue'
import { listSupplier, searchOrderInventory, getInventory, getOrder, createOrder, updateOrder } from '@/api'
import { ORDER_TYPES, fmtDate, toLocalIso } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const isEdit = computed(() => Boolean(route.params.id))
const saving = ref(false)
const suppliers = ref([])
const pickerOptions = ref([])
const picking = ref(false)
const pickerId = ref(null)
// pickerKw 跟踪 el-select 内部当前的搜索关键词（el-select 不会自动同步到 v-model）
const pickerKw = ref('')
const orderNo = ref('')
// 单框支持「名称 型号」：按空白切分，第 1 段作为名称类关键词，其余段合并作为型号关键词
const parsedKw = computed(() => {
  const parts = pickerKw.value.trim().split(/\s+/).filter(Boolean)
  return { name: parts[0] || '', type: parts.slice(1).join(' ') }
})

const form = reactive({
  order_type: Number(route.query.type) || 1,
  date: fmtDate(new Date()),
  supplier_id: null,
  remark: ''
})

// 明细行
const lines = ref([])

const totalQty = computed(() => lines.value.reduce((s, l) => s + (l.quantity || 0), 0))
const totalAmount = computed(() => lines.value.reduce((s, l) => s + (l.quantity || 0) * (l.price || 0), 0))

function fmtMoney(n) {
  return Number(n || 0).toFixed(2)
}

function typeColor(t) {
  return { 1: '#2f6bff', 2: '#f56c6c', 3: '#e6a23c', 4: '#909399' }[t] || '#909399'
}
function typeBg(t) {
  const c = typeColor(t)
  return `${c}14`
}
function typeIcon(t) {
  return { 1: 'Download', 2: 'Upload', 3: 'RefreshLeft', 4: 'Delete' }[t]
}
function typeDesc(t) {
  return { 1: '采购/期初入库，增加库存', 2: '领用/销售出库，扣减库存', 3: '退回供应商/退货入库', 4: '损坏过期报废，扣减库存' }[t]
}

function addPicked(id) {
  if (id == null) return
  const o = pickerOptions.value.find((x) => x.id === id)
  pickerId.value = null
  if (!o) return
  if (lines.value.some((l) => l.inventory_id === o.id)) {
    ElMessage.warning(`「${o.name}」已在明细中`)
    return
  }
  lines.value.push({
    inventory_id: o.id,
    code: o.code,
    name: o.name,
    type: o.type || '',
    unit: o.unit || '',
    stock: o.stock ?? 0,
    quantity: 1,
    price: 0
  })
}

// 防抖：用户连续敲键时合并请求，避免每个字符都触发一次查询
let _searchTimer = null
function scheduleSearch() {
  clearTimeout(_searchTimer)
  _searchTimer = setTimeout(doSearch, 250)
}

async function doSearch() {
  picking.value = true
  try {
    pickerOptions.value = await searchOrderInventory({
      name: parsedKw.value.name || undefined,
      type: parsedKw.value.type || undefined,
      limit: 20
    })
  } finally {
    picking.value = false
  }
}

// el-select 的 remote-method：把当前关键词写回 ref，再走统一的搜索流程（同样走防抖）
function searchRemote(kw) {
  pickerKw.value = (kw || '').trim()
  scheduleSearch()
}

// 点 clearable 清空时同步清掉查询关键词（部分版本 el-select 清空不会触发 remote-method）
function onSelectClear() {
  pickerKw.value = ''
  scheduleSearch()
}

function resetForm() {
  lines.value = []
  form.remark = ''
}

function buildPayload() {
  return {
    order_type: form.order_type,
    transaction_date: toLocalIso(new Date(`${form.date} 00:00:00`)),
    supplier_id: form.order_type === 1 ? form.supplier_id : null,
    remark: form.remark || null,
    items: lines.value.map((l) => ({
      inventory_id: l.inventory_id,
      quantity: l.quantity,
      price: l.price || 0
    }))
  }
}

async function submit() {
  if (!lines.value.length) {
    ElMessage.warning('请先添加物料明细')
    return
  }
  const bad = lines.value.find((l) => !l.quantity || l.quantity <= 0)
  if (bad) {
    ElMessage.warning(`「${bad.name}」的数量必须大于 0`)
    return
  }
  if (form.order_type === 1 && !form.supplier_id) {
    ElMessage.warning('入库单请选择供应商')
    return
  }
  saving.value = true
  try {
    if (isEdit.value) {
      await updateOrder(route.params.id, buildPayload())
      ElMessage.success('单据已保存')
    } else {
      const created = await createOrder(buildPayload())
      ElMessage.success(`草稿已保存，单据号：${created.order_no || ''}`)
    }
    router.push('/orders')
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

async function loadEditOrder() {
  const order = await getOrder(route.params.id)
  if (order.status !== 1) {
    ElMessage.warning('只有草稿状态的单据可以编辑')
    router.replace('/orders')
    return
  }
  orderNo.value = order.order_no
  form.order_type = order.order_type
  form.supplier_id = order.supplier_id ?? null
  form.remark = order.remark || ''
  const raw = order.transaction_date ? String(order.transaction_date) : ''
  form.date = raw.slice(0, 10) || fmtDate(new Date())

  const items = order.items || []
  // 尽量补当前库存
  const current = {}
  try {
    const all = await searchOrderInventory({ limit: 10000 })
    all.forEach((i) => {
      current[i.id] = i
    })
  } catch (e) {
    /* ignore */
  }
  lines.value = items.map((it) => {
    const cur = current[it.inventory_id] || {}
    return {
      inventory_id: it.inventory_id,
      code: it.item_code || cur.code,
      name: it.item_name || cur.name || '',
      type: it.item_type || cur.type || '',
      unit: it.item_unit || cur.unit || '',
      stock: cur.stock ?? 0,
      quantity: it.quantity,
      price: Number(it.unit_price ?? it.price ?? 0)
    }
  })
}

async function quickAddInventory(inventoryId) {
  try {
    const o = await getInventory(inventoryId)
    lines.value.push({
      inventory_id: o.id,
      code: o.code,
      name: o.name,
      type: o.type || '',
      unit: o.unit || '',
      stock: o.stock ?? 0,
      quantity: 1,
      price: 0
    })
    ElMessage.success(`已添加「${o.name}」`)
  } catch (e) {
    /* ignore */
  }
}

onMounted(async () => {
  suppliers.value = await listSupplier()
  doSearch() // 预加载候选
  if (route.query.inventory_id) {
    await quickAddInventory(Number(route.query.inventory_id))
  }
  if (isEdit.value) {
    await loadEditOrder()
  }
})
</script>

<style scoped>
.head-bar,
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.head-bar {
  margin-bottom: 18px;
}
.head-title {
  font-size: 17px;
  font-weight: 700;
  color: #1f2d3d;
}
.ml8 {
  margin-left: 8px;
}

/* 类型 */
.type-block {
  margin-bottom: 18px;
}
.type-label,
.field-label {
  font-size: 13px;
  color: #6b7488;
  margin-bottom: 8px;
}
.field-label .required {
  color: #f56c6c;
}
.type-group {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}
.type-item {
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1.5px solid #e3e8f0;
  border-radius: 10px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.18s;
  background: #fff;
}
.type-item:hover {
  border-color: #b9c6dd;
}
.type-name {
  font-weight: 600;
  color: #2a3348;
  font-size: 14px;
}
.type-desc {
  font-size: 11px;
  color: #9aa3b2;
  margin-top: 1px;
}
.info-row {
  align-items: flex-end;
}
.mt-card {
  margin-top: 14px;
}

/* 明细 */
.picker-select {
  width: 420px;
}
/* 下拉底部的分词提示 */
.picker-hint {
  padding: 2px 12px 6px;
  font-size: 12px;
  line-height: 1.5;
  color: #8a94a6;
}
.opt-line {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.opt-type {
  margin-left: 6px;
  font-size: 12px;
  color: #a0a8b8;
}
.opt-stock {
  font-size: 12px;
  color: #8a94a6;
}
.mono {
  font-family: Consolas, monospace;
}
.row-name {
  font-weight: 500;
  color: #2a3348;
}
.row-type {
  font-size: 12px;
  color: #a0a8b8;
}

.foot-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding-top: 14px;
  border-top: 1px dashed #e8ecf3;
  flex-wrap: wrap;
  gap: 10px;
}
.sums {
  display: flex;
  gap: 22px;
  color: #5a6478;
  font-size: 13px;
}
.sum-amount {
  color: #f56c6c;
  font-size: 18px;
  font-weight: 700;
}
.ops {
  display: flex;
  gap: 10px;
}

@media (max-width: 1000px) {
  .type-group {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>

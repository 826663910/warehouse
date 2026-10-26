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
          <el-date-picker
            v-model="form.date"
            type="datetime"
            format="YYYY-MM-DD HH:mm:ss"
            value-format="YYYY-MM-DD HH:mm:ss"
            :default-time="defaultTime"
            style="width: 100%"
          />
        </el-col>
        <!-- 合作方字段：
             入库/退货 → 供应商（退货是退给供应商，所以对手方也是供应商）
             出库      → 客户
             报废      → 无（仓库内部处理，没有交易对手） -->
        <el-col v-if="form.order_type === 1 || form.order_type === 3" :span="6">
          <div class="field-label">供应商 <span class="required">*</span></div>
          <el-select v-model="form.supplier_id" placeholder="请选择供应商" style="width: 100%">
            <el-option v-for="s in suppliers" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-col>
        <el-col v-else-if="form.order_type === 2" :span="6">
          <div class="field-label">客户</div>
          <el-select v-model="form.customer_id" placeholder="请选择客户" style="width: 100%" clearable>
            <el-option v-for="c in customers" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-col>
        <!-- 备注栏宽度：报废=24 整行；入库/退货=12；出库=18 -->
        <el-col :span="remarkSpan">
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
              <span class="opt-stock">库存 {{ fmtQty(o.stock_display ?? o.stock) }} {{ o.unit }}</span>
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
        <el-table-column label="当前库存" width="115" align="center">
          <template #default="{ row }">
            <!-- 显示用 stock_display（已换算成物料显示单位）；
                 但"够不够"的比较必须在【基础单位】上做：stock vs baseQty -->
            <span :class="row.stock < baseQty(row) ? 'text-danger' : ''">
              {{ fmtQty(row.stock_display ?? row.stock) }}
              <span class="qty-unit-text">{{ row.unit }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="数量" width="150" align="center">
          <template #default="{ row }">
            <div class="qty-cell">
              <el-input-number
                v-model="row.input_qty"
                :min="0"
                :precision="2"
                :step="1"
                size="small"
                controls-position="right"
                class="qty-input"
              />
              <!-- 默认就是物料的显示单位，平时像纯文本，点一下才展开换单位；
                   只有 1 个可选单位（或 other 赛道没换算表）时干脆不下拉 -->
              <el-select
                v-if="lineUnits(row).length > 1"
                v-model="row.input_unit"
                size="small"
                class="qty-unit-plain"
              >
                <el-option v-for="u in lineUnits(row)" :key="u" :label="u" :value="u" />
              </el-select>
              <span v-else class="qty-unit-text">{{ row.input_unit || row.unit }}</span>
            </div>
            <!-- 只有选了【非物料默认单位】才提示，默认保持安静 -->
            <div v-if="row.input_unit && row.input_unit !== row.unit" class="qty-hint">
              = {{ fmtMoney(displayQty(row)) }} {{ row.unit }}
            </div>
          </template>
        </el-table-column>
        <!-- 报废没有"成交价"概念：隐藏单价列；金额列改成"报废损失 = 数量 × 当前均价" -->
        <el-table-column v-if="form.order_type !== 4" :label="priceLabel" width="165" align="center">
          <template #default="{ row }">
            <div class="qty-cell">
              <el-input-number
                v-model="row.price"
                :min="0"
                :precision="2"
                :step="1"
                size="small"
                controls-position="right"
                class="qty-input"
              />
              <!-- 明码标价：单价是按【物料显示单位】计的，写出来杜绝歧义 -->
              <span class="qty-unit-text">/{{ row.unit }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column :label="amountLabel" width="110" align="right">
          <template #default="{ row }">
            <template v-if="form.order_type === 4">
              <!-- 报废：损失 = 显示单位数量 × 当前库存均价（avg_cost 是【每显示单位】的成本） -->
              ¥ {{ fmtMoney(displayQty(row) * (row.avg_cost || 0)) }}
            </template>
            <template v-else>
              <!-- 入库/出库/退货：金额 = 显示单位数量 × 单价（单价锚定物料显示单位） -->
              ¥ {{ fmtMoney(displayQty(row) * (row.price || 0)) }}
            </template>
          </template>
        </el-table-column>
        <el-table-column label="参考成本" width="120" align="center">
          <template #default="{ row }">
            <template v-if="row.avg_cost">
              <div class="ref-cost">¥ {{ fmtMoney(row.avg_cost) }}</div>
              <div
                v-if="form.order_type === 2"
                :class="lineProfit(row) >= 0 ? 'line-profit' : 'line-loss'"
              >
                毛利 ¥ {{ fmtMoney(lineProfit(row)) }}
              </div>
            </template>
            <span v-else class="text-muted">—</span>
          </template>
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
          <!-- 报废没有成交价，损失按库存成本算 -->
          <span v-if="form.order_type === 4">
            报废成本：<b class="sum-cost">¥ {{ fmtMoney(totalCost) }}</b>
          </span>
          <template v-else>
            <span>{{ amountLabel }}：<b class="sum-amount">¥ {{ fmtMoney(totalAmount) }}</b></span>
            <!-- 出库才有毛利概念：销售额 − 结转成本 -->
            <template v-if="form.order_type === 2">
              <span>预计成本：<b class="sum-cost">¥ {{ fmtMoney(totalCost) }}</b></span>
              <span>
                预计毛利：
                <b :class="totalProfit >= 0 ? 'sum-profit' : 'sum-loss'">¥ {{ fmtMoney(totalProfit) }}</b>
              </span>
            </template>
          </template>
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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back, Delete, RefreshLeft, DocumentChecked } from '@element-plus/icons-vue'
import { listSupplier, listCustomer, searchOrderInventory, getInventory, getOrder, createOrder, updateOrder, getUnits } from '@/api'
import { ORDER_TYPES, fmtDateTimeFull, toLocalIso } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const isEdit = computed(() => Boolean(route.params.id))
const saving = ref(false)
const suppliers = ref([])
const customers = ref([])
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
  date: fmtDateTimeFull(new Date()),   // 业务日期默认 = 当前时刻（带时间）
  supplier_id: null,
  customer_id: null,
  remark: ''
})

// datetime 选择器里点选某个日期时，时间部分默认用"此刻"而不是 00:00:00
const defaultTime = new Date()

// 哪些类型用 supplier_id、哪些用 customer_id。切类型时自动清空用不到的那边
const usesSupplier = (t) => t === 1 || t === 3
const usesCustomer = (t) => t === 2
// 备注栏宽度：报废=24 整行；入库/退货=12（与供应商字段一起换行）；出库=18
const remarkSpan = computed(() => {
  if (form.order_type === 4) return 24
  if (form.order_type === 1 || form.order_type === 3) return 12
  return 18
})
watch(() => form.order_type, (t) => {
  if (!usesSupplier(t)) form.supplier_id = null
  if (!usesCustomer(t)) form.customer_id = null
})

// 明细行
const lines = ref([])

/* ===== 单位换算 =====
   每个赛道（weight/count/...）的单位表只拉一次，按 category 缓存复用。
   factors = 「单位 → 基础单位的乘数」，前端靠它把录入值换算成基础单位：
   "库存不足"预警、报废损失预估都要先换算（因为 avg_cost 是【每基础单位】的成本）。 */
const unitCache = reactive({}) // { category: { units: [...], factors: { 单位: 乘数 } } }

async function ensureUnitMeta(category) {
  // count 赛道没有换算表，不用拉单位选项（前端回退成纯文本）
  if (!category || category === 'count') return
  if (unitCache[category]) return
  try {
    const res = await getUnits(category)
    unitCache[category] = { units: res.units || [], factors: res.factors || {} }
  } catch (e) {
    unitCache[category] = { units: [], factors: {} }
  }
}

/* 该行可选的录入单位 = 物料显示单位 + 赛道全局单位 + 该物料的包装单位。
   包装是物料私有的（螺丝 1箱=24个），全局换算表里查不到，必须单独拼上 */
function lineUnits(row) {
  const globals = unitCache[row.unit_category]?.units || []
  const pkgs = (row.packages || []).map((p) => p.unit_name)
  // row.unit 排最前：count 赛道全局表是空的，物料单位就是唯一的默认选项
  return [...new Set([row.unit, ...globals, ...pkgs])].filter(Boolean)
}

/* 录入数量 → 基础单位数量（库存比较、成本运算必须用这个） */
function baseQty(row) {
  const qty = Number(row.input_qty) || 0
  // 包装单位优先：它不在全局换算表里，只能查该物料自己的包装
  const pkg = (row.packages || []).find((p) => p.unit_name === row.input_unit)
  if (pkg) return qty * (Number(pkg.qty_per_base) || 1)
  const factor = unitCache[row.unit_category]?.factors?.[row.input_unit] ?? 1
  return qty * factor
}

/* 基础单位数量 → 物料【显示单位】的数量。
   开单用了别的单位时才给对照："5 斤 = 2.5 公斤" */
function displayQty(row) {
  const factor = unitCache[row.unit_category]?.factors?.[row.unit] ?? 1
  return baseQty(row) / factor
}

// 各行录入单位可能不同，总数量只在同单位时才有意义，这里按录入值直接求和
const totalQty = computed(() => lines.value.reduce((s, l) => s + (Number(l.input_qty) || 0), 0))
// 金额：单价锚定【物料显示单位】→ 用 displayQty（与后端 total_amount = from_base(...) × price 一致）
const totalAmount = computed(() => lines.value.reduce((s, l) => s + displayQty(l) * (l.price || 0), 0))
// 成本侧：avg_cost 是【每显示单位】的成本（后端 review 时除以 from_base 得来），
// 所以要配【显示单位】的数量：displayQty × avg_cost
const totalCost = computed(() => lines.value.reduce((s, l) => s + displayQty(l) * (l.avg_cost || 0), 0))
const totalProfit = computed(() => totalAmount.value - totalCost.value)

// 同一个「单价」列在不同单据下的语义完全不同：入库=采购价、出库=售价、退货=退货价（报废不涉及成交价）
const PRICE_LABELS = { 1: '采购单价 (¥)', 2: '销售单价 (¥)', 3: '退货单价 (¥)', 4: '单价 (¥)' }
const AMOUNT_LABELS = { 1: '采购金额', 2: '销售金额', 3: '退货金额', 4: '报废损失' }
const priceLabel = computed(() => PRICE_LABELS[form.order_type] || '单价 (¥)')
const amountLabel = computed(() => AMOUNT_LABELS[form.order_type] || '金额')

// 单行毛利 = (售价 − 参考成本) × 数量
// 单行毛利 = 销售额(显示单位计价) − 结转成本(显示单位计价)
function lineProfit(row) {
  return displayQty(row) * (row.price || 0) - displayQty(row) * (row.avg_cost || 0)
}

function fmtMoney(n) {
  return Number(n || 0).toFixed(2)
}

// 展示数量：去掉浮点尾巴（2.5000000001 → 2.5，40 → 40）
function fmtQty(n) {
  return Number(Number(n ?? 0).toFixed(3))
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

async function addPicked(id) {
  if (id == null) return
  const o = pickerOptions.value.find((x) => x.id === id)
  pickerId.value = null
  if (!o) return
  if (lines.value.some((l) => l.inventory_id === o.id)) {
    ElMessage.warning(`「${o.name}」已在明细中`)
    return
  }
  await ensureUnitMeta(o.unit_category)
  lines.value.push({
    inventory_id: o.id,
    code: o.code,
    name: o.name,
    type: o.type || '',
    unit: o.unit || '',
    unit_category: o.unit_category || 'count',
    unit_base: o.unit_base || '',   // 基础单位（克/个...），用于显示"= 2500 克"换算提示
    stock: o.stock ?? 0,            // 基础单位：库存够不够的比较用它
    stock_display: o.stock_display ?? o.stock ?? 0,   // 显示单位：界面上给人看
    avg_cost: o.avg_cost ?? null,   // 参考成本（当前库存均价）
    packages: o.packages || [],     // 包装规格（大小件）：开单可按「箱」录入
    input_qty: 1,                   // 用户录入的数量（按 input_unit 计）
    input_unit: o.unit || '',       // 默认用物料的显示单位
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
  // 业务日期带时间；选择器被清空时兜底为当前时刻
  const dateStr = (form.date || fmtDateTimeFull(new Date())).replace(' ', 'T')
  return {
    order_type: form.order_type,
    transaction_date: toLocalIso(new Date(dateStr)),
    supplier_id: usesSupplier(form.order_type) ? form.supplier_id : null,
    customer_id: usesCustomer(form.order_type) ? form.customer_id : null,
    remark: form.remark || null,
    items: lines.value.map((l) => ({
      inventory_id: l.inventory_id,
      input_qty: Number(l.input_qty) || 0,          // 用户录入的数量
      input_unit: l.input_unit || l.unit || null,   // 用户录入的单位（后端负责换算成基础单位）
      price: l.price || 0
    }))
  }
}

async function submit() {
  if (!lines.value.length) {
    ElMessage.warning('请先添加物料明细')
    return
  }
  const bad = lines.value.find((l) => !(Number(l.input_qty) > 0))
  if (bad) {
    ElMessage.warning(`「${bad.name}」的数量必须大于 0`)
    return
  }
  if (usesSupplier(form.order_type) && !form.supplier_id) {
    ElMessage.warning(form.order_type === 1 ? '入库单请选择供应商' : '退货单请选择供应商')
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
  form.customer_id = order.customer_id ?? null
  form.remark = order.remark || ''
  const raw = order.transaction_date ? String(order.transaction_date) : ''
  // 保留时间部分（"2026-10-09T13:06:59" → "2026-10-09 13:06:59"），只截到秒
  form.date = raw.slice(0, 19).replace('T', ' ') || fmtDateTimeFull(new Date())

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
      unit_category: cur.unit_category || 'count',
      unit_base: cur.unit_base || '',
      stock: cur.stock ?? 0,
      stock_display: cur.stock_display ?? cur.stock ?? 0,
      avg_cost: cur.avg_cost ?? null,   // 参考成本（当前库存均价）
      packages: cur.packages || [],     // 包装规格（大小件）
      // 优先用录入值；老单据没有 input_* 就用 quantity_display（已换算成显示单位）
      input_qty: Number(it.input_qty ?? it.quantity_display ?? it.quantity ?? 0),
      input_unit: it.input_unit || it.item_unit || cur.unit || '',
      price: Number(it.unit_price ?? it.price ?? 0)
    }
  })
  // 单位表要提前拉齐，后面 baseQty() 才算得出"库存不足"和报废损失
  await Promise.all(lines.value.map((l) => ensureUnitMeta(l.unit_category)))
}

async function quickAddInventory(inventoryId) {
  try {
    const o = await getInventory(inventoryId)
    await ensureUnitMeta(o.unit_category)
    lines.value.push({
      inventory_id: o.id,
      code: o.code,
      name: o.name,
      type: o.type || '',
      unit: o.unit || '',
      unit_category: o.unit_category || 'count',
      unit_base: o.unit_base || '',
      stock: o.stock ?? 0,
      stock_display: o.stock_display ?? o.stock ?? 0,
      avg_cost: o.avg_cost ?? null,   // 参考成本（当前库存均价）
      packages: o.packages || [],     // 包装规格（大小件）：开单可按「箱」录入
      input_qty: 1,
      input_unit: o.unit || '',
      price: 0
    })
    ElMessage.success(`已添加「${o.name}」`)
  } catch (e) {
    /* ignore */
  }
}

onMounted(async () => {
  suppliers.value = await listSupplier()
  customers.value = await listCustomer()
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
/* 数量单元格：数字输入 + 单位下拉 并排 */
.qty-cell {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
}
.qty-input {
  width: 96px;
}
/* 单位选择器：平时伪装成纯文本（无边框无阴影），点一下才展开 */
.qty-unit-plain {
  width: 58px;
}
.qty-unit-plain :deep(.el-select__wrapper) {
  box-shadow: none !important;
  background: transparent;
  padding: 0 2px;
  min-height: 22px;
}
.qty-unit-text {
  font-size: 12px;
  color: #6b7488;
}
/* 换算提示：= 2.5 公斤（只在换了单位时出现） */
.qty-hint {
  margin-top: 2px;
  font-size: 11px;
  color: #8a94a6;
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
.sum-cost {
  color: #d98800;
  font-weight: 700;
}
.sum-profit {
  color: #2f9e44;
  font-weight: 700;
}
.sum-loss {
  color: #f56c6c;
  font-weight: 700;
}
/* 明细行里的参考成本 / 单行毛利 */
.ref-cost {
  font-size: 13px;
  color: #d98800;
  font-weight: 600;
}
.line-profit,
.line-loss {
  font-size: 12px;
}
.line-profit {
  color: #2f9e44;
}
.line-loss {
  color: #f56c6c;
}
.text-muted {
  color: #c0c4cc;
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

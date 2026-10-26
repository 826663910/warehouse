<template>
  <div class="page-container">
    <!-- 单据信息 -->
    <div v-loading="loading" class="page-card">
      <div class="head-bar">
        <div class="head-left">
          <el-button :icon="Back" @click="goList">返回列表</el-button>
          <span class="head-title">单据详情</span>
          <el-tag v-if="order" class="mono" type="info" effect="plain">{{ order.order_no }}</el-tag>
        </div>
        <div v-if="order && order.status === 1" class="head-right">
          <el-button type="warning" :icon="EditPen" @click="goEdit">编辑</el-button>
          <el-button type="success" :icon="CircleCheck" :loading="reviewing" @click="handleReview">
            审核该单据
          </el-button>
        </div>
      </div>

      <el-empty v-if="!order && !loading" description="单据不存在或已被删除" />

      <el-descriptions v-if="order" :column="3" border size="small">
        <el-descriptions-item label="单据号">
          <span class="mono">{{ order.order_no }}</span>
        </el-descriptions-item>
        <el-descriptions-item label="类型">
          <el-tag :type="ORDER_TYPES[order.order_type]?.tag" effect="dark" size="small">
            {{ ORDER_TYPES[order.order_type]?.label || `未知(${order.order_type})` }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="ORDER_STATUS[order.status]?.tag" effect="light" size="small">
            {{ ORDER_STATUS[order.status]?.label || `未知(${order.status})` }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="业务日期">{{ fmtDateTimeFull(order.transaction_date) }}</el-descriptions-item>
        <el-descriptions-item label="合作方">
          <template v-if="order.order_type === 4">
            <!-- 报废是仓库内部处理，没有合作方 -->
            <span class="text-muted">—</span>
          </template>
          <template v-else>
            <el-tag v-if="isSupplierType(order.order_type)" size="small" effect="light" type="primary" class="role-tag">供应商</el-tag>
            <el-tag v-else size="small" effect="light" type="warning" class="role-tag">客户</el-tag>
            <span class="partner-name">
              {{ isSupplierType(order.order_type) ? supplierName(order.supplier_id) : customerName(order.customer_id) }}
            </span>
          </template>
        </el-descriptions-item>
        <el-descriptions-item label="制单人">{{ order.created_by }}</el-descriptions-item>
        <el-descriptions-item label="备注" :span="3">{{ order.remark || '—' }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <!-- 物料明细 -->
    <div v-if="order" class="page-card mt-card">
      <div class="card-head">
        <span class="head-title">物料明细</span>
        <span class="text-muted">共 {{ items.length }} 项</span>
      </div>

      <el-table :data="items" size="small" stripe empty-text="该单据没有物料明细">
        <el-table-column label="#" type="index" width="45" align="center" />
        <el-table-column prop="item_code" label="编码" width="95" />
        <el-table-column prop="item_name" label="物料名称" min-width="170" />
        <el-table-column prop="item_type" label="型号" min-width="110">
          <template #default="{ row }">{{ row.item_type || '—' }}</template>
        </el-table-column>
        <el-table-column label="数量" width="130" align="center">
          <template #default="{ row }">
            <!-- 展示用 quantity_display（后端已换算成【物料显示单位】）；
                 quantity 是基础单位，不能直接给人看 -->
            <div>{{ fmtQty(row.quantity_display ?? row.quantity) }} {{ row.item_unit }}</div>
            <!-- 录入单位和物料单位不一致时，把当时填的也标出来 -->
            <div v-if="row.input_unit && row.input_unit !== row.item_unit" class="cell-hint">
              录入 {{ row.input_qty }} {{ row.input_unit }}
            </div>
          </template>
        </el-table-column>
        <!-- 报废单没有"成交价"：单价列隐藏（它存的是成本均价，不是价格），损失看金额列 -->
        <el-table-column v-if="order?.order_type !== 4" :label="priceLabel" width="110" align="right">
          <template #default="{ row }">
            {{ priceOf(row) != null ? `¥ ${fmtMoney(priceOf(row))}` : '—' }}
          </template>
        </el-table-column>
        <el-table-column :label="amountLabel" width="120" align="right">
          <template #default="{ row }"><b>¥ {{ fmtMoney(amountOf(row)) }}</b></template>
        </el-table-column>
      </el-table>

      <div class="foot-bar">
        <div class="sums">
          <span>共 <b>{{ items.length }}</b> 项物料</span>
          <span>总数量：<b>{{ totalQty }}</b></span>
          <span v-if="hasPrice">{{ amountLabel }}：<b class="sum-amount">¥ {{ fmtMoney(totalAmount) }}</b></span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, CircleCheck, EditPen } from '@element-plus/icons-vue'
import { getOrder, listSupplier, listCustomer, reviewOrder } from '@/api'
import { ORDER_TYPES, ORDER_STATUS, fmtDateTimeFull } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const reviewing = ref(false)
const order = ref(null)
const suppliers = ref([])
const customers = ref([])

const items = computed(() => order.value?.items || [])
const hasPrice = computed(() => items.value.some((i) => priceOf(i) != null))

// 同一列在不同单据下的语义：入库=采购价、出库=售价、退货=退货价（报废无成交价，存的是成本均价）
const PRICE_LABELS = { 1: '采购单价', 2: '销售单价', 3: '退货单价' }
const AMOUNT_LABELS = { 1: '采购金额', 2: '销售金额', 3: '退货金额', 4: '报废损失' }
const priceLabel = computed(() => PRICE_LABELS[order.value?.order_type] || '单价')
const amountLabel = computed(() => AMOUNT_LABELS[order.value?.order_type] || '金额')
// 合计用展示值（各行物料单位可能不同，这个数仅供参考）
const totalQty = computed(() => items.value.reduce((s, i) => s + (Number(i.quantity_display ?? i.quantity) || 0), 0))
const totalAmount = computed(() => items.value.reduce((s, i) => s + amountOf(i), 0))

const supplierMap = computed(() => {
  const m = new Map()
  suppliers.value.forEach((s) => m.set(s.id, s.name))
  return m
})

const customerMap = computed(() => {
  const m = new Map()
  customers.value.forEach((c) => m.set(c.id, c.name))
  return m
})

function supplierName(id) {
  return id ? supplierMap.value.get(id) || `#${id}` : '—'
}

function customerName(id) {
  return id ? customerMap.value.get(id) || `#${id}` : '—'
}

// 合作方判定：入库/退货 = 供应商，出库 = 客户（报废在模板里特判）
function isSupplierType(t) {
  return t === 1 || t === 3
}

function priceOf(row) {
  return row.unit_price != null ? row.unit_price : row.price
}

// 后端给了 total_amount 就用它，否则按 数量 × 单价 兜底
function amountOf(row) {
  if (row.total_amount != null) return Number(row.total_amount)
  // 后端 total_amount = 显示单位数量 × 单价，兜底也要同口径
  return priceOf(row) != null ? Number(priceOf(row)) * (Number(row.quantity_display ?? row.quantity) || 0) : 0
}

function fmtMoney(n) {
  return Number(n || 0).toFixed(2)
}

// 展示数量：去掉浮点尾巴（2.5000000001 → 2.5，40 → 40）
function fmtQty(n) {
  return Number(Number(n || 0).toFixed(3))
}

function goList() {
  router.push('/orders')
}

function goEdit() {
  router.push(`/orders/edit/${order.value.id}`)
}

async function load() {
  loading.value = true
  try {
    order.value = await getOrder(route.params.id)
  } catch (e) {
    order.value = null // 错误提示由 axios 拦截器统一处理
  } finally {
    loading.value = false
  }
}

async function handleReview() {
  try {
    await ElMessageBox.confirm(
      `审核后库存将立即生效且不可再编辑，确定审核单据「${order.value.order_no}」吗？`,
      '审核确认',
      { type: 'warning', confirmButtonText: '确定审核', cancelButtonText: '再想想' }
    )
  } catch (e) {
    return
  }
  reviewing.value = true
  try {
    await reviewOrder(order.value.id)
    ElMessage.success('审核成功，库存已更新')
    await load() // 重新拉一次，状态变为已审核
  } finally {
    reviewing.value = false
  }
}

// 同一个组件实例内切换单据 id（改 URL hash / 从详情跳详情）时重新加载
watch(() => route.params.id, load)

onMounted(() => {
  load()
  listSupplier().then((list) => {
    suppliers.value = list
  })
  listCustomer().then((list) => {
    customers.value = list
  })
})
</script>

<style scoped>
.head-bar,
.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.head-bar {
  margin-bottom: 16px;
}
.head-left {
  display: flex;
  align-items: center;
  gap: 12px;
}
.head-right {
  display: flex;
  gap: 10px;
}
.head-title {
  font-size: 17px;
  font-weight: 700;
  color: #1f2d3d;
}
.mono {
  font-family: Consolas, 'Courier New', monospace;
}
/* 数量单元格下方的次要说明："录入 5 斤" */
.cell-hint {
  margin-top: 2px;
  font-size: 11px;
  color: #8a94a6;
}
.mt-card {
  margin-top: 14px;
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
/* 合作方：角色 tag + 名称 */
.role-tag {
  vertical-align: middle;
}
.partner-name {
  margin-left: 6px;
  vertical-align: middle;
}
.text-muted {
  color: #c0c4cc;
}
</style>

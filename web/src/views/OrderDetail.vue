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
        <el-descriptions-item label="供应商">{{ supplierName(order.supplier_id) }}</el-descriptions-item>
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
        <el-table-column label="数量" width="110" align="center">
          <template #default="{ row }">{{ row.quantity }} {{ row.item_unit }}</template>
        </el-table-column>
        <el-table-column label="单价" width="110" align="right">
          <template #default="{ row }">
            {{ priceOf(row) != null ? `¥ ${fmtMoney(priceOf(row))}` : '—' }}
          </template>
        </el-table-column>
        <el-table-column label="金额" width="120" align="right">
          <template #default="{ row }"><b>¥ {{ fmtMoney(amountOf(row)) }}</b></template>
        </el-table-column>
      </el-table>

      <div class="foot-bar">
        <div class="sums">
          <span>共 <b>{{ items.length }}</b> 项物料</span>
          <span>总数量：<b>{{ totalQty }}</b></span>
          <span v-if="hasPrice">单据金额：<b class="sum-amount">¥ {{ fmtMoney(totalAmount) }}</b></span>
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
import { getOrder, listSupplier, reviewOrder } from '@/api'
import { ORDER_TYPES, ORDER_STATUS, fmtDateTimeFull } from '@/utils/format'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const reviewing = ref(false)
const order = ref(null)
const suppliers = ref([])

const items = computed(() => order.value?.items || [])
const hasPrice = computed(() => items.value.some((i) => priceOf(i) != null))
const totalQty = computed(() => items.value.reduce((s, i) => s + (i.quantity || 0), 0))
const totalAmount = computed(() => items.value.reduce((s, i) => s + amountOf(i), 0))

const supplierMap = computed(() => {
  const m = new Map()
  suppliers.value.forEach((s) => m.set(s.id, s.name))
  return m
})

function supplierName(id) {
  return id ? supplierMap.value.get(id) || `#${id}` : '—'
}

function priceOf(row) {
  return row.unit_price != null ? row.unit_price : row.price
}

// 后端给了 total_amount 就用它，否则按 数量 × 单价 兜底
function amountOf(row) {
  if (row.total_amount != null) return Number(row.total_amount)
  return priceOf(row) != null ? Number(priceOf(row)) * (row.quantity || 0) : 0
}

function fmtMoney(n) {
  return Number(n || 0).toFixed(2)
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
</style>

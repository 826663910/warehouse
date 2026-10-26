<template>
  <div class="page-container">
    <div class="page-card">
      <div class="head-bar">
        <div>
          <span class="head-title">{{ isEdit ? '编辑物料' : '新增物料' }}</span>
          <el-tag v-if="isEdit && code" class="ml8" type="info" effect="plain">{{ code }}</el-tag>
        </div>
        <el-button :icon="Back" @click="goBack()">返回列表</el-button>
      </div>

      <el-form
        ref="formRef"
        v-loading="loading"
        :model="form"
        :rules="rules"
        label-width="96px"
        class="inv-form"
      >
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
                :disabled="!isEdit"
              />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="所属分类" prop="category_id">
              <el-select v-model="form.category_id" placeholder="请选择末级分类" style="width: 100%">
                <el-option v-for="c in categoryOptions" :key="c.id" :label="c.name" :value="c.id" />
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
            <el-form-item label="单位类型" prop="unit_category">
              <el-select v-model="form.unit_category" placeholder="请选择单位类型" style="width: 100%">
                <el-option v-for="c in UNIT_CATEGORIES" :key="c.value" :label="c.label" :value="c.value" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="单位" prop="unit">
              <!-- count 赛道没有换算表，退回自由输入（个 / 只 / 台 / 袋 / 箱 / 套…随便填） -->
              <el-input
                v-if="form.unit_category === 'count'"
                v-model="form.unit"
                placeholder="自定义单位，如：台"
                clearable
              />
              <el-select v-else v-model="form.unit" placeholder="请先选单位类型" style="width: 100%">
                <el-option v-for="u in unitOptions" :key="u" :label="u" :value="u" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="初始库存" prop="stock">
              <el-input-number v-model="form.stock" :min="0" :precision="0" style="width: 100%" />
            </el-form-item>
          </el-col>
          <el-col v-if="isEdit" :span="12">
            <el-form-item label="成本均价">
              <el-input :model-value="form.avg_cost ? `¥ ${fmtMoney(form.avg_cost)}` : '暂无成本'" disabled />
              <div class="form-hint">移动加权平均成本，由入库单审核时自动重算，不可手工修改</div>
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
          <el-col v-if="isEdit" :span="12">
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

      <!-- ===== 包装规格（大小件）===== -->
      <div class="pkg-block">
        <div class="pkg-head">
          <span class="pkg-title">包装规格</span>
          <el-button link type="primary" :icon="Plus" @click="addPackage">添加包装</el-button>
        </div>
        <div class="pkg-hint">
          开单时可直接按包装单位录入（如「3 箱」），系统自动换算成 {{ baseUnitLabel }}。
          包装名不能与物料单位「{{ form.unit || '—' }}」相同。
        </div>

        <el-table v-if="form.packages.length" :data="form.packages" size="small" border>
          <el-table-column label="包装单位" min-width="130">
            <template #default="{ row }">
              <el-input v-model="row.unit_name" placeholder="如：箱 / 盒" size="small" />
            </template>
          </el-table-column>
          <el-table-column :label="`1 包装 = 多少 ${baseUnitLabel}`" min-width="160">
            <template #default="{ row }">
              <el-input-number
                v-model="row.qty_per_base"
                :min="1"
                :precision="0"
                size="small"
                style="width: 100%"
              />
            </template>
          </el-table-column>
          <el-table-column label="换算" min-width="160">
            <template #default="{ row }">
              <span class="pkg-demo">
                1 {{ row.unit_name || '?' }} = {{ row.qty_per_base || 0 }} {{ baseUnitLabel }}
              </span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="70" align="center">
            <template #default="{ $index }">
              <el-button link type="danger" size="small" @click="removePackage($index)">删除</el-button>
            </template>
          </el-table-column>
        </el-table>
        <div v-else class="pkg-empty">暂无包装规格，点「添加包装」新增</div>
      </div>

      <div class="foot-bar">
        <el-button @click="goBack()">取 消</el-button>
        <el-button type="primary" :loading="saving" @click="submit">保 存</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Back, Plus } from '@element-plus/icons-vue'
import {
  getInventory,
  createInventory,
  updateInventory,
  listSupplier,
  listCategory,
  getUnits
} from '@/api'

const route = useRoute()
const router = useRouter()

// 路由带 id = 编辑，不带 = 新增（与 orders/edit/:id? 同一套约定）
const id = computed(() => {
  const n = Number(route.params.id)
  return Number.isInteger(n) && n > 0 ? n : null
})
const isEdit = computed(() => id.value != null)

const loading = ref(false)
const saving = ref(false)
const formRef = ref(null)
const code = ref('')            // 编辑时展示物料编码（只读）
const supplierList = ref([])
const categoryList = ref([])

// 单位类型（赛道）：决定"单位"下拉里能选哪些
const UNIT_CATEGORIES = [
  { value: 'count', label: '数量' },
  { value: 'weight', label: '重量' },
  { value: 'length', label: '长度' },
  { value: 'volume', label: '体积' }
]
const unitOptions = ref([])     // 当前赛道下可选单位，来自 GET /units/?category=xxx

const form = reactive({
  id: null,
  name: '',
  type: '',
  mnemonic_code: '',
  category_id: null,
  supplier_id: null,
  unit_category: 'count',
  unit: '个',
  stock: 0,
  avg_cost: null,     // 只读：编辑时展示，不参与提交
  warning: null,
  status: 1,
  // 包装规格（大小件）。保存时整批提交，后端是全量替换（先删旧再插新）
  packages: []
})

const rules = {
  name: [{ required: true, message: '请输入物料名称', trigger: 'blur' }],
  category_id: [{ required: true, message: '请选择末级分类', trigger: 'change' }],
  supplier_id: [{ required: true, message: '请选择供应商', trigger: 'change' }],
  unit_category: [{ required: true, message: '请选择单位类型', trigger: 'change' }],
  unit: [{ required: true, message: '请选择单位', trigger: 'change' }]
}

// 拉取某赛道的可选单位。抽成独立函数，是为了让 loadDetail 能 await 它：
// 否则回填 form.unit 时选项还没到，el-select 匹配不到就显示空白（时好时坏的竞态）
async function loadUnitOptions(cat) {
  // count 赛道没有换算表：单位由用户自己填，下拉给空（前端回退成文本框）
  if (!cat || cat === 'count') {
    unitOptions.value = []
    return
  }
  try {
    const res = await getUnits(cat)
    unitOptions.value = res.units || []
  } catch (e) {
    console.error('[units] 拉取单位选项失败', cat, e)
    unitOptions.value = []
  }
}

// 回填详情期间为 true：watcher 不插手，由 loadDetail 自己按序处理，避免重复请求和误清空
let applyingDetail = false

/* 用户手动改赛道时才清空旧单位 */
watch(
  () => form.unit_category,
  async (cat) => {
    if (applyingDetail) return
    await loadUnitOptions(cat)
    if (form.unit && unitOptions.value.length && !unitOptions.value.includes(form.unit)) {
      form.unit = ''
    }
  },
  { immediate: true }
)

/* 只允许选择末级分类 */
const categoryOptions = computed(() => {
  const hasChild = new Set(categoryList.value.filter((c) => c.parent_id !== 0).map((c) => c.parent_id))
  return categoryList.value
    .filter((c) => !hasChild.has(c.id))
    .map((c) => ({ id: c.id, name: c.name }))
})

function fmtMoney(n) {
  return Number(n || 0).toFixed(2)
}

/* ===== 包装规格（大小件）===== */

// 包装的 qty_per_base 是相对【基础单位】的。换算表里 factor=1 的那个才是基础单位，
// count 赛道没有换算表，基础单位就是物料自己填的那个单位。这里只用于界面文案。
const BASE_UNIT = { weight: '克', length: '毫米', volume: '毫升' }
const baseUnitLabel = computed(() => BASE_UNIT[form.unit_category] || form.unit || '基础单位')

function addPackage() {
  form.packages.push({ unit_name: '', qty_per_base: 1 })
}

function removePackage(index) {
  form.packages.splice(index, 1)
}

// 后端也有这些校验（拦成 400），这里先拦一次，省一次往返
function validatePackages() {
  const names = form.packages.map((p) => (p.unit_name || '').trim())
  if (names.some((n) => !n)) {
    ElMessage.warning('包装单位名称不能为空')
    return false
  }
  if (new Set(names).size !== names.length) {
    ElMessage.warning('包装单位名称不能重复')
    return false
  }
  if (form.unit && names.includes(form.unit)) {
    ElMessage.warning(`包装名不能与物料单位「${form.unit}」相同`)
    return false
  }
  if (form.packages.some((p) => !(Number(p.qty_per_base) > 0))) {
    ElMessage.warning('每包数量必须大于 0')
    return false
  }
  return true
}

// 返回列表：优先 back()，这样列表页 URL 上的筛选 / 排序 / 分页query能保住，
// 且路由变化会让 Inventory.vue 重新挂载 → onMounted 自动重新 load()，新数据直接可见。
// 直接输地址进来（没有上一条历史）时才退化成 push，避免 back 退出应用。
function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/inventory')
}

async function loadDetail() {
  if (!isEdit.value) return
  loading.value = true
  applyingDetail = true
  try {
    const detail = await getInventory(id.value)
    code.value = detail.code || ''
    form.id = detail.id
    form.name = detail.name
    form.type = detail.type || ''
    form.mnemonic_code = detail.mnemonic_code || ''
    form.category_id = detail.category_id ?? null
    form.supplier_id = detail.supplier_id ?? null
    form.unit_category = detail.unit_category || 'count'
    // 先等该赛道的单位选项就位，再回填单位值，否则 el-select 匹配不到会显示空白
    await loadUnitOptions(form.unit_category)
    form.unit = detail.unit || '个'
    form.stock = detail.stock_display ?? detail.stock ?? 0
    form.avg_cost = detail.avg_cost ?? null
    form.warning = detail.warning_display ?? detail.warning ?? null
    form.status = detail.status ?? 1
    form.packages = (detail.packages || []).map((p) => ({
      id: p.id,
      unit_name: p.unit_name,
      qty_per_base: p.qty_per_base
    }))
  } finally {
    applyingDetail = false
    loading.value = false
  }
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
  if (!validatePackages()) return
  saving.value = true
  try {
    const payload = {
      name: form.name,
      type: form.type || null,
      mnemonic_code: form.mnemonic_code || null,
      category_id: form.category_id,
      supplier_id: form.supplier_id,
      unit_category: form.unit_category,
      unit: form.unit,
      stock: form.stock,
      warning: form.warning,
      // 整批提交（后端全量替换），id 不传
      packages: form.packages.map((p) => ({
        unit_name: (p.unit_name || '').trim(),
        qty_per_base: Number(p.qty_per_base)
      }))
    }
    if (isEdit.value) {
      // 编辑额外带 status；创建不用传，后端 schema 里 server_default=1 兜底
      await updateInventory(form.id, { ...payload, status: form.status })
      ElMessage.success('保存成功')
    } else {
      await createInventory(payload)
      ElMessage.success('新增成功')
    }
    goBack()
  } catch (e) {
    /* 拦截器已提示 */
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  // 分类 / 供应商先拉，编辑态还要等详情回来才知道选中谁
  const [sups, cats] = await Promise.all([listSupplier(), listCategory()])
  supplierList.value = sups
  categoryList.value = cats
  await loadDetail()
})
</script>

<style scoped>
.head-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
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
/* 整页比弹窗宽得多，给表单限个宽，两列不至于拉散 */
.inv-form {
  max-width: 900px;
}
.form-hint {
  font-size: 12px;
  color: #a0a8b8;
  line-height: 1.4;
  margin-top: 2px;
}
/* ===== 包装规格 ===== */
.pkg-block {
  max-width: 900px;
  margin-top: 22px;
  padding-top: 16px;
  border-top: 1px solid #eef1f7;
}
.pkg-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 4px;
}
.pkg-title {
  font-size: 15px;
  font-weight: 600;
  color: #1f2d3d;
}
.pkg-hint {
  font-size: 12px;
  color: #a0a8b8;
  line-height: 1.5;
  margin-bottom: 10px;
}
.pkg-demo {
  color: #8a94a6;
}
.pkg-empty {
  font-size: 13px;
  color: #b0b7c3;
  padding: 14px 0;
  text-align: center;
  border: 1px dashed #e4e8f0;
  border-radius: 6px;
}
.foot-bar {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #eef1f7;
  max-width: 900px;
}
</style>

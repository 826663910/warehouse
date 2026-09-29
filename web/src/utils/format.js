export function pad2(n) {
  return String(n).padStart(2, '0')
}

// YYYY-MM-DD
export function fmtDate(d) {
  if (!d) return ''
  const dt = d instanceof Date ? d : new Date(d)
  if (Number.isNaN(dt.getTime())) return String(d).slice(0, 10)
  return `${dt.getFullYear()}-${pad2(dt.getMonth() + 1)}-${pad2(dt.getDate())}`
}

// YYYY-MM-DD HH:mm
export function fmtDateTime(d) {
  if (!d) return ''
  const dt = d instanceof Date ? d : new Date(d)
  if (Number.isNaN(dt.getTime())) return String(d).replace('T', ' ').slice(0, 16)
  return `${fmtDate(dt)} ${pad2(dt.getHours())}:${pad2(dt.getMinutes())}`
}

// YYYY-MM-DD HH:mm:ss
export function fmtDateTimeFull(d) {
  if (!d) return ''
  const dt = d instanceof Date ? d : new Date(d)
  if (Number.isNaN(dt.getTime())) return String(d).replace('T', ' ').slice(0, 19)
  return `${fmtDate(dt)} ${pad2(dt.getHours())}:${pad2(dt.getMinutes())}:${pad2(dt.getSeconds())}`
}

// 生成本地时间 ISO 串，供后端 datetime 字段
export function toLocalIso(d) {
  const dt = d instanceof Date ? d : new Date(d)
  const tzOff = dt.getTimezoneOffset() * 60000
  return new Date(dt.getTime() - tzOff).toISOString().slice(0, 19)
}

// 单据类型映射
export const ORDER_TYPES = {
  1: { label: '入库', tag: 'primary', icon: 'download' },
  2: { label: '出库', tag: 'danger', icon: 'upload' },
  3: { label: '退货', tag: 'warning', icon: 'refresh-left' },
  4: { label: '报废', tag: 'info', icon: 'delete' }
}

// 单据状态映射
export const ORDER_STATUS = {
  1: { label: '草稿', tag: 'info' },
  2: { label: '已审核', tag: 'success' },
  3: { label: '已作废', tag: 'danger' }
}

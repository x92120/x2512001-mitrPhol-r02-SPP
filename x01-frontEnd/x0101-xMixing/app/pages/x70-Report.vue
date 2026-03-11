<template>
    <div class="row q-col-gutter-lg q-pa-md" style="height: calc(100vh - 56px);">
        <!-- Controls Pane -->
        <div class="col-12 col-md-4">
            <q-card flat bordered class="rounded-borders-xl">
                <q-card-section class="bg-primary text-white row items-center">
                    <q-icon name="picture_as_pdf" size="md" class="q-mr-sm" />
                    <div class="text-h6">Report Generator</div>
                </q-card-section>

                <q-card-section>
                    <q-select
                        v-model="selectedType"
                        :options="reportTypes"
                        label="Report Type"
                        outlined dense
                        class="q-mb-md"
                        color="primary"
                        emit-value map-options
                    />

                    <!-- Plan selector (for plan-based reports) -->
                    <transition name="fade">
                        <div v-if="needsPlanSelect">
                            <q-select
                                v-model="selectedPlan"
                                :options="planOptions"
                                label="Select Plan"
                                outline dense
                                class="q-mb-md"
                                color="primary"
                            >
                                <template v-slot:no-option>
                                    <q-item><q-item-section class="text-italic text-grey">No plans available</q-item-section></q-item>
                                </template>
                            </q-select>
                        </div>
                    </transition>

                    <!-- Batch ID input (for traceability) -->
                    <transition name="fade">
                        <div v-if="selectedType === 'traceability'">
                            <q-input
                                v-model="traceId"
                                label="Lot ID or Batch ID"
                                outlined dense
                                class="q-mb-md"
                                placeholder="e.g. LOT-001 or P260309-03-01-001"
                            />
                        </div>
                    </transition>

                    <!-- Date picker (for daily / date-range reports) -->
                    <transition name="fade">
                        <div v-if="needsDatePicker">
                            <q-input v-model="reportDate" label="Date" type="date" outlined dense class="q-mb-md" />
                        </div>
                    </transition>

                    <!-- Date range (for prebatch summary, quality check) -->
                    <transition name="fade">
                        <div v-if="needsDateRange" class="row q-gutter-sm q-mb-md">
                            <q-input v-model="dateFrom" label="From" type="date" outlined dense class="col" />
                            <q-input v-model="dateTo" label="To" type="date" outlined dense class="col" />
                        </div>
                    </transition>

                    <q-btn
                        color="indigo-8"
                        icon="picture_as_pdf"
                        label="Generate PDF Preview"
                        class="full-width q-mt-md"
                        :disable="!canGenerate"
                        :loading="isGenerating"
                        @click="generatePreview"
                        unelevated
                    />
                </q-card-section>

                <!-- Action buttons -->
                <q-card-section v-if="pdfBlobUrl" class="q-pt-none">
                    <q-separator class="q-mb-md" />
                    <div class="text-subtitle2 text-grey-7 q-mb-sm">
                        <q-icon name="check_circle" color="green" size="xs" class="q-mr-xs" />
                        PDF ready — {{ pdfFileName }}
                    </div>
                    <div class="row q-gutter-sm">
                        <q-btn color="green-7" icon="download" label="Download" unelevated no-caps class="col" @click="downloadPdf" />
                        <q-btn color="blue-7" icon="email" label="Email" unelevated no-caps class="col" @click="showEmailDialog = true" />
                    </div>
                </q-card-section>
            </q-card>
        </div>

        <!-- PDF Preview Pane -->
        <div class="col-12 col-md-8" style="height: 100%;">
            <q-card flat bordered class="rounded-borders-xl column" style="height: 100%;">
                <q-card-section class="bg-grey-9 text-white row items-center justify-between q-py-xs">
                    <div class="row items-center q-gutter-xs">
                        <q-icon name="preview" size="sm" />
                        <div class="text-subtitle1 text-weight-bold">PDF Preview</div>
                    </div>
                    <div v-if="pdfBlobUrl" class="row items-center q-gutter-xs">
                        <q-btn flat dense round icon="print" size="sm" color="white" @click="printPdf"><q-tooltip>Print</q-tooltip></q-btn>
                        <q-btn flat dense round icon="open_in_new" size="sm" color="white" @click="openInNewTab"><q-tooltip>Open in New Tab</q-tooltip></q-btn>
                    </div>
                </q-card-section>
                <div class="col relative-position">
                    <div v-if="!pdfBlobUrl && !isGenerating" class="fit flex flex-center text-grey-5" style="flex-direction: column;">
                        <q-icon name="picture_as_pdf" size="80px" class="q-mb-md" style="opacity: 0.3;" />
                        <div class="text-h6 text-weight-medium">No Preview Available</div>
                        <div class="text-caption q-mt-xs text-center" style="max-width: 300px;">Select a report type and click "Generate PDF Preview".</div>
                    </div>
                    <div v-if="isGenerating" class="fit flex flex-center">
                        <q-spinner-gears size="60px" color="primary" />
                        <div class="text-subtitle1 q-ml-md text-grey-7">Generating PDF...</div>
                    </div>
                    <iframe v-if="pdfBlobUrl" :src="pdfBlobUrl" class="fit" style="border: none; background: #f0f0f0;" />
                </div>
            </q-card>
        </div>

        <!-- Email Dialog -->
        <q-dialog v-model="showEmailDialog" persistent>
            <q-card style="min-width: 420px;">
                <q-card-section class="bg-blue-7 text-white row items-center">
                    <q-icon name="email" size="sm" class="q-mr-sm" /><div class="text-h6">Send Report via Email</div>
                    <q-space /><q-btn flat round dense icon="close" color="white" v-close-popup />
                </q-card-section>
                <q-card-section>
                    <q-input v-model="emailTo" label="Recipient Email" type="email" outlined dense class="q-mb-md" placeholder="example@company.com" :rules="[val => !!val || 'Required', val => /.+@.+\..+/.test(val) || 'Invalid email']"><template v-slot:prepend><q-icon name="person" /></template></q-input>
                    <q-input v-model="emailSubject" label="Subject" outlined dense class="q-mb-md"><template v-slot:prepend><q-icon name="subject" /></template></q-input>
                    <q-input v-model="emailBody" label="Message (optional)" type="textarea" outlined dense rows="3"><template v-slot:prepend><q-icon name="message" /></template></q-input>
                </q-card-section>
                <q-card-actions align="right" class="q-pa-md">
                    <q-btn flat label="Cancel" color="grey" v-close-popup />
                    <q-btn unelevated icon="send" label="Send Email" color="blue-7" :loading="isSendingEmail" :disable="!emailTo || !/.+@.+\..+/.test(emailTo)" @click="sendEmail" />
                </q-card-actions>
            </q-card>
        </q-dialog>
    </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from 'vue'
import { appConfig } from '~/appConfig/config'
import { useQuasar } from 'quasar'
import { useAuth } from '~/composables/useAuth'

definePageMeta({ layout: 'default' })

const $q = useQuasar()
const { getAuthHeader } = useAuth()
const hdr = () => getAuthHeader() as Record<string, string>

// ═══════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════
const isGenerating = ref(false)
const reportTypes = [
    { label: '1. Production Plan Overview', value: 'plan-overview' },
    { label: '2. Batch Manufacturing Record', value: 'batch-record' },
    { label: '3. Ingredient Traceability', value: 'traceability' },
    { label: '4. Daily Production Summary', value: 'daily-summary' },
    { label: '5. Pre-Batch Summary', value: 'prebatch-summary' },
    { label: '6. Packing & Delivery', value: 'packing-delivery' },
    { label: '7. Stock & Expiry Alert', value: 'stock-expiry' },
    { label: '8. Quality Check Report', value: 'quality-check' },
]
const selectedType = ref('plan-overview')
const selectedPlan = ref<any>(null)
const productionPlans = ref<any[]>([])
const traceId = ref('')
const reportDate = ref(new Date().toISOString().slice(0, 10))
const dateFrom = ref(new Date().toISOString().slice(0, 10))
const dateTo = ref(new Date().toISOString().slice(0, 10))

const pdfBlobUrl = ref<string | null>(null)
const pdfFileName = ref('')
const showEmailDialog = ref(false)
const emailTo = ref('')
const emailSubject = ref('')
const emailBody = ref('')
const isSendingEmail = ref(false)

// ═══════════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════════
const planOptions = computed(() => productionPlans.value.map(p => ({ label: `${p.plan_id} - ${p.sku_name || p.sku_id}`, value: p.plan_id, ...p })))
const needsPlanSelect = computed(() => ['plan-overview', 'batch-record', 'packing-delivery'].includes(selectedType.value))
const needsDatePicker = computed(() => selectedType.value === 'daily-summary')
const needsDateRange = computed(() => ['prebatch-summary', 'quality-check'].includes(selectedType.value))
const canGenerate = computed(() => {
    if (needsPlanSelect.value) return !!selectedPlan.value
    if (selectedType.value === 'traceability') return !!traceId.value
    return true
})

// ═══════════════════════════════════════════════════════════════════
// LIFECYCLE
// ═══════════════════════════════════════════════════════════════════
onMounted(() => { fetchPlans() })
onUnmounted(() => { if (pdfBlobUrl.value) URL.revokeObjectURL(pdfBlobUrl.value) })

const fetchPlans = async () => {
    try {
        const resp = await $fetch<any>(`${appConfig.apiBaseUrl}/production-plans/`, { headers: hdr() })
        productionPlans.value = resp.plans || resp || []
    } catch (e) { console.error('Error fetching plans', e) }
}

// ═══════════════════════════════════════════════════════════════════
// SHARED CSS
// ═══════════════════════════════════════════════════════════════════
const CSS = `
@page { size: A4 portrait; margin: 15mm 20mm; }
@media print { .page-break { page-break-before: always; } }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:'Helvetica Neue',Arial,sans-serif; font-size:12px; color:#333; line-height:1.5; background:#fff; padding:24px 32px; }
.header { border-bottom:3px solid #1565c0; padding-bottom:12px; margin-bottom:20px; }
.header h1 { font-size:22px; font-weight:700; color:#1565c0; }
.header .sub { font-size:11px; color:#777; }
.section-title { font-size:14px; font-weight:700; color:#1565c0; border-left:4px solid #1565c0; padding-left:8px; margin:20px 0 10px; }
.batch-header { background:#1565c0; color:white; padding:10px 16px; border-radius:6px; margin:10px 0; display:flex; justify-content:space-between; align-items:center; }
.batch-header h2 { font-size:16px; font-weight:700; margin:0; }
.batch-header .meta { font-size:11px; opacity:0.9; }
table { width:100%; border-collapse:collapse; margin-bottom:14px; }
th { background:#e3f2fd; color:#0d47a1; font-weight:700; text-align:left; border-bottom:2px solid #90caf9; }
th, td { padding:7px 10px; font-size:10.5px; }
td { border-bottom:1px solid #e0e0e0; color:#333; }
tr:nth-child(even) td { background:#fafafa; }
.info-table { margin-bottom:16px; }
.info-table td { padding:6px 12px; }
.info-table .lbl { font-weight:700; color:#555; width:140px; background:#f5f5f5; }
.info-table .val { color:#111; font-weight:500; }
.footer { margin-top:30px; padding-top:10px; border-top:2px solid #e0e0e0; font-size:10px; color:#999; display:flex; justify-content:space-between; }
.badge { display:inline-block; padding:2px 10px; border-radius:4px; font-size:10px; font-weight:600; color:white; }
.badge-ok,.badge-green { background:#43a047; } .badge-pending,.badge-orange { background:#fb8c00; }
.badge-prep,.badge-blue { background:#1e88e5; } .badge-packed,.badge-purple { background:#7b1fa2; }
.badge-red { background:#e53935; } .badge-cyan { background:#00838f; } .badge-grey { background:#757575; }
.stat-row { display:flex; gap:16px; margin:10px 0 16px; }
.stat-box { flex:1; background:#f5f5f5; border-radius:6px; padding:10px 14px; text-align:center; border:1px solid #e0e0e0; }
.stat-box .num { font-size:20px; font-weight:700; color:#1565c0; }
.stat-box .lbl { font-size:9px; color:#777; text-transform:uppercase; letter-spacing:0.5px; }
.alert-expired { background:#ffebee !important; }
.alert-warning { background:#fff8e1 !important; }
.mono { font-family:monospace; font-size:9.5px; }
.sign-line { border-bottom:1px solid #333; width:200px; display:inline-block; margin-top:30px; }
`

const fmtDate = (d?: string|null) => d ? new Date(d).toLocaleDateString('en-GB') : '-'
const nowStr = () => { const n=new Date(); return n.toLocaleDateString('en-GB')+' '+n.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}) }
const wrap = (title: string, body: string) => `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title><style>${CSS}</style></head><body>${body}<div class="footer"><div>xMixing Control System v1.0</div><div>${title} | ${nowStr()}</div></div></body></html>`

// ═══════════════════════════════════════════════════════════════════
// GENERATE PREVIEW — ROUTER
// ═══════════════════════════════════════════════════════════════════
const generatePreview = async () => {
    isGenerating.value = true
    if (pdfBlobUrl.value) { URL.revokeObjectURL(pdfBlobUrl.value); pdfBlobUrl.value = null }

    try {
        let html = ''
        const t = selectedType.value
        if (t === 'plan-overview') html = await buildPlanOverview()
        else if (t === 'batch-record') html = await buildBatchRecord()
        else if (t === 'traceability') html = await buildTraceability()
        else if (t === 'daily-summary') html = await buildDailySummary()
        else if (t === 'prebatch-summary') html = await buildPrebatchSummary()
        else if (t === 'packing-delivery') html = await buildPackingDelivery()
        else if (t === 'stock-expiry') html = await buildStockExpiry()
        else if (t === 'quality-check') html = await buildQualityCheck()

        const blob = new Blob([html], { type: 'text/html' })
        pdfBlobUrl.value = URL.createObjectURL(blob)
        pdfFileName.value = `${t}_${Date.now()}.pdf`
        emailSubject.value = `xMixing Report — ${reportTypes.find(r => r.value === t)?.label || t}`
        $q.notify({ type: 'positive', icon: 'check_circle', message: 'PDF preview generated!', position: 'top', timeout: 2000 })
    } catch (e: any) {
        console.error('Report error:', e)
        $q.notify({ type: 'negative', message: 'Failed: ' + e.message })
    } finally { isGenerating.value = false }
}

// ═══════════════════════════════════════════════════════════════════
// 1. PRODUCTION PLAN OVERVIEW
// ═══════════════════════════════════════════════════════════════════
const buildPlanOverview = async () => {
    const plan = selectedPlan.value; const planId = plan.value
    const items = await $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-items/by-plan/${planId}`, { headers: hdr() }).catch(() => [])
    const bMap = new Map<string, any[]>()
    for (const it of (items || [])) { const b = it.batch_id||'?'; if (!bMap.has(b)) bMap.set(b,[]); bMap.get(b)!.push(it) }
    const batches = plan.batches || []

    let cover = `<div class="header"><h1>📋 Production Plan Report</h1><div class="sub">Generated: ${nowStr()}</div></div>
<div class="section-title">Plan Information</div>
<table class="info-table">
  <tr><td class="lbl">Plan ID</td><td class="val">${planId}</td><td class="lbl">SKU Name</td><td class="val">${plan.sku_name||plan.label||'-'}</td></tr>
  <tr><td class="lbl">Start Date</td><td class="val">${fmtDate(plan.start_date)}</td><td class="lbl">Finish Date</td><td class="val">${fmtDate(plan.finish_date)}</td></tr>
  <tr><td class="lbl">Total Volume</td><td class="val">${plan.total_plan_volume||plan.total_volume||'-'} kg</td><td class="lbl">Batches</td><td class="val">${batches.length}</td></tr>
</table>
<div class="section-title">Batch Overview</div>
<table><thead><tr><th>#</th><th>Batch ID</th><th>Size (kg)</th><th>Items</th><th>Status</th></tr></thead><tbody>
${batches.map((b:any,i:number)=>{const its=bMap.get(b.batch_id)||[];const pk=its.filter((x:any)=>x.packing_status===1).length;return`<tr><td style="text-align:center;color:#999">${i+1}</td><td style="font-weight:600">${b.batch_id}</td><td>${b.batch_size||'-'}</td><td>${its.length} (${pk} packed)</td><td><span class="badge badge-${b.status==='completed'?'ok':'orange'}">${b.status||'Prepared'}</span></td></tr>`}).join('')}
</tbody></table>`

    let batchPages = ''
    for (let bi=0;bi<batches.length;bi++) {
        const batch=batches[bi]; const its=bMap.get(batch.batch_id)||[]
        const tv=its.reduce((s:number,x:any)=>s+(x.net_volume||x.required_volume||0),0)
        const pk=its.filter((x:any)=>x.packing_status===1).length; const pr=its.filter((x:any)=>x.status>=2).length
        batchPages+=`<div class="page-break"></div>
<div class="batch-header"><div><h2>Batch ${bi+1}: ${batch.batch_id}</h2><div class="meta">${plan.sku_name||'-'} | Size: ${batch.batch_size||'-'} kg</div></div><div style="text-align:right"><div class="meta">Page ${bi+2} of ${batches.length+1}</div></div></div>
<div class="stat-row"><div class="stat-box"><div class="num">${its.length}</div><div class="lbl">Total Items</div></div><div class="stat-box"><div class="num">${pr}</div><div class="lbl">Prepared</div></div><div class="stat-box"><div class="num">${pk}</div><div class="lbl">Packed</div></div><div class="stat-box"><div class="num" style="color:#333">${tv.toFixed(2)}</div><div class="lbl">Total Vol</div></div></div>
<div class="section-title">Ingredient Items</div>
<table><thead><tr><th>#</th><th>Dept</th><th>PreBatch ID</th><th>RE Code</th><th>SAP Code</th><th style="text-align:right">Required</th><th style="text-align:right">Net Vol</th><th>Pkg</th><th>Status</th></tr></thead><tbody>
${[...its].sort((a:any,b:any)=>(a.wh||'').localeCompare(b.wh||'')).map((it:any,idx:number)=>{
    const st=it.packing_status===1?'Packed':it.status>=2?'Prepared':'Pending'
    const sc=it.packing_status===1?'purple':it.status>=2?'blue':'orange'
    const dpt=(it.wh||'').toUpperCase().includes('FH')||(it.wh||'').toLowerCase().includes('flavour')?'FH':(it.wh||'').toUpperCase().includes('SPP')||(it.wh||'').toLowerCase().includes('seasoning')?'SPP':(it.wh||'-')
    const dc=dpt==='FH'?'#1565c0':'#00838f'
    return`<tr><td style="text-align:center;color:#aaa">${idx+1}</td><td><span style="display:inline-block;padding:1px 8px;border-radius:3px;font-size:9px;font-weight:700;color:white;background:${dc}">${dpt}</span></td><td class="mono" style="font-weight:600">${it.prebatch_id||it.batch_record_id||'-'}</td><td style="font-weight:600">${it.re_code||'-'}</td><td style="color:#666">${it.mat_sap_code||'-'}</td><td style="text-align:right">${(it.required_volume||0).toFixed(4)}</td><td style="text-align:right;font-weight:600">${it.net_volume?it.net_volume.toFixed(4):'-'}</td><td>${it.package_no||'-'}/${it.total_packages||'-'}</td><td><span class="badge badge-${sc}">${st}</span></td></tr>`}).join('')}
</tbody></table>`}
    return wrap(`Plan ${planId}`, cover + batchPages)
}

// ═══════════════════════════════════════════════════════════════════
// 2. BATCH MANUFACTURING RECORD
// ═══════════════════════════════════════════════════════════════════
const buildBatchRecord = async () => {
    const plan = selectedPlan.value; const planId = plan.value
    const batches = plan.batches || []
    const items = await $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-items/by-plan/${planId}`, { headers: hdr() }).catch(() => [])

    let pages = ''
    for (let bi = 0; bi < batches.length; bi++) {
        const batch = batches[bi]
        const bItems = (items || []).filter((it: any) => it.batch_id === batch.batch_id)
        if (bi > 0) pages += '<div class="page-break"></div>'

        pages += `
<div class="batch-header"><div><h2>Batch Manufacturing Record</h2><div class="meta">${batch.batch_id} | ${plan.sku_name || '-'}</div></div><div style="text-align:right"><div class="meta">Page ${bi+1} of ${batches.length}</div></div></div>

<table class="info-table">
  <tr><td class="lbl">Batch ID</td><td class="val">${batch.batch_id}</td><td class="lbl">Plan ID</td><td class="val">${planId}</td></tr>
  <tr><td class="lbl">SKU</td><td class="val">${plan.sku_name || plan.label || '-'}</td><td class="lbl">Batch Size</td><td class="val">${batch.batch_size || '-'} kg</td></tr>
  <tr><td class="lbl">Status</td><td class="val">${batch.status || '-'}</td><td class="lbl">Date</td><td class="val">${nowStr()}</td></tr>
</table>

<div class="section-title">Ingredient Detail</div>
<table>
  <thead><tr><th>#</th><th>Dept</th><th>RE Code</th><th>SAP Code</th><th style="text-align:right">Required (kg)</th><th style="text-align:right">Actual (kg)</th><th style="text-align:right">Variance (%)</th><th>Pkg</th><th>Status</th></tr></thead>
  <tbody>
${bItems.map((it: any, idx: number) => {
    const req = it.required_volume || 0; const act = it.net_volume || 0
    const variance = req > 0 ? (((act - req) / req) * 100).toFixed(2) : '0.00'
    const varClass = Math.abs(parseFloat(variance)) > 5 ? 'color:#e53935;font-weight:700' : 'color:#43a047'
    const dpt = (it.wh||'').toUpperCase().includes('FH')? 'FH' : (it.wh||'').toUpperCase().includes('SPP')? 'SPP' : (it.wh||'-')
    const st = it.packing_status===1?'Packed':it.status>=2?'Prepared':'Pending'
    const sc = it.packing_status===1?'purple':it.status>=2?'blue':'orange'
    return `<tr><td style="text-align:center;color:#aaa">${idx+1}</td><td><span class="badge badge-${dpt==='FH'?'blue':'cyan'}">${dpt}</span></td><td style="font-weight:600">${it.re_code||'-'}</td><td style="color:#666">${it.mat_sap_code||'-'}</td><td style="text-align:right">${req.toFixed(4)}</td><td style="text-align:right;font-weight:600">${act?act.toFixed(4):'-'}</td><td style="text-align:right;${varClass}">${act?variance:'-'}%</td><td>${it.package_no||'-'}/${it.total_packages||'-'}</td><td><span class="badge badge-${sc}">${st}</span></td></tr>`}).join('')}
  </tbody>
</table>

<div style="margin-top:40px;">
  <div class="section-title">Sign-Off</div>
  <table style="border:none;">
    <tr><td style="border:none;padding:20px 0"><b>Prepared by:</b> <span class="sign-line"></span></td><td style="border:none"><b>Date:</b> <span class="sign-line" style="width:120px"></span></td></tr>
    <tr><td style="border:none;padding:20px 0"><b>Checked by:</b> <span class="sign-line"></span></td><td style="border:none"><b>Date:</b> <span class="sign-line" style="width:120px"></span></td></tr>
    <tr><td style="border:none;padding:20px 0"><b>Approved by:</b> <span class="sign-line"></span></td><td style="border:none"><b>Date:</b> <span class="sign-line" style="width:120px"></span></td></tr>
  </table>
</div>`
    }
    return wrap(`BMR — ${planId}`, pages)
}

// ═══════════════════════════════════════════════════════════════════
// 3. INGREDIENT TRACEABILITY
// ═══════════════════════════════════════════════════════════════════
const buildTraceability = async () => {
    const id = traceId.value
    const data = await $fetch<any>(`${appConfig.apiBaseUrl}/reports/traceability/${id}`, { headers: hdr() })

    let body = `<div class="header"><h1>🔍 Ingredient Traceability Report</h1><div class="sub">Search ID: ${id} | ${nowStr()}</div></div>`

    if (data.type === 'forward' && data.forward) {
        const f = data.forward
        body += `<div class="section-title">Source Lot Information</div>
<table class="info-table">
  <tr><td class="lbl">Lot ID</td><td class="val">${f.lot.intake_lot_id}</td><td class="lbl">SAP Code</td><td class="val">${f.lot.mat_sap_code}</td></tr>
  <tr><td class="lbl">RE Code</td><td class="val">${f.lot.re_code||'-'}</td><td class="lbl">Intake Vol</td><td class="val">${f.lot.intake_vol} kg</td></tr>
  <tr><td class="lbl">Remaining</td><td class="val">${f.lot.remain_vol} kg</td><td class="lbl">Trace Type</td><td class="val"><span class="badge badge-blue">Forward: Lot → Batch</span></td></tr>
  <tr><td class="lbl">Intake Date</td><td class="val">${fmtDate(f.lot.intake_at)}</td><td class="lbl">Expire Date</td><td class="val">${fmtDate(f.lot.expire_date)}</td></tr>
</table>
<div class="section-title">Used in Batches (${f.used_in.length})</div>
<table><thead><tr><th>#</th><th>Batch Record ID</th><th>Plan ID</th><th>RE Code</th><th style="text-align:right">Volume Used (kg)</th><th>Date</th></tr></thead><tbody>
${f.used_in.map((u:any,i:number)=>`<tr><td style="text-align:center">${i+1}</td><td class="mono" style="font-weight:600">${u.batch_record_id}</td><td>${u.plan_id}</td><td>${u.re_code}</td><td style="text-align:right">${u.take_volume}</td><td>${fmtDate(u.date)}</td></tr>`).join('')}
</tbody></table>`
    } else if (data.type === 'backward' && data.backward) {
        const b = data.backward
        body += `<div class="section-title">Batch Information</div>
<table class="info-table">
  <tr><td class="lbl">Batch ID</td><td class="val">${b.batch.batch_id}</td><td class="lbl">SKU</td><td class="val">${b.plan.sku_name||'-'}</td></tr>
  <tr><td class="lbl">Plan ID</td><td class="val">${b.plan.plan_id||'-'}</td><td class="lbl">Trace Type</td><td class="val"><span class="badge badge-green">Backward: Batch → Lots</span></td></tr>
</table>
<div class="section-title">Ingredients & Source Lots</div>`
        for (const ing of b.ingredients) {
            body += `<div style="font-weight:700;color:#1565c0;margin:12px 0 6px;">● ${ing.re_code} (Required: ${ing.required_volume} kg)</div>
<table><thead><tr><th>Lot ID</th><th>SAP Code</th><th style="text-align:right">Volume Used</th><th>Supplier</th></tr></thead><tbody>
${(ing.lots_used||[]).map((l:any)=>`<tr><td class="mono" style="font-weight:600">${l.intake_lot_id}</td><td>${l.mat_sap_code}</td><td style="text-align:right">${l.take_volume} kg</td><td>${l.intake_from||'-'}</td></tr>`).join('')}
</tbody></table>`}
    } else {
        body += '<div style="text-align:center;padding:40px;color:#999">No traceability data found for this ID.</div>'
    }
    return wrap(`Traceability — ${id}`, body)
}

// ═══════════════════════════════════════════════════════════════════
// 4. DAILY PRODUCTION SUMMARY
// ═══════════════════════════════════════════════════════════════════
const buildDailySummary = async () => {
    const date = reportDate.value
    const data = await $fetch<any>(`${appConfig.apiBaseUrl}/reports/production-daily?date=${date}`, { headers: hdr() })
    const s = data.summary || {}

    let body = `<div class="header"><h1>📊 Daily Production Summary</h1><div class="sub">Date: ${fmtDate(date)} | ${nowStr()}</div></div>
<div class="stat-row">
  <div class="stat-box"><div class="num">${s.total_plans||0}</div><div class="lbl">Plans</div></div>
  <div class="stat-box"><div class="num">${s.total_batches||0}</div><div class="lbl">Batches</div></div>
  <div class="stat-box"><div class="num" style="color:#333">${(s.total_volume||0).toLocaleString()}</div><div class="lbl">Total Vol (kg)</div></div>
</div>
<div class="section-title">Production Plans</div>
<table><thead><tr><th>#</th><th>Plan ID</th><th>SKU</th><th style="text-align:right">Volume (kg)</th><th>Batches</th><th>Status</th></tr></thead><tbody>
${(data.plans||[]).map((p:any,i:number)=>`<tr><td style="text-align:center;color:#aaa">${i+1}</td><td style="font-weight:600">${p.plan_id}</td><td>${p.sku_name||p.sku_id}</td><td style="text-align:right">${(p.total_volume||0).toLocaleString()}</td><td>${p.num_batches||0} (${(p.batches||[]).length} active)</td><td><span class="badge badge-${p.status==='completed'?'ok':p.status==='active'?'blue':'orange'}">${p.status||'-'}</span></td></tr>`).join('')}
</tbody></table>
<div class="section-title">Ingredient Consumption</div>
<table><thead><tr><th>#</th><th>SAP Code</th><th>RE Code</th><th style="text-align:right">Total Volume</th><th style="text-align:right">Transactions</th></tr></thead><tbody>
${(data.ingredient_consumption||[]).map((c:any,i:number)=>`<tr><td style="text-align:center;color:#aaa">${i+1}</td><td>${c.mat_sap_code}</td><td style="font-weight:600">${c.re_code||'-'}</td><td style="text-align:right;font-weight:600">${c.total_volume} kg</td><td style="text-align:right">${c.transaction_count}</td></tr>`).join('')||'<tr><td colspan="5" style="text-align:center;color:#999;padding:20px">No consumption data for this date</td></tr>'}
</tbody></table>`
    return wrap(`Daily Summary — ${date}`, body)
}

// ═══════════════════════════════════════════════════════════════════
// 5. PRE-BATCH SUMMARY
// ═══════════════════════════════════════════════════════════════════
const buildPrebatchSummary = async () => {
    const data = await $fetch<any>(`${appConfig.apiBaseUrl}/reports/prebatch-summary?from_date=${dateFrom.value}&to_date=${dateTo.value}`, { headers: hdr() })
    const s = data.summary || {}

    let body = `<div class="header"><h1>🧪 Pre-Batch Summary Report</h1><div class="sub">${fmtDate(dateFrom.value)} — ${fmtDate(dateTo.value)} | ${nowStr()}</div></div>
<div class="stat-row">
  <div class="stat-box"><div class="num">${s.total_records||0}</div><div class="lbl">Total Records</div></div>
  <div class="stat-box"><div class="num" style="color:#333">${(s.total_net_volume||0).toFixed(2)}</div><div class="lbl">Total Net Vol (kg)</div></div>
</div>
<div class="section-title">Ingredient Totals</div>
<table><thead><tr><th>RE Code</th><th>SAP Code</th><th style="text-align:right">Total Net</th><th style="text-align:right">Total Request</th><th style="text-align:right">Variance (kg)</th><th style="text-align:right">Variance (%)</th><th>Count</th></tr></thead><tbody>
${(data.ingredient_totals||[]).map((t:any)=>{
    const v = (t.total_net||0)-(t.total_request||0); const vp = t.total_request>0?((v/t.total_request)*100).toFixed(2):'0'
    const vc = Math.abs(parseFloat(vp))>5?'color:#e53935;font-weight:700':'color:#43a047'
    return`<tr><td style="font-weight:600">${t.re_code}</td><td style="color:#666">${t.mat_sap_code||'-'}</td><td style="text-align:right">${(t.total_net||0).toFixed(2)}</td><td style="text-align:right">${(t.total_request||0).toFixed(2)}</td><td style="text-align:right;${vc}">${v.toFixed(2)}</td><td style="text-align:right;${vc}">${vp}%</td><td style="text-align:center">${t.count}</td></tr>`}).join('')||'<tr><td colspan="7" style="text-align:center;color:#999;padding:20px">No data</td></tr>'}
</tbody></table>
<div class="section-title">Detailed Records (${(data.records||[]).length})</div>
<table><thead><tr><th>#</th><th>Batch Record ID</th><th>RE Code</th><th>Plan</th><th style="text-align:right">Net Vol</th><th>Pkg</th><th>Recheck</th><th>Packing</th></tr></thead><tbody>
${(data.records||[]).slice(0,100).map((r:any,i:number)=>`<tr><td style="text-align:center;color:#aaa">${i+1}</td><td class="mono" style="font-weight:600">${r.batch_record_id||'-'}</td><td>${r.re_code||'-'}</td><td>${r.plan_id||'-'}</td><td style="text-align:right">${(r.net_volume||0).toFixed(4)}</td><td>${r.package_no||'-'}/${r.total_packages||'-'}</td><td><span class="badge badge-${r.recheck_status===1?'green':r.recheck_status===2?'red':'grey'}">${r.recheck_status===1?'OK':r.recheck_status===2?'Fail':'—'}</span></td><td><span class="badge badge-${r.packing_status===1?'purple':'grey'}">${r.packing_status===1?'Packed':'—'}</span></td></tr>`).join('')}
</tbody></table>`
    return wrap('Pre-Batch Summary', body)
}

// ═══════════════════════════════════════════════════════════════════
// 6. PACKING & DELIVERY
// ═══════════════════════════════════════════════════════════════════
const buildPackingDelivery = async () => {
    const plan = selectedPlan.value; const planId = plan.value
    const data = await $fetch<any>(`${appConfig.apiBaseUrl}/reports/packing-list/${planId}`, { headers: hdr() })
    const s = data.summary || {}

    let body = `<div class="header"><h1>📦 Packing & Delivery Report</h1><div class="sub">Plan: ${planId} | ${nowStr()}</div></div>
<table class="info-table">
  <tr><td class="lbl">Plan ID</td><td class="val">${data.plan_id}</td><td class="lbl">SKU</td><td class="val">${data.sku_name||'-'}</td></tr>
  <tr><td class="lbl">Total Volume</td><td class="val">${data.total_volume||'-'} kg</td><td class="lbl">Total Bags</td><td class="val">${s.total_bags||0}</td></tr>
</table>
<div class="stat-row">
  <div class="stat-box"><div class="num">${s.total_bags||0}</div><div class="lbl">Total Bags</div></div>
  <div class="stat-box"><div class="num" style="color:#43a047">${s.packed||0}</div><div class="lbl">Packed</div></div>
  <div class="stat-box"><div class="num" style="color:#fb8c00">${s.unpacked||0}</div><div class="lbl">Unpacked</div></div>
  <div class="stat-box"><div class="num" style="color:#1565c0">${s.checked||0}</div><div class="lbl">QC Checked</div></div>
</div>
<div class="section-title">Bag List</div>
<table><thead><tr><th>#</th><th>Batch Record ID</th><th>RE Code</th><th>SAP Code</th><th style="text-align:right">Net Vol</th><th>Pkg</th><th>Recheck</th><th>Packed</th><th>Packed At</th></tr></thead><tbody>
${(data.bags||[]).map((b:any,i:number)=>`<tr><td style="text-align:center;color:#aaa">${i+1}</td><td class="mono" style="font-weight:600">${b.batch_record_id||'-'}</td><td style="font-weight:600">${b.re_code||'-'}</td><td style="color:#666">${b.mat_sap_code||'-'}</td><td style="text-align:right">${(b.net_volume||0).toFixed(4)}</td><td>${b.package_no||'-'}/${b.total_packages||'-'}</td><td><span class="badge badge-${b.recheck_status===1?'green':b.recheck_status===2?'red':'grey'}">${b.recheck_status===1?'OK':b.recheck_status===2?'Fail':'—'}</span></td><td><span class="badge badge-${b.packing_status===1?'purple':'grey'}">${b.packing_status===1?'Yes':'No'}</span></td><td style="font-size:9px">${b.packed_at?fmtDate(b.packed_at):'-'}</td></tr>`).join('')}
</tbody></table>`
    return wrap(`Packing — ${planId}`, body)
}

// ═══════════════════════════════════════════════════════════════════
// 7. STOCK & EXPIRY ALERT
// ═══════════════════════════════════════════════════════════════════
const buildStockExpiry = async () => {
    const data = await $fetch<any>(`${appConfig.apiBaseUrl}/reports/expiry-alert`, { headers: hdr() })
    const s = data.summary || {}

    const renderTable = (items: any[], cls: string) => items.length === 0
        ? `<tr><td colspan="7" style="text-align:center;color:#999;padding:12px">None</td></tr>`
        : items.map((it: any, i: number) => `<tr class="${cls}"><td style="text-align:center;color:#aaa">${i+1}</td><td class="mono" style="font-weight:600">${it.intake_lot_id}</td><td style="font-weight:600">${it.re_code||'-'}</td><td style="color:#666">${it.mat_sap_code}</td><td style="text-align:right;font-weight:600">${it.remain_vol} kg</td><td style="font-weight:600">${fmtDate(it.expire_date)}</td><td style="text-align:center;font-weight:700">${it.days_left!=null?it.days_left+' d':'-'}</td></tr>`).join('')

    let body = `<div class="header"><h1>⚠️ Ingredient Stock & Expiry Alert</h1><div class="sub">${nowStr()}</div></div>
<div class="stat-row">
  <div class="stat-box"><div class="num">${s.total_lots||0}</div><div class="lbl">Active Lots</div></div>
  <div class="stat-box"><div class="num" style="color:#e53935">${s.expired_count||0}</div><div class="lbl">🔴 Expired</div></div>
  <div class="stat-box"><div class="num" style="color:#fb8c00">${s.warning_count||0}</div><div class="lbl">🟡 Warning</div></div>
  <div class="stat-box"><div class="num" style="color:#43a047">${s.ok_count||0}</div><div class="lbl">🟢 OK</div></div>
</div>
<div class="section-title">🔴 Expired Items (${(data.expired||[]).length})</div>
<table><thead><tr><th>#</th><th>Lot ID</th><th>RE Code</th><th>SAP Code</th><th style="text-align:right">Remaining</th><th>Expire Date</th><th>Days</th></tr></thead><tbody>
${renderTable(data.expired||[],'alert-expired')}
</tbody></table>
<div class="section-title">🟡 Expiring Soon — within 30 days (${(data.warning||[]).length})</div>
<table><thead><tr><th>#</th><th>Lot ID</th><th>RE Code</th><th>SAP Code</th><th style="text-align:right">Remaining</th><th>Expire Date</th><th>Days</th></tr></thead><tbody>
${renderTable(data.warning||[],'alert-warning')}
</tbody></table>
<div class="section-title">🟢 OK (${(data.ok||[]).length})</div>
<table><thead><tr><th>#</th><th>Lot ID</th><th>RE Code</th><th>SAP Code</th><th style="text-align:right">Remaining</th><th>Expire Date</th><th>Days</th></tr></thead><tbody>
${renderTable(data.ok||[],'')}
</tbody></table>`
    return wrap('Stock & Expiry', body)
}

// ═══════════════════════════════════════════════════════════════════
// 8. QUALITY CHECK
// ═══════════════════════════════════════════════════════════════════
const buildQualityCheck = async () => {
    const data = await $fetch<any>(`${appConfig.apiBaseUrl}/reports/quality-check?from_date=${dateFrom.value}&to_date=${dateTo.value}`, { headers: hdr() })
    const s = data.summary || {}
    const passRate = s.total_checked > 0 ? ((s.passed / s.total_checked) * 100).toFixed(1) : '-'

    let body = `<div class="header"><h1>✅ Quality Check Report</h1><div class="sub">${fmtDate(dateFrom.value)} — ${fmtDate(dateTo.value)} | ${nowStr()}</div></div>
<div class="stat-row">
  <div class="stat-box"><div class="num">${s.total_checked||0}</div><div class="lbl">Total Checked</div></div>
  <div class="stat-box"><div class="num" style="color:#43a047">${s.passed||0}</div><div class="lbl">✅ Passed</div></div>
  <div class="stat-box"><div class="num" style="color:#e53935">${s.failed||0}</div><div class="lbl">❌ Failed</div></div>
  <div class="stat-box"><div class="num" style="color:#1565c0">${passRate}%</div><div class="lbl">Pass Rate</div></div>
</div>
<div class="section-title">Check Results</div>
<table><thead><tr><th>#</th><th>Batch Record ID</th><th>Plan</th><th>RE Code</th><th>SAP Code</th><th>Pkg</th><th>Result</th><th>Checked By</th><th>Date</th></tr></thead><tbody>
${(data.items||[]).map((it:any,i:number)=>`<tr><td style="text-align:center;color:#aaa">${i+1}</td><td class="mono" style="font-weight:600">${it.batch_record_id||'-'}</td><td>${it.plan_id||'-'}</td><td style="font-weight:600">${it.re_code||'-'}</td><td style="color:#666">${it.mat_sap_code||'-'}</td><td>${it.package_no||'-'}</td><td><span class="badge badge-${it.recheck_status===1?'green':'red'}">${it.recheck_status===1?'PASS':'FAIL'}</span></td><td>${it.recheck_by||'-'}</td><td style="font-size:9px">${fmtDate(it.recheck_at)}</td></tr>`).join('')||'<tr><td colspan="9" style="text-align:center;color:#999;padding:20px">No quality check records found</td></tr>'}
</tbody></table>`
    return wrap('Quality Check', body)
}

// ═══════════════════════════════════════════════════════════════════
// ACTIONS (download, print, email)
// ═══════════════════════════════════════════════════════════════════
const downloadPdf = () => {
    if (!pdfBlobUrl.value) return
    const a = document.createElement('a'); a.href = pdfBlobUrl.value
    a.download = pdfFileName.value.replace('.pdf', '.html')
    document.body.appendChild(a); a.click(); document.body.removeChild(a)
    $q.notify({ type: 'positive', icon: 'download', message: 'Downloaded!', position: 'top', timeout: 1500 })
}
const printPdf = () => { if (!pdfBlobUrl.value) return; const w=window.open(pdfBlobUrl.value,'_blank'); if(w) w.onload=()=>setTimeout(()=>w.print(),500) }
const openInNewTab = () => { if (pdfBlobUrl.value) window.open(pdfBlobUrl.value, '_blank') }

const sendEmail = async () => {
    if (!emailTo.value || !pdfBlobUrl.value) return
    isSendingEmail.value = true
    try {
        const resp = await fetch(pdfBlobUrl.value); const htmlBlob = await resp.blob()
        const fd = new FormData()
        fd.append('to', emailTo.value); fd.append('subject', emailSubject.value); fd.append('body', emailBody.value); fd.append('attachment', htmlBlob, pdfFileName.value)
        await $fetch(`${appConfig.apiBaseUrl}/reports/send-email`, { method: 'POST', headers: hdr(), body: fd })
        $q.notify({ type: 'positive', icon: 'email', message: `Sent to ${emailTo.value}`, position: 'top' })
        showEmailDialog.value = false
    } catch {
        const s = encodeURIComponent(emailSubject.value || 'Report'); const b = encodeURIComponent(emailBody.value || '')
        window.open(`mailto:${emailTo.value}?subject=${s}&body=${b}`, '_blank')
        $q.notify({ type: 'info', icon: 'email', message: 'Email client opened — attach report manually.', position: 'top', timeout: 4000 })
        showEmailDialog.value = false
    } finally { isSendingEmail.value = false }
}
</script>

<style scoped>
.rounded-borders-xl { border-radius: 12px; overflow: hidden; }
</style>

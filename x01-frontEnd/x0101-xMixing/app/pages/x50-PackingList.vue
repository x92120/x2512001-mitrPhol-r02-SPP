<script setup lang="ts">
/**
 * x50-PackingList.vue — Packing List View v2.1
 * 3-Panel Layout: Production Plans | Warehouse Bags | Batch Packing
 */
import { ref, computed, onMounted, watch } from 'vue'
import { useQuasar } from 'quasar'
import { appConfig } from '~/appConfig/config'
import { useAuth } from '../composables/useAuth'
import { useMqttLocalDevice } from '../composables/useMqttLocalDevice'
import { usePackingPrints } from '../composables/packing/usePackingPrints'

const $q = useQuasar()
const { getAuthHeader } = useAuth()
const { t } = useI18n()
const { lastScan, connect } = useMqttLocalDevice()

// ═══════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════
const loading = ref(false)
const loadingRecords = ref(false)
const plans = ref<any[]>([])
const fhRecords = ref<any[]>([])         // FH prebatch_recs (middle panel)
const sppRecords = ref<any[]>([])        // SPP prebatch_recs (middle panel)
const allRecords = computed(() => [...fhRecords.value, ...sppRecords.value])
const batchRecords = ref<any[]>([])      // Records for selected batch (right panel)
const selectedBatch = ref<any>(null)
const selectedPlan = ref<any>(null)
const scanBatchId = ref('')
const scanFH = ref('')
const scanSPP = ref('')

// Track bags scanned in the CURRENT session, before "Closing" the box
const currentBoxScans = ref<any[]>([])

// ── Modals & Dialogs ──
const showScanDialog = ref(false)
const scanDialogWh = ref<'FH' | 'SPP'>('FH')
const scanDialogFilter = ref('')

// Warehouse sort
const whSortCol = ref<'bag_id' | 're_code' | 'weight' | 'status' | 'batch_id' | 'plan_id'>('re_code')
const whSortAsc = ref(true)
const filterMiddleWh = ref<'ALL' | 'FH' | 'SPP'>('ALL')
const middleHideBoxed = ref(false)   // false = show All, true = hide Boxed
const filterReCode = ref('')         // filter ingredients by re_code

// ═══════════════════════════════════════════════════════════════════
// SOUND SETTINGS
// ═══════════════════════════════════════════════════════════════════
const showSoundSettings = ref(false)

interface SoundSettings {
  enabled: boolean
  volume: number           // 0 - 100
  correctSound: 'beep' | 'chime' | 'bell' | 'ding'
  wrongSound: 'buzzer' | 'error' | 'alarm' | 'honk'
}

const defaultSoundSettings: SoundSettings = {
  enabled: true,
  volume: 60,
  correctSound: 'chime',
  wrongSound: 'buzzer',
}

const soundSettings = ref<SoundSettings>({ ...defaultSoundSettings })

// Load from localStorage
const loadSoundSettings = () => {
  try {
    const saved = localStorage.getItem('packinglist_sound_settings')
    if (saved) {
      soundSettings.value = { ...defaultSoundSettings, ...JSON.parse(saved) }
    }
  } catch { /* ignore */ }
}

const saveSoundSettings = () => {
  try {
    localStorage.setItem('packinglist_sound_settings', JSON.stringify(soundSettings.value))
  } catch { /* ignore */ }
}

watch(soundSettings, saveSoundSettings, { deep: true })

// ═══════════════════════════════════════════════════════════════════
// SOUND EFFECTS
// ═══════════════════════════════════════════════════════════════════
const correctSoundOptions = [
  { value: 'beep',  label: '🔔 Beep',  desc: 'Simple beep tone' },
  { value: 'chime', label: '🎵 Chime', desc: 'Two-tone ascending chime' },
  { value: 'bell',  label: '🔔 Bell',  desc: 'Bright bell ring' },
  { value: 'ding',  label: '✨ Ding',  desc: 'Soft ding notification' },
]
const wrongSoundOptions = [
  { value: 'buzzer', label: '🚨 Buzzer', desc: 'Low buzzer tone' },
  { value: 'error',  label: '❌ Error',  desc: 'Error alert sound' },
  { value: 'alarm',  label: '⚠️ Alarm',  desc: 'Warning alarm' },
  { value: 'honk',   label: '📢 Honk',   desc: 'Short horn honk' },
]

const playSound = async (type: 'correct' | 'wrong') => {
  if (!soundSettings.value.enabled) return

  const vol = soundSettings.value.volume / 100
  try {
    const ctx = new AudioContext()
    await ctx.resume()

    if (type === 'correct') {
      await _playCorrectSound(ctx, vol)
    } else {
      await _playWrongSound(ctx, vol)
    }
  } catch (e) {
    console.warn('Sound playback failed:', e)
  }
}

const _playCorrectSound = async (ctx: AudioContext, vol: number) => {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)
  gain.gain.value = vol * 0.5

  const soundType = soundSettings.value.correctSound
  switch (soundType) {
    case 'beep':
      osc.frequency.value = 1000
      osc.type = 'sine'
      osc.start()
      setTimeout(() => { osc.stop(); ctx.close() }, 200)
      break
    case 'chime':
      osc.frequency.value = 880
      osc.type = 'sine'
      osc.start()
      setTimeout(() => { osc.frequency.value = 1320 }, 100)
      setTimeout(() => { osc.stop(); ctx.close() }, 280)
      break
    case 'bell': {
      osc.frequency.value = 1200
      osc.type = 'sine'
      gain.gain.setValueAtTime(vol * 0.6, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.5)
      osc.start()
      setTimeout(() => { osc.stop(); ctx.close() }, 500)
      break
    }
    case 'ding': {
      osc.frequency.value = 1500
      osc.type = 'sine'
      gain.gain.setValueAtTime(vol * 0.4, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3)
      osc.start()
      setTimeout(() => { osc.stop(); ctx.close() }, 350)
      break
    }
  }
}

const _playWrongSound = async (ctx: AudioContext, vol: number) => {
  const osc = ctx.createOscillator()
  const gain = ctx.createGain()
  osc.connect(gain)
  gain.connect(ctx.destination)
  gain.gain.value = vol * 0.5

  const soundType = soundSettings.value.wrongSound
  switch (soundType) {
    case 'buzzer':
      osc.frequency.value = 200
      osc.type = 'square'
      osc.start()
      setTimeout(() => { osc.frequency.value = 150 }, 150)
      setTimeout(() => { osc.stop(); ctx.close() }, 400)
      break
    case 'error': {
      osc.frequency.value = 400
      osc.type = 'sawtooth'
      osc.start()
      setTimeout(() => { osc.frequency.value = 300 }, 100)
      setTimeout(() => { osc.frequency.value = 200 }, 200)
      setTimeout(() => { osc.stop(); ctx.close() }, 350)
      break
    }
    case 'alarm': {
      osc.frequency.value = 600
      osc.type = 'square'
      gain.gain.value = vol * 0.35
      osc.start()
      setTimeout(() => { osc.frequency.value = 400 }, 120)
      setTimeout(() => { osc.frequency.value = 600 }, 240)
      setTimeout(() => { osc.frequency.value = 400 }, 360)
      setTimeout(() => { osc.stop(); ctx.close() }, 480)
      break
    }
    case 'honk': {
      osc.frequency.value = 250
      osc.type = 'sawtooth'
      gain.gain.setValueAtTime(vol * 0.5, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.3)
      osc.start()
      setTimeout(() => { osc.stop(); ctx.close() }, 350)
      break
    }
  }
}

// ═══════════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════════

const activePlans = computed(() =>
  plans.value.filter(p => p.status !== 'Cancelled')
)

const isFH = (wh: string) =>
  wh?.toUpperCase().includes('FH') || wh?.toUpperCase().includes('FLAVOUR')

const isSPP = (wh: string) =>
  wh?.toUpperCase().includes('SPP')

/** Get bags for the selected batch, grouped by warehouse (FH/SPP only, excludes MIX) */
const bagsByWarehouse = computed((): { FH: any[]; SPP: any[] } => {
  const result = { FH: [] as any[], SPP: [] as any[] }
  if (!selectedBatch.value) return result
  // Use batch-specific records (fetched via /prebatch-recs/by-batch/)
  batchRecords.value.forEach(bag => {
    const wh = bag.wh || ''
    if (isFH(wh)) {
      result.FH.push(bag)
    } else if (isSPP(wh)) {
      result.SPP.push(bag)
    }
    // MIX and other warehouses are excluded
  })
  return result
})

/** Weight summaries */
const fhWeight = computed(() =>
  bagsByWarehouse.value.FH.reduce((sum: number, b: any) => sum + (b.net_volume || 0), 0)
)
const sppWeight = computed(() =>
  bagsByWarehouse.value.SPP.reduce((sum: number, b: any) => sum + (b.net_volume || 0), 0)
)
const totalWeight = computed(() => fhWeight.value + sppWeight.value)

/** 3-tier packing status for lower card: Wait → Scan → packing_ok */
const getReqPackingState = (req: any): { icon: string; color: string; label: string; bg: string } => {
  if (req.status < 2) {
    // PreBatch not done yet
    return { icon: 'radio_button_unchecked', color: 'grey-5', label: 'Wait', bg: '' }
  }
  // PreBatch done (status === 2). Check packing_status directly on the item.
  if (req.packing_status === 1) {
    return { icon: 'check_circle', color: 'green', label: 'packing_ok', bg: 'bg-green-1' }
  }
  // PreBatch done but not yet packed → Scan
  return { icon: 'qr_code_scanner', color: 'orange', label: 'Scan', bg: 'bg-orange-1' }
}
const isReqPackingOk = (req: any): boolean => getReqPackingState(req).label === 'packing_ok'

/** Derive batch-level status from its prebatch_items data */
const getBatchStatus = (batch: any): { icon: string; color: string; label: string } => {
  // Boxed takes priority
  if (batch.fh_boxed_at || batch.spp_boxed_at) {
    return { icon: 'inventory_2', color: 'green', label: 'Boxed' }
  }
  const reqs = batch.reqs || []
  if (reqs.length === 0) {
    // No items loaded yet — fall back to batch_prepare flag
    if (batch.batch_prepare) return { icon: 'check_circle', color: 'blue-7', label: 'Prepared' }
    return { icon: 'pending', color: 'grey-5', label: batch.status || 'Created' }
  }
  // Check packing progress
  const anyPacked = reqs.some((r: any) => r.packing_status === 1)
  if (anyPacked) return { icon: 'qr_code_scanner', color: 'orange', label: 'Packing' }
  // Check prebatch progress
  const allDone = reqs.every((r: any) => r.status === 2)
  const anyStarted = reqs.some((r: any) => r.status >= 1)
  if (allDone) return { icon: 'check_circle', color: 'blue-7', label: 'Prepared' }
  if (anyStarted) return { icon: 'hourglass_top', color: 'orange', label: 'In-Progress' }
  return { icon: 'pending', color: 'grey-5', label: batch.status || 'Created' }
}

/** Check if all bags are packed per warehouse — must match requirement count */
const fhPackedCount = computed(() => bagsByWarehouse.value.FH.filter(b => isPacked(b)).length)
const sppPackedCount = computed(() => bagsByWarehouse.value.SPP.filter(b => isPacked(b)).length)

// Count required ingredients per WH from batch.reqs (not from records)
const fhRequiredCount = computed(() => {
  if (!selectedBatch.value) return 0
  return (selectedBatch.value.reqs || []).filter((r: any) => isFH(r.wh || '')).length
})
const sppRequiredCount = computed(() => {
  if (!selectedBatch.value) return 0
  return (selectedBatch.value.reqs || []).filter((r: any) => isSPP(r.wh || '')).length
})

// Box is complete ONLY when packed count matches required count (not just existing records)
const allFhPacked = computed(() => fhRequiredCount.value > 0 && fhPackedCount.value >= fhRequiredCount.value)
const allSppPacked = computed(() => sppRequiredCount.value > 0 && sppPackedCount.value >= sppRequiredCount.value)

/** Group bags by ingredient re_code within selected warehouse for requirement list */
interface IngredientReq {
  re_code: string
  name: string
  wh: string
  batch_record_id: string
  totalVol: number
  packedVol: number
  totalBags: number
  packedBags: number
  bags: any[]
}
const ingredientsByDept = computed((): IngredientReq[] => {
  const isAll = filterMiddleWh.value === 'ALL'
  const isCurrentFH = filterMiddleWh.value === 'FH'
  const whBags = isAll
    ? [...bagsByWarehouse.value.FH, ...bagsByWarehouse.value.SPP]
    : (isCurrentFH ? bagsByWarehouse.value.FH : bagsByWarehouse.value.SPP)
  const map = new Map<string, IngredientReq>()

  // Step 1: Seed from batch requirements so unweighed ingredients appear
  if (selectedBatch.value) {
    const reqs = (selectedBatch.value.reqs || []).filter((r: any) =>
      isAll ? (isFH(r.wh || '') || isSPP(r.wh || '')) : (isCurrentFH ? isFH(r.wh || '') : isSPP(r.wh || ''))
    )
    for (const req of reqs) {
      const code = req.re_code || '?'
      if (!map.has(code)) {
        map.set(code, { re_code: code, name: req.ingredient_name || code, wh: req.wh || '', batch_record_id: req.batch_record_id || '', totalVol: 0, packedVol: 0, totalBags: 0, packedBags: 0, bags: [] })
      }
    }
  }

  // Step 2: Overlay with actual packed records
  for (const bag of whBags) {
    const code = bag.re_code || '?'
    if (!map.has(code)) {
      map.set(code, { re_code: code, name: bag.ingredient_name || code, wh: bag.wh || '', batch_record_id: bag.batch_record_id || '', totalVol: 0, packedVol: 0, totalBags: 0, packedBags: 0, bags: [] })
    }
    const ing = map.get(code)!
    ing.totalVol += bag.net_volume || 0
    ing.totalBags++
    ing.bags.push(bag)
    if (isPacked(bag)) {
      ing.packedVol += bag.net_volume || 0
      ing.packedBags++
    }
  }
  let result = [...map.values()].sort((a, b) => a.re_code.localeCompare(b.re_code))
  // Apply re_code filter
  if (filterReCode.value.trim()) {
    const q = filterReCode.value.trim().toLowerCase()
    result = result.filter(i => i.re_code.toLowerCase().includes(q) || i.name.toLowerCase().includes(q))
  }
  return result
})

/** Sort helper for warehouse records */
const sortWarehouseRecords = (list: any[]) => {
  const col = whSortCol.value
  const asc = whSortAsc.value ? 1 : -1
  return [...list].sort((a, b) => {
    let va: any, vb: any
    if (col === 'bag_id') {
      va = a.batch_record_id || ''
      vb = b.batch_record_id || ''
    } else if (col === 'batch_id') {
      va = a.batch_id || ''
      vb = b.batch_id || ''
    } else if (col === 'plan_id') {
      va = a.plan_id || ''
      vb = b.plan_id || ''
    } else if (col === 're_code') {
      va = a.re_code || ''
      vb = b.re_code || ''
    } else if (col === 'weight') {
      va = a.net_volume || 0
      vb = b.net_volume || 0
    } else {
      va = a.packing_status || 0
      vb = b.packing_status || 0
    }
    if (va < vb) return -1 * asc
    if (va > vb) return 1 * asc
    return 0
  })
}

const toggleWhSort = (col: 'bag_id' | 're_code' | 'weight' | 'status' | 'batch_id' | 'plan_id') => {
  if (whSortCol.value === col) {
    whSortAsc.value = !whSortAsc.value
  } else {
    whSortCol.value = col
    whSortAsc.value = true
  }
}

const whSortIcon = (col: string) => {
  if (whSortCol.value !== col) return 'unfold_more'
  return whSortAsc.value ? 'arrow_upward' : 'arrow_downward'
}

/** Middle panel: records per warehouse, sorted */
const middlePanelFH = computed(() => sortWarehouseRecords(fhRecords.value.filter((b: any) => b.packing_status !== 1)))
const middlePanelSPP = computed(() => sortWarehouseRecords(sppRecords.value.filter((b: any) => b.packing_status !== 1)))

/** Hierarchical grouping for middle panel tree view:
 *  Level 1: re_code  → totalWeight (all packages across all batches)
 *  Level 2: batch_id → totalWeight (all packages for that batch)
 *  Level 3: individual prebatch package (batch_record_id, weight, status)
 */
interface PkgNode   { id: string; label: string; weight: number; status: number; recheck: number }
interface BatchNode { batch_id: string; totalWeight: number; pkgs: PkgNode[] }
interface RecodeNode { re_code: string; totalWeight: number; batches: BatchNode[] }

const groupedMiddlePanel = computed((): RecodeNode[] => {
  let src = filterMiddleWh.value === 'FH' ? fhRecords.value : sppRecords.value
  if (middleHideBoxed.value) src = src.filter((b: any) => b.packing_status !== 1)

  const map = new Map<string, RecodeNode>()

  for (const bag of src) {
    const re = bag.re_code || '?'
    const bid = bag.batch_id || '?'

    if (!map.has(re)) map.set(re, { re_code: re, totalWeight: 0, batches: [] })
    const reNode = map.get(re)!

    let bNode = reNode.batches.find(b => b.batch_id === bid)
    if (!bNode) { bNode = { batch_id: bid, totalWeight: 0, pkgs: [] }; reNode.batches.push(bNode) }

    const pkgNo  = bag.package_no ?? 1
    const pkgTot = bag.total_packages ?? 1
    const label  = `${(bag.batch_record_id || bid + '-PKG').split('-').slice(-2).join('-')}  (Pkg ${pkgNo}/${pkgTot})`
    bNode.pkgs.push({ id: bag.id || bag.batch_record_id, label, weight: bag.net_volume || 0, status: bag.packing_status || 0, recheck: bag.recheck_status || 0 })
    bNode.totalWeight += bag.net_volume || 0
    reNode.totalWeight += bag.net_volume || 0
  }

  // Sort: re_code alphabetically, batches by id, pkgs by label
  return [...map.values()]
    .sort((a, b) => a.re_code.localeCompare(b.re_code))
    .map(r => ({
      ...r,
      batches: r.batches
        .sort((a, b) => a.batch_id.localeCompare(b.batch_id))
        .map(b => ({ ...b, pkgs: b.pkgs.sort((a, b) => a.label.localeCompare(b.label)) }))
    }))
})

/** Batch info for right panel */
const batchInfo = computed(() => {
  if (!selectedBatch.value) return null
  const plan = plans.value.find(p =>
    p.batches?.some((b: any) => b.batch_id === selectedBatch.value.batch_id)
  )
  return {
    batch_id: selectedBatch.value.batch_id,
    sku_name: plan?.sku_name || plan?.sku_id || '-',
    plan_id: plan?.plan_id || '-',
    batch_size: selectedBatch.value.batch_size || 0,
    status: selectedBatch.value.status,
  }
})

/** Scan dialog — list of bags filtered to correct ingredients for selected batch */
const scanDialogBags = computed(() => {
  const wh = scanDialogWh.value
  const whBags = wh === 'FH' ? middlePanelFH.value : middlePanelSPP.value
  // If a batch is selected, filter to only show bags with matching re_code
  if (selectedBatch.value) {
    const batchReqs = selectedBatch.value.reqs || []
    const requiredReCodes = new Set(batchReqs.map((r: any) => r.re_code))
    if (requiredReCodes.size === 0) return whBags
    return whBags.filter(b => requiredReCodes.has(b.re_code))
  }
  return whBags
})

// ═══════════════════════════════════════════════════════════════════
// DATA FETCHING
// ═══════════════════════════════════════════════════════════════════

const fetchPlans = async () => {
  loading.value = true
  try {
    const resp = await $fetch<any>(`${appConfig.apiBaseUrl}/production-plans/?skip=0&limit=1000&status=all`, {
      headers: getAuthHeader() as Record<string, string>
    })
    plans.value = resp.plans || resp || []
  } catch (e) {
    console.error('Error fetching plans:', e)
    $q.notify({ type: 'negative', message: 'Failed to load production plans' })
  } finally {
    loading.value = false
  }
}

/** Fetch prebatch items for a batch on-demand (when user expands it) */
const fetchBatchReqs = async (batch: any) => {
  if (batch._reqsLoaded) return // already loaded
  batch._reqsLoading = true
  try {
    const items = await $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-items/by-batch/${batch.batch_id}`, {
      headers: getAuthHeader() as Record<string, string>
    })
    batch.reqs = items || []
    batch._reqsLoaded = true
  } catch (e) {
    console.error('Error fetching items for', batch.batch_id, e)
  } finally {
    batch._reqsLoading = false
  }
}

/** Fetch ready-to-deliver batches from the database */
const fetchReadyToDeliver = async () => {
  try {
    const showAll = filterDeliveryStatus.value === 'SHOW_ALL'
    const url = showAll
      ? `${appConfig.apiBaseUrl}/production-batches/ready-to-deliver?show_all=true`
      : `${appConfig.apiBaseUrl}/production-batches/ready-to-deliver`
    const data = await $fetch<any[]>(url, {
      headers: getAuthHeader() as Record<string, string>
    })
    // Convert API response to TransferredBox entries
    const boxes: TransferredBox[] = []
    for (const b of (data || [])) {
      if (b.fh_boxed_at) {
        boxes.push({
          id: `${b.batch_id}-FH`,
          wh: 'FH',
          batch_id: b.batch_id,
          bagsCount: b.fh_packed || b.fh_total || 0,
          time: new Date(b.fh_boxed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          inProduction: !!b.production,
          sku_id: b.sku_id,
          batch_size: b.batch_size,
          fh_total: b.fh_total || 0,
          fh_packed: b.fh_packed || 0,
        })
      }
      if (b.spp_boxed_at) {
        boxes.push({
          id: `${b.batch_id}-SPP`,
          wh: 'SPP',
          batch_id: b.batch_id,
          bagsCount: b.spp_packed || b.spp_total || 0,
          time: new Date(b.spp_boxed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          inProduction: !!b.production,
          sku_id: b.sku_id,
          batch_size: b.batch_size,
          spp_total: b.spp_total || 0,
          spp_packed: b.spp_packed || 0,
        })
      }
      // Populate deliveredMap from DB (keyed per WH: "batch_id-FH" / "batch_id-SPP")
      if (b.fh_delivered_at) {
        deliveredMap.value.set(`${b.batch_id}-FH`, new Date(b.fh_delivered_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
      }
      if (b.spp_delivered_at) {
        deliveredMap.value.set(`${b.batch_id}-SPP`, new Date(b.spp_delivered_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }))
      }
    }
    transferredBoxes.value = boxes
    // Store raw data for Show All status table
    allBatchStatuses.value = data || []
  } catch (e) {
    console.error('Error fetching ready-to-deliver:', e)
  }
}

// ── Delivery Expand/Collapse All ──
const deliveryExpandMap = ref<Record<string, boolean>>({})
const deliveryWhFilter = ref<'ALL' | 'FH' | 'SPP'>('ALL')
const expandAllBoxes = () => {
  groupedTransferredBoxes.value.forEach((r: any) => { deliveryExpandMap.value[r.batch_id] = true; fetchBoxContents(r.batch_id) })
}
const collapseAllBoxes = () => {
  Object.keys(deliveryExpandMap.value).forEach(k => { deliveryExpandMap.value[k] = false })
}

// ── Box Contents Cache for Expandable Delivery View ──
interface BoxPkg { id: number; batch_record_id: string; package_no: number; total_packages: number; net_volume: number; packing_status: number; recheck_status: number }
interface BoxReCode { re_code: string; ingredient_name: string; required_volume: number; total_packed: number; status: number; packing_status: number; packages: BoxPkg[]; total_weight: number }
interface BoxWhGroup { wh: string; re_codes: BoxReCode[]; total_weight: number }
interface BoxContents { batch_id: string; wh_groups: BoxWhGroup[]; total_box_weight: number; _loading?: boolean }
const boxContentsCache = ref<Map<string, BoxContents>>(new Map())

const fetchBoxContents = async (batchId: string) => {
  if (boxContentsCache.value.has(batchId)) return
  // Set loading placeholder
  boxContentsCache.value.set(batchId, { batch_id: batchId, wh_groups: [], total_box_weight: 0, _loading: true })
  try {
    const data = await $fetch<BoxContents>(`${appConfig.apiBaseUrl}/production-batches/box-contents/${batchId}`, {
      headers: getAuthHeader() as Record<string, string>
    })
    boxContentsCache.value.set(batchId, { ...data, _loading: false })
  } catch (e) {
    console.error('Error fetching box contents for', batchId, e)
    boxContentsCache.value.set(batchId, { batch_id: batchId, wh_groups: [], total_box_weight: 0, _loading: false })
  }
}

// ── Cancel Packing Box ──
const showCancelBoxDialog = ref(false)
const cancelBoxBatchId = ref('')
const cancelBoxWh = ref('')
const cancelBoxReason = ref('')
const cancelBoxLoading = ref(false)

const openCancelBoxDialog = (batchId: string, wh: string) => {
  cancelBoxBatchId.value = batchId
  cancelBoxWh.value = wh
  cancelBoxReason.value = ''
  showCancelBoxDialog.value = true
}

const cancelBox = async () => {
  if (!cancelBoxReason.value.trim()) {
    $q.notify({ type: 'warning', message: 'Please enter a reason for cancellation.', position: 'top' })
    return
  }
  cancelBoxLoading.value = true
  try {
    await $fetch(`${appConfig.apiBaseUrl}/production-batches/by-batch-id/${cancelBoxBatchId.value}/box-cancel`, {
      method: 'PATCH',
      headers: getAuthHeader() as Record<string, string>,
      body: {
        wh: cancelBoxWh.value,
        reason: cancelBoxReason.value.trim(),
        cancelled_by: 'operator',
      },
    })
    $q.notify({
      type: 'positive',
      icon: 'cancel',
      message: `${cancelBoxWh.value} Box Cancelled — ${cancelBoxBatchId.value}`,
      caption: cancelBoxReason.value.trim(),
      position: 'top',
      timeout: 4000,
    })
    showCancelBoxDialog.value = false
    // Clear cache so it reloads
    boxContentsCache.value.delete(cancelBoxBatchId.value)
    // Refresh delivery list
    await fetchReadyToDeliver()
  } catch (e: any) {
    const msg = e?.data?.detail || e?.message || 'Failed to cancel box'
    $q.notify({ type: 'negative', message: msg, position: 'top' })
  } finally {
    cancelBoxLoading.value = false
  }
}
const fetchAllRecords = async () => {
  loadingRecords.value = true
  try {
    const [fh, spp] = await Promise.all([
      $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-recs/?limit=200&wh=FH`, {
        headers: getAuthHeader() as Record<string, string>
      }),
      $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-recs/?limit=200&wh=SPP`, {
        headers: getAuthHeader() as Record<string, string>
      }),
    ])
    fhRecords.value = fh || []
    sppRecords.value = spp || []
  } catch (e) {
    console.error('Error fetching records:', e)
  } finally {
    loadingRecords.value = false
  }
}

let _batchFetchController: AbortController | null = null
const fetchBatchRecords = async (batchId: string) => {
  // Cancel any in-flight request
  if (_batchFetchController) _batchFetchController.abort()
  _batchFetchController = new AbortController()
  try {
    const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/prebatch-recs/by-batch/${batchId}`, {
      headers: getAuthHeader() as Record<string, string>,
      signal: _batchFetchController.signal as AbortSignal,
    })
    batchRecords.value = data || []
  } catch (e: any) {
    if (e?.name !== 'AbortError') {
      console.error('Error fetching batch records:', e)
      batchRecords.value = []
    }
  }
}

// ═══════════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════════

const onPlanClick = (plan: any) => {
  selectedPlan.value = plan
}

const onBatchClick = (batch: any, plan: any) => {
  selectedBatch.value = batch
  selectedPlan.value = plan
  scanBatchId.value = batch.batch_id
  fetchBatchRecords(batch.batch_id)
  currentBoxScans.value = [] // Clear current scans when a new batch is selected
}

const onScanBatchEnter = async () => {
  if (!scanBatchId.value) return
  for (const plan of plans.value) {
    const batch = plan.batches?.find((b: any) => b.batch_id === scanBatchId.value)
    if (batch) {
      selectedBatch.value = batch
      selectedPlan.value = plan
      
      // Ensure we immediately load reqs and records before allowing bag verification
      await Promise.all([
        fetchBatchReqs(batch),
        fetchBatchRecords(batch.batch_id)
      ])

      $q.notify({ type: 'positive', message: `Batch ${batch.batch_id} loaded`, position: 'top' })
      currentBoxScans.value = [] // Clear current scans when a new batch is loaded
      return
    }
  }
  $q.notify({ type: 'warning', message: `Batch "${scanBatchId.value}" not found`, position: 'top' })
}

const isPacked    = (bag: any) => bag.packing_status === 1
const isPrepared  = (bag: any) => bag.recheck_status === 1 && bag.packing_status !== 1

// 3-tier status
const getBagStatus = (bag: any): 'boxed' | 'prepare' | 'waiting' => {
  if (bag.packing_status === 1) return 'boxed'
  if (bag.recheck_status === 1) return 'prepare'
  return 'waiting'
}
const getBagStatusColor = (bag: any) => {
  const s = getBagStatus(bag)
  if (s === 'boxed')   return 'blue-7'
  if (s === 'prepare') return 'orange-7'
  return 'grey-5'
}
const getBagStatusIcon = (bag: any) => {
  const s = getBagStatus(bag)
  if (s === 'boxed')   return 'inventory'
  if (s === 'prepare') return 'hourglass_top'
  return 'radio_button_unchecked'
}
const getBagStatusLabel = (bag: any) => {
  const s = getBagStatus(bag)
  if (s === 'boxed')   return 'Boxed'
  if (s === 'prepare') return 'Prepare'
  return 'Waiting'
}
const getBagRowClass = (bag: any) => {
  const s = getBagStatus(bag)
  if (s === 'boxed')   return 'bg-blue-1'
  if (s === 'prepare') return 'bg-orange-1'
  return ''
}

/** Close packing box — ready to transfer */
interface TransferredBox {
  id: string
  wh: 'FH' | 'SPP'
  batch_id: string
  bagsCount: number
  time: string
  inProduction: boolean
  // Status pipeline flags
  batch_size?: number
  sku_id?: string
  flavour_house?: boolean
  spp_flag?: boolean
  batch_prepare?: boolean
  ready_to_product?: boolean
  production_flag?: boolean
  done?: boolean
  // Packing counts
  fh_total?: number
  fh_packed?: number
  spp_total?: number
  spp_packed?: number
}
const transferredBoxes = ref<TransferredBox[]>([])
const allBatchStatuses = ref<any[]>([])

// ── Transfer Dialog ──────────────────────────────────────────────
const showTransferDialog   = ref(false)
const selectedForTransfer  = ref<string[]>([])   // list of TransferredBox.id
const filterDeliveryWh     = ref<'ALL'|'FH'|'SPP'>('ALL')
const filterDeliveryStatus = ref<'SHOW_ALL'|'ALL'|'WAITING'>('WAITING')  // SHOW_ALL=show everything, ALL=show delivered too, WAITING=pending only
const deliveredMap         = ref<Map<string, string>>(new Map())  // "batch_id-WH" → delivery time

watch(filterDeliveryStatus, () => { fetchReadyToDeliver() })

const markDelivered = async (batch_id: string, wh: 'FH' | 'SPP') => {
  const label = wh === 'FH' ? 'FH → SPP' : 'SPP → Production'
  try {
    await $fetch(`${appConfig.apiBaseUrl}/production-batches/by-batch-id/${batch_id}/deliver`, {
      method: 'PATCH',
      headers: getAuthHeader() as Record<string, string>,
      body: { wh, delivered_by: 'operator' },
    })
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    deliveredMap.value = new Map(deliveredMap.value).set(`${batch_id}-${wh}`, time)
    playSound('correct')
    $q.notify({ type: 'positive', icon: 'local_shipping', message: `✅ ${label}: ${batch_id} delivered at ${time}`, position: 'top', timeout: 2500 })
  } catch (e) {
    console.error('Error marking delivery:', e)
    $q.notify({ type: 'negative', message: `Failed to mark ${batch_id} ${wh} as delivered` })
  }
}

const cancelDelivery = async (batch_id: string, wh: 'FH' | 'SPP') => {
  $q.dialog({
    title: `Undo ${wh} Delivery`,
    message: `Are you sure you want to undo the delivery of ${batch_id} (${wh})?`,
    cancel: true,
    persistent: true,
    ok: { label: 'Undo Delivery', color: 'orange', icon: 'undo' },
  }).onOk(async () => {
    try {
      await $fetch(`${appConfig.apiBaseUrl}/production-batches/by-batch-id/${batch_id}/cancel-deliver`, {
        method: 'PATCH',
        headers: getAuthHeader() as Record<string, string>,
        body: { wh, delivered_by: 'operator' },
      })
      const newMap = new Map(deliveredMap.value)
      newMap.delete(`${batch_id}-${wh}`)
      deliveredMap.value = newMap
      playSound('correct')
      $q.notify({ type: 'positive', icon: 'undo', message: `${wh} delivery of ${batch_id} has been undone`, position: 'top', timeout: 2500 })
    } catch (e: any) {
      console.error('Error cancelling delivery:', e)
      $q.notify({ type: 'negative', message: `Failed to undo ${wh} delivery: ${e?.data?.detail || e.message}` })
    }
  })
}

const filteredBoxScans = computed(() => {
  if (filterMiddleWh.value === 'ALL') return currentBoxScans.value
  if (filterMiddleWh.value === 'FH') return currentBoxScans.value.filter(bag => isFH(bag.wh || ''))
  if (filterMiddleWh.value === 'SPP') return currentBoxScans.value.filter(bag => isSPP(bag.wh || ''))
  return currentBoxScans.value.filter(bag => bag.wh === filterMiddleWh.value)
})

/** Group items by re_code for current WH — merge prebatch_recs (per-package) + prebatch_items (fallback) */
interface BoxReqGroup { re_code: string; items: any[] }
const boxReqsGrouped = computed((): BoxReqGroup[] => {
  if (!selectedBatch.value) return []
  const wh = filterMiddleWh.value
  const whFilter = (r: any) => {
    if (wh === 'ALL') return true
    if (wh === 'FH') return isFH(r.wh || '')
    if (wh === 'SPP') return isSPP(r.wh || '')
    return r.wh === wh
  }

  // 1. Use prebatch_recs (per-package) as primary source  
  const recs = batchRecords.value.filter(whFilter)
  const map = new Map<string, BoxReqGroup>()
  const recCodes = new Set<string>()
  for (const r of recs) {
    const code = r.re_code || '?'
    recCodes.add(code)
    if (!map.has(code)) map.set(code, { re_code: code, items: [] })
    map.get(code)!.items.push(r)
  }

  // 2. Add prebatch_items that have NO recs (fallback for items without packages)
  if (selectedBatch.value.reqs) {
    for (const r of (selectedBatch.value.reqs as any[])) {
      if (!whFilter(r)) continue
      if (recCodes.has(r.re_code)) continue // already covered by recs
      const code = r.re_code || '?'
      if (!map.has(code)) map.set(code, { re_code: code, items: [] })
      map.get(code)!.items.push(r)
    }
  }
  return Array.from(map.values())
})

/** Count boxed vs total for current WH */
const boxReqsTotal = computed(() => boxReqsGrouped.value.reduce((s, g) => s + g.items.length, 0))
const boxReqsBoxed = computed(() => boxReqsGrouped.value.reduce((s, g) => s + g.items.filter(i => i.packing_status === 1).length, 0))
const allCurrentWhBoxed = computed(() => boxReqsTotal.value > 0 && boxReqsBoxed.value >= boxReqsTotal.value)

const filteredTransferredBoxes = computed(() => {
  return transferredBoxes.value.filter(b => b.wh === filterMiddleWh.value)
})

/** Group transferred boxes by batch_id so FH+SPP appear in one row */
interface TransferredBatchRow {
  batch_id: string
  fh: TransferredBox | null
  spp: TransferredBox | null
  time: string
  inProduction: boolean
}
const groupedTransferredBoxes = computed((): TransferredBatchRow[] => {
  const map = new Map<string, TransferredBatchRow>()
  for (const box of transferredBoxes.value) {
    if (!map.has(box.batch_id)) {
      map.set(box.batch_id, { batch_id: box.batch_id, fh: null, spp: null, time: box.time, inProduction: box.inProduction })
    }
    const row = map.get(box.batch_id)!
    if (box.wh === 'FH') row.fh = box
    else row.spp = box
    if (box.time !== '—') row.time = box.time
    if (box.inProduction) row.inProduction = true
  }
  return Array.from(map.values())
})

// Group delivery rows by SKU → Plan → Batches
interface DeliveryPlanGroup {
  plan_id: string
  batches: TransferredBatchRow[]
}
interface DeliverySkuGroup {
  sku_id: string
  sku_name: string
  plans: DeliveryPlanGroup[]
}
const deliveryBySku = computed((): DeliverySkuGroup[] => {
  const skuMap = new Map<string, { sku_name: string; planMap: Map<string, TransferredBatchRow[]> }>()
  for (const row of groupedTransferredBoxes.value) {
    const plan = plans.value.find((p: any) => p.batches?.some((b: any) => b.batch_id === row.batch_id))
    const planId = plan?.plan_id || row.batch_id.replace(/-\d+$/, '') || 'Unknown'
    const skuId = plan?.sku_id || 'Unknown'
    const skuName = plan?.sku_name || ''

    if (!skuMap.has(skuId)) skuMap.set(skuId, { sku_name: skuName, planMap: new Map() })
    const entry = skuMap.get(skuId)!
    if (!entry.planMap.has(planId)) entry.planMap.set(planId, [])
    entry.planMap.get(planId)!.push(row)
  }
  const result: DeliverySkuGroup[] = []
  for (const [skuId, entry] of skuMap) {
    const plans: DeliveryPlanGroup[] = []
    for (const [planId, batches] of entry.planMap) {
      plans.push({ plan_id: planId, batches })
    }
    result.push({ sku_id: skuId, sku_name: entry.sku_name, plans })
  }
  return result
})

// ── Paused Boxes storage (in-memory) ──
const pausedBoxes = ref<any[]>([])

/** Pause current box — save state and clear UI for a new box */
const onPauseBox = () => {
  if (!selectedBatch.value) return
  const batchId = selectedBatch.value.batch_id
  const wh = filterMiddleWh.value === 'ALL' ? 'FH' : filterMiddleWh.value

  // Save current box state
  const existingIdx = pausedBoxes.value.findIndex(p => p.batch_id === batchId && p.wh === wh)
  const pausedData = {
    batch_id: batchId,
    wh,
    scans: [...currentBoxScans.value],
    pausedAt: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  }
  if (existingIdx >= 0) {
    pausedBoxes.value[existingIdx] = pausedData
  } else {
    pausedBoxes.value.push(pausedData)
  }

  playSound('correct')
  $q.notify({
    type: 'info',
    icon: 'pause_circle',
    message: `Box paused: ${batchId} [${wh}]`,
    caption: `${currentBoxScans.value.length} items saved. Scan a new batch to start a new box.`,
    position: 'top',
    timeout: 3000,
  })

  // Clear UI for new box
  currentBoxScans.value = []
  selectedBatch.value = null
  scanBatchId.value = ''
  batchRecords.value = []
  scanFH.value = ''
  scanSPP.value = ''
}

/** Resume a paused box */
const onResumeBox = async (pausedBox: any) => {
  scanBatchId.value = pausedBox.batch_id
  await onScanBatchEnter()
  currentBoxScans.value = pausedBox.scans || []
  filterMiddleWh.value = pausedBox.wh || 'FH'
  // Remove from paused list
  pausedBoxes.value = pausedBoxes.value.filter(p => !(p.batch_id === pausedBox.batch_id && p.wh === pausedBox.wh))
  $q.notify({
    type: 'positive',
    icon: 'play_circle',
    message: `Resumed box: ${pausedBox.batch_id} [${pausedBox.wh}]`,
    position: 'top',
    timeout: 2000,
  })
}

const onCloseBox = (wh: 'FH' | 'SPP') => {
  if (!selectedBatch.value) return
  const batchId = selectedBatch.value.batch_id

  // Check if this box is already closed (in transferred/delivered boxes)
  const alreadyClosed = transferredBoxes.value.some(
    (b: any) => b.batch_id === batchId && (b.wh === wh || b.wh === 'ALL')
  )
  if (alreadyClosed) {
    playSound('wrong')
    $q.notify({
      type: 'warning',
      icon: 'error',
      message: `${wh} Box already closed for ${batchId}`,
      caption: 'Cannot close again. Only one box per batch.',
      position: 'top',
      timeout: 3000,
    })
    return
  }

  // Get all items for this WH: prebatch_recs (per-package) + prebatch_items fallback
  const whMatcher = (r: any) => wh === 'FH' ? isFH(r.wh || '') : isSPP(r.wh || '')
  const recs = batchRecords.value.filter(whMatcher)
  const recCodes = new Set(recs.map((r: any) => r.re_code))
  // Add prebatch_items that have no recs
  const itemsFallback = ((selectedBatch.value.reqs || []) as any[]).filter((r: any) =>
    whMatcher(r) && !recCodes.has(r.re_code)
  )
  const whReqs = [...recs, ...itemsFallback]
  const boxedReqs = whReqs.filter((r: any) => r.packing_status === 1)
  const waitReqs = whReqs.filter((r: any) => r.packing_status !== 1)

  if (whReqs.length === 0) {
     $q.notify({ type: 'warning', message: `No items found for ${wh} box.`, position: 'top' })
     return
  }

  const allBoxed = waitReqs.length === 0
  const statusMsg = allBoxed
    ? `All ${boxedReqs.length} items are boxed. Seal and print label?`
    : `${boxedReqs.length}/${whReqs.length} items boxed (${waitReqs.length} still waiting). Seal anyway?`

  $q.dialog({
    title: `Close ${wh} Packing Box`,
    message: statusMsg,
    cancel: true,
    persistent: true,
    ok: { label: 'Seal & Print', color: allBoxed ? 'green' : 'orange', icon: 'check_circle' },
  }).onOk(async () => {
    try {
      // Close the box on the batch
      console.log(`[CloseBox] Closing ${wh} box for batch ${batchId}...`)
      await $fetch(`${appConfig.apiBaseUrl}/production-batches/by-batch-id/${batchId}/box-close`, {
        method: 'PATCH',
        headers: getAuthHeader() as Record<string, string>,
        body: { wh },
      })
      console.log(`[CloseBox] ✅ ${wh} box closed successfully`)
      playSound('correct')
      $q.notify({
        type: 'positive',
        icon: 'local_shipping',
        message: `✅ ${wh} Box Closed & Ready for Delivery!`,
        position: 'top',
        timeout: 3000,
      })
      
      // Auto-trigger the print box label function
      await printBoxLabel(wh)
      
      // Refresh data
      await fetchBatchRecords(batchId)
      await fetchAllRecords()
      await fetchReadyToDeliver()
      console.log(`[CloseBox] Data refreshed. Transferred boxes:`, transferredBoxes.value.length)

      // Reset all state — wait for next box scan
      currentBoxScans.value = []
      selectedBatch.value = null
      scanBatchId.value = ''
      batchRecords.value = []
      scanFH.value = ''
      scanSPP.value = ''
    } catch (e) {
      console.error('Error closing box:', e)
      $q.notify({ type: 'negative', message: `Failed to close ${wh} box for ${batchId}` })
    }
  })
}

// ── Reprint Box Label for already-closed box ──────────────
const reprintBoxLabel = async (box: any) => {
  try {
    $q.notify({ type: 'info', icon: 'print', message: `Reprinting label for ${box.batch_id} [${box.wh}]...`, position: 'top', timeout: 1500 })

    // Save current state
    const prevBatch = selectedBatch.value
    const prevRecords = batchRecords.value

    // Temporarily load the batch data for printing
    const batchId = box.batch_id
    // Load batch items
    const itemsData: any = await $fetch(`${appConfig.apiBaseUrl}/prebatch-items/by-batch/${batchId}`, {
      headers: getAuthHeader() as Record<string, string>,
    })
    // Load batch records (per-package)
    let recsData: any[] = []
    try {
      recsData = await $fetch(`${appConfig.apiBaseUrl}/prebatch-recs/by-batch/${batchId}`, {
        headers: getAuthHeader() as Record<string, string>,
      }) as any[]
    } catch { /* no recs — OK */ }

    // Find the plan and batch info
    const plan = plans.value.find((p: any) => p.batches?.some((b: any) => b.batch_id === batchId))
    const batchData = plan?.batches?.find((b: any) => b.batch_id === batchId)

    // Temporarily set state for printing
    selectedBatch.value = { batch_id: batchId, reqs: itemsData || [], ...batchData }
    batchRecords.value = recsData

    // Print
    await printBoxLabel(box.wh as 'FH' | 'SPP')

    // Restore state
    selectedBatch.value = prevBatch
    batchRecords.value = prevRecords
  } catch (e) {
    console.error('Error reprinting box label:', e)
    $q.notify({ type: 'negative', message: `Failed to reprint label for ${box.batch_id}` })
  }
}

// ── Print Functions (composable) ──────────────────────────────────
const { printPackingBoxReport, printTransferReport, printBoxLabel, printBagLabel } = usePackingPrints({
  $q,
  plans,
  selectedBatch,
  batchInfo,
  bagsByWarehouse,
  allRecords,
  transferredBoxes,
  selectedForTransfer,
  showTransferDialog,
  currentBoxScans,
  filteredBoxScans,
  batchRecords,
})

// ── Inline Print: Packing Box Label (no new tab) ──────────────────
const printBoxLabelInline = async (batchId: string, wh: string) => {
  // Ensure box contents are loaded
  if (!boxContentsCache.value.has(batchId)) {
    await fetchBoxContents(batchId)
  }
  const contents = boxContentsCache.value.get(batchId)
  if (!contents || contents._loading) {
    $q.notify({ type: 'warning', message: 'Box contents still loading, try again.', position: 'top' })
    return
  }

  const plan = plans.value.find((p: any) => p.batches?.some((b: any) => b.batch_id === batchId))

  // Build ingredient rows from box contents
  const ROW_H = 14, START_Y = 0, MAX_Y = 118
  let pages: string[] = []
  let curY = START_Y
  let currentRowsSvg = ''

  const pushPageAndReset = () => {
    pages.push(currentRowsSvg)
    currentRowsSvg = ''
    curY = START_Y
  }

  // Filter to only the selected WH
  const whGroups = contents.wh_groups.filter(g => g.wh === wh)
  let rowIdx = 0
  for (const whGrp of whGroups) {
    for (const reGrp of whGrp.re_codes) {
      if (curY + ROW_H > MAX_Y) pushPageAndReset()

      const bg = rowIdx % 2 === 0 ? '#f0f0f0' : '#ffffff'
      const statusIcon = reGrp.status === 2 ? '✓' : reGrp.status === 1 ? '◐' : '○'
      currentRowsSvg += `
        <rect x="10" y="${curY}" width="364" height="${ROW_H}" fill="${bg}"/>
        <text x="14" y="${curY + 10}" style="font-size:9px;font-family:Arial,sans-serif;font-weight:bold;fill:#000000">${statusIcon} ${reGrp.re_code}</text>
        <text x="120" y="${curY + 10}" style="font-size:8px;font-family:Arial,sans-serif;fill:#555555">${(reGrp.ingredient_name || '').substring(0, 30)}</text>
        <text x="370" y="${curY + 10}" text-anchor="end" style="font-size:9px;font-family:Arial,sans-serif;font-weight:bold;fill:#000000">${reGrp.total_weight.toFixed(4)}</text>
        <line x1="10" y1="${curY + ROW_H}" x2="374" y2="${curY + ROW_H}" stroke="#e0e0e0" stroke-width="0.5"/>`
      curY += ROW_H
      rowIdx++
    }
  }
  if (currentRowsSvg !== '') pages.push(currentRowsSvg)
  if (pages.length === 0) {
    pages.push(`<text x="192" y="40" text-anchor="middle" style="font-size:12px;font-family:Arial,sans-serif;fill:#999999">No items in box</text>`)
  }

  const totalWt = whGroups.reduce((sum, g) => sum + g.total_weight, 0)
  const now = new Date()
  const printDate = now.toLocaleDateString('en-GB') + ' ' + now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })

  try {
    const resp = await fetch('/labels/packingbox-label_4x3.svg')
    const templateSvg = await resp.text()

    let finalSvgContent = ''
    const totalPages = pages.length

    for (let i = 0; i < totalPages; i++) {
      const boxNum = i + 1
      const boxIdVal = totalPages > 1 ? `${batchId}-${wh}-${boxNum}/${totalPages}` : `${batchId}-${wh}`

      let pageSvg = templateSvg
        .replaceAll('{{Warehouse}}', wh)
        .replaceAll('{{PrintDate}}', printDate)
        .replace('{{BoxId}}', boxIdVal)
        .replace('{{Plant}}', plan?.plant || 'Line-1')
        .replace('{{TotalNetWeight}}', totalWt.toFixed(4))
        .replace('{{PreBatchRows}}', pages[i] || '')

      const QRCode = (await import('qrcode')).default
      const qrDataUrl = await QRCode.toDataURL(boxIdVal, { width: 72, margin: 1, color: { dark: '#000000', light: '#ffffff' } })
      pageSvg = pageSvg.replace('{{BoxQRCode}}', `<image x="0" y="0" width="72" height="72" href="${qrDataUrl}" />`)

      finalSvgContent += pageSvg
    }

    // Print via hidden iframe (no new tab)
    const iframe = document.createElement('iframe')
    iframe.style.position = 'fixed'
    iframe.style.top = '-10000px'
    iframe.style.left = '-10000px'
    iframe.style.width = '0'
    iframe.style.height = '0'
    iframe.style.border = 'none'
    document.body.appendChild(iframe)

    const iframeDoc = iframe.contentDocument || iframe.contentWindow?.document
    if (!iframeDoc) {
      $q.notify({ type: 'negative', message: 'Cannot create print frame', position: 'top' })
      document.body.removeChild(iframe)
      return
    }
    iframeDoc.open()
    iframeDoc.write(`<!DOCTYPE html><html><head>
      <title>Box Label — ${batchId} [${wh}]</title>
      <style>
        @page { size: 4in 3in; margin: 0; }
        body { margin: 0; padding: 0; }
        svg { display: block; width: 4in; height: 3in; page-break-after: always; }
        svg:last-of-type { page-break-after: auto; }
      </style>
    </head><body>${finalSvgContent}</body></html>`)
    iframeDoc.close()

    // Wait for content to render, then print
    iframe.onload = () => {
      setTimeout(() => {
        iframe.contentWindow?.print()
        // Clean up after print dialog closes
        setTimeout(() => {
          document.body.removeChild(iframe)
        }, 1000)
      }, 300)
    }
    // Trigger load for about:blank iframes
    if (iframe.contentDocument?.readyState === 'complete') {
      setTimeout(() => {
        iframe.contentWindow?.print()
        setTimeout(() => {
          document.body.removeChild(iframe)
        }, 1000)
      }, 300)
    }
  } catch (e) {
    console.error('Print error:', e)
    $q.notify({ type: 'negative', message: 'Failed to load label template', position: 'top' })
  }
}




// ── Scan Simulation ─────────────────────────────────────────────
const openScanSimulator = (wh: 'FH' | 'SPP') => {
  scanDialogWh.value = wh
  showScanDialog.value = true
}

const onItemClick = (req: any) => {
  if (!selectedBatch.value) return
  // Fuzzy WH matching: check if item's WH matches the selected filter
  const reqWh = req.wh || ''
  const whMatches = filterMiddleWh.value === 'ALL' ||
    (filterMiddleWh.value === 'FH' && isFH(reqWh)) ||
    (filterMiddleWh.value === 'SPP' && isSPP(reqWh))
  if (!whMatches) {
    playSound('wrong')
    $q.notify({ type: 'warning', message: `Cannot pack ${req.wh} item while viewing ${filterMiddleWh.value}`, position: 'top', timeout: 2000 })
    return
  }
  if (req.packing_status === 1 || currentBoxScans.value.some(b => b.id === req.id || b.req_id === req.id)) {
    playSound('wrong')
    $q.notify({ type: 'info', message: 'Already packed or in box', position: 'top', timeout: 1000 })
    return
  }
  
  playSound('correct')
  currentBoxScans.value.push(req)
  $q.notify({
    type: 'positive',
    icon: 'check_circle',
    message: `✅ ${req.re_code} added to ${req.wh} box`,
    position: 'top',
    timeout: 1000,
  })
}

/** Click an ingredient requirement row to simulate scanning it into the Current Box */
const onIngredientScanClick = (ing: IngredientReq) => {
  if (!selectedBatch.value) {
    playSound('wrong')
    $q.notify({ type: 'negative', message: 'Please select a Packing Box first!', icon: 'warning', position: 'top' })
    return
  }
  const reqs = selectedBatch.value.reqs || []
  // Helper: match warehouse using fuzzy isFH/isSPP
  const whMatcher = isFH(ing.wh) ? isFH : (isSPP(ing.wh) ? isSPP : (w: string) => w === ing.wh)
  
  // 1. Try to find an unpacked req matching re_code + wh
  let req = reqs.find((r: any) =>
    r.re_code === ing.re_code && whMatcher(r.wh || '') && r.packing_status !== 1
    && !currentBoxScans.value.some(b => b.id === r.id)
  )
  // 2. Fallback: match by re_code only (unpacked)
  if (!req) {
    req = reqs.find((r: any) =>
      r.re_code === ing.re_code && r.packing_status !== 1
      && !currentBoxScans.value.some(b => b.id === r.id)
    )
  }
  // 3. Final fallback: any matching req (even packed — onItemClick will show message)
  if (!req) {
    req = reqs.find((r: any) => r.re_code === ing.re_code && whMatcher(r.wh || ''))
    || reqs.find((r: any) => r.re_code === ing.re_code)
  }
  if (!req) {
    playSound('wrong')
    $q.notify({ type: 'warning', message: `No matching requirement found for ${ing.re_code}`, position: 'top', timeout: 2000 })
    return
  }
  onItemClick(req)
}

const onSimScanClick = async (bag: any) => {
  if (!selectedBatch.value) {
    playSound('wrong')
    $q.notify({ type: 'negative', message: 'Please select a Packing Box first!', icon: 'warning', position: 'top' })
    return
  }

  const bagWh = bag.wh || ''
  const whOk = filterMiddleWh.value === 'ALL' ||
    (filterMiddleWh.value === 'FH' && isFH(bagWh)) ||
    (filterMiddleWh.value === 'SPP' && isSPP(bagWh))
  if (!whOk) {
    playSound('wrong')
    $q.notify({ type: 'warning', message: `Cannot pack ${bag.wh} item while viewing ${filterMiddleWh.value}`, caption: bag.re_code, position: 'top', timeout: 2000 })
    return
  }

  // Check if this bag belongs to the selected batch
  const batchReqs = selectedBatch.value.reqs || []
  const batchId = selectedBatch.value.batch_id
  const belongsToBox = 
    // Match by batch_record_id prefix (e.g. P260311-02-02-001-FV044A-1 starts with P260311-02-02-001)
    (bag.batch_record_id && bag.batch_record_id.startsWith(batchId)) ||
    // Or match by re_code existing in batch reqs
    batchReqs.some((r: any) => r.re_code === bag.re_code)

  if (belongsToBox) {
    // Correct — this bag belongs to the selected packing box
    playSound('correct')

    // Find the specific PACKAGE in batchRecords to update packing_status
    // Match by batch_record_id first (exact package), then by re_code (first unpacked)
    const matchingRec = batchRecords.value.find((r: any) => r.batch_record_id === bag.batch_record_id && r.packing_status !== 1)
      || batchRecords.value.find((r: any) => r.re_code === bag.re_code && r.packing_status !== 1)
    if (matchingRec && matchingRec.packing_status !== 1) {
      try {
        await $fetch(`${appConfig.apiBaseUrl}/prebatch-recs/${matchingRec.id}/packing-status`, {
          method: 'PATCH',
          headers: getAuthHeader() as Record<string, string>,
          body: { packing_status: 1, packed_by: 'operator' },
        })
        matchingRec.packing_status = 1
      } catch (e) {
        console.error('Failed to update prebatch-rec packing status:', e)
      }
    } else {
      // Fallback: update prebatch_items if no prebatch_rec exists for this ingredient
      const matchingItem = batchReqs.find((r: any) => r.re_code === bag.re_code && r.packing_status !== 1)
      if (matchingItem) {
        try {
          await $fetch(`${appConfig.apiBaseUrl}/prebatch-items/${matchingItem.id}/packing-status`, {
            method: 'PATCH',
            headers: getAuthHeader() as Record<string, string>,
            body: { packing_status: 1, packed_by: 'operator' },
          })
          matchingItem.packing_status = 1
        } catch (e) {
          console.error('Failed to update prebatch-item packing status:', e)
        }
      }
    }

    // Add to currentBoxScans if not already there
    if (!currentBoxScans.value.some(b => b.id === bag.id)) {
      currentBoxScans.value.push(bag)
    }
    
    $q.notify({
      type: 'positive',
      icon: 'check_circle',
      message: `✅ ${bag.re_code} packed into box`,
      caption: bag.batch_record_id,
      position: 'top',
      timeout: 2000,
    })
  } else {
    // Wrong — this bag does NOT belong to the selected packing box
    playSound('wrong')
    $q.notify({
      type: 'negative',
      icon: 'error',
      message: `❌ Wrong box! This bag belongs to a different batch`,
      caption: `Bag: ${bag.batch_record_id} ≠ Box: ${selectedBatch.value.batch_id}`,
      position: 'top',
      timeout: 3000,
    })
  }
  showScanDialog.value = false
}

/** 
 * Shared logic for both text input scans and MQTT scans 
 */
const processBagScan = async (rawScan: string) => {
  if (!rawScan) return
  let barcode = rawScan
  let inferredBatchId = null
  let scannedReCode = ''

  // 1a) Parse NEW JSON QR format:
  //    {"b":"P260311-02-02-002","m":"1200000041000029","p":"1/2","n":5.398,"t":10.71}
  //    m = mat_sap_code (SAP material code), not re_code
  if (rawScan.trim().startsWith('{')) {
    try {
      const qr = JSON.parse(rawScan.trim())
      if (qr.b) {
        inferredBatchId = qr.b
        // Look up re_code from mat_sap_code (m field)
        if (qr.m) {
          // 1. Try bagsByWarehouse (prebatch_recs)
          const allBagsSearch = [...bagsByWarehouse.value.FH, ...bagsByWarehouse.value.SPP]
          let matchedIng = allBagsSearch.find((i: any) => i.mat_sap_code === qr.m)
          
          // 2. Try ingredients API lookup for SAP code → re_code
          if (!matchedIng) {
            try {
              const ings = await $fetch<any[]>(`${appConfig.apiBaseUrl}/ingredients/?limit=200`, {
                headers: getAuthHeader() as Record<string, string>,
              })
              const ingMatch = ings?.find((i: any) => String(i.mat_sap_code) === String(qr.m))
              if (ingMatch) {
                scannedReCode = ingMatch.re_code
                console.log(`[JSON QR] mat_sap_code ${qr.m} → re_code ${scannedReCode} (via ingredients)`)
              }
            } catch (e) {
              console.error('Failed to lookup ingredients for SAP code:', e)
            }
          } else {
            scannedReCode = matchedIng.re_code
          }
        }
        barcode = `${qr.b}-${scannedReCode || qr.m}`
      }
    } catch (e) {
      // Not valid JSON, fall through to other parsers
    }
  }

  // 1b) Parse OLD comma-separated barcode format:
  //    Format A: "seq,batchId,concatPrebatchId,reCode,weight"
  //      e.g. "9,P260311-03-03-001,P260311-03-03-001FV021A01,FV021A,2"
  //    Format B: "planId,prebatchId,,reCode,weight"
  //      e.g. "P260311-01-01,P260311-01-01-001-CL001A-1,,CL001A,0.24"
  if (!inferredBatchId && rawScan.includes(',')) {
    const parts = rawScan.split(',')
    if (parts.length >= 4) {
      const field0 = parts[0]?.trim() || ''
      const field1 = parts[1]?.trim() || ''
      const field3 = parts[3]?.trim() || ''
      scannedReCode = field3 // re_code is always parts[3]

      // Detect format: if parts[0] is numeric → Format A, else → Format B
      if (/^\d+$/.test(field0)) {
        // Format A: seq,batchId,concatId,reCode,weight
        inferredBatchId = field1  // e.g. "P260311-03-03-001"
      } else {
        // Format B: planId,prebatchId,,reCode,weight
        // Extract batch_id from the prebatchId by removing the re_code suffix
        const prebatchId = field1 // e.g. "P260311-01-01-001-CL001A-1"
        if (scannedReCode && prebatchId.includes(`-${scannedReCode}-`)) {
          inferredBatchId = prebatchId.split(`-${scannedReCode}-`)[0] // e.g. "P260311-01-01-001"
        } else {
          // Fallback: search across plans
          inferredBatchId = field1
        }
        barcode = prebatchId // Use the full prebatchId for item search
      }
    } else if (parts.length > 1) {
      barcode = parts[1]?.trim() || ''
    }
  }

  // 2) If no batch ID parsed from commas, search across all plans/batches
  if (!inferredBatchId) {
    for (const plan of plans.value) {
      for (const batch of plan.batches || []) {
        if (rawScan.includes(batch.batch_id)) {
          inferredBatchId = batch.batch_id
          break
        }
      }
      if (inferredBatchId) break
    }
  }

  // 3) Auto Select Box if not selected or different from current scan
  if (inferredBatchId && (!selectedBatch.value || selectedBatch.value?.batch_id !== inferredBatchId)) {
    // If a box is currently active, ask user before switching
    if (selectedBatch.value && selectedBatch.value.batch_id !== inferredBatchId) {
      const currentBatch = selectedBatch.value.batch_id
      return new Promise<boolean>((resolve) => {
        $q.dialog({
          title: 'Different Batch Scanned',
          message: `You scanned batch "${inferredBatchId}" but current box is "${currentBatch}".\n\nStart a new box or keep scanning current box?`,
          cancel: { label: 'Keep Current Box', color: 'grey', flat: true },
          ok: { label: 'Start New Box', color: 'orange', icon: 'swap_horiz' },
          persistent: true,
        }).onOk(async () => {
          // Switch to new batch
          scanBatchId.value = inferredBatchId!
          await onScanBatchEnter()
          resolve(true)
        }).onCancel(() => {
          // Stay on current box — play error since it's wrong batch
          playSound('wrong')
          $q.notify({ type: 'warning', icon: 'error', message: 'Wrong batch for this box!', caption: `Scanned: ${inferredBatchId} | Current: ${currentBatch}`, position: 'top', timeout: 3000 })
          resolve(false)
        })
      })
    }
    scanBatchId.value = inferredBatchId
    await onScanBatchEnter() // Automatically loads the batch and displays req ingredients
  }

  // If STILL no batch selected, we cannot proceed
  if (!selectedBatch.value) {
    // Treat as raw batch ID scan fallback if it wasn't comma separated
    if (!rawScan.includes(',')) {
      scanBatchId.value = rawScan.trim()
      await onScanBatchEnter()
      if (selectedBatch.value) return true // Was purely a box select scan
    }
    
    if (!selectedBatch.value) {
      playSound('wrong')
      $q.notify({ type: 'negative', message: t('packingList.selectBatchFirst'), icon: 'warning', position: 'top' })
    }
    return false
  }

  // 4) Try to find the matching ingredient in the selected batch
  const batchReqs = selectedBatch.value.reqs || []
  const allBags = [...bagsByWarehouse.value.FH, ...bagsByWarehouse.value.SPP]

  let bag = null
  let item = null

  // Primary: Match by exact batch_record_id (specific package like FV044A-2)
  bag = allBags.find(x => x.batch_record_id === barcode)
  item = batchReqs.find((r: any) => r.batch_record_id === barcode)

  // Then try by re_code — prefer UNPACKED items first (to avoid "Already packed" on wrong package)
  if (!bag && !item && scannedReCode) {
    bag = allBags.find(x => x.re_code === scannedReCode && x.packing_status !== 1)
      || allBags.find(x => x.re_code === scannedReCode)
    item = batchReqs.find((r: any) => r.re_code === scannedReCode && r.packing_status !== 1)
      || batchReqs.find((r: any) => r.re_code === scannedReCode)
  }

  // Fallback: match by prebatch_id / batch_record_id
  if (!bag && !item) {
    bag = allBags.find(x => x.batch_record_id === barcode || x.prebatch_id === barcode || x.id?.toString() === barcode || x.intake_id === barcode)
    item = batchReqs.find((r: any) => r.batch_record_id === barcode || r.prebatch_id === barcode)
  }

  // Fallback: try each comma part
  if (!bag && !item && rawScan.includes(',')) {
    const parts = rawScan.split(',').map(p => p.trim())
    for (const p of parts) {
      if (!p) continue
      bag = allBags.find(x => x.batch_record_id === p || x.prebatch_id === p || x.re_code === p)
      item = batchReqs.find((r: any) => r.batch_record_id === p || r.prebatch_id === p || r.re_code === p)
      if (bag || item) { barcode = p; break }
    }
  }

  if (!bag && !item) {
    playSound('wrong')
    $q.notify({ type: 'negative', icon: 'error', message: t('packingList.bagNotFound'), caption: scannedReCode || barcode, position: 'top', timeout: 3000 })
    return false
  }

  // 5) Auto-fill Department (FH / SPP) based on scanned ingredient
  const foundWh = bag ? bag.wh : (item?.wh)
  if (foundWh && (foundWh === 'FH' || foundWh === 'SPP')) {
    filterMiddleWh.value = foundWh
  }

  // 6) Process Packing
  if (bag) {
    if (isPacked(bag)) {
      playSound('wrong')
      $q.notify({ type: 'warning', icon: 'error', message: 'This PreBatch already Boxed!', caption: bag.batch_record_id || bag.re_code, position: 'top', timeout: 3000 })
    } else {
      await onSimScanClick(bag) // Handles the frontend UI packing logic + notifying
    }
  } else if (item) {
    if (item.packing_status === 1) {
      playSound('wrong')
      $q.notify({ type: 'warning', icon: 'error', message: 'This PreBatch already Boxed!', caption: item.batch_record_id || item.re_code, position: 'top', timeout: 3000 })
    } else {
      playSound('correct')
      try {
        await $fetch(`${appConfig.apiBaseUrl}/prebatch-items/${item.id}/packing-status`, {
          method: 'PATCH',
          headers: getAuthHeader() as Record<string, string>,
          body: { packing_status: 1, packed_by: 'operator' },
        })
        item.packing_status = 1
        // Add to current box visually
        if (!currentBoxScans.value.some((b: any) => b.id === item.id)) {
          currentBoxScans.value.push(item)
        }
        $q.notify({
          type: 'positive',
          icon: 'check_circle',
          message: `✅ ${item.re_code} packed into box`,
          caption: item.batch_record_id,
          position: 'top',
          timeout: 2000,
        })
      } catch (e) {
        console.error('Failed to update packing status:', e)
        $q.notify({ type: 'negative', message: 'Failed to update packing status', position: 'top' })
      }
    }
  }
  return true
}

/** Handle scan input from FH/SPP scan fields via Keyboard */
const onScanInputEnter = async (wh: 'FH' | 'SPP') => {
  const scanValue = wh === 'FH' ? scanFH.value.trim() : scanSPP.value.trim()
  if (scanValue) {
    await processBagScan(scanValue)
  }
  // Always clear the input after processing, whether successful or not
  if (wh === 'FH') scanFH.value = ''
  else scanSPP.value = ''
}

// Auto-detect barcode scanner paste (comma-separated data) — no Enter key needed
let _scanDebounceTimer: ReturnType<typeof setTimeout> | null = null
watch(scanFH, (val) => {
  if (_scanDebounceTimer) clearTimeout(_scanDebounceTimer)
  if (val && val.includes(',')) {
    _scanDebounceTimer = setTimeout(() => { onScanInputEnter('FH') }, 300)
  }
})
watch(scanSPP, (val) => {
  if (_scanDebounceTimer) clearTimeout(_scanDebounceTimer)
  if (val && val.includes(',')) {
    _scanDebounceTimer = setTimeout(() => { onScanInputEnter('SPP') }, 300)
  }
})

// Watch for MQTT scans — smart routing: intake ID vs batch ID
watch(lastScan, async (scan) => {
  if (!scan?.barcode) return
  await processBagScan(scan.barcode.trim())
})

// Auto-popup Close Box when all prebatch items for current WH are boxed
let _closeBoxTriggered = false
watch(allCurrentWhBoxed, (allBoxed) => {
  if (!allBoxed || !selectedBatch.value) {
    _closeBoxTriggered = false  // reset when condition changes
    return
  }
  if (_closeBoxTriggered) return  // prevent double trigger
  _closeBoxTriggered = true
  const wh = filterMiddleWh.value === 'ALL' ? 'FH' : filterMiddleWh.value
  playSound('correct')
  // Auto-trigger Close Box dialog after a short delay
  setTimeout(() => onCloseBox(wh as 'FH' | 'SPP'), 600)
}, { immediate: true })

// ═══════════════════════════════════════════════════════════════════
// LIFECYCLE
// ═══════════════════════════════════════════════════════════════════

// ── Packing List Report ──────────────
const showPackingReportDialog = ref(false)
const packingReportLoading = ref(false)
const packingReportPlanId = ref('')

const printPackingListReport = async () => {
  packingReportLoading.value = true
  const planId = packingReportPlanId.value || selectedPlan.value?.plan_id
  if (!planId) { $q.notify({ type: 'warning', message: 'Select plan first' }); packingReportLoading.value = false; return }
  const printWindow = window.open('', '_blank')
  if (!printWindow) { packingReportLoading.value = false; return }
  printWindow.document.write('<html><body><h2 style="font-family:sans-serif;color:#1565c0;">⏳ Loading...</h2></body></html>')
  try {
    const data = await $fetch<any>(`${appConfig.apiBaseUrl}/reports/packing-list/${planId}`)
    const now = new Date().toLocaleString('en-GB')
    const bagRows = (data.bags || []).map((b: any, i: number) => `
      <tr class="${b.packing_status === 1 ? 'bg-ok' : ''}"><td class="tc">${i+1}</td><td>${b.batch_record_id}</td><td>${b.re_code || '-'}</td><td>${b.mat_sap_code || '-'}</td><td class="tc">${b.package_no || '-'}/${b.total_packages || '-'}</td><td class="tr">${(b.net_volume || 0).toFixed(4)}</td><td class="tc">${b.packing_status === 1 ? '✅ Packed' : '⏳ Unpacked'}</td><td class="tc">${b.recheck_status === 1 ? '✅' : (b.recheck_status === 2 ? '❌' : '⏳')}</td><td class="tc">${b.packed_at ? new Date(b.packed_at).toLocaleString('en-GB') : '-'}</td></tr>
    `).join('')
    const s = data.summary || {}
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Packing List</title>
    <style>@page{size:A4 landscape;margin:8mm 10mm}*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Courier Prime',monospace;font-size:13px;color:#222;line-height:1.4}.header{background:#1565c0;color:#fff;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;border-radius:4px;margin-bottom:8px}.header h1{font-size:22px;margin:0}.info-bar{background:#e3f2fd;padding:8px 14px;border-radius:3px;margin-bottom:10px;font-size:13px;color:#1565c0;font-weight:bold}table.dt{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}table.dt th{background:#546e7a;color:#fff;padding:4px 8px;text-align:left;font-size:10px;text-transform:uppercase}table.dt td{padding:4px 8px;border-bottom:1px solid #e0e0e0;overflow:hidden;text-overflow:ellipsis}.bg-ok{background:#e8f5e9}.grand{background:#1565c0;color:#fff;padding:12px 18px;border-radius:4px;font-size:14px;margin-top:10px;display:flex;justify-content:space-between}.footer{border-top:2px solid #1565c0;font-size:10px;color:#888;padding:6px 0;margin-top:10px;display:flex;justify-content:space-between}.tr{text-align:right}.tc{text-align:center}@media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}</style></head><body>
    <div class="header"><div><h1>📦 Packing List Report</h1><div style="font-size:12px;margin-top:3px;opacity:.85">xMixing Control System</div></div><div style="font-size:12px;text-align:right;opacity:.9">Generated: ${now}</div></div>
    <div class="info-bar">📋 Plan: ${data.plan_id} | SKU: ${data.sku_id} — ${data.sku_name || ''} | Volume: ${(data.total_volume || 0).toFixed(4)} kg</div>
    <div class="info-bar" style="background:#e8f5e9;color:#2e7d32;">Bags: ${s.total_bags || 0} | Packed: ${s.packed || 0} | Unpacked: ${s.unpacked || 0} | Checked: ${s.checked || 0}</div>
    <table class="dt"><thead><tr><th style="width:3%">#</th><th>Batch Record ID</th><th>RE Code</th><th>Mat SAP Code</th><th class="tc">Pkg</th><th class="tr">Net Vol (kg)</th><th class="tc">Packing</th><th class="tc">QC</th><th class="tc">Packed At</th></tr></thead>
    <tbody>${bagRows || '<tr><td colspan="9" class="tc">No bags</td></tr>'}</tbody></table>
    <div class="grand"><span>Total: ${s.total_bags || 0} bags</span><span>Packed: ${s.packed || 0} | Unpacked: ${s.unpacked || 0}</span></div>
    <div class="footer"><span>xMixing 2025 | xMix.co.th</span><span>Packing List — ${data.plan_id}</span></div>
    </body></html>`
    printWindow.document.open(); printWindow.document.write(html); printWindow.document.close()
    showPackingReportDialog.value = false
  } catch (e) { console.error(e); printWindow.close(); $q.notify({ type: 'negative', message: 'Failed' }) }
  finally { packingReportLoading.value = false }
}

onMounted(async () => {
  loadSoundSettings()
  connect()
  // Parallel fetch — plans, records, and delivery list
  await Promise.all([fetchPlans(), fetchAllRecords(), fetchReadyToDeliver()])
})
</script>

<template>
  <q-page class="bg-grey-2" style="height:100vh;max-height:100vh;overflow:hidden;display:flex;flex-direction:column;padding:6px;">
    <!-- Page Header -->
    <div class="bg-white q-pa-sm rounded-borders q-mb-sm shadow-2">
      <div class="row justify-between items-center">
        <div class="row items-center q-gutter-sm">
          <q-icon name="view_list" size="sm" color="blue-9" />
          <div class="text-h6 text-weight-bolder text-blue-9">{{ t('nav.packingList') }}</div>
          <q-separator vertical class="q-mx-xs" />
          <!-- Department Filter -->
          <q-select
            v-model="filterMiddleWh"
            :options="['ALL', 'FH', 'SPP']"
            dense outlined options-dense
            style="width: 80px;"
            class="text-weight-bold"
            color="blue-9"
          />
          <!-- RE-Code Filter -->
          <q-input
            v-model="filterReCode"
            outlined dense clearable
            placeholder="Filter RE-Code..."
            style="width: 180px;"
            bg-color="grey-1"
          >
            <template v-slot:prepend>
              <q-icon name="filter_list" color="grey-6" size="xs" />
            </template>
          </q-input>
        </div>
        <div class="row items-center q-gutter-sm">
          <q-btn flat dense round :icon="soundSettings.enabled ? 'volume_up' : 'volume_off'" color="blue-9" @click="showSoundSettings = true">
            <q-tooltip>Sound Settings</q-tooltip>
          </q-btn>
          <q-btn flat dense round icon="assessment" color="blue-9" @click="showPackingReportDialog = true">
            <q-tooltip>Packing List Report</q-tooltip>
          </q-btn>
          <q-btn flat dense round icon="refresh" color="blue-9" @click="fetchPlans(); fetchAllRecords(); fetchReadyToDeliver()" :loading="loading">
            <q-tooltip>Refresh</q-tooltip>
          </q-btn>
          <div class="text-caption text-grey-5">v2.3</div>
        </div>
      </div>
    </div>

    <!-- 4-PANEL LAYOUT -->
    <div class="row q-col-gutter-sm" style="flex:1;min-height:0;overflow-x:auto;overflow-y:hidden;flex-wrap:nowrap;">

      <!-- ═══ LEFT PANEL: Production Plans + Transferred ═══ -->
      <div class="col-4 column q-gutter-y-sm" style="height:100%;min-height:0;overflow:hidden;">
        <!-- ── Upper Card: Production Plans (1/3 height) ── -->
        <q-card class="column shadow-2" style="flex:0 0 33.33%;min-height:0;overflow:hidden;">
          <q-card-section class="bg-blue-9 text-white q-py-xs">
            <div class="row items-center justify-between no-wrap">
              <div class="row items-center q-gutter-xs">
                <q-icon name="assignment" size="sm" />
                <div class="text-subtitle2 text-weight-bold">{{ t('packingList.productionPlans') }}</div>
              </div>
              <q-badge color="white" text-color="blue-9" class="text-weight-bold">
                {{ activePlans.length }}
              </q-badge>
            </div>
          </q-card-section>

          <div class="col relative-position">
            <q-scroll-area class="fit">
              <q-list dense separator class="bg-white">
                <q-expansion-item
                  v-for="plan in activePlans" :key="plan.plan_id"
                  dense expand-separator
                  :header-class="selectedPlan?.plan_id === plan.plan_id ? 'bg-blue-1 text-blue-10' : 'bg-grey-1 text-grey-9'"
                  @show="onPlanClick(plan)"
                >
                  <!-- Level 1 header: plan_id + batch count -->
                  <template v-slot:header>
                    <q-item-section>
                      <q-item-label class="text-weight-bold" style="font-size:0.8rem">
                        {{ plan.plan_id }}
                      </q-item-label>
                      <q-item-label caption style="font-size:0.65rem">{{ plan.sku_name || plan.sku_id }}</q-item-label>
                    </q-item-section>
                    <q-item-section side>
                      <q-badge color="blue-7" class="text-weight-bold" style="font-size:0.7rem">
                        {{ (plan.batches || []).length }} batch
                      </q-badge>
                    </q-item-section>
                  </template>

                  <!-- Level 2: per-batch expansion -->
                  <q-list dense separator class="q-pl-sm">
                    <q-expansion-item
                      v-for="batch in (plan.batches || [])" :key="batch.batch_id"
                      dense expand-separator
                      :header-class="selectedBatch?.batch_id === batch.batch_id ? 'bg-blue-1 text-blue-9' : 'bg-grey-1 text-grey-9'"
                      @show="onBatchClick(batch, plan); fetchBatchReqs(batch)"
                    >
                      <template v-slot:header>
                        <q-item-section avatar style="min-width:20px">
                          <q-icon
                            :name="getBatchStatus(batch).icon"
                            :color="getBatchStatus(batch).color"
                            size="xs"
                          />
                        </q-item-section>
                        <q-item-section>
                          <q-item-label style="font-size:0.72rem" class="text-weight-medium">
                            {{ batch.batch_id.split('-').slice(-1)[0] }}
                            <span class="text-grey-5" style="font-size:0.65rem"> — {{ batch.batch_id }}</span>
                          </q-item-label>
                        </q-item-section>
                        <q-item-section side>
                          <q-badge
                            :color="getBatchStatus(batch).color"
                            :label="getBatchStatus(batch).label"
                            style="font-size:0.6rem"
                          />
                        </q-item-section>
                      </template>

                      <!-- Level 3: grouped by WH → RE-Code → PreBatch Packages -->
                      <div v-if="batch._reqsLoading" class="text-center q-pa-sm">
                        <q-spinner color="blue" size="sm" /> <span class="text-caption text-grey">Loading...</span>
                      </div>
                      <q-list v-else dense separator class="q-pl-sm">
                        <!-- WH Groups -->
                        <template v-for="whGroup in (() => {
                          const reqs = (batch.reqs || []).filter((r: any) => filterMiddleWh === 'ALL' ? true : (filterMiddleWh === 'FH' ? isFH(r.wh || '') : isSPP(r.wh || '')))
                          const groups: Record<string, any[]> = {}
                          reqs.forEach((r: any) => { const w = r.wh || '-'; if (!groups[w]) groups[w] = []; groups[w].push(r) })
                          return Object.entries(groups).map(([wh, items]) => ({ wh, items, totalVol: items.reduce((s: number, i: any) => s + (i.required_volume || 0), 0) }))
                        })()" :key="whGroup.wh">
                          <q-expansion-item
                            dense expand-separator
                            :header-class="whGroup.wh === 'FH' ? 'bg-blue-1' : (whGroup.wh === 'SPP' ? 'bg-light-blue-1' : 'bg-grey-2')"
                          >
                            <template v-slot:header>
                              <q-item-section avatar style="min-width:20px">
                                <q-badge
                                  :color="whGroup.wh === 'FH' ? 'blue-6' : (whGroup.wh === 'SPP' ? 'light-blue-6' : 'grey-6')"
                                  :label="whGroup.wh"
                                  style="font-size:0.6rem;"
                                />
                              </q-item-section>
                              <q-item-section>
                                <q-item-label class="text-weight-bold" style="font-size:0.72rem">
                                  {{ whGroup.wh }} — {{ whGroup.items.length }} items
                                </q-item-label>
                              </q-item-section>
                              <q-item-section side>
                                <span class="text-weight-bold" style="font-size:0.68rem">{{ whGroup.totalVol.toFixed(4) }} kg</span>
                              </q-item-section>
                            </template>

                            <!-- RE-Code items within WH group -->
                            <q-list dense separator class="q-pl-sm">
                              <q-expansion-item
                                v-for="req in whGroup.items" :key="req.id"
                                dense expand-separator
                                :header-class="getReqPackingState(req).bg"
                              >
                                <template v-slot:header>
                                  <q-item-section avatar style="min-width:18px">
                                    <q-icon
                                      :name="getReqPackingState(req).icon"
                                      :color="getReqPackingState(req).color"
                                      size="xs"
                                    />
                                  </q-item-section>
                                  <q-item-section>
                                    <q-item-label style="font-size:0.7rem" class="text-weight-bold">
                                      {{ req.ingredient_name || req.re_code }}
                                    </q-item-label>
                                  </q-item-section>
                                  <q-item-section side>
                                    <span class="text-weight-bold" style="font-size:0.68rem">{{ req.required_volume?.toFixed(4) }}</span>
                                  </q-item-section>
                                  <q-item-section side style="min-width:60px">
                                    <q-badge
                                      :color="getReqPackingState(req).color"
                                      :label="getReqPackingState(req).label"
                                      style="font-size:0.55rem"
                                    />
                                  </q-item-section>
                                </template>

                                <!-- PreBatch Item Detail -->
                                <q-list dense class="q-pl-md bg-grey-1">
                                  <q-item v-if="req.batch_record_id" dense style="min-height:24px;">
                                    <q-item-section avatar style="min-width:16px">
                                      <q-icon
                                        :name="req.packing_status === 1 ? 'check_box' : 'check_box_outline_blank'"
                                        :color="req.packing_status === 1 ? 'green' : 'grey-4'"
                                        size="xs"
                                      />
                                    </q-item-section>
                                    <q-item-section>
                                      <q-item-label style="font-size:0.62rem;font-family:monospace;">
                                        {{ req.batch_record_id }}
                                      </q-item-label>
                                    </q-item-section>
                                    <q-item-section side>
                                      <span style="font-size:0.62rem;font-weight:bold;">{{ req.total_packaged?.toFixed(4) }} kg</span>
                                    </q-item-section>
                                  </q-item>
                                  <q-item v-else dense style="min-height:22px">
                                    <q-item-section class="text-grey-5 text-italic" style="font-size:0.6rem">Not weighed yet</q-item-section>
                                  </q-item>
                                </q-list>
                              </q-expansion-item>
                            </q-list>
                          </q-expansion-item>
                        </template>

                        <q-item v-if="!batch.reqs || batch.reqs.length === 0" style="min-height:28px">
                          <q-item-section class="text-grey text-italic" style="font-size:0.65rem">No requirements</q-item-section>
                        </q-item>
                      </q-list>
                    </q-expansion-item>
                    <q-item v-if="!plan.batches || plan.batches.length === 0" style="min-height:28px">
                      <q-item-section class="text-grey text-italic" style="font-size:0.7rem">No batches</q-item-section>
                    </q-item>
                  </q-list>
                </q-expansion-item>

                <q-item v-if="activePlans.length === 0">
                  <q-item-section class="text-center text-grey q-pa-lg text-caption">
                    <q-icon name="inbox" size="sm" class="q-mb-xs" /><br>No active plans
                  </q-item-section>
                </q-item>
              </q-list>
            </q-scroll-area>
          </div>
        </q-card>

        <!-- ── Lower Card: PreBatch Packing (2/3 height) ── -->
        <q-card class="column shadow-2" style="flex:1;min-height:0;overflow:hidden;">
          <q-card-section class="bg-blue-7 text-white q-py-xs">
            <div class="row items-center justify-between no-wrap">
              <div class="row items-center q-gutter-xs">
                <q-icon name="inventory_2" size="sm" />
                <div class="text-subtitle2 text-weight-bold">PreBatch Packing</div>
              </div>
              <q-badge v-if="selectedBatch" color="white" text-color="blue-7" class="text-weight-bold">
                {{ (selectedBatch.reqs || []).filter((r: any) => (filterMiddleWh === 'FH' ? isFH(r.wh || '') : filterMiddleWh === 'SPP' ? isSPP(r.wh || '') : true) && isReqPackingOk(r)).length }}/{{ (selectedBatch.reqs || []).filter((r: any) => filterMiddleWh === 'FH' ? isFH(r.wh || '') : filterMiddleWh === 'SPP' ? isSPP(r.wh || '') : true).length }}
              </q-badge>
            </div>
          </q-card-section>
          <div class="col relative-position">
            <q-scroll-area class="fit">
              <!-- No batch selected -->
              <div v-if="!selectedBatch" class="text-center q-pa-lg text-grey">
                <q-icon name="inventory_2" size="xl" class="q-mb-sm" /><br>
                <span class="text-caption">Select a batch to view packing items</span>
              </div>

              <template v-else>
                <!-- FH Section -->
                <q-expansion-item
                  v-if="filterMiddleWh === 'FH' && (selectedBatch.reqs || []).filter((r: any) => isFH(r.wh || '')).length > 0"
                  dense expand-separator default-opened
                  header-class="bg-blue-1"
                >
                  <template v-slot:header>
                    <q-item-section avatar style="min-width:24px">
                      <q-badge color="blue-6" label="FH" style="font-size:0.6rem" />
                    </q-item-section>
                    <q-item-section>
                      <q-item-label class="text-weight-bold" style="font-size:0.78rem">FH — Flavour House</q-item-label>
                    </q-item-section>
                    <q-item-section side>
                      <q-badge color="blue-7" class="text-weight-bold" style="font-size:0.65rem">
                        {{ (selectedBatch.reqs || []).filter((r: any) => isFH(r.wh || '') && isReqPackingOk(r)).length }}/{{ (selectedBatch.reqs || []).filter((r: any) => isFH(r.wh || '')).length }}
                      </q-badge>
                    </q-item-section>
                  </template>
                  <q-list dense separator class="bg-white">
                    <q-item
                      v-for="req in (selectedBatch.reqs || []).filter((r: any) => isFH(r.wh || ''))" :key="req.id"
                      dense style="min-height:28px"
                      class="cursor-pointer"
                      :class="getReqPackingState(req).bg"
                      @click="onItemClick(req)"
                    >
                      <q-item-section avatar style="min-width:20px">
                        <q-icon
                          :name="getReqPackingState(req).icon"
                          :color="getReqPackingState(req).color"
                          size="xs"
                        />
                      </q-item-section>
                      <q-item-section>
                        <q-item-label style="font-size:0.7rem" class="text-weight-bold">
                          {{ req.re_code }}
                        </q-item-label>
                        <q-item-label caption style="font-size:0.6rem">{{ req.required_volume?.toFixed(4) }} kg</q-item-label>
                      </q-item-section>
                      <q-item-section side style="min-width:60px">
                        <q-badge
                          :color="getReqPackingState(req).color"
                          :label="getReqPackingState(req).label"
                          style="font-size:0.55rem"
                        />
                      </q-item-section>
                    </q-item>
                  </q-list>
                </q-expansion-item>

                <!-- SPP Section -->
                <q-expansion-item
                  v-if="filterMiddleWh === 'SPP' && (selectedBatch.reqs || []).filter((r: any) => isSPP(r.wh || '')).length > 0"
                  dense expand-separator default-opened
                  header-class="bg-light-blue-1"
                >
                  <template v-slot:header>
                    <q-item-section avatar style="min-width:24px">
                      <q-badge color="light-blue-6" label="SPP" style="font-size:0.6rem" />
                    </q-item-section>
                    <q-item-section>
                      <q-item-label class="text-weight-bold" style="font-size:0.78rem">SPP — Spray Powder Plant</q-item-label>
                    </q-item-section>
                    <q-item-section side>
                      <q-badge color="light-blue-7" class="text-weight-bold" style="font-size:0.65rem">
                        {{ (selectedBatch.reqs || []).filter((r: any) => isSPP(r.wh || '') && isReqPackingOk(r)).length }}/{{ (selectedBatch.reqs || []).filter((r: any) => isSPP(r.wh || '')).length }}
                      </q-badge>
                    </q-item-section>
                  </template>
                  <q-list dense separator class="bg-white">
                    <q-item
                      v-for="req in (selectedBatch.reqs || []).filter((r: any) => isSPP(r.wh || ''))" :key="req.id"
                      dense style="min-height:28px"
                      class="cursor-pointer"
                      :class="getReqPackingState(req).bg"
                      @click="onItemClick(req)"
                    >
                      <q-item-section avatar style="min-width:20px">
                        <q-icon
                          :name="getReqPackingState(req).icon"
                          :color="getReqPackingState(req).color"
                          size="xs"
                        />
                      </q-item-section>
                      <q-item-section>
                        <q-item-label style="font-size:0.7rem" class="text-weight-bold">
                          {{ req.re_code }}
                        </q-item-label>
                        <q-item-label caption style="font-size:0.6rem">{{ req.required_volume?.toFixed(4) }} kg</q-item-label>
                      </q-item-section>
                      <q-item-section side style="min-width:60px">
                        <q-badge
                          :color="getReqPackingState(req).color"
                          :label="getReqPackingState(req).label"
                          style="font-size:0.55rem"
                        />
                      </q-item-section>
                    </q-item>
                  </q-list>
                </q-expansion-item>

                <!-- No items -->
                <div v-if="!selectedBatch.reqs || selectedBatch.reqs.length === 0" class="text-center q-pa-md text-grey">
                  <q-icon name="inbox" size="md" class="q-mb-xs" /><br>
                  <span class="text-caption">No prebatch items for this batch</span>
                </div>
              </template>
            </q-scroll-area>
          </div>
        </q-card>
      </div>


      <!-- ═══ PANEL 2+3: Packing Box + Pre-Batch Packages ═══ -->
      <div class="col-4 column q-gutter-y-sm" style="order:2;height:100%;min-height:0;overflow:hidden;">
        <q-card class="column shadow-2" style="flex:0 0 auto;min-height:0;overflow:hidden;">
          <q-card-section class="bg-indigo-9 text-white q-py-xs">
            <div class="row items-center justify-between no-wrap">
              <div class="row items-center q-gutter-xs">
                <q-icon name="qr_code_scanner" size="sm" />
                <div class="text-subtitle2 text-weight-bold">{{ filterMiddleWh === 'FH' ? 'Current FH Box' : (filterMiddleWh === 'SPP' ? 'Current SPP Box' : 'Current Box') }}</div>
              </div>
              <div class="row items-center q-gutter-sm">
                <q-badge color="white" text-color="indigo-9" class="text-weight-bold">
                  {{ boxReqsBoxed }}/{{ boxReqsTotal }} items
                </q-badge>
                <q-btn
                  unelevated size="sm" icon="pause_circle" label="Pause"
                  color="orange-7"
                  :disable="!selectedBatch"
                  @click="onPauseBox()"
                  class="q-mr-xs"
                >
                  <q-tooltip>Pause this box and open a new one</q-tooltip>
                </q-btn>
                <q-btn
                  unelevated size="sm" icon="check_box" label="Close & Print"
                  :color="boxReqsBoxed > 0 ? 'green-5' : 'grey-5'"
                  :disable="!selectedBatch"
                  @click="onCloseBox(filterMiddleWh === 'ALL' ? 'FH' : filterMiddleWh)"
                >
                  <q-tooltip>{{ boxReqsBoxed > 0 ? 'Seal Box & Print Label' : 'Scan items first' }}</q-tooltip>
                </q-btn>
              </div>
            </div>
          </q-card-section>

          <!-- Paused Boxes Banner -->
          <div v-if="pausedBoxes.length > 0" class="q-px-sm q-py-xs" style="background: #fff3e0;">
            <div class="row items-center q-gutter-xs" style="flex-wrap: wrap;">
              <q-icon name="pause_circle" color="orange-8" size="xs" />
              <span class="text-caption text-weight-bold text-orange-9">Paused:</span>
              <q-btn
                v-for="pb in pausedBoxes" :key="`${pb.batch_id}-${pb.wh}`"
                dense unelevated size="xs"
                color="orange-7" text-color="white"
                :label="`${pb.batch_id} [${pb.wh}] (${pb.scans.length})`"
                icon="play_circle"
                class="q-mr-xs"
                @click="onResumeBox(pb)"
              >
                <q-tooltip>Resume this box ({{ pb.scans.length }} items, paused at {{ pb.pausedAt }})</q-tooltip>
              </q-btn>
            </div>
          </div>
          
          <q-card-section class="q-py-xs q-px-sm">
            <div
              v-if="selectedBatch"
              class="q-pa-sm bg-grey-2 text-indigo-9 text-weight-bold row items-center no-wrap"
              style="border: 1px solid #ccc; border-radius: 4px; font-size: 0.85rem; min-height: 38px;"
            >
              {{ selectedBatch.batch_id }}
              <span v-if="filterMiddleWh !== 'ALL'"> &nbsp;{ {{ filterMiddleWh }} }</span>
            </div>
            <div
              v-else
              class="q-pa-sm bg-grey-1 text-grey-6 text-italic row items-center no-wrap"
              style="border: 1px dashed #ccc; border-radius: 4px; font-size: 0.85rem; min-height: 38px;"
            >
              Auto filled when first ingredient scanned...
            </div>
            <div v-if="batchInfo" class="row items-center q-gutter-x-sm q-mt-xs" style="font-size:0.7rem">
              <span class="text-weight-bold">{{ batchInfo.sku_name }}</span>
              <span class="text-grey-6">|</span>
              <span>{{ batchInfo.plan_id }}</span>
              <span class="text-grey-6">|</span>
              <span>{{ batchInfo.batch_size }} kg</span>
              <q-badge
                :color="batchInfo.status === 'Prepared' ? 'blue' : (batchInfo.status === 'Created' ? 'grey' : 'light-blue')"
                :label="batchInfo.status"
                style="font-size:0.55rem"
              />
            </div>
          </q-card-section>

          <!-- Current Box Items: grouped by ReCode → PreBatchID with Wait/Boxed status -->
          <div v-if="boxReqsGrouped.length > 0" style="max-height:300px; overflow-y:auto; background:#f5f7fa;">
            <q-list dense class="bg-white" style="border-radius:0;">
              <template v-for="grp in boxReqsGrouped" :key="grp.re_code">
                <!-- ReCode header -->
                <q-item dense style="min-height:22px; background:#e8eaf6;">
                  <q-item-section avatar style="min-width:18px">
                    <q-icon name="science" size="14px" color="indigo-5" />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label class="text-weight-bold text-indigo-8" style="font-size:0.72rem">
                      {{ grp.re_code }}
                    </q-item-label>
                  </q-item-section>
                  <q-item-section side>
                    <q-badge
                      :color="grp.items.every(i => i.packing_status === 1) ? 'green-6' : 'orange-6'"
                      style="font-size:0.55rem"
                    >
                      {{ grp.items.filter(i => i.packing_status === 1).length }}/{{ grp.items.length }}
                    </q-badge>
                  </q-item-section>
                </q-item>
                <!-- PreBatchID rows -->
                <q-item
                  v-for="item in grp.items" :key="item.id"
                  dense style="min-height:24px; padding-left:28px;"
                  :class="item.packing_status === 1 ? 'bg-green-1' : 'bg-white'"
                >
                  <q-item-section avatar style="min-width:16px">
                    <q-icon
                      :name="item.packing_status === 1 ? 'check_circle' : 'hourglass_empty'"
                      :color="item.packing_status === 1 ? 'green-6' : 'orange-5'"
                      size="14px"
                    />
                  </q-item-section>
                  <q-item-section>
                    <q-item-label style="font-size:0.62rem; font-family:monospace;">
                      {{ item.batch_record_id || item.prebatch_id || (item.batch_id ? `${item.batch_id}-${item.re_code}` : item.re_code) }}
                    </q-item-label>
                  </q-item-section>
                  <q-item-section side>
                    <q-badge
                      :color="item.packing_status === 1 ? 'green-6' : 'orange-5'"
                      :text-color="'white'"
                      style="font-size:0.5rem; min-width:38px; text-align:center;"
                    >
                      {{ item.packing_status === 1 ? 'Boxed' : 'Wait' }}
                    </q-badge>
                  </q-item-section>
                </q-item>
              </template>
            </q-list>
          </div>
          <!-- All boxed banner -->
          <div v-if="allCurrentWhBoxed && selectedBatch" class="q-pa-xs text-center" style="background:#e8f5e9;">
            <q-icon name="check_circle" color="green-8" size="xs" />
            <span class="text-caption text-weight-bold text-green-8"> All items boxed! Ready to close.</span>
          </div>
        </q-card>

        <!-- Required Ingredients Card (fills remaining space) -->
        <q-card class="col column shadow-2" style="flex:1;min-height:0;overflow:hidden;">
          <q-card-section :class="filterMiddleWh === 'FH' ? 'bg-blue-8 text-white' : 'bg-light-blue-8 text-white'" class="q-py-xs">
            <div class="row items-center justify-between no-wrap">
              <div class="row items-center q-gutter-xs">
                <q-icon :name="filterMiddleWh === 'FH' ? 'science' : 'inventory_2'" size="sm" />
                <div class="text-subtitle2 text-weight-bold">{{ t('packingList.requiredIngredients') }} — {{ filterMiddleWh }}</div>
              </div>
              <div class="row items-center q-gutter-xs">
                <q-badge color="white" :text-color="filterMiddleWh === 'FH' ? 'blue-9' : 'light-blue-9'" class="text-weight-bold">
                  {{ ingredientsByDept.reduce((s, i) => s + i.packedVol, 0).toFixed(2) }}/{{ ingredientsByDept.reduce((s, i) => s + i.totalVol, 0).toFixed(2) }} kg
                </q-badge>
                <q-badge color="white" :text-color="filterMiddleWh === 'FH' ? 'blue-9' : 'light-blue-9'" class="text-weight-bold">
                  {{ ingredientsByDept.reduce((s, i) => s + i.packedBags, 0) }}/{{ ingredientsByDept.reduce((s, i) => s + i.totalBags, 0) }}
                </q-badge>
              </div>
            </div>
          </q-card-section>

          <!-- Scan Field -->
          <q-card-section class="q-py-xs">
            <q-input
              v-if="filterMiddleWh === 'FH'"
              v-model="scanFH"
              outlined dense
              :placeholder="t('packingList.scanFhBag')"
              bg-color="blue-1"
              @keyup.enter="onScanInputEnter('FH')"
            >
              <template v-slot:prepend>
                <q-icon name="qr_code_scanner" color="blue-8" size="sm" class="cursor-pointer" @click="openScanSimulator('FH')">
                  <q-tooltip>{{ t('packingList.clickSimScan') }}</q-tooltip>
                </q-icon>
              </template>
              <template v-slot:append>
                <q-btn flat round dense icon="search" color="blue-8" size="sm" @click="onScanInputEnter('FH')" />
              </template>
            </q-input>
            <q-input
              v-else
              v-model="scanSPP"
              outlined dense
              :placeholder="t('packingList.scanSppBag')"
              bg-color="light-blue-1"
              @keyup.enter="onScanInputEnter('SPP')"
            >
              <template v-slot:prepend>
                <q-icon name="qr_code_scanner" color="light-blue-8" size="sm" class="cursor-pointer" @click="openScanSimulator('SPP')">
                  <q-tooltip>{{ t('packingList.clickSimScan') }}</q-tooltip>
                </q-icon>
              </template>
              <template v-slot:append>
                <q-btn flat round dense icon="search" color="light-blue-8" size="sm" @click="onScanInputEnter('SPP')" />
              </template>
            </q-input>
          </q-card-section>

          <div class="col relative-position">
            <q-scroll-area class="fit q-pa-xs">
              <div v-if="!selectedBatch" class="text-center q-pa-lg text-grey">
                <q-icon name="inventory_2" size="xl" class="q-mb-xs" /><br>
                {{ t('packingList.selectBatchToView') }}
              </div>

              <template v-else>
                <!-- Ingredient Requirements List -->
                <q-list dense separator class="bg-white">
                  <q-expansion-item
                    v-for="ing in ingredientsByDept" :key="ing.re_code"
                    dense expand-separator default-opened
                    :header-class="(ing.packedBags === ing.totalBags && ing.totalBags > 0) ? 'bg-blue-1' : (ing.totalBags > 0 ? 'bg-orange-1' : 'bg-grey-1')"
                  >
                    <template v-slot:header>
                      <q-item-section avatar style="min-width:24px">
                        <q-icon
                          :name="(ing.packedBags === ing.totalBags && ing.totalBags > 0) ? 'check_circle' : (ing.totalBags > 0 ? 'hourglass_top' : 'radio_button_unchecked')"
                          :color="(ing.packedBags === ing.totalBags && ing.totalBags > 0) ? 'blue-7' : (ing.totalBags > 0 ? 'orange-7' : 'grey-4')"
                          size="sm"
                          class="cursor-pointer"
                          @click.stop="onIngredientScanClick(ing)"
                        >
                          <q-tooltip>Click to scan into Current Box</q-tooltip>
                        </q-icon>
                      </q-item-section>
                      <q-item-section>
                        <q-item-label class="text-weight-bold" style="font-size:0.8rem">
                          {{ ing.re_code }}
                          <q-badge
                            v-if="ing.wh"
                            :color="ing.wh === 'FH' ? 'blue-4' : 'light-blue-4'"
                            :label="ing.wh"
                            class="q-ml-xs"
                            style="font-size:0.55rem; padding: 1px 4px;"
                          />
                        </q-item-label>
                        <q-item-label caption style="font-size:0.65rem">
                          <span v-if="ing.batch_record_id" class="text-mono text-grey-7">{{ ing.batch_record_id }}</span>
                          <span v-if="ing.batch_record_id"> · </span>
                          {{ ing.totalVol.toFixed(3) }} kg
                        </q-item-label>
                      </q-item-section>
                      <q-item-section side>
                        <q-badge
                          :color="(ing.packedBags === ing.totalBags && ing.totalBags > 0) ? 'blue-7' : (ing.totalBags > 0 ? 'orange-7' : 'grey-4')"
                          class="text-weight-bold"
                          style="font-size:0.65rem"
                        >
                          {{ ing.packedBags }}/{{ ing.totalBags }} bags
                        </q-badge>
                      </q-item-section>
                      <q-item-section side style="min-width:32px">
                        <q-btn flat round dense icon="add_circle" size="sm" color="green-7" @click.stop="onIngredientScanClick(ing)">
                          <q-tooltip>Click to add to Current Box (Scan)</q-tooltip>
                        </q-btn>
                      </q-item-section>
                    </template>

                    <!-- Expandable: individual bags -->
                    <q-list dense class="q-pl-md bg-white">
                      <q-item
                        v-for="bag in ing.bags" :key="bag.id"
                        dense clickable style="min-height:30px;cursor:pointer"
                        :class="getBagRowClass(bag)"
                        @click="onSimScanClick(bag)"
                      >
                        <q-item-section avatar style="min-width:20px">
                          <q-icon :name="getBagStatusIcon(bag)" :color="getBagStatusColor(bag)" size="xs" />
                        </q-item-section>
                        <q-item-section>
                          <q-item-label style="font-size:0.7rem; font-weight:600;" class="text-mono">
                            {{ bag.prebatch_id || bag.batch_record_id }}
                          </q-item-label>
                          <q-item-label caption style="font-size:0.6rem; margin-top:0;">
                            ID: {{ bag.batch_record_id }}
                          </q-item-label>
                        </q-item-section>
                        <q-item-section side>
                          <span class="text-weight-bold" style="font-size:0.7rem">{{ bag.net_volume?.toFixed(3) }} kg</span>
                        </q-item-section>
                        <q-item-section side style="min-width:70px" class="row items-center no-wrap">
                          <q-badge :color="getBagStatusColor(bag)" :label="getBagStatusLabel(bag)" style="font-size:0.6rem" class="q-mr-xs" />
                          <q-btn flat round dense icon="print" size="xs" color="grey-7" @click.stop="printBagLabel(bag)">
                            <q-tooltip>Re-Print Packing Bag Label</q-tooltip>
                          </q-btn>
                        </q-item-section>
                      </q-item>
                    </q-list>
                  </q-expansion-item>

                  <q-item v-if="ingredientsByDept.length === 0">
                    <q-item-section class="text-center text-grey text-italic text-caption q-pa-md">
                      <q-icon name="inbox" size="md" class="q-mb-xs" /><br>
                      {{ filterMiddleWh === 'FH' ? t('packingList.noFhBags') : t('packingList.noSppBags') }}
                    </q-item-section>
                  </q-item>
                </q-list>
              </template>
            </q-scroll-area>
          </div>
        </q-card>


      </div>
      <!-- ═══ 4TH PANEL: Ready to Delivery ═══ -->
      <div class="col-4 column" style="order:3;height:100%;min-height:0;overflow:hidden;">
        <q-card class="column shadow-2" style="flex:1;min-height:0;overflow:hidden;">
          <q-card-section class="bg-indigo-7 text-white q-py-xs">
            <div class="row items-center justify-between no-wrap">
              <div class="row items-center q-gutter-xs">
                <q-icon name="local_shipping" size="sm" />
                <div class="text-subtitle2 text-weight-bold">
                  Ready to Delivery
                </div>
              </div>
              <div class="row items-center q-gutter-xs">
                <q-btn flat round dense icon="unfold_more" size="xs" color="white" @click="expandAllBoxes()">
                  <q-tooltip>Expand All</q-tooltip>
                </q-btn>
                <q-btn flat round dense icon="unfold_less" size="xs" color="white" @click="collapseAllBoxes()">
                  <q-tooltip>Collapse All</q-tooltip>
                </q-btn>

                <q-select
                  v-model="filterDeliveryStatus"
                  :options="[{ label: 'Show All', value: 'SHOW_ALL' }, { label: 'All', value: 'ALL' }, { label: 'Waiting', value: 'WAITING' }]"
                  emit-value map-options dense outlined
                  style="min-width:80px;background:rgba(255,255,255,0.15);border-radius:4px;"
                  input-class="text-white text-caption"
                  popup-content-class="text-caption"
                  color="white"
                  dark
                />
                <q-badge color="white" text-color="indigo-7" class="text-weight-bold">
                  {{ groupedTransferredBoxes.filter(r => {
                    if (filterDeliveryStatus === 'SHOW_ALL') return true
                    if (r.inProduction) return false
                    const whF = deliveryWhFilter
                    const hasWh = whF === 'ALL' ? (!!r.fh || !!r.spp) : (whF === 'FH' ? !!r.fh : !!r.spp)
                    if (!hasWh) return false
                    const isDelivered = (whF === 'FH' || whF === 'ALL') ? !!deliveredMap.get(`${r.batch_id}-FH`) : !!deliveredMap.get(`${r.batch_id}-SPP`)
                    return filterDeliveryStatus === 'ALL' || !isDelivered
                  }).length }}
                </q-badge>
                <q-btn
                  flat round dense icon="local_shipping" size="sm" color="white"
                  :disable="groupedTransferredBoxes.length === 0"
                  @click="selectedForTransfer = transferredBoxes.map(b => b.id); showTransferDialog = true"
                >
                  <q-tooltip>Delivery &amp; Print Report</q-tooltip>
                </q-btn>
                <q-btn
                  flat round dense icon="print" size="sm" color="white"
                  :disable="groupedTransferredBoxes.length === 0"
                  @click="selectedForTransfer = transferredBoxes.map(b => b.id); showTransferDialog = true"
                >
                  <q-tooltip>Print Delivery Report</q-tooltip>
                </q-btn>
              </div>
            </div>
          </q-card-section>

          <div class="col relative-position">
            <q-scroll-area class="fit bg-white">
              <!-- ═══ SHOW ALL: Status Pipeline Table ═══ -->
              <template v-if="filterDeliveryStatus === 'SHOW_ALL'">
                <table style="width:100%;border-collapse:collapse;font-size:0.72rem;">
                  <thead>
                    <tr style="background:#e3f2fd;position:sticky;top:0;z-index:1;">
                      <th style="text-align:left;padding:4px 6px;border-bottom:2px solid #ccc;">Batch ID</th>
                      <th style="text-align:center;padding:4px 4px;border-bottom:2px solid #ccc;width:50px;">Size</th>
                      <th style="text-align:center;padding:4px 4px;border-bottom:2px solid #ccc;width:40px;">FH</th>
                      <th style="text-align:center;padding:4px 4px;border-bottom:2px solid #ccc;width:40px;">SPP</th>
                      <th style="text-align:center;padding:4px 4px;border-bottom:2px solid #ccc;width:55px;">ReCheck</th>
                      <th style="text-align:center;padding:4px 4px;border-bottom:2px solid #ccc;width:45px;">Ready</th>
                      <th style="text-align:center;padding:4px 4px;border-bottom:2px solid #ccc;width:40px;">Prod</th>
                      <th style="text-align:center;padding:4px 4px;border-bottom:2px solid #ccc;width:40px;">Done</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="b in allBatchStatuses" :key="b.batch_id"
                        :style="{background: b.done ? '#e8f5e9' : b.production ? '#fffde7' : ''}"
                        style="border-bottom:1px solid #eee;">
                      <td style="padding:3px 6px;font-family:monospace;font-weight:600;">{{ b.batch_id }}</td>
                      <td style="text-align:center;padding:3px 4px;">{{ b.batch_size }}</td>
                      <!-- FH: boxed? -->
                      <td style="text-align:center;">
                        <q-icon v-if="b.fh_boxed_at" name="check_circle" color="blue" size="16px">
                          <q-tooltip>FH Box Closed ✅</q-tooltip>
                        </q-icon>
                        <q-icon v-else-if="b.fh_packed > 0" name="pending" color="amber" size="16px">
                          <q-tooltip>FH Preparing {{ b.fh_packed }}/{{ b.fh_total }} packed</q-tooltip>
                        </q-icon>
                        <q-icon v-else name="radio_button_unchecked" color="grey-4" size="16px" />
                      </td>
                      <!-- SPP: boxed? -->
                      <td style="text-align:center;">
                        <q-icon v-if="b.spp_boxed_at" name="check_circle" color="light-blue" size="16px">
                          <q-tooltip>SPP Box Closed ✅</q-tooltip>
                        </q-icon>
                        <q-icon v-else-if="b.spp_packed > 0" name="pending" color="amber" size="16px">
                          <q-tooltip>SPP Preparing {{ b.spp_packed }}/{{ b.spp_total }} packed</q-tooltip>
                        </q-icon>
                        <q-icon v-else name="radio_button_unchecked" color="grey-4" size="16px" />
                      </td>
                      <!-- ReCheck: from DB -->
                      <td style="text-align:center;">
                        <template v-if="b.recheck_total > 0 && b.recheck_ok === b.recheck_total && b.fh_boxed_at && b.spp_boxed_at">
                          <q-icon name="verified" color="green" size="16px">
                            <q-tooltip>All {{ b.recheck_ok }}/{{ b.recheck_total }} checked ✅</q-tooltip>
                          </q-icon>
                        </template>
                        <template v-else-if="b.recheck_ok > 0">
                          <q-icon name="pending" color="amber" size="16px">
                            <q-tooltip>{{ b.recheck_ok }}/{{ b.recheck_total }} checked</q-tooltip>
                          </q-icon>
                        </template>
                        <q-icon v-else name="radio_button_unchecked" color="grey-4" size="16px" />
                      </td>
                      <!-- Ready -->
                      <td style="text-align:center;">
                        <q-icon v-if="b.ready_to_product" name="check_circle" color="teal" size="16px">
                          <q-tooltip>Ready to Production</q-tooltip>
                        </q-icon>
                        <q-icon v-else name="radio_button_unchecked" color="grey-4" size="16px" />
                      </td>
                      <!-- Prod -->
                      <td style="text-align:center;">
                        <template v-if="b.done">
                          <q-icon name="check_circle" color="green" size="16px">
                            <q-tooltip>Production Finished</q-tooltip>
                          </q-icon>
                        </template>
                        <template v-else-if="b.production">
                          <q-icon name="pending" color="amber-8" size="16px">
                            <q-tooltip>Production In Process</q-tooltip>
                          </q-icon>
                        </template>
                        <q-icon v-else name="radio_button_unchecked" color="grey-4" size="16px" />
                      </td>
                      <!-- Done -->
                      <td style="text-align:center;">
                        <q-icon v-if="b.done" name="check_circle" color="green-8" size="16px">
                          <q-tooltip>All Done</q-tooltip>
                        </q-icon>
                        <q-icon v-else name="radio_button_unchecked" color="grey-4" size="16px" />
                      </td>
                    </tr>
                    <tr v-if="allBatchStatuses.length === 0">
                      <td colspan="8" style="text-align:center;padding:20px;color:#999;">No batches found</td>
                    </tr>
                  </tbody>
                </table>
              </template>

              <!-- ═══ Normal View: Expandable Delivery List ═══ -->
              <q-list v-else dense separator>
                <!-- ── Level 0: SKU ── -->
                <template v-for="skuGrp in deliveryBySku" :key="skuGrp.sku_name">
                  <q-expansion-item
                    dense expand-separator switch-toggle-side default-opened
                    header-class="bg-deep-purple-1"
                  >
                    <template v-slot:header>
                      <q-item-section avatar style="min-width:22px">
                        <q-icon name="category" color="deep-purple-6" size="xs" />
                      </q-item-section>
                      <q-item-section>
                        <q-item-label class="text-weight-bold text-deep-purple-9" style="font-size:0.78rem;">
                          {{ skuGrp.sku_id }}
                        </q-item-label>
                        <q-item-label v-if="skuGrp.sku_name" caption style="font-size:0.58rem">{{ skuGrp.sku_name }}</q-item-label>
                      </q-item-section>
                      <q-item-section side style="padding-left:0;min-width:28px">
                        <q-btn flat round dense icon="close" size="xs" color="red-4"
                          @click.stop="openCancelBoxDialog(skuGrp.plans[0]?.batches[0]?.batch_id || '', deliveryWhFilter === 'ALL' ? 'FH' : deliveryWhFilter)">
                          <q-tooltip>Cancel Box</q-tooltip>
                        </q-btn>
                      </q-item-section>
                    </template>

                    <!-- ── Level 1: Plan ID ── -->
                    <q-list dense class="q-pl-xs">
                      <template v-for="planGrp in skuGrp.plans" :key="planGrp.plan_id">
                        <q-expansion-item
                          dense expand-separator switch-toggle-side default-opened
                          header-class="bg-indigo-1"
                        >
                          <template v-slot:header>
                            <q-item-section avatar style="min-width:22px">
                              <q-icon name="event_note" color="indigo-7" size="xs" />
                            </q-item-section>
                            <q-item-section>
                              <q-item-label class="text-weight-bold" style="font-size:0.76rem;font-family:monospace;">
                                {{ planGrp.plan_id }}
                              </q-item-label>
                            </q-item-section>
                            <q-item-section side>
                              <q-badge color="indigo-6" class="text-weight-bold" style="font-size:0.58rem">
                                {{ planGrp.batches.length }} batch{{ planGrp.batches.length > 1 ? 'es' : '' }}
                              </q-badge>
                            </q-item-section>
                            <q-item-section side style="padding-left:0;min-width:28px">
                              <q-btn flat round dense icon="close" size="xs" color="red-4"
                                @click.stop="openCancelBoxDialog(planGrp.batches[0]?.batch_id || '', deliveryWhFilter === 'ALL' ? 'FH' : deliveryWhFilter)">
                                <q-tooltip>Cancel Box</q-tooltip>
                              </q-btn>
                            </q-item-section>
                          </template>

                          <!-- ── Level 2: Batch IDs ── -->
                          <q-list dense class="q-pl-xs">
                            <template v-for="row in planGrp.batches" :key="row.batch_id">
                              <q-expansion-item
                                v-if="(() => {
                                  if (row.inProduction) return false
                                  const wf = deliveryWhFilter
                                  const hasWh = wf === 'ALL' ? (!!row.fh || !!row.spp) : (wf === 'FH' ? !!row.fh : !!row.spp)
                                  if (!hasWh) return false
                                  if (filterDeliveryStatus === 'ALL') return true
                                  const fhDel = !!deliveredMap.get(`${row.batch_id}-FH`)
                                  const sppDel = !!deliveredMap.get(`${row.batch_id}-SPP`)
                                  const isDelivered = wf === 'ALL' ? (fhDel && sppDel) : (wf === 'FH' ? fhDel : sppDel)
                                  return !isDelivered
                                })()"
                                v-model="deliveryExpandMap[row.batch_id]"
                                dense expand-separator switch-toggle-side
                                header-class="bg-grey-1"
                                @show="fetchBoxContents(row.batch_id)"
                              >
                                <template v-slot:header>
                                  <q-item-section avatar style="min-width:22px">
                                    <q-icon name="inventory_2" color="indigo-6" size="xs" />
                                  </q-item-section>
                                  <q-item-section>
                                    <q-item-label class="text-weight-bold" style="font-size:0.78rem;font-family:monospace;">
                                      {{ row.batch_id }}
                                    </q-item-label>
                                  </q-item-section>

                                  <q-item-section side style="padding-right:0;min-width:28px">
                                    <q-btn flat round dense icon="print" size="xs" color="indigo-4"
                                      @click.stop="printBoxLabelInline(row.batch_id, deliveryWhFilter === 'ALL' ? 'FH' : deliveryWhFilter)">
                                      <q-tooltip>Print Box Label</q-tooltip>
                                    </q-btn>
                                  </q-item-section>

                                  <q-item-section side>
                                    <div class="row items-center q-gutter-xs">
                                      <template v-if="row.fh && (deliveryWhFilter === 'ALL' || deliveryWhFilter === 'FH')">
                                        <q-badge color="blue-7" style="font-size:0.58rem;">
                                          FH <q-icon name="unarchive" size="10px" class="q-ml-xs"/> {{ row.fh.time }}
                                        </q-badge>
                                        <q-badge v-if="deliveredMap.get(`${row.batch_id}-FH`)" color="green-8" class="text-weight-bold" style="font-size:0.58rem;">
                                          <q-icon name="local_shipping" size="10px" class="q-mr-xs"/> {{ deliveredMap.get(`${row.batch_id}-FH`) }}
                                        </q-badge>
                                      </template>
                                      <template v-if="row.spp && (deliveryWhFilter === 'ALL' || deliveryWhFilter === 'SPP')">
                                        <q-badge color="light-blue-7" style="font-size:0.58rem;">
                                          SPP <q-icon name="unarchive" size="10px" class="q-ml-xs"/> {{ row.spp.time }}
                                        </q-badge>
                                        <q-badge v-if="deliveredMap.get(`${row.batch_id}-SPP`)" color="green-8" class="text-weight-bold" style="font-size:0.58rem;">
                                          <q-icon name="local_shipping" size="10px" class="q-mr-xs"/> {{ deliveredMap.get(`${row.batch_id}-SPP`) }}
                                        </q-badge>
                                      </template>
                                    </div>
                                  </q-item-section>

                                  <!-- Cancel Box icon (far right, always visible) -->
                                  <q-item-section side style="padding-left:0;min-width:28px">
                                    <q-btn flat round dense icon="close" size="xs" color="red-4"
                                      @click.stop="openCancelBoxDialog(row.batch_id, deliveryWhFilter === 'ALL' ? 'FH' : deliveryWhFilter)">
                                      <q-tooltip>Cancel Box</q-tooltip>
                                    </q-btn>
                                  </q-item-section>
                                </template>

                                <!-- ── Expanded: Box Details (ReCode → Package) ── -->
                                <div v-if="boxContentsCache.get(row.batch_id)?._loading" class="text-center q-pa-sm">
                                  <q-spinner color="indigo" size="sm" /> <span class="text-caption text-grey">Loading...</span>
                                </div>
                                <template v-else-if="boxContentsCache.get(row.batch_id)">
                                  <q-list dense class="q-pl-xs">
                                    <!-- ── Level 3: RE-Codes (flattened across WH groups) ── -->
                                    <template v-for="whGrp in boxContentsCache.get(row.batch_id)!.wh_groups" :key="whGrp.wh">
                                      <q-expansion-item
                                        v-for="reGrp in whGrp.re_codes" :key="`${whGrp.wh}-${reGrp.re_code}`"
                                        dense expand-separator switch-toggle-side
                                        header-class="bg-grey-1"
                                      >
                                        <template v-slot:header>
                                          <q-item-section avatar style="min-width:18px">
                                            <q-icon
                                              :name="reGrp.status === 2 ? 'check_circle' : (reGrp.status === 1 ? 'hourglass_top' : 'radio_button_unchecked')"
                                              :color="reGrp.status === 2 ? 'green' : (reGrp.status === 1 ? 'orange' : 'grey-4')"
                                              size="xs"
                                            />
                                          </q-item-section>
                                          <q-item-section>
                                            <q-item-label style="font-size:0.7rem" class="text-weight-bold">{{ reGrp.re_code }}</q-item-label>
                                            <q-item-label caption style="font-size:0.58rem">{{ reGrp.ingredient_name }}</q-item-label>
                                          </q-item-section>
                                          <q-item-section side>
                                            <div class="column items-end">
                                              <span class="text-weight-bold" style="font-size:0.65rem">{{ reGrp.total_weight.toFixed(4) }} kg</span>
                                              <span class="text-grey-6" style="font-size:0.55rem">req: {{ reGrp.required_volume?.toFixed(4) || '0.0000' }}</span>
                                            </div>
                                          </q-item-section>
                                        </template>

                                        <!-- ── Level 4: Packages (preBatchID Pkg X/Y net/total) ── -->
                                        <q-list dense class="q-pl-md bg-grey-1">
                                          <q-item v-for="pkg in reGrp.packages" :key="pkg.id" dense style="min-height:24px;">
                                            <q-item-section avatar style="min-width:16px">
                                              <q-icon
                                                :name="pkg.packing_status === 1 ? 'check_box' : 'check_box_outline_blank'"
                                                :color="pkg.packing_status === 1 ? 'green' : 'grey-4'"
                                                size="xs"
                                              />
                                            </q-item-section>
                                            <q-item-section>
                                              <q-item-label style="font-size:0.62rem;font-family:monospace;">
                                                <span v-if="pkg.batch_record_id" class="text-indigo-7">{{ pkg.batch_record_id }}</span>
                                                Pkg {{ pkg.package_no }}/{{ pkg.total_packages }}
                                              </q-item-label>
                                            </q-item-section>
                                            <q-item-section side>
                                              <span style="font-size:0.62rem;font-weight:bold;">
                                                {{ pkg.net_volume.toFixed(4) }} / {{ reGrp.total_weight.toFixed(4) }} kg
                                              </span>
                                            </q-item-section>
                                          </q-item>
                                          <q-item v-if="reGrp.packages.length === 0" dense style="min-height:22px">
                                            <q-item-section class="text-grey-5 text-italic" style="font-size:0.6rem">No packages weighed yet</q-item-section>
                                          </q-item>
                                        </q-list>
                                      </q-expansion-item>
                                    </template>

                                    <!-- Total Box Weight -->
                                    <q-item dense class="bg-indigo-1" style="min-height:28px;">
                                      <q-item-section>
                                        <q-item-label class="text-weight-bold text-indigo-9" style="font-size:0.72rem">
                                          📦 Total Box Weight
                                        </q-item-label>
                                      </q-item-section>
                                      <q-item-section side>
                                        <span class="text-weight-bold text-indigo-9" style="font-size:0.72rem">
                                          {{ boxContentsCache.get(row.batch_id)!.total_box_weight.toFixed(4) }} kg
                                        </span>
                                      </q-item-section>
                                    </q-item>

                                    <!-- Actions: Deliver / Cancel Box -->
                                    <q-item dense class="bg-grey-2" style="min-height:32px;">
                                      <q-item-section>
                                        <div class="row items-center q-gutter-xs">
                                          <template v-if="row.fh && !deliveredMap.get(`${row.batch_id}-FH`) && (deliveryWhFilter === 'ALL' || deliveryWhFilter === 'FH')">
                                            <q-btn dense unelevated no-caps size="xs" color="blue-7" text-color="white" icon="local_shipping" label="Deliver FH"
                                              @click="markDelivered(row.batch_id, 'FH')" />
                                            <q-btn dense flat no-caps size="xs" color="red-5" icon="close" label="Cancel FH"
                                              @click="openCancelBoxDialog(row.batch_id, 'FH')" />
                                          </template>
                                          <template v-if="row.spp && !deliveredMap.get(`${row.batch_id}-SPP`) && (deliveryWhFilter === 'ALL' || deliveryWhFilter === 'SPP')">
                                            <q-btn dense unelevated no-caps size="xs" color="amber-7" text-color="white" icon="local_shipping" label="Deliver SPP"
                                              @click="markDelivered(row.batch_id, 'SPP')" />
                                            <q-btn dense flat no-caps size="xs" color="red-5" icon="close" label="Cancel SPP"
                                              @click="openCancelBoxDialog(row.batch_id, 'SPP')" />
                                          </template>
                                        </div>
                                      </q-item-section>
                                    </q-item>
                                  </q-list>
                                </template>
                              </q-expansion-item>
                            </template>
                          </q-list>
                        </q-expansion-item>
                      </template>
                    </q-list>
                  </q-expansion-item>
                </template>

                <q-item v-if="deliveryBySku.length === 0">
                  <q-item-section class="text-center text-grey q-pa-lg text-caption">
                    <q-icon name="inbox" size="sm" class="q-mb-sm" /><br>
                    No boxes ready for delivery yet
                  </q-item-section>
                </q-item>
              </q-list>
            </q-scroll-area>
          </div>
        </q-card>
      </div>
    </div>


    <!-- ═══ CANCEL BOX DIALOG ═══ -->
    <q-dialog v-model="showCancelBoxDialog" persistent>
      <q-card style="width:400px;max-width:96vw;">
        <q-card-section class="bg-red-7 text-white q-py-sm">
          <div class="row items-center q-gutter-sm">
            <q-icon name="undo" size="sm" />
            <div class="text-subtitle1 text-weight-bold">
              Cancel Packing Box
            </div>
            <q-space />
            <q-btn flat round dense icon="close" v-close-popup />
          </div>
        </q-card-section>

        <q-card-section class="q-pa-md">
          <div class="text-subtitle2 q-mb-sm">
            <q-icon name="inventory_2" class="q-mr-xs" />
            <span class="text-weight-bold" style="font-family:monospace;">{{ cancelBoxBatchId }}</span>
            <q-badge :color="cancelBoxWh === 'FH' ? 'blue-6' : 'light-blue-6'" class="q-ml-sm">{{ cancelBoxWh }}</q-badge>
          </div>

          <q-input
            v-model="cancelBoxReason"
            type="textarea"
            outlined dense
            label="Reason for cancellation *"
            placeholder="e.g. Wrong items packed, weight mismatch, etc."
            :rows="3"
            autofocus
            :rules="[(v: string) => !!v?.trim() || 'Reason is required']"
          />
        </q-card-section>

        <q-card-actions align="right" class="q-px-md q-pb-md">
          <q-btn flat no-caps label="Keep Box" color="grey" v-close-popup />
          <q-btn
            unelevated no-caps
            label="Cancel Box"
            color="red-7"
            icon="undo"
            :loading="cancelBoxLoading"
            :disable="!cancelBoxReason.trim()"
            @click="cancelBox"
          />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- ═══ TRANSFER REPORT DIALOG ═══ -->
    <q-dialog v-model="showTransferDialog" persistent>
      <q-card style="width:560px;max-width:96vw;">
        <q-card-section class="bg-indigo-9 text-white q-py-sm">
          <div class="row items-center q-gutter-sm">
            <q-icon name="print" size="sm" />
            <div class="text-subtitle1 text-weight-bold">
              Transfer Report
              <span class="text-caption" style="opacity:0.8"> — {{ filterMiddleWh === 'FH' ? 'FH → SPP' : 'SPP → Production' }}</span>
            </div>
            <q-space />
            <q-btn flat round dense icon="close" v-close-popup />
          </div>
        </q-card-section>

        <q-card-section class="q-pa-sm">
          <div class="row items-center justify-between q-mb-sm">
            <div class="text-caption text-grey-7">Select boxes to include in report</div>
            <div class="row q-gutter-xs">
              <q-btn flat dense no-caps size="sm" label="All" color="indigo"
                @click="selectedForTransfer = transferredBoxes.filter(b => b.wh === filterMiddleWh).map(b => b.id)" />
              <q-btn flat dense no-caps size="sm" label="None" color="grey"
                @click="selectedForTransfer = []" />
            </div>
          </div>
          <q-scroll-area style="height:320px;">
            <q-list dense separator>
              <q-item
                v-for="box in transferredBoxes.filter(b => b.wh === filterMiddleWh)" :key="box.id"
                clickable @click="() => {
                  const idx = selectedForTransfer.indexOf(box.id)
                  if (idx >= 0) selectedForTransfer.splice(idx, 1)
                  else selectedForTransfer.push(box.id)
                }"
                :class="selectedForTransfer.includes(box.id) ? 'bg-indigo-1' : ''"
              >
                <q-item-section avatar style="min-width:32px">
                  <q-checkbox
                    :model-value="selectedForTransfer.includes(box.id)"
                    color="indigo"
                    @update:model-value="(v) => {
                      const idx = selectedForTransfer.indexOf(box.id)
                      if (v && idx < 0) selectedForTransfer.push(box.id)
                      else if (!v && idx >= 0) selectedForTransfer.splice(idx, 1)
                    }"
                  />
                </q-item-section>
                <q-item-section avatar style="min-width:28px">
                  <q-icon
                    name="inventory_2"
                    :color="box.wh === 'FH' ? 'blue-7' : 'light-blue-7'"
                    size="sm"
                  />
                </q-item-section>
                <q-item-section>
                  <q-item-label class="text-weight-bold text-caption">
                    {{ box.batch_id }}
                  </q-item-label>
                  <q-item-label caption>{{ box.bagsCount }} bags · {{ box.time }}</q-item-label>
                </q-item-section>
                <q-item-section side class="row items-center no-wrap q-gutter-xs">
                  <q-btn
                    flat round dense
                    icon="print"
                    size="sm"
                    color="grey-7"
                    @click.stop="reprintBoxLabel(box)"
                  >
                    <q-tooltip>Reprint Box Label</q-tooltip>
                  </q-btn>
                  <q-badge
                    :color="box.wh === 'FH' ? 'blue-7' : 'light-blue-7'"
                    :label="box.wh === 'FH' ? 'FH→SPP' : 'SPP→Prod'"
                    class="text-weight-bold"
                  />
                </q-item-section>
              </q-item>
            </q-list>
          </q-scroll-area>
        </q-card-section>

        <q-separator />
        <q-card-actions align="between" class="q-px-md q-py-sm">
          <div class="text-caption text-grey-6">
            {{ selectedForTransfer.length }} / {{ transferredBoxes.filter(b => b.wh === filterMiddleWh).length }} selected
          </div>
          <div class="row q-gutter-sm">
            <q-btn flat no-caps label="Cancel" color="grey" v-close-popup />
            <q-btn
              no-caps unelevated color="indigo-8"
              icon="print" label="Print Report"
              :disable="selectedForTransfer.length === 0"
              @click="printTransferReport"
            />
          </div>
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- ═══ SCAN SIMULATION DIALOG ═══ -->
    <q-dialog v-model="showScanDialog" position="bottom" full-width>
      <q-card style="max-height: 60vh;">
        <q-card-section :class="scanDialogWh === 'FH' ? 'bg-blue-7 text-white' : 'bg-light-blue-8 text-white'" class="q-py-sm">
          <div class="row items-center justify-between no-wrap">
            <div class="row items-center q-gutter-sm">
              <q-icon :name="scanDialogWh === 'FH' ? 'science' : 'inventory_2'" size="sm" />
              <div class="text-subtitle1 text-weight-bold">
                Simulate Scan — {{ scanDialogWh }} Pre-Batch
              </div>
            </div>
            <div class="row items-center q-gutter-xs">
              <q-badge color="white" :text-color="scanDialogWh === 'FH' ? 'blue-9' : 'light-blue-9'">
                {{ scanDialogBags.length }} bags
              </q-badge>
              <q-btn flat round dense icon="close" color="white" v-close-popup />
            </div>
          </div>
        </q-card-section>

        <!-- Filter -->
        <q-card-section class="q-py-xs">
          <q-input
            v-model="scanDialogFilter"
            outlined dense clearable
            placeholder="Filter by Packing-ID or RE-Code..."
            bg-color="grey-1"
          >
            <template v-slot:prepend>
              <q-icon name="filter_list" size="sm" />
            </template>
          </q-input>
        </q-card-section>

        <q-separator />

        <q-card-section class="q-pa-none" style="max-height: 45vh; overflow: auto;">
          <table style="width:100%;border-collapse:collapse;font-size:0.75rem;">
            <thead>
              <tr style="background:#f5f5f5;border-bottom:1px solid #e0e0e0;position:sticky;top:0;z-index:1;">
                <th style="text-align:left;padding:6px 8px;">Packing-ID</th>
                <th style="text-align:left;padding:6px 8px;">RE-Code</th>
                <th style="text-align:right;padding:6px 8px;width:100px;">Volume</th>
                <th style="text-align:center;padding:6px 8px;width:90px;">Action</th>
              </tr>
            </thead>
            <tbody>
              <tr
                v-for="bag in scanDialogBags.filter((b: any) => {
                  if (!scanDialogFilter) return true
                  const q = scanDialogFilter.toLowerCase()
                  return (b.batch_record_id || '').toLowerCase().includes(q) || (b.re_code || '').toLowerCase().includes(q)
                })"
                :key="bag.id"
                :class="isPacked(bag) ? 'bg-blue-1' : ''"
                style="border-bottom:1px solid #f0f0f0;cursor:pointer;"
                @click="onSimScanClick(bag)"
              >
                <td style="padding:6px 8px;font-family:monospace;font-size:0.68rem;">{{ bag.batch_record_id }}</td>
                <td style="padding:6px 8px;font-weight:600;">{{ bag.re_code }}</td>
                <td style="padding:6px 8px;text-align:right;font-weight:bold;">{{ bag.net_volume?.toFixed(4) }} kg</td>
                <td style="padding:6px 8px;text-align:center;">
                  <q-badge
                    :color="isPacked(bag) ? 'blue' : 'blue-grey'"
                    :label="isPacked(bag) ? 'Packed' : 'Tap to scan'"
                  />
                </td>
              </tr>
              <tr v-if="scanDialogBags.length === 0">
                <td colspan="4" style="padding:24px;text-align:center;color:#999;">
                  <q-icon name="inbox" size="lg" class="q-mb-sm" /><br>
                  No {{ scanDialogWh }} pre-batch bags available
                </td>
              </tr>
            </tbody>
          </table>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- ═══ SOUND SETTINGS DIALOG ═══ -->
    <q-dialog v-model="showSoundSettings" position="right" full-height>
      <q-card style="width: 380px; max-width: 90vw;" class="column">
        <!-- Header -->
        <q-card-section class="bg-blue-9 text-white q-py-sm">
          <div class="row items-center justify-between no-wrap">
            <div class="row items-center q-gutter-sm">
              <q-icon name="tune" size="sm" />
              <div class="text-subtitle1 text-weight-bold">Sound Settings</div>
            </div>
            <q-btn flat round dense icon="close" color="white" v-close-popup />
          </div>
        </q-card-section>

        <q-separator />

        <q-card-section class="col q-pa-md" style="overflow: auto;">
          <!-- Master Enable -->
          <div class="row items-center justify-between q-mb-md q-pa-sm rounded-borders" :class="soundSettings.enabled ? 'bg-green-1' : 'bg-grey-2'">
            <div class="row items-center q-gutter-sm">
              <q-icon :name="soundSettings.enabled ? 'volume_up' : 'volume_off'" :color="soundSettings.enabled ? 'green' : 'grey'" size="sm" />
              <div>
                <div class="text-weight-bold">Sound Effects</div>
                <div class="text-caption text-grey-7">{{ soundSettings.enabled ? 'Sounds are ON' : 'Sounds are OFF' }}</div>
              </div>
            </div>
            <q-toggle v-model="soundSettings.enabled" color="green" />
          </div>

          <template v-if="soundSettings.enabled">
            <!-- Volume Slider -->
            <div class="q-mb-lg">
              <div class="row items-center justify-between q-mb-xs">
                <div class="text-weight-bold text-body2">
                  <q-icon name="volume_up" size="xs" class="q-mr-xs" />Volume
                </div>
                <q-badge color="blue-9" :label="`${soundSettings.volume}%`" />
              </div>
              <q-slider
                v-model="soundSettings.volume"
                :min="10" :max="100" :step="5"
                color="blue-9"
                label
                :label-value="`${soundSettings.volume}%`"
                markers marker-labels
                snap
              />
            </div>

            <q-separator class="q-mb-md" />

            <!-- Correct Sound Selection -->
            <div class="q-mb-md">
              <div class="row items-center q-gutter-xs q-mb-sm">
                <q-icon name="check_circle" color="green" size="sm" />
                <span class="text-weight-bold text-body2">Correct Scan Sound</span>
              </div>
              <div class="q-gutter-xs">
                <q-btn
                  v-for="opt in correctSoundOptions" :key="opt.value"
                  :outline="soundSettings.correctSound !== opt.value"
                  :color="soundSettings.correctSound === opt.value ? 'green' : 'grey-5'"
                  :text-color="soundSettings.correctSound === opt.value ? 'white' : 'dark'"
                  dense no-caps size="sm"
                  class="q-mr-xs q-mb-xs"
                  @click="soundSettings.correctSound = opt.value as any"
                >
                  {{ opt.label }}
                </q-btn>
              </div>
              <div class="text-caption text-grey-6 q-mt-xs">
                {{ correctSoundOptions.find(o => o.value === soundSettings.correctSound)?.desc }}
              </div>
              <q-btn
                flat dense size="sm" icon="play_circle" label="Preview"
                color="green" class="q-mt-xs" no-caps
                @click="playSound('correct')"
              />
            </div>

            <q-separator class="q-mb-md" />

            <!-- Wrong Sound Selection -->
            <div class="q-mb-md">
              <div class="row items-center q-gutter-xs q-mb-sm">
                <q-icon name="cancel" color="red" size="sm" />
                <span class="text-weight-bold text-body2">Wrong Scan Sound</span>
              </div>
              <div class="q-gutter-xs">
                <q-btn
                  v-for="opt in wrongSoundOptions" :key="opt.value"
                  :outline="soundSettings.wrongSound !== opt.value"
                  :color="soundSettings.wrongSound === opt.value ? 'red' : 'grey-5'"
                  :text-color="soundSettings.wrongSound === opt.value ? 'white' : 'dark'"
                  dense no-caps size="sm"
                  class="q-mr-xs q-mb-xs"
                  @click="soundSettings.wrongSound = opt.value as any"
                >
                  {{ opt.label }}
                </q-btn>
              </div>
              <div class="text-caption text-grey-6 q-mt-xs">
                {{ wrongSoundOptions.find(o => o.value === soundSettings.wrongSound)?.desc }}
              </div>
              <q-btn
                flat dense size="sm" icon="play_circle" label="Preview"
                color="red" class="q-mt-xs" no-caps
                @click="playSound('wrong')"
              />
            </div>
          </template>

          <template v-else>
            <div class="text-center q-pa-lg text-grey">
              <q-icon name="volume_off" size="xl" class="q-mb-sm" /><br>
              <div class="text-body2">Sound effects are disabled</div>
              <div class="text-caption">Toggle the switch above to enable</div>
            </div>
          </template>
        </q-card-section>

        <!-- Footer -->
        <q-separator />
        <q-card-actions align="between" class="q-px-md">
          <q-btn flat dense no-caps color="grey" label="Reset Defaults" icon="restart_alt" @click="soundSettings = { ...defaultSoundSettings }" />
          <q-btn flat dense no-caps color="blue-9" label="Done" icon="check" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- ── Footer Bar ── -->
    <div class="row items-center justify-between q-px-sm"
         style="height:22px;background:#1a237e;flex-shrink:0;">
      <span style="font-size:0.65rem;color:#7986cb;">
        Packing List v2.2
      </span>
      <span style="font-size:0.65rem;font-family:'Courier New',monospace;color:#FFCC00;font-weight:bold;">
        xdev.co.th
      </span>
    </div>

    <!-- Packing Report Dialog -->
    <q-dialog v-model="showPackingReportDialog">
      <q-card style="min-width: 380px;">
        <q-card-section class="bg-primary text-white">
          <div class="text-h6"><q-icon name="assessment" class="q-mr-sm" />Packing List Report</div>
        </q-card-section>
        <q-card-section>
          <q-select v-model="packingReportPlanId" :options="activePlans.map((p: any) => ({ label: p.plan_id + ' — ' + (p.sku_name || p.sku_id), value: p.plan_id }))" emit-value map-options label="Select Plan" filled />
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" icon="print" label="Generate Report" :loading="packingReportLoading" @click="printPackingListReport" />
        </q-card-actions>
      </q-card>
    </q-dialog>
  </q-page>
</template>

<style scoped>
.transition-all {
  transition: background-color 0.2s ease, color 0.2s ease;
}
</style>

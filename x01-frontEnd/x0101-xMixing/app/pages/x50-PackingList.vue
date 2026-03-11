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
    const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/production-batches/ready-to-deliver`, {
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
          bagsCount: 0,
          time: new Date(b.fh_boxed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          inProduction: !!b.production,
        })
      }
      if (b.spp_boxed_at) {
        boxes.push({
          id: `${b.batch_id}-SPP`,
          wh: 'SPP',
          batch_id: b.batch_id,
          bagsCount: 0,
          time: new Date(b.spp_boxed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          inProduction: !!b.production,
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
  } catch (e) {
    console.error('Error fetching ready-to-deliver:', e)
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

const onScanBatchEnter = () => {
  if (!scanBatchId.value) return
  for (const plan of plans.value) {
    const batch = plan.batches?.find((b: any) => b.batch_id === scanBatchId.value)
    if (batch) {
      selectedBatch.value = batch
      selectedPlan.value = plan
      fetchBatchRecords(batch.batch_id)
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
  inProduction: boolean  // batch.production flag — hides from delivery panel
}
const transferredBoxes = ref<TransferredBox[]>([])

// ── Transfer Dialog ──────────────────────────────────────────────
const showTransferDialog   = ref(false)
const selectedForTransfer  = ref<string[]>([])   // list of TransferredBox.id
const filterDeliveryWh     = ref<'ALL'|'FH'|'SPP'>('ALL')
const filterDeliveryStatus = ref<'ALL'|'WAITING'>('WAITING')  // ALL=show delivered too, WAITING=pending only
const deliveredMap         = ref<Map<string, string>>(new Map())  // "batch_id-WH" → delivery time

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

const filteredBoxScans = computed(() => {
  if (filterMiddleWh.value === 'ALL') return currentBoxScans.value
  if (filterMiddleWh.value === 'FH') return currentBoxScans.value.filter(bag => isFH(bag.wh || ''))
  if (filterMiddleWh.value === 'SPP') return currentBoxScans.value.filter(bag => isSPP(bag.wh || ''))
  return currentBoxScans.value.filter(bag => bag.wh === filterMiddleWh.value)
})

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


const onCloseBox = (wh: 'FH' | 'SPP') => {
  if (!selectedBatch.value) return
  const scannedBagsForWh = currentBoxScans.value.filter(bag => (wh === 'FH' ? isFH(bag.wh) : isSPP(bag.wh)))
  if (scannedBagsForWh.length === 0) {
     $q.notify({ type: 'warning', message: `No bags scanned for ${wh} box yet.`, position: 'top' })
     return
  }
  const batchId = selectedBatch.value.batch_id
  $q.dialog({
    title: `Close ${wh} Packing Box`,
    message: `You have scanned ${scannedBagsForWh.length} bags. Seal this box and print label?`,
    cancel: true,
    persistent: true,
    ok: { label: 'Seal & Print', color: wh === 'FH' ? 'blue' : 'light-blue', icon: 'check_circle' },
  }).onOk(async () => {
    try {
      // 1. Mark all scanned items as packed individually
      for (const bag of scannedBagsForWh) {
        // Update prebatch_recs (legacy) - only if bag has a prebatch rec id
        if (bag.batch_record_id || bag.prebatch_id) {
          try {
            await $fetch(`${appConfig.apiBaseUrl}/prebatch-recs/${bag.id}/packing-status`, {
              method: 'PATCH',
              headers: getAuthHeader() as Record<string, string>,
              body: { packing_status: 1, packed_by: 'operator' },
            })
          } catch (e) {
            // Expected to fail if bag.id is a prebatch_item id, not a rec id
          }
        }

        // Update prebatch_items (new unified table)
        // The bag itself might BE a req item from onItemClick — use its id directly
        const whMatcher = wh === 'FH' ? isFH : isSPP
        const matchingItem = selectedBatch.value.reqs?.find((r: any) =>
          r.re_code === bag.re_code && whMatcher(r.wh || '')
        ) || (bag.required_volume !== undefined ? bag : null) // bag IS a req
        
        if (matchingItem) {
          try {
            await $fetch(`${appConfig.apiBaseUrl}/prebatch-items/${matchingItem.id}/packing-status`, {
              method: 'PATCH',
              headers: getAuthHeader() as Record<string, string>,
              body: { packing_status: 1, packed_by: 'operator' },
            })
            matchingItem.packing_status = 1
          } catch (e) {
            console.error(`Failed to update packing status for item ${matchingItem.id}:`, e)
          }
        }
      }

      // 2. Close the box on the batch
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
      
      // Auto-trigger the print box label function (must await before clearing scans)
      await printBoxLabel(wh)
      
      // Clear current box session for this WH (after print is done reading the data)
      currentBoxScans.value = currentBoxScans.value.filter(bag => (wh === 'FH' ? !isFH(bag.wh) : !isSPP(bag.wh)))
      
      // Refresh data
      await fetchBatchRecords(batchId)
      await fetchAllRecords() // Refresh middle panel
      await fetchReadyToDeliver()
      console.log(`[CloseBox] Data refreshed. Transferred boxes:`, transferredBoxes.value.length)
    } catch (e) {
      console.error('Error closing box:', e)
      $q.notify({ type: 'negative', message: `Failed to close ${wh} box for ${batchId}` })
    }
  })
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
})




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

  // Check if this bag belongs to the selected batch via req_id
  const batchReqs = selectedBatch.value.reqs || []
  const reqIds = new Set(batchReqs.map((r: any) => r.id))
  const belongsToBox = reqIds.has(bag.req_id)

  if (belongsToBox) {
    // Correct — this bag belongs to the selected packing box
    playSound('correct')

    // Add to currentBoxScans if not already there
    if (!currentBoxScans.value.some(b => b.id === bag.id)) {
      currentBoxScans.value.push(bag)
    }
    
    const whLabel = scanDialogWh.value
    if (whLabel === 'FH') scanFH.value = bag.batch_record_id
    else scanSPP.value = bag.batch_record_id
    $q.notify({
      type: 'positive',
      icon: 'check_circle',
      message: `✅ Correct! ${bag.re_code} added to current box`,
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

/** Handle scan input from FH/SPP scan fields — lookup by batch_record_id */
const onScanInputEnter = async (wh: 'FH' | 'SPP') => {
  let scanValue = wh === 'FH' ? scanFH.value.trim() : scanSPP.value.trim()
  if (!scanValue) return

  let batchIdFromScan = null

  // Parse comma-separated barcode format (e.g. PlanID,PreBatchID,,ReCode,Weight)
  if (scanValue.includes(',')) {
    const parts = scanValue.split(',')
    if (parts.length > 2) {
      batchIdFromScan = parts[1]?.trim() || ''
      scanValue = parts[2]?.trim() || ''
    } else if (parts.length > 1) {
      scanValue = parts[1]?.trim() || ''
    }
  }

  // Auto Select Box if not selected or different from current scan
  if (batchIdFromScan && (!selectedBatch.value || selectedBatch.value?.batch_id !== batchIdFromScan)) {
    scanBatchId.value = batchIdFromScan
    onScanBatchEnter()
  }

  if (!selectedBatch.value) {
    playSound('wrong')
    $q.notify({ type: 'negative', message: t('packingList.selectBatchFirst'), icon: 'warning', position: 'top' })
    return
  }

  // 1. Try to find in legacy bags (prebatch_recs via bagsByWarehouse)
  const whBags = wh === 'FH' ? bagsByWarehouse.value.FH : bagsByWarehouse.value.SPP
  const bag = whBags.find(b => 
    b.batch_record_id === scanValue || 
    b.id?.toString() === scanValue ||
    b.intake_id === scanValue
  )

  if (bag) {
    if (isPacked(bag)) {
      $q.notify({ type: 'info', message: t('packingList.alreadyPacked'), caption: bag.batch_record_id, position: 'top', timeout: 2000 })
    } else {
      await onSimScanClick(bag)
    }
    if (wh === 'FH') scanFH.value = ''
    else scanSPP.value = ''
    return
  }

  // 2. Fallback: find in prebatch_items (lower card) by batch_record_id
  const batchReqs = selectedBatch.value.reqs || []
  const whFilter = wh === 'FH' ? isFH : isSPP
  const item = batchReqs.find((r: any) =>
    whFilter(r.wh || '') && r.batch_record_id === scanValue
  )

  if (item) {
    if (item.packing_status === 1) {
      playSound('correct')
      $q.notify({ type: 'info', message: 'Already packed', caption: item.batch_record_id, position: 'top', timeout: 2000 })
    } else {
      playSound('correct')
      try {
        await $fetch(`${appConfig.apiBaseUrl}/prebatch-items/${item.id}/packing-status`, {
          method: 'PATCH',
          headers: getAuthHeader() as Record<string, string>,
          body: { packing_status: 1, packed_by: 'operator' },
        })
        item.packing_status = 1
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
    if (wh === 'FH') scanFH.value = ''
    else scanSPP.value = ''
    return
  }

  // 3. Not found anywhere
  playSound('wrong')
  $q.notify({ type: 'negative', icon: 'error', message: t('packingList.bagNotFound'), caption: scanValue, position: 'top', timeout: 3000 })
  if (wh === 'FH') scanFH.value = ''
  else scanSPP.value = ''
}

// Watch for MQTT scans — smart routing: intake ID vs batch ID
watch(lastScan, async (scan) => {
  if (!scan?.barcode) return
  let barcode = scan.barcode.trim()
  let batchIdFromScan = null

  // Parse comma-separated barcode format (e.g. PlanID,PreBatchID,,ReCode,Weight)
  if (barcode.includes(',')) {
    const parts = barcode.split(',')
    if (parts.length > 2) {
      batchIdFromScan = parts[1]?.trim() || ''
      barcode = parts[2]?.trim() || ''
    } else if (parts.length > 1) {
      barcode = parts[1]?.trim() || ''
    }
  }

  // Auto Select Box if not selected or different from current scan
  if (batchIdFromScan && (!selectedBatch.value || selectedBatch.value?.batch_id !== batchIdFromScan)) {
    scanBatchId.value = batchIdFromScan
    onScanBatchEnter()
  }

  // If a batch is selected, try to match as intake ID first
  if (selectedBatch.value) {
    // 1. Try legacy bags (prebatch_recs)
    const allBags = [...bagsByWarehouse.value.FH, ...bagsByWarehouse.value.SPP]
    const bag = allBags.find(b =>
      b.batch_record_id === barcode ||
      b.id?.toString() === barcode ||
      b.intake_id === barcode
    )
    if (bag) {
      onSimScanClick(bag)
      return
    }

    // 2. Fallback: try prebatch_items (lower card)
    const batchReqs = selectedBatch.value.reqs || []
    const item = batchReqs.find((r: any) => r.batch_record_id === barcode)
    if (item && item.packing_status !== 1) {
      playSound('correct')
      try {
        await $fetch(`${appConfig.apiBaseUrl}/prebatch-items/${item.id}/packing-status`, {
          method: 'PATCH',
          headers: getAuthHeader() as Record<string, string>,
          body: { packing_status: 1, packed_by: 'operator' },
        })
        item.packing_status = 1
        $q.notify({ type: 'positive', icon: 'check_circle', message: `✅ ${item.re_code} packed`, caption: barcode, position: 'top', timeout: 2000 })
      } catch (e) { console.error('MQTT scan packing error:', e) }
      return
    } else if (item && item.packing_status === 1) {
      $q.notify({ type: 'info', message: 'Already packed', caption: barcode, position: 'top', timeout: 2000 })
      return
    }
  }

  // Otherwise, treat as batch ID scan
  scanBatchId.value = barcode
  onScanBatchEnter()
})

// Auto-close box when all bags for a warehouse are packed
watch([allFhPacked, allSppPacked], async ([fhDone, sppDone]) => {
  if (!selectedBatch.value) return
  const batchId = selectedBatch.value.batch_id

  const autoCloseBox = async (wh: 'FH' | 'SPP') => {
    try {
      await $fetch(`${appConfig.apiBaseUrl}/production-batches/by-batch-id/${batchId}/box-close`, {
        method: 'PATCH',
        headers: getAuthHeader() as Record<string, string>,
        body: { wh },
      })
      playSound('correct')
      $q.notify({
        type: 'positive',
        icon: 'unarchive',
        message: `✅ ${wh} Box auto-closed — all bags packed!`,
        position: 'top',
        timeout: 3000,
      })
      await fetchReadyToDeliver()
    } catch (e) {
      console.error(`Auto-close ${wh} box failed:`, e)
    }
  }

  if (fhDone && bagsByWarehouse.value.FH.length > 0) {
    await autoCloseBox('FH')
  }
  if (sppDone && bagsByWarehouse.value.SPP.length > 0) {
    await autoCloseBox('SPP')
  }
})

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
                {{ (selectedBatch.reqs || []).filter((r: any) => isReqPackingOk(r)).length }}/{{ (selectedBatch.reqs || []).length }}
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
                  v-if="(selectedBatch.reqs || []).filter((r: any) => isFH(r.wh || '')).length > 0"
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
                  v-if="(selectedBatch.reqs || []).filter((r: any) => isSPP(r.wh || '')).length > 0"
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
                  {{ filteredBoxScans.length }} items
                </q-badge>
                <q-btn
                  unelevated size="sm" icon="check_box" label="Close Box & Print"
                  :color="filteredBoxScans.length > 0 ? 'green-5' : 'grey-5'"
                  :disable="filteredBoxScans.length === 0"
                  @click="onCloseBox(filterMiddleWh === 'ALL' ? 'FH' : filterMiddleWh)"
                >
                  <q-tooltip>{{ filteredBoxScans.length > 0 ? 'Seal Box & Print Label' : 'Scan items first' }}</q-tooltip>
                </q-btn>
              </div>
            </div>
          </q-card-section>
          
          <!-- Compact Batch Scanner + Info -->
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

          <!-- Current Box Items (compact, scrollable) -->
          <div v-if="filteredBoxScans.length > 0" style="max-height:300px; overflow-y:auto; background:#f5f7fa;">
            <q-list dense separator class="bg-white" style="border-radius:0;">
              <q-item v-for="(bag, idx) in filteredBoxScans" :key="idx" dense style="min-height:24px">
                <q-item-section avatar style="min-width:20px">
                   <q-icon name="check_circle" size="xs" color="green-6" />
                </q-item-section>
                <q-item-section>
                   <q-item-label style="font-size:0.7rem" class="text-weight-bold">{{ bag.re_code }}</q-item-label>
                </q-item-section>
                <q-item-section side>
                   <span style="font-size:0.65rem" class="text-weight-bold text-green-8">
                     {{ bag.net_volume?.toFixed(3) || bag.total_request_volume?.toFixed(3) || bag.required_volume?.toFixed(3) }} kg
                   </span>
                </q-item-section>
              </q-item>
            </q-list>
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
                  <span class="text-caption" style="opacity:0.8">— {{ filterMiddleWh === 'FH' ? 'FH → SPP' : 'SPP → Prod' }}</span>
                </div>
              </div>
              <div class="row items-center q-gutter-xs">
                <q-select
                  v-model="filterDeliveryStatus"
                  :options="[{ label: 'All', value: 'ALL' }, { label: 'Waiting', value: 'WAITING' }]"
                  emit-value map-options dense outlined
                  style="min-width:80px;background:rgba(255,255,255,0.15);border-radius:4px;"
                  input-class="text-white text-caption"
                  popup-content-class="text-caption"
                  color="white"
                  dark
                />
                <q-badge color="white" text-color="indigo-7" class="text-weight-bold">
                  {{ groupedTransferredBoxes.filter(r => {
                    if (r.inProduction) return false
                    const hasWh = filterMiddleWh === 'FH' ? !!r.fh : !!r.spp
                    const isDelivered = filterMiddleWh === 'FH' ? !!deliveredMap.get(`${r.batch_id}-FH`) : !!deliveredMap.get(`${r.batch_id}-SPP`)
                    return hasWh && (filterDeliveryStatus === 'ALL' || !isDelivered)
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
              <q-list dense separator>
                <template v-for="row in groupedTransferredBoxes" :key="row.batch_id">
                  <q-item
                    v-if="(() => {
                      if (row.inProduction) return false
                      const hasWh = filterMiddleWh === 'FH' ? !!row.fh : !!row.spp
                      const isDelivered = filterMiddleWh === 'FH' ? !!deliveredMap.get(`${row.batch_id}-FH`) : !!deliveredMap.get(`${row.batch_id}-SPP`)
                      return hasWh && (filterDeliveryStatus === 'ALL' || !isDelivered)
                    })()"
                    class="q-pa-xs"
                  >
                    <q-item-section>
                      <q-item-label class="text-weight-bold text-caption text-mono">
                        📦 {{ row.batch_id }}-{{ filterMiddleWh === 'FH' ? 'FH' : 'SPP' }}
                      </q-item-label>
                    </q-item-section>

                    <q-item-section side style="padding-right:0;min-width:28px">
                      <q-btn flat round dense icon="print" size="xs" color="indigo-4"
                        @click.stop="printPackingBoxReport(row.batch_id, filterMiddleWh === 'ALL' ? 'FH' : filterMiddleWh)">
                        <q-tooltip>Print Box Report (A4)</q-tooltip>
                      </q-btn>
                    </q-item-section>

                    <!-- Per-WH delivery: only shows the section matching the Packing Box dropdown -->
                    <q-item-section side>
                      <div class="column q-gutter-xs items-end">
                        <!-- FH boxed → deliver to SPP (only when FH dropdown selected) -->
                        <template v-if="row.fh && filterMiddleWh === 'FH'">
                          <div class="row items-center q-gutter-xs">
                            <q-badge color="blue-7" style="font-size:0.58rem;">
                              FH <q-icon name="unarchive" size="10px" class="q-ml-xs"/> {{ row.fh.time }}
                            </q-badge>
                            <q-badge v-if="deliveredMap.get(`${row.batch_id}-FH`)" color="green-8" class="text-weight-bold" style="font-size:0.58rem;">
                              <q-icon name="local_shipping" size="10px" class="q-mr-xs"/>→SPP {{ deliveredMap.get(`${row.batch_id}-FH`) }}
                            </q-badge>
                            <q-btn v-else dense unelevated no-caps size="xs" color="blue-7" text-color="white" icon="local_shipping" label="→SPP" @click="markDelivered(row.batch_id, 'FH')">
                              <q-tooltip>Deliver FH to SPP</q-tooltip>
                            </q-btn>
                          </div>
                        </template>
                        <!-- SPP boxed → deliver to Production Hall (only when SPP dropdown selected) -->
                        <template v-if="row.spp && filterMiddleWh === 'SPP'">
                          <div class="row items-center q-gutter-xs">
                            <q-badge color="light-blue-7" style="font-size:0.58rem;">
                              SPP <q-icon name="unarchive" size="10px" class="q-ml-xs"/> {{ row.spp.time }}
                            </q-badge>
                            <q-badge v-if="deliveredMap.get(`${row.batch_id}-SPP`)" color="green-8" class="text-weight-bold" style="font-size:0.58rem;">
                              <q-icon name="local_shipping" size="10px" class="q-mr-xs"/>→Prod {{ deliveredMap.get(`${row.batch_id}-SPP`) }}
                            </q-badge>
                            <q-btn v-else dense unelevated no-caps size="xs" color="amber-7" text-color="white" icon="local_shipping" label="→Prod" @click="markDelivered(row.batch_id, 'SPP')">
                              <q-tooltip>Deliver SPP to Production Hall</q-tooltip>
                            </q-btn>
                          </div>
                        </template>
                      </div>
                    </q-item-section>
                  </q-item>
                </template>

                <q-item v-if="groupedTransferredBoxes.length === 0">
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
                <q-item-section side>
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

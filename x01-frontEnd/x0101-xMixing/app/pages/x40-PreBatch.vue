<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue'
import { useQuasar } from 'quasar'

import { useAuth } from '../composables/useAuth'
import { appConfig } from '~/appConfig/config'
import { useLabelPrinter } from '~/composables/useLabelPrinter'
import { usePreBatchProduction } from '~/composables/prebatch/usePreBatchProduction'
import { usePreBatchIngredients } from '~/composables/prebatch/usePreBatchIngredients'
import { usePreBatchInventory } from '~/composables/prebatch/usePreBatchInventory'
import { usePreBatchScales } from '~/composables/prebatch/usePreBatchScales'
import { usePreBatchLabels } from '~/composables/prebatch/usePreBatchLabels'
import { usePreBatchRecords } from '~/composables/prebatch/usePreBatchRecords'
import { useMqttLocalDevice } from '~/composables/useMqttLocalDevice'

const $q = useQuasar()
const { getAuthHeader, user } = useAuth()
const authHeader = () => getAuthHeader() as Record<string, string>
const { generateLabelSvg, printLabel } = useLabelPrinter()
const { t } = useI18n()
const { connect: connectMqtt, mqttClient } = useMqttLocalDevice()

/** Parse date safely — handles DD/MM/YYYY, YYYY-MM-DD, ISO, and Date objects */
const parseDateSafe = (date: any): Date | null => {
  if (!date) return null
  if (date instanceof Date) return isNaN(date.getTime()) ? null : date
  const s = String(date).trim()
  // DD/MM/YYYY format (e.g. "09/07/2027" = July 9, 2027)
  const slashMatch = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})$/)
  if (slashMatch) {
    const [, day, month, year] = slashMatch
    return new Date(Number(year), Number(month) - 1, Number(day))
  }
  // DD-MM-YYYY format
  const dashDMY = s.match(/^(\d{1,2})-(\d{1,2})-(\d{4})$/)
  if (dashDMY) {
    const [, day, month, year] = dashDMY
    return new Date(Number(year), Number(month) - 1, Number(day))
  }
  // ISO or other formats
  const d = new Date(s)
  return isNaN(d.getTime()) ? null : d
}

const formatDate = (date: any) => {
  if (!date) return '-'
  const d = parseDateSafe(date)
  if (!d) return String(date)
  return d.toLocaleDateString('en-GB')
}

// ─── Shared refs (owned by page, passed into composables) ───
const selectedReCode = ref('')
const selectedRequirementId = ref<number | null>(null)
const requireVolume = ref(0)
const packageSize = ref(0)
const isBatchSelected = ref(false)
const ingredients = ref<any[]>([])



// ─── 1. Inventory ───
const {
  warehouses, selectedWarehouse, inventoryRows, inventoryLoading,
  selectedInventoryItem, selectedIntakeLotId, showAllInventory,
  showHistoryDialog, showIntakeLabelDialog, selectedHistoryItem,
  intakeLabelData, selectedPrinter, intakeLotInputRef,
  inventoryColumns, filteredInventory, sortedAllInventory, inventorySummary,
  fetchWarehouses, fetchInventory, updateInventoryStatus,
  printIntakeLabel, openIntakeLabelDialog, onViewHistory,
  focusIntakeLotInput, onIntakeLotScanEnter, isFIFOCompliant,
} = usePreBatchInventory({
  $q, getAuthHeader: authHeader, t, formatDate,
  selectedReCode,
})

// ─── 2. Scales ───
const scalesComposable = usePreBatchScales({
  $q, t,
  selectedReCode,
  requireVolume,
  packageSize,
  mqttClient,
})
const {
  selectedScale, scales, connectedScales, batchedVolume, currentPackageOrigins,
  activeScale, actualScaleValue, remainVolume, lastCapturedWeight,
  targetWeight, requestBatch, isToleranceExceeded, isPackagedVolumeInTol,
  packagedVolumeBgColor,
  onScaleInput, isScaleConnected, toggleScaleConnection,
  getScaleClass, getDisplayClass, onTare,
  getOriginDelta, onAddLot, onRemoveLot,
} = scalesComposable

// ─── Forward declarations for cross-references ───
// These functions are set after the composables that own them are created.
let _fetchPrebatchItems: (batchId: string) => Promise<void> = async () => {}
let _updatePrebatchItemStatus: (batchId: string, reCode: string, status: number) => Promise<void> = async () => {}
let _fetchPreBatchRecords: () => Promise<void> = async () => {}
let _updateRequireVolume: () => void = () => {}
let _finalizeBatchPreparation: (batchId: number) => Promise<void> = async () => {}
let _onBatchIngredientClick: (batch: any, req: any, plan: any) => Promise<void> = async () => {}


// (Moved logic below destructuring to fix ID 599 lint errors)

// ─── 3. Ingredients ───
// selectedProductionPlan and selectedBatch are owned by production composable
// but ingredients needs them. We create a ref/computed that we'll sync later.
const _selectedProductionPlan = ref('')
const _selectedBatch = ref<any>(null)
const _preBatchLogs = ref<any[]>([])
const autoPrint = ref(true)


const ingredientsComposable = usePreBatchIngredients({
  $q, getAuthHeader: authHeader, t,
  ingredients,
  selectedProductionPlan: _selectedProductionPlan,
  selectedBatch: computed(() => _selectedBatch.value),
  selectedReCode,
  selectedRequirementId,
  selectedWarehouse,
  isBatchSelected,
  inventoryRows,
  preBatchLogs: _preBatchLogs,
  requireVolume,
  packageSize,
  filteredInventory,
  selectedInventoryItem,
  selectedIntakeLotId,
  updatePrebatchItemStatus: (...args: [string, string, number]) => _updatePrebatchItemStatus(...args),
  onBatchIngredientClick: (...args: [any, any, any]) => _onBatchIngredientClick(...args),
})
const {
  prebatchItems, expandedIngredients, ingredientBatchDetail, expandedBatchRows,
  selectableIngredients, ingredientsByWarehouse,
  fetchPrebatchItems, updatePrebatchItemStatus,
  toggleIngredientExpand, isExpanded, fetchIngredientBatchDetail,
  toggleBatchRow, isBatchRowExpanded, getPackagePlan,
  getIngredientLogs, getIngredientRowClass,
  onSelectIngredient, updateRequireVolume, onIngredientSelect, onIngredientDoubleClick,
} = ingredientsComposable

// Wire forward refs
_fetchPrebatchItems = fetchPrebatchItems
_updatePrebatchItemStatus = updatePrebatchItemStatus
_updateRequireVolume = updateRequireVolume

// ─── 4. Records ───
const recordsComposable = usePreBatchRecords({
  $q, getAuthHeader: authHeader, t, user, formatDate,
  selectedBatch: computed(() => _selectedBatch.value),
  selectedProductionPlan: _selectedProductionPlan,
  selectedReCode,
  requireVolume,
  selectableIngredients,
  requestBatch,
  fetchPrebatchItems,
  finalizeBatchPreparation: (...args: [number]) => _finalizeBatchPreparation(...args),
})
const {
  preBatchLogs, recordToDelete, showDeleteDialog, deleteInput, selectedPreBatchLogs,
  prebatchColumns, filteredPreBatchLogs, totalCompletedWeight,
  completedCount, nextPackageNo, preBatchSummary,
  fetchPreBatchRecords, executeDeletion, onDeleteRecord,
  onConfirmDeleteManual, onDeleteScanEnter, clearAllBatchRecords,
} = recordsComposable

// Wire forward refs
_fetchPreBatchRecords = fetchPreBatchRecords

// Sync preBatchLogs into ingredients composable
watch(preBatchLogs, (val) => { _preBatchLogs.value = val }, { deep: true, immediate: true })

// Sync computed values from records into scales
watch(totalCompletedWeight, (val) => { scalesComposable.totalCompletedWeight.value = val }, { immediate: true })
watch(completedCount, (val) => { scalesComposable.completedCount.value = val }, { immediate: true })
watch(nextPackageNo, (val) => { scalesComposable.nextPackageNo.value = val }, { immediate: true })

// ─── 5. Production ───
const production = usePreBatchProduction({
  $q, getAuthHeader: authHeader, t,
  ingredients,
  prebatchItems,
  inventoryRows,
  requireVolume,
  packageSize,
  selectedReCode,
  selectedRequirementId,
  isBatchSelected,
  selectedWarehouse,
  fetchPrebatchItems,
  fetchPreBatchRecords,
  updatePrebatchItemStatus,
  updateRequireVolume,
  ingredientBatchDetail,
  selectedIntakeLotId,
})
const {
  selectedBatchIndex, isLoading, productionPlans, planFilter, productionPlanOptions,
  searchPlanId, searchSkuName,
  allBatches, filteredBatches, ingredientOptions, batchIngredients,
  filteredProductionPlans, plansWithBatches, batchIds, selectedBatch, selectedProductionPlan, selectedPlanDetails, structuredSkuList,
  fetchIngredients, fetchProductionPlans, fetchBatchIds,
  filterBatchesByPlan, onPlanShow, onBatchSelect, onBatchExpand,
  onBatchIngredientClick, advanceToNextBatch, finalizeBatchPreparation, onSelectBatch,
} = production

// Wire forward ref & sync production-owned refs into ingredients/records composable
_finalizeBatchPreparation = finalizeBatchPreparation
_onBatchIngredientClick = onBatchIngredientClick
watch(selectedProductionPlan, (val) => { _selectedProductionPlan.value = val }, { immediate: true })
watch(selectedBatch, (val) => { _selectedBatch.value = val }, { immediate: true })

// ─── 6. Labels ───
const {
  showLabelDialog, packageLabelId, capturedScaleValue, renderedLabel,
  showPackingBoxLabelDialog, renderedPackingBoxLabel,
  labelDataMapping, packingBoxLabelDataMapping,
  buildLotStrings, buildLabelData,
  updateDialogPreview, updatePackingBoxPreview,
  openLabelDialog, onPrintLabel, onReprintLabel,
  quickReprint, printAllPlanLabels, printAllBatchLabels, printGlobalPlanLabels, onPrintPackingBoxLabel, onDone,
} = usePreBatchLabels({
  $q, getAuthHeader: authHeader, t, user, formatDate,
  generateLabelSvg: (async (template: string, data: any) => (await generateLabelSvg(template, data)) ?? '') as (template: string, data: any) => Promise<string>,
  printLabel,
  selectedBatch,
  selectedReCode,
  selectedRequirementId,
  selectedProductionPlan,
  selectedPlanDetails,
  selectableIngredients,
  ingredients,
  requireVolume,
  packageSize,
  capturedScaleValue: batchedVolume,
  nextPackageNo,
  requestBatch,
  actualScaleValue,
  currentPackageOrigins,
  preBatchLogs,
  selectedPreBatchLogs,
  totalCompletedWeight,
  getPackagePlan,
  fetchPreBatchRecords,
  fetchPrebatchItems,
  updatePrebatchItemStatus,
  onBatchExpand,
  onPlanShow,
  advanceToNextBatch,
  getOriginDelta,
  selectedIntakeLotId,
  selectedInventoryItem,
  productionPlans,
  prebatchItems,
  ingredientBatchDetail,
})

// Step 7: After label print (dialog closes) → reopen scan dialog for next batch
watch(showLabelDialog, async (newVal, oldVal) => {
  if (oldVal === true && newVal === false && selectedReCode.value) {
    // If a lot is already checked in, skip the scan dialog and go to next item
    if (selectedIntakeLotId.value) {
      console.log('🔄 Auto-continuing to next batch (Lot already checked in)')
      await fetchScanDialogItems()
      const next = nextPendingItem.value
      if (next) {
        onScanItemSelect(next)
        return
      }
    }
    // Else (no lot or no more items) -> reopen scan dialog for next item
    setTimeout(() => openScanDialog(), 500)
  }
})

// ─── Post-Destructuring Logic & Reactive Logic ───
const currentContainerType = computed(() => {
  return selectableIngredients.value.find((i: any) => i.re_code === selectedReCode.value)?.package_container_type || 'Bag'
})

const fetchedContainerSizes = ref<any[]>([])

const fetchContainerSizes = async () => {
  try {
    const data = await $fetch<any[]>(`${appConfig.apiBaseUrl}/package-container-sizes/`, { headers: authHeader() })
    fetchedContainerSizes.value = data
  } catch (err) {
    console.error('Failed to fetch container sizes', err)
  }
}

const containerSizeOptions = computed(() => {
  const type = currentContainerType.value
  const matching = fetchedContainerSizes.value.filter(s => s.container_type === type).map(s => s.size)
  const options = [...new Set(matching)]
  
  if (options.length === 0) {
    // fallback
    options.push(...(type === 'Bag' ? [0.1, 0.2, 0.3, 0.5, 1, 2, 5, 10, 20, 25] : [5, 10, 20, 25, 50]))
  }

  // selectableIngredients is now defined
  const config = selectableIngredients.value.find((i: any) => i.re_code === selectedReCode.value)
  if (config && config.std_package_size > 0 && !options.includes(config.std_package_size)) {
    options.push(config.std_package_size)
  }
  return options.sort((a, b) => a - b)
})

const showContainerSizeDialog = ref(false)
const newContainerSize = ref<number | null>(null)

const addContainerSize = async () => {
    if (!newContainerSize.value || newContainerSize.value <= 0) return
    try {
        await $fetch(`${appConfig.apiBaseUrl}/package-container-sizes/`, {
            method: 'POST',
            headers: authHeader(),
            body: { size: newContainerSize.value, container_type: currentContainerType.value }
        })
        newContainerSize.value = null
        await fetchContainerSizes()
    } catch(err) {
        console.error('Add size error', err)
        $q.notify({ type: 'negative', message: 'Failed to add container size' })
    }
}

const deleteContainerSize = async (id: number) => {
    try {
        await $fetch(`${appConfig.apiBaseUrl}/package-container-sizes/${id}`, {
            method: 'DELETE',
            headers: authHeader()
        })
        await fetchContainerSizes()
    } catch(err) {
        console.error('Delete size error', err)
        $q.notify({ type: 'negative', message: 'Failed to delete container size' })
    }
}
const containerSize = ref(25)

// Watch containerSize to update packageSize
watch(containerSize, (val) => {
  if (val !== packageSize.value) {
    packageSize.value = val
  }
})

watch(packageSize, (val) => {
  if (containerSizeOptions.value.includes(val)) {
    containerSize.value = val
  }
})

// Watch selectedReCode to initialize containerSize from config AND clear lot on change
watch(selectedReCode, (newReCode) => {
  // Clear the intake lot when the ingredient changes
  selectedIntakeLotId.value = ''
  
  if (newReCode) {
    const config = selectableIngredients.value.find((i: any) => i.re_code === newReCode)
    if (config && config.std_package_size > 0) {
      containerSize.value = config.std_package_size
    }
  }
})

const currentPackageId = computed(() => {
  if (selectedBatch.value && selectedReCode.value) {
    return `${selectedBatch.value.batch_id}-${selectedReCode.value}-${nextPackageNo.value}`
  }
  return '-'
})


// --- 7-Step Guided Workflow Logic ---
const workflowStep = ref(1)
const pendingAdvance = ref<{ batchId: string, reCode: string } | null>(null)

const workflowStatus = computed(() => {
    if (!selectedReCode.value) return { id: 1, msg: 'Select Ingredient', color: 'primary' }
    if (!selectedIntakeLotId.value) return { id: 2, msg: 'Scan Intake Lot', color: 'orange-10' }
    if (workflowStep.value === 3) return { id: 3, msg: 'Ready to Start Pre-Batch', color: 'blue-8' }
    if (workflowStep.value === 4) return { id: 4, msg: 'Manual Weighing in Progress', color: 'green-8' }
    if (workflowStep.value === 7) return { id: 7, msg: 'Package Complete - Clear Scale', color: 'red-9' }
    return { id: 0, msg: 'Idle', color: 'grey' }
})

// --- Tare Popup ---
const showTarePopup = ref(false)
const selectedTareScale = ref(0)
const showConfirmStartPopup = ref(false)
let tarePopupTimer: ReturnType<typeof setTimeout> | null = null

// Parse capacity from scale label, e.g. "Scale 1 (10 Kg +/- 0.02kg)" -> 10
const getScaleCapacity = (scale: any): number => {
    const match = scale.label.match(/(\d+)\s*[Kk]g/)
    return match ? Number(match[1]) : 999
}

// Auto-select the most suitable scale: smallest capacity that fits the packageSize
const autoSelectBestScale = () => {
    const target = packageSize.value || requireVolume.value || 0
    const sorted = [...scalesComposable.scales.value]
        .filter(s => !s.isError)
        .sort((a, b) => getScaleCapacity(a) - getScaleCapacity(b))
    
    // Pick smallest scale whose capacity >= target weight
    const best = sorted.find(s => getScaleCapacity(s) >= target) || sorted[sorted.length - 1]
    if (best) {
        selectedTareScale.value = best.id
        scalesComposable.selectedScale.value = best.id
    }
}

const openTarePopup = () => {
    autoSelectBestScale()
    showTarePopup.value = true
    // No auto-advance timer — operator must tare, then confirm start popup appears when zero
    if (tarePopupTimer) clearTimeout(tarePopupTimer)
}

const closeTarePopupAndAdvance = () => {
    if (tarePopupTimer) clearTimeout(tarePopupTimer)
    showTarePopup.value = false
    // Apply the selected scale
    scalesComposable.selectedScale.value = selectedTareScale.value
    // Don't jump to step 4 — let watcher detect zero and show confirm start popup
}

const handleTareAndAdvance = () => {
    if (selectedTareScale.value) {
        scalesComposable.selectedScale.value = selectedTareScale.value
        scalesComposable.onTare(selectedTareScale.value)
    }
    closeTarePopupAndAdvance()
}

const confirmStartWeighing = () => {
    showConfirmStartPopup.value = false
    workflowStep.value = 4
}

const handleDoneClick = async () => {
    const currentBatchId = selectedBatch.value?.batch_id
    const currentReCode = selectedReCode.value
    
    // Capture weight
    lastCapturedWeight.value = actualScaleValue.value
    
    // Save and Print (Step 6)
    await onDone(true)
    
    // Move to Take Out state (Step 7)
    workflowStep.value = 7
    pendingAdvance.value = { batchId: currentBatchId, reCode: currentReCode }
}

const isScaleAtZero = computed(() => {
    const tolerance = activeScale.value?.tolerance || 0.01
    return Math.abs(actualScaleValue.value) <= tolerance * 2
})

const handleStartWeighting = () => {
    // Auto-select scale that has weight (if current scale reads 0)
    const currentReading = scalesComposable.actualScaleValue.value
    if (Math.abs(currentReading) < 0.01) {
        const scaleWithWeight = scalesComposable.scales.value.find(
            (s: any) => !s.isError && Math.abs(s.value) > 0.01
        )
        if (scaleWithWeight) {
            scalesComposable.selectedScale.value = scaleWithWeight.id
        }
    }
    workflowStep.value = 4 // Manual Batching (Weighing)
}

const onScaleSelect = (scale: any) => {
    const prevScale = selectedScale.value
    selectedScale.value = scale.id
    
    if (prevScale !== scale.id && workflowStep.value >= 3) {
        $q.notify({
            type: 'warning',
            icon: 'scale',
            message: `⚖️ Switched to ${scale.label}`,
            caption: 'Please ensure the scale is tared (zero) before placing material',
            position: 'top',
            timeout: 4000,
            actions: [{ label: 'OK', color: 'white' }]
        })
    }
}

/**
 * "Next Intake Lot" — capture current weight from current lot, scan next lot
 * Used when current lot doesn't have enough volume for full package
 */
const handleNextLot = () => {
    // 1. Capture current scale reading as partial from current lot
    scalesComposable.onAddLot(selectedIntakeLotId, selectableIngredients, selectedInventoryItem)
    
    // 2. Clear current lot selection (but keep ingredient selected)
    selectedIntakeLotId.value = ''
    scanLotInput.value = ''
    scanLotValidated.value = false
    scanLotError.value = ''
    
    // 3. Open scan dialog to scan next lot
    showScanDialog.value = true
    
    $q.notify({ 
        type: 'info', 
        message: 'Scan next intake lot to continue weighing', 
        position: 'top', 
        timeout: 2000 
    })
}

const handleStep7Confirm = (manual = false) => {
    // Determine the logical next step based on remaining items (Step 7 Loop)
    const packages = getPackagePlan(selectedBatch.value?.batch_id, selectedReCode.value, requireVolume.value)
    
    // CRITICAL: If remainVolume is 0, we MUST advance to the next batch, regardless of package count.
    const isBatchFinished = remainVolume.value <= 0.0001
    const hasMorePkgsInCurrentBatch = packages.some(p => p.status === 'pending')
    
    if (!isBatchFinished && hasMorePkgsInCurrentBatch) {
        // More packages needed (e.g. 1/3 → 2/3) — loop back to Step 3 silently
        const completed = packages.filter(p => p.status === 'completed').length
        const total = packages.length
        currentPackageOrigins.value = [] // Fresh container
        workflowStep.value = 3
        $q.notify({ 
            type: 'info', 
            message: `Package ${completed}/${total} done — ready for next package`, 
            position: 'top',
            timeout: 2000
        })
    } else {
        // ALL packages for this batch are done → go to Step 2 (re-scan lot for next batch)
        handleAdvanceInternal()
    }
}

const handleStopPreBatch = () => {
    $q.dialog({
        title: 'STOP PRE-BATCH',
        message: 'Are you sure you want to <b class="text-red-9">STOP</b> and reset the current workflow? <br/>Any unprinted weights will be lost.',
        ok: { label: 'Yes, Stop & Reset', color: 'red-9', unelevated: true },
        cancel: { flat: true, color: 'grey-7' },
        html: true,
        persistent: true
    }).onOk(() => {
        workflowStep.value = 1
        selectedReCode.value = ''
        selectedIntakeLotId.value = ''
        currentPackageOrigins.value = []
        $q.notify({ type: 'info', message: 'Workflow reset to Step 1', position: 'top' })
    })
}

const handleAdvanceInternal = async () => {
    if (pendingAdvance.value) {
        const nextBatchPromise = advanceToNextBatch(pendingAdvance.value.batchId, pendingAdvance.value.reCode)
        
        // Popup for next Batch in the queue
        $q.dialog({
            title: '✅ BATCH COMPLETE',
            message: `Batch <b>${pendingAdvance.value.batchId}</b> — all packages done!<br/><br/>` +
                     `Next: <b>Re-scan intake lot</b> for ${pendingAdvance.value.reCode}<br/>` +
                     `<span class="text-grey-7">(ensures correct & permissible lot is used)</span>`,
            ok: { label: 'Next Batch → Scan Lot', color: 'blue-10', unelevated: true },
            cancel: { label: 'Stop/Exit', flat: true, color: 'grey-7' },
            html: true,
            persistent: true
        }).onOk(async () => {
            await nextBatchPromise
            currentPackageOrigins.value = [] // Reset weighing data
            // Clear lot and go to Step 2 — force re-scan for next batch
            selectedIntakeLotId.value = ''
            if (selectedReCode.value === pendingAdvance.value?.reCode) {
                workflowStep.value = 2
                $q.notify({ type: 'info', message: `Scan lot for: ${selectedBatch.value?.batch_id}`, position: 'top' })
                // Open scan dialog for lot verification
                setTimeout(() => openScanDialog(), 300)
            } else {
                workflowStep.value = selectedReCode.value ? 2 : 1
            }
            pendingAdvance.value = null
        })
    }
}

// --- Workflow Confirmation Helper ---
const confirmTransition = (nextStep: number, message: string, onOk?: () => void) => {
    // If already in the target step, don't re-trigger logic
    if (workflowStep.value === nextStep) return
    
    console.log(`[Workflow] Silent transition to Step ${nextStep}: ${message.replace(/<[^>]+>/g, '')}`)
    
    // Jump to next step immediately
    workflowStep.value = nextStep
    
    // Execute callback if any
    if (onOk) onOk()
    
    // Show a transient notification instead of a blocking popup
    $q.notify({
        message: message,
        html: true,
        icon: 'info',
        color: 'blue-10',
        position: 'top',
        timeout: 1500
    })
}

// Global workflow watcher for transitions
watch([workflowStep, actualScaleValue, selectedReCode, selectedIntakeLotId], 
([step, val, re, lot]) => {
    
    // 1. If ingredient selected but no lot -> Scan (Step 2)
    if (re && !lot && step === 1) {
        workflowStep.value = 2
        openScanDialog() // Open the popup as requested
    }

    // 2. If lot is matched -> Ready (Step 3)
    if (re && lot && step === 2) {
        workflowStep.value = 3
    }
    
    // 3. At Step 3: handle scale state
    if (step === 3 && re && lot) {
        const isZero = Math.abs(val) <= 0.001
        if (!isZero) {
            // Scale NOT zero → show Tare popup so operator can tare
            // Close confirm popup if it was open (scale went back to non-zero)
            showConfirmStartPopup.value = false
            if (!showTarePopup.value) {
                openTarePopup()
            }
        } else {
            // Scale IS zero → close tare popup and show Confirm start popup
            if (showTarePopup.value) {
                showTarePopup.value = false
            }
            if (!showConfirmStartPopup.value) {
                showConfirmStartPopup.value = true
            }
        }
    }

    // 3b. At Step 4, if current scale reads 0 but another has weight → auto-switch
    if (step === 4 && re && Math.abs(val) < 0.01) {
        const scaleWithWeight = scalesComposable.scales.value.find(
            (s: any) => !s.isError && Math.abs(s.value) > 0.01
        )
        if (scaleWithWeight && scaleWithWeight.id !== scalesComposable.selectedScale.value) {
            scalesComposable.selectedScale.value = scaleWithWeight.id
        }
    }
    // 4. If at Step 7 and scale cleared -> confirm takeout
    if (step === 7) {
        const zeroThreshold = (activeScale.value?.tolerance || 0.01) * 2
        if (Math.abs(val) <= zeroThreshold) {
            handleStep7Confirm()
        }
    }

    // Protection: Keep state if re-code temporarily vanishes
    if (!re && step > 2 && step <= 7) return 
    
    if (!re && step !== 1) {
        workflowStep.value = 1
    }
})

watch(() => workflowStep.value, (step) => {
    if (step === 2 && !showScanDialog.value && !selectedIntakeLotId.value) {
        openScanDialog()
    }
})

// Sync workflow when selecting ingredient manually
watch([selectedReCode, selectedIntakeLotId], ([re, lot]) => {
    // If we are already in the middle of a procedure (Steps 3-7), 
    // do NOT let this sync-watcher push us back to 1/2 unless re is cleared.
    if (workflowStep.value >= 3 && re) return

    if (re && !lot) {
        workflowStep.value = 2
    } else if (re && lot && workflowStep.value < 3) {
        workflowStep.value = 3
    } else if (!re) {
        workflowStep.value = 1
    }
})

// ── Pre-Batch Summary Report ──────────────
const showPreBatchReportDialog = ref(false)
const prebatchReportFromDate = ref('')
const prebatchReportToDate = ref(new Date().toLocaleDateString('en-GB', { day: '2-digit', month: '2-digit', year: 'numeric' }))
const prebatchReportLoading = ref(false)

const formatDateToApi2 = (val: string) => {
  if (!val) return null
  const parts = val.split('/')
  if (parts.length === 3) return `${parts[2]}-${parts[1]}-${parts[0]}`
  return null
}

const printPreBatchReport = async () => {
  prebatchReportLoading.value = true
  const printWindow = window.open('', '_blank')
  if (!printWindow) { prebatchReportLoading.value = false; return }
  printWindow.document.write('<html><body><h2 style="font-family:sans-serif;color:#1565c0;">⏳ Loading...</h2></body></html>')
  try {
    let url = `${appConfig.apiBaseUrl}/reports/prebatch-summary`
    const p: string[] = []
    const f = formatDateToApi2(prebatchReportFromDate.value)
    const t2 = formatDateToApi2(prebatchReportToDate.value)
    if (f) p.push(`from_date=${f}`)
    if (t2) p.push(`to_date=${t2}`)
    if (p.length) url += '?' + p.join('&')
    const data = await $fetch<any>(url)
    const now = new Date().toLocaleString('en-GB')

    const recordRows = (data.records || []).map((r: any, i: number) => `
      <tr><td class="tc">${i+1}</td><td>${r.batch_record_id}</td><td>${r.plan_id || '-'}</td><td>${r.mat_sap_code || '-'}</td><td>${r.re_code || '-'}</td><td class="tr">${(r.net_volume || 0).toFixed(4)}</td><td class="tr">${(r.total_request_volume || 0).toFixed(4)}</td><td class="tc">${r.package_no || '-'}/${r.total_packages || '-'}</td><td class="tc">${r.created_at ? new Date(r.created_at).toLocaleString('en-GB') : '-'}</td></tr>
    `).join('')

    const ingredientRows = (data.ingredient_totals || []).map((ing: any, i: number) => `
      <tr><td class="tc">${i+1}</td><td class="tb">${ing.mat_sap_code || '-'}</td><td>${ing.re_code || '-'}</td><td class="tr">${(ing.total_net || 0).toFixed(4)}</td><td class="tr">${(ing.total_request || 0).toFixed(4)}</td><td class="tr">${((ing.total_net || 0) - (ing.total_request || 0)).toFixed(4)}</td><td class="tc">${ing.count}</td></tr>
    `).join('')

    const s = data.summary || {}
    const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><title>Pre-Batch Summary Report</title>
    <style>@page{size:A4 landscape;margin:8mm 10mm}*{box-sizing:border-box;margin:0;padding:0}body{font-family:'Courier Prime',monospace;font-size:13px;color:#222;line-height:1.4}.header{background:#1565c0;color:#fff;padding:14px 20px;display:flex;justify-content:space-between;align-items:center;border-radius:4px;margin-bottom:8px}.header h1{font-size:22px;margin:0}.info-bar{background:#e3f2fd;padding:8px 14px;border-radius:3px;margin-bottom:10px;font-size:13px;color:#1565c0;font-weight:bold}.section-title{background:#37474f;color:#fff;padding:8px 14px;font-size:14px;font-weight:bold;border-radius:3px;margin:12px 0 4px}table.dt{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed}table.dt th{background:#546e7a;color:#fff;padding:4px 8px;text-align:left;font-size:10px;text-transform:uppercase}table.dt td{padding:4px 8px;border-bottom:1px solid #e0e0e0;overflow:hidden;text-overflow:ellipsis}.grand{background:#1565c0;color:#fff;padding:12px 18px;border-radius:4px;font-size:14px;margin-top:10px;display:flex;justify-content:space-between}.footer{border-top:2px solid #1565c0;font-size:10px;color:#888;padding:6px 0;margin-top:10px;display:flex;justify-content:space-between}.tr{text-align:right}.tc{text-align:center}.tb{font-weight:bold}@media print{body{-webkit-print-color-adjust:exact;print-color-adjust:exact}}</style></head><body>
    <div class="header"><div><h1>🧪 Pre-Batch Summary Report</h1><div style="font-size:12px;margin-top:3px;opacity:.85">xMixing Control System</div></div><div style="font-size:12px;text-align:right;opacity:.9">Generated: ${now}</div></div>
    <div class="info-bar">📅 Period: ${prebatchReportFromDate.value || 'All'} — ${prebatchReportToDate.value || 'All'} | Total Records: ${s.total_records || 0} | Total Net: ${(s.total_net_volume || 0).toFixed(4)} kg</div>
    <div class="section-title">📋 Pre-Batch Records</div>
    <table class="dt"><thead><tr><th style="width:3%">#</th><th style="width:16%">Batch Record ID</th><th style="width:10%">Plan ID</th><th style="width:14%">Mat SAP Code</th><th style="width:8%">RE Code</th><th style="width:10%" class="tr">Net Vol (kg)</th><th style="width:10%" class="tr">Request (kg)</th><th style="width:8%" class="tc">Pkg</th><th style="width:12%" class="tc">Date</th></tr></thead>
    <tbody>${recordRows || '<tr><td colspan="9" class="tc">No records</td></tr>'}</tbody></table>
    <div class="section-title">📊 Ingredient Totals</div>
    <table class="dt"><thead><tr><th style="width:4%">#</th><th style="width:18%">Mat SAP Code</th><th style="width:10%">RE Code</th><th style="width:14%" class="tr">Total Net (kg)</th><th style="width:14%" class="tr">Total Request (kg)</th><th style="width:14%" class="tr">Variance (kg)</th><th style="width:8%" class="tc">Count</th></tr></thead>
    <tbody>${ingredientRows}</tbody></table>
    <div class="grand"><span>Total: ${s.total_records || 0} pre-batch records</span><span>Net Volume: ${(s.total_net_volume || 0).toFixed(4)} kg</span></div>
    <div class="footer"><span>xMixing 2025 | xMix.co.th</span><span>Pre-Batch Summary Report</span></div>
    </body></html>`
    printWindow.document.open(); printWindow.document.write(html); printWindow.document.close()
    showPreBatchReportDialog.value = false
  } catch (e) { console.error(e); printWindow.close(); $q.notify({ type: 'negative', message: 'Failed', position: 'top' }) }
  finally { prebatchReportLoading.value = false }
}

// ─── Lifecycle ───
onMounted(() => {
  fetchContainerSizes()
  fetchIngredients()
  fetchProductionPlans()
  fetchBatchIds()
  fetchInventory()
  fetchPreBatchRecords()
  fetchWarehouses()
  focusIntakeLotInput()
  connectMqtt()
})

// ── Rebatch ────────────────────────────────────
const showRebatchDialog = ref(false)
const rebatchRemark = ref('')
const rebatchReason = ref('')
const rebatchTarget = ref<any>(null)
const rebatchIng = ref<any>(null)

const rebatchReasonOptions = [
  'Weight out of tolerance',
  'Wrong ingredient',
  'Contamination / Foreign matter',
  'Equipment malfunction',
  'Wrong lot / batch used',
  'Other',
]

const rebatchFinalRemark = computed(() => {
  if (rebatchReason.value === 'Other') return rebatchRemark.value.trim()
  return rebatchReason.value
})

const onRebatchClick = (bd: any, ing: any) => {
  rebatchTarget.value = bd
  rebatchIng.value = ing
  rebatchReason.value = ''
  rebatchRemark.value = ''
  showRebatchDialog.value = true
}

const confirmRebatch = async () => {
  if (!rebatchFinalRemark.value) {
    $q.notify({ type: 'warning', message: 'Please select or enter a reason for rebatch.', position: 'top' })
    return
  }
  const bd = rebatchTarget.value
  if (!bd) return
  try {
    // Unpack the item (clears packing fields, restores inventory)
    await $fetch(`${appConfig.apiBaseUrl}/prebatch-items/${bd.req_id}/unpack`, {
      method: 'DELETE',
      headers: authHeader() as Record<string, string>,
    })
    $q.notify({ type: 'positive', message: `Rebatch: ${bd.batch_id} / ${rebatchIng.value?.re_code} — ready for re-weighing.`, position: 'top' })
    showRebatchDialog.value = false
    // Refresh data
    const plan = productionPlans.value.find((p: any) => p.plan_id === selectedProductionPlan.value)
    if (plan) await onPlanShow(plan)
    if (rebatchIng.value) {
      await ingredientsComposable.fetchIngredientBatchDetail(rebatchIng.value.re_code)
    }
    await fetchPreBatchRecords()
  } catch (err) {
    console.error('Rebatch error:', err)
    $q.notify({ type: 'negative', message: 'Rebatch failed. Try again.', position: 'top' })
  }
}

// ── Scan Prebatch Dialog (Workflow Controller) ──
const playSound = async (type: 'correct' | 'wrong') => {
  try {
    const ctx = new (window.AudioContext || (window as any).webkitAudioContext)()
    await ctx.resume()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    if (type === 'correct') {
      osc.frequency.value = 880
      osc.type = 'sine'
      gain.gain.value = 0.1
      osc.start()
      setTimeout(() => { osc.frequency.value = 1320 }, 100)
      setTimeout(() => { osc.stop(); ctx.close() }, 280)
    } else {
      osc.frequency.value = 200
      osc.type = 'square'
      gain.gain.value = 0.1
      osc.start()
      setTimeout(() => { osc.frequency.value = 150 }, 150)
      setTimeout(() => { osc.stop(); ctx.close() }, 400)
    }
  } catch (e) {
    console.warn('Sound playback failed:', e)
  }
}

const showScanDialog = ref(false)
const mainLotInputRef = ref<any>(null)
const scanDialogItems = ref<any[]>([])

// --- Container Setup Dialog (after scan, before weighing) ---
const showContainerSetupDialog = ref(false)
const setupContainerSize = ref(0)
const setupSelectedScale = ref(0)
const setupMatchedIngredient = ref('')
const setupMatchedLot = ref('')
const setupPendingItem = ref<any>(null)

// --- Scan Full Lot Dialog ---
const showScanFullLotDialog = ref(false)
const scanFullLotPackageVol = ref(0)
const scanFullLotInput = ref('')
const scanFullLotScanned = ref<{ lot_id: string; volume: number; status: string; pkg_no: number }[]>([])
const scanFullLotProcessing = ref(false)

const scanFullLotCalc = computed(() => {
  const required = remainVolume.value
  const pkgVol = scanFullLotPackageVol.value
  if (pkgVol <= 0 || required <= 0) return { fullPacks: 0, remainder: 0, totalFullVol: 0 }
  const fullPacks = Math.floor(required / pkgVol)
  const totalFullVol = fullPacks * pkgVol
  const remainder = required - totalFullVol
  return { fullPacks, remainder: Math.round(remainder * 10000) / 10000, totalFullVol }
})

const scanFullLotRemaining = computed(() => {
  const scannedVol = scanFullLotScanned.value.reduce((s, o) => s + o.volume, 0)
  return Math.max(0, scanFullLotCalc.value.totalFullVol - scannedVol)
})

const openScanFullLotDialog = () => {
  scanFullLotPackageVol.value = packageSize.value || containerSize.value || 0
  scanFullLotInput.value = ''
  scanFullLotScanned.value = []
  showScanFullLotDialog.value = true
}

const onScanFullLotEnter = async () => {
  const lotId = scanFullLotInput.value.trim()
  scanFullLotInput.value = ''
  if (!lotId || scanFullLotProcessing.value) return

  // Check if already scanned
  if (scanFullLotScanned.value.some(s => s.lot_id === lotId)) {
    $q.notify({ type: 'warning', message: `Lot ${lotId} already scanned`, position: 'top' })
    return
  }

  // Check if enough full packs already scanned
  if (scanFullLotScanned.value.length >= scanFullLotCalc.value.fullPacks) {
    $q.notify({ type: 'warning', message: 'All full packs already scanned!', position: 'top' })
    return
  }

  scanFullLotProcessing.value = true
  try {
    // Validate lot exists in inventory for this ingredient
    const inv = inventoryRows.value.find((r: any) => 
      r.intake_lot_id?.trim().toUpperCase() === lotId.toUpperCase() && 
      r.re_code === selectedReCode.value
    )
    if (!inv) {
      $q.notify({ type: 'negative', message: `Lot ${lotId} not found in inventory for ${selectedReCode.value}`, position: 'top' })
      scanFullLotProcessing.value = false
      return
    }

    const pkgVol = scanFullLotPackageVol.value
    const pkgNo = (completedCount.value || 0) + scanFullLotScanned.value.length + 1
    const totalPkgs = scanFullLotCalc.value.fullPacks + (scanFullLotCalc.value.remainder > 0 ? 1 : 0)
    
    // Build batch_record_id
    const batchId = selectedBatch.value?.batch_id || ''
    const batchRecordId = `${batchId}-${selectedReCode.value}-${pkgNo}`

    // Save to API (pack item)
    const reqItem = prebatchItems.value.find((it: any) => 
      it.batch_id === batchId && it.re_code === selectedReCode.value
    )
    if (!reqItem) {
      $q.notify({ type: 'negative', message: 'PreBatch item not found', position: 'top' })
      scanFullLotProcessing.value = false
      return
    }

    await $fetch(`${appConfig.apiBaseUrl}/prebatch-items/${reqItem.id}/pack`, {
      method: 'PUT',
      headers: authHeader() as Record<string, string>,
      body: {
        batch_record_id: batchRecordId,
        package_no: pkgNo,
        total_packages: totalPkgs,
        net_volume: pkgVol,
        intake_lot_id: lotId,
        mat_sap_code: inv.mat_sap_code || '',
        recode_batch_id: String(pkgNo),
        origins: [{ intake_lot_id: lotId, mat_sap_code: inv.mat_sap_code || '', take_volume: pkgVol }],
      }
    })

    scanFullLotScanned.value.push({ lot_id: lotId, volume: pkgVol, status: 'ok', pkg_no: pkgNo })

    // Print label
    try {
      const ing = ingredients.value.find((i: any) => i.re_code === selectedReCode.value)
      const labelData = buildLabelData({
        batch: selectedBatch.value,
        planId: selectedProductionPlan.value,
        plan: selectedPlanDetails.value,
        reCode: selectedReCode.value,
        ingName: ing?.ingredient_name || ing?.name || selectedReCode.value,
        matSapCode: inv.mat_sap_code || '-',
        containerType: ing?.package_container_type || 'Bag',
        netVol: pkgVol,
        totalVol: requireVolume.value,
        pkgNo: pkgNo,
        totalPkgs: totalPkgs,
        qrCode: JSON.stringify({ b: batchId, m: inv.mat_sap_code || '', p: `${pkgNo}/${totalPkgs}`, n: pkgVol, t: requireVolume.value }),
        timestamp: new Date().toLocaleString('en-GB'),
        origins: [{ intake_lot_id: lotId, mat_sap_code: inv.mat_sap_code || '', take_volume: pkgVol }],
      })
      const svgContent = await generateLabelSvg('prebatch-label_4x3', labelData)
      if (svgContent) await printLabel(svgContent)
    } catch (e) {
      console.warn('Label print failed:', e)
    }

    // Refresh data
    await fetchPreBatchRecords()
    await fetchPrebatchItems(batchId)

    $q.notify({ type: 'positive', message: `Pkg #${pkgNo}: ${lotId} — ${pkgVol} kg ✓`, position: 'top', timeout: 2000 })

    // Auto-close when all full packs scanned
    if (scanFullLotScanned.value.length >= scanFullLotCalc.value.fullPacks) {
      setTimeout(() => {
        showScanFullLotDialog.value = false
        if (scanFullLotCalc.value.remainder > 0) {
          $q.notify({ 
            type: 'info', 
            message: `All full lots scanned! Remaining ${scanFullLotCalc.value.remainder} kg — weigh on scale`,
            position: 'top', timeout: 4000 
          })
        } else {
          $q.notify({ type: 'positive', message: 'All packages complete!', position: 'top' })
        }
      }, 500)
    }
  } catch (err: any) {
    console.error('Scan Full Lot error:', err)
    $q.notify({ type: 'negative', message: err?.data?.detail || 'Failed to save package', position: 'top' })
  }
  scanFullLotProcessing.value = false
}

// --- Production plan pagination ---
const planPage = ref(1)
const planPerPage = 5
const paginatedPlans = computed(() => {
  const start = (planPage.value - 1) * planPerPage
  return plansWithBatches.value.slice(start, start + planPerPage)
})
const planTotalPages = computed(() => Math.ceil(plansWithBatches.value.length / planPerPage) || 1)

// Reset plan page when filters change
watch([searchPlanId, searchSkuName], () => { planPage.value = 1 })

// --- Ingredient pagination ---
const ingredientPage = ref(1)
const ingredientPerPage = 5
const paginatedIngredients = computed(() => {
  const start = (ingredientPage.value - 1) * ingredientPerPage
  return selectableIngredients.value.slice(start, start + ingredientPerPage)
})
const ingredientTotalPages = computed(() => Math.ceil(selectableIngredients.value.length / ingredientPerPage) || 1)

// --- FIFO Violation Dialog ---
const showFifoViolationDialog = ref(false)
const fifoViolationScannedLot = ref('')
const fifoViolationExpectedLot = ref('')
const fifoViolationExpectedExpiry = ref('')
const fifoViolationScannedExpiry = ref('')
const setupCalcPackages = computed(() => {
  if (setupContainerSize.value <= 0 || requireVolume.value <= 0) return 0
  return Math.ceil(requireVolume.value / setupContainerSize.value)
})

// Auto-update scale recommendation when container size changes in setup dialog
watch(setupContainerSize, (newSize) => {
  if (!showContainerSetupDialog.value || newSize <= 0) return
  const sorted = [...scalesComposable.scales.value]
      .filter(s => !s.isError)
      .sort((a, b) => getScaleCapacity(a) - getScaleCapacity(b))
  const best = sorted.find(s => getScaleCapacity(s) >= newSize) || sorted[sorted.length - 1]
  if (best) setupSelectedScale.value = best.id
})
const confirmContainerSetup = () => {
  if (setupContainerSize.value <= 0 || !setupPendingItem.value) return
  containerSize.value = setupContainerSize.value
  packageSize.value = setupContainerSize.value
  // Apply selected scale
  if (setupSelectedScale.value) {
    scalesComposable.selectedScale.value = setupSelectedScale.value
  }
  showContainerSetupDialog.value = false
  
  // Now proceed to weighing with the pending item
  const item = setupPendingItem.value
  onBatchIngredientClick(
    { batch_id: item.batch_id },
    { re_code: selectedReCode.value, id: item.req_id, required_volume: item.required_volume, status: item.status },
    selectedPlanDetails.value
  )
  
  // Advance workflow
  if (workflowStep.value < 3) {
    workflowStep.value = 3
  }
  $q.notify({ type: 'info', message: `Weighing: ${item.batch_id}`, position: 'top', timeout: 2000 })
  setupPendingItem.value = null

  // Show tare popup after dialog closes (if scale is at zero)
  setTimeout(() => {
    const zeroThreshold = (activeScale.value?.tolerance || 0.01) * 2
    if (workflowStep.value === 3 && Math.abs(actualScaleValue.value) <= zeroThreshold) {
      openTarePopup()
    }
  }, 500)
}
const scanDialogLoading = ref(false)
const scanLotInput = ref('')
const scanLotValidated = ref(false)
const scanLotError = ref('')
const dialogScanInputRef = ref<any>(null)

// ─── Auto-focus scan input: always keep focus on the scan field ───
let scanFocusInterval: ReturnType<typeof setInterval> | null = null

const startScanFocusInterval = () => {
  if (scanFocusInterval) return
  scanFocusInterval = setInterval(() => {
    // Priority 1: Dialog scan input (when dialog is open)
    if (showScanDialog.value && dialogScanInputRef.value) {
      dialogScanInputRef.value.focus()
      return
    }
    // Priority 2: Main page scan input (when at workflow step 2)
    if (workflowStep.value === 2 && mainLotInputRef.value) {
      mainLotInputRef.value.focus()
    }
  }, 500)
}

const stopScanFocusInterval = () => {
  if (scanFocusInterval) {
    clearInterval(scanFocusInterval)
    scanFocusInterval = null
  }
}

// Start/stop the focus interval based on dialog or workflow step
watch([showScanDialog, workflowStep], ([dialogOpen, step]) => {
  if (dialogOpen || step === 2) {
    startScanFocusInterval()
  } else {
    stopScanFocusInterval()
  }
}, { immediate: true })

onBeforeUnmount(() => {
  stopScanFocusInterval()
})

const handleScanError = (msg: string) => {
  scanLotError.value = msg
  scanLotValidated.value = false
  playSound('wrong')
  // Wait 2 sec then clear
  setTimeout(() => {
    scanLotInput.value = ''
    scanLotError.value = ''
  }, 2000)
}

// Current ingredient info for the dialog header
const scanDialogIngInfo = computed(() => {
  if (!selectedReCode.value) return null
  const ing = ingredients.value.find((i: any) => i.re_code === selectedReCode.value)
  const selIng = selectableIngredients.value.find((i: any) => i.re_code === selectedReCode.value)
  return {
    re_code: selectedReCode.value,
    ingredient_name: selIng?.ingredient_name || ing?.name || selectedReCode.value,
    mat_sap_code: ing?.mat_sap_code || '-',
    total_require: selIng?.batch_require || requireVolume.value || 0,
  }
})

// Group items by plan → batch → packs tree
const scanDialogTree = computed(() => {
  const grouped: Record<string, { plan_id: string; items: any[] }> = {}
  for (const item of scanDialogItems.value) {
    const pid = item.plan_id || '-'
    if (!grouped[pid]) grouped[pid] = { plan_id: pid, items: [] }
    grouped[pid].items.push(item)
  }
  return Object.values(grouped)
})

// --- Scan dialog batch pagination (5 per page) ---
const scanDialogBatchPage = ref<Record<string, number>>({})
const scanDialogBatchPerPage = 5
const getScanDialogPage = (planId: string) => scanDialogBatchPage.value[planId] || 1
const getScanDialogTotalPages = (items: any[]) => Math.ceil(items.length / scanDialogBatchPerPage) || 1
const getPaginatedScanItems = (planId: string, items: any[]) => {
  const page = getScanDialogPage(planId)
  const start = (page - 1) * scanDialogBatchPerPage
  return items.slice(start, start + scanDialogBatchPerPage)
}
const setScanDialogPage = (planId: string, page: number) => {
  scanDialogBatchPage.value = { ...scanDialogBatchPage.value, [planId]: page }
}

// Next pending item
const nextPendingItem = computed(() => {
  return scanDialogItems.value.find((item: any) => item.status !== 2)
})

// Count of completed / total
const scanProgress = computed(() => {
  const total = scanDialogItems.value.length
  const done = scanDialogItems.value.filter((i: any) => i.status === 2).length
  return { done, total }
})

// Recommended FIFO lot (first expiry, active, has stock)
const fifoRecommendedLot = computed(() => {
  if (filteredInventory.value.length === 0) return null
  return filteredInventory.value[0] // Already sorted by expire_date ASC
})

/**
 * Fetch all batches for the current ingredient to show in scan/progress dialog
 */
const fetchScanDialogItems = async () => {
  if (!selectedReCode.value || !selectedProductionPlan.value) return
  scanDialogLoading.value = true
  try {
    const data = await $fetch<any[]>(
      `${appConfig.apiBaseUrl}/prebatch-items/batches-by-ingredient/${selectedProductionPlan.value}/${encodeURIComponent(selectedReCode.value)}`,
      { headers: authHeader() as Record<string, string> }
    )
    scanDialogItems.value = data
  } catch (err) {
    console.error('Scan dialog fetch error:', err)
    scanDialogItems.value = []
  } finally {
    scanDialogLoading.value = false
  }
}

/**
 * Start PreBatch from Plan list — select plan, open scan dialog (no ingredient pre-selected)
 * Operator scans intake lot → system identifies ingredient → validates → starts weighing
 */
const startPreBatch = async (plan: any) => {
  // 1. Select the plan (triggers ingredient loading)
  await onPlanShow(plan)
  await nextTick()

  // 2. Open scan dialog WITHOUT pre-selecting ingredient
  selectedReCode.value = ''
  selectedIntakeLotId.value = ''
  scanLotInput.value = ''
  scanLotValidated.value = false
  scanLotError.value = ''
  scanDialogItems.value = []
  showScanDialog.value = true
}

/**
 * Step 1: Click ingredient → open scan dialog
 */
const openScanDialog = async (ing?: any) => {
  // 1. If an ingredient is passed, select it first
  if (ing) {
    // Manual click on ingredient row -> Reset Lot ID for new scan as per "until next Click" requirement
    if (selectedIntakeLotId.value) {
      console.log('🔄 Manual ingredient selection. Clearing lot for fresh scan.')
      selectedIntakeLotId.value = ''
    }
    
    selectedReCode.value = ing.re_code
    ingredientsComposable.onSelectIngredient(ing)
  }

  // 2. Pre-fetch items to know what's next
  await fetchScanDialogItems()

  // 3. SHOW DIALOG: Always show popup as requested in Step 2
  scanLotInput.value = ''
  scanLotValidated.value = false
  scanLotError.value = ''
  showScanDialog.value = true
}

/**
 * Step 3: Scan intake lot label → validate
 * Accepts only intake labels like "LB-26-004205"
 * Checks FIFO (first expiry, active lot)
 */
// Auto-process scanner input aggressively
watch(scanLotInput, (newVal) => {
  if (!newVal || scanLotValidated.value) return
  
  // Auto-trigger scan validation when barcode input is detected:
  // 1. Has at least 2 delimited segments (pipe or comma): e.g. "intake-2026-02-21-001,9/19"
  // 2. Or starts with 'intake-' (intake lot label)
  const hasDelim = newVal.includes('|') || newVal.includes(',')
  if (hasDelim) {
    const segCount = newVal.includes('|') ? newVal.split('|').length : newVal.split(',').length
    if (segCount >= 2) {
      onScanLotEnter()
    }
  }
})

const onScanLotEnter = async () => {
  const scannedValue = scanLotInput.value.trim()
  if (!scannedValue || scanLotValidated.value) return

  console.log('--- SCAN-FIRST WORKFLOW ---')
  console.log('1. Raw Input:', scannedValue)
  
  // Support both pipe '|' and comma ',' delimited barcodes
  const delimiter = scannedValue.includes('|') ? '|' : ','
  const rawParts = scannedValue.split(delimiter).map(p => p.trim())
  const parts = rawParts.filter(p => p.length > 0)
  console.log('2. Parsed Parts (delim=' + delimiter + '):', parts)

  // Basic format check — need at least 2 segments
  if (parts.length < 2) return

  // --- SCAN-FIRST: Search ALL inventory for this lot ---
  let matchedLot: any = null

  // Priority 1: Match by Lot ID or Supplier Lot ID across ALL inventory
  for (const part of parts) {
    const pUpper = part.toUpperCase()
    matchedLot = inventoryRows.value.find(inv => 
      inv.remain_vol > 0 && inv.status === 'Active' &&
      ((inv.intake_lot_id?.trim().toUpperCase() === pUpper) || 
       (inv.lot_id?.trim().toUpperCase() === pUpper))
    )
    if (matchedLot) {
      console.log('✅ Found lot match:', part, '→ re_code:', matchedLot.re_code)
      break
    }
  }

  // Priority 2: Fallback by date matching
  if (!matchedLot) {
    const scanDates = parts.filter(p => /^\d{1,2}\/\d{1,2}\/\d{4}$/.test(p))
    if (scanDates.length > 0) {
      matchedLot = inventoryRows.value.find(inv => 
        inv.remain_vol > 0 && inv.status === 'Active' &&
        scanDates.includes(formatDate(inv.expire_date))
      )
      if (matchedLot) console.log('✅ Fallback match by date → re_code:', matchedLot.re_code)
    }
  }

  if (!matchedLot) {
    console.error('❌ NO MATCH FOUND in inventory')
    if (parts.length >= 2) {
      handleScanError('Lot not found in inventory. Check if the lot has been received.')
    }
    return
  }

  // --- VALIDATE CONDITION 1: Is this ingredient in the plan? ---
  const lotReCode = (matchedLot.re_code || '').trim().toUpperCase()
  const lotSapCode = (matchedLot.mat_sap_code || '').trim().toUpperCase()
  const matchedIngredient = selectableIngredients.value.find((ing: any) => {
    const ingRe = (ing.re_code || '').trim().toUpperCase()
    const ingSap = (ing.mat_sap_code || '').trim().toUpperCase()
    return ingRe === lotReCode || (lotSapCode && ingSap === lotSapCode)
  })

  if (!matchedIngredient) {
    handleScanError(`Ingredient "${matchedLot.re_code}" is NOT required for this production plan.`)
    return
  }

  // If already weighing (Step 4 = next lot mode), validate same ingredient
  const isNextLotMode = workflowStep.value === 4 && selectedReCode.value
  if (isNextLotMode && matchedIngredient.re_code !== selectedReCode.value) {
    handleScanError(`Wrong ingredient! Expected: ${selectedReCode.value}, Scanned: ${matchedIngredient.re_code}`)
    return
  }

  if (!isNextLotMode && matchedIngredient.status === 2) {
    handleScanError(`Ingredient "${matchedLot.re_code}" is already completed for this plan.`)
    return
  }

  // --- Auto-select the identified ingredient (skip if already selected in next-lot mode) ---
  if (!isNextLotMode) {
    selectedReCode.value = matchedIngredient.re_code
    ingredientsComposable.onSelectIngredient(matchedIngredient)
    await nextTick()
  }

  // --- VALIDATE CONDITION 2: FIFO check ---
  const lotId = matchedLot.intake_lot_id
  if (matchedLot.status === 'Inactive' || matchedLot.status === 'Hold') {
    handleScanError(`Lot ${lotId} is ${matchedLot.status}.`)
    return
  }

  // Get FIFO lots for this ingredient (exclude already-used lots in current package)
  const usedLotIds = currentPackageOrigins.value.map(o => o.intake_lot_id.trim().toUpperCase())
  const allLotsForIng = inventoryRows.value.filter(inv => {
    const reMatch = (inv.re_code || '').trim().toUpperCase() === lotReCode
    return reMatch && inv.remain_vol > 0 && inv.status === 'Active'
  })
  const fifoLots = allLotsForIng
    .filter(inv => !usedLotIds.includes((inv.intake_lot_id || '').trim().toUpperCase()))
    .sort((a, b) => {
      const dateA = parseDateSafe(a.expire_date)?.getTime() ?? Infinity
      const dateB = parseDateSafe(b.expire_date)?.getTime() ?? Infinity
      if (dateA !== dateB) return dateA - dateB
      // Same expire date → sort by intake_at (earlier intake first)
      const intakeA = parseDateSafe((a as any).intake_at)?.getTime() ?? Infinity
      const intakeB = parseDateSafe((b as any).intake_at)?.getTime() ?? Infinity
      if (intakeA !== intakeB) return intakeA - intakeB
      return (a.intake_lot_id || '').localeCompare(b.intake_lot_id || '')
    })

  console.log('🔍 FIFO DEBUG:', {
    scannedLot: lotId,
    lotReCode,
    allLotsCount: allLotsForIng.length,
    fifoLotsCount: fifoLots.length,
    fifoLots: fifoLots.map(l => ({ lot: l.intake_lot_id, expire: l.expire_date, expParsed: parseDateSafe(l.expire_date)?.toISOString(), intake_at: (l as any).intake_at })),
    fifoFirst: fifoLots[0]?.intake_lot_id,
    wouldViolate: fifoLots.length > 0 && lotId.trim().toUpperCase() !== fifoLots[0]?.intake_lot_id.trim().toUpperCase()
  })

  if (fifoLots.length > 0) {
    const fifoFirst = fifoLots[0]!
    if (lotId.trim().toUpperCase() !== fifoFirst.intake_lot_id.trim().toUpperCase()) {
      // Show FIFO violation popup
      fifoViolationScannedLot.value = lotId
      fifoViolationScannedExpiry.value = formatDate(matchedLot.expire_date)
      fifoViolationExpectedLot.value = fifoFirst.intake_lot_id
      fifoViolationExpectedExpiry.value = formatDate(fifoFirst.expire_date)
      showFifoViolationDialog.value = true
      playSound('wrong')
      scanLotInput.value = ''
      scanLotValidated.value = false
      // Auto-close after 5 seconds
      setTimeout(() => { showFifoViolationDialog.value = false }, 5000)
      return
    }
  }

  // --- SUCCESS ---
  console.log('--- SCAN VERIFIED ---', { re_code: matchedIngredient.re_code, lot: lotId, isNextLot: isNextLotMode })
  scanLotError.value = ''
  scanLotValidated.value = true
  selectedIntakeLotId.value = lotId
  selectedInventoryItem.value = [matchedLot] as any

  playSound('correct')
  const msg = isNextLotMode 
    ? `✅ Next lot: ${lotId} — continue weighing`
    : `✅ ${matchedIngredient.re_code} → Lot: ${lotId}`
  $q.notify({ type: 'positive', message: msg, position: 'top', timeout: 1500 })

  if (isNextLotMode) {
    // Next lot mode: close scan dialog, return to weighing (Step 4 already active)
    showScanDialog.value = false
    return
  }

  // First lot: fetch batch items and auto-advance to weighing
  console.log('📦 FETCH scanDialogItems: plan=', selectedProductionPlan.value, 're_code=', selectedReCode.value)
  await fetchScanDialogItems()
  console.log('📦 scanDialogItems:', JSON.stringify(scanDialogItems.value))

  // Auto-advance to weighing
  const pending = nextPendingItem.value
  console.log('📦 nextPendingItem:', pending, 'workflowStep:', workflowStep.value)
  if (pending) {
    setTimeout(() => {
      console.log('📦 AUTO-SELECT pending item:', pending.batch_id, 'req_id:', pending.req_id)
      onScanItemSelect(pending)
    }, 400)
  } else {
    console.warn('⚠️ No pending item found — cannot auto-advance!')
  }
}

/**
 * Step 4+5: Select item → close dialog → start weighing
 */
const onScanItemSelect = (item: any) => {
  if (item.status === 2) return
  
  // Close scan dialog
  showScanDialog.value = false
  
  // Set requireVolume so the setup dialog can calculate packages
  requireVolume.value = item.required_volume || 0
  
  // Look up std_package_size from ingredient config
  const ingInfo = selectableIngredients.value.find((i: any) => i.re_code === selectedReCode.value)
  const stdSize = ingInfo?.std_package_size || 0
  
  // Show container setup dialog with matched ingredient info
  setupMatchedIngredient.value = ingInfo?.ingredient_name || selectedReCode.value
  setupMatchedLot.value = selectedIntakeLotId.value
  setupPendingItem.value = item
  setupContainerSize.value = stdSize > 0 ? Math.min(item.required_volume, stdSize) : item.required_volume
  // Auto-select best scale for this container size
  const target = setupContainerSize.value || item.required_volume || 0
  const sorted = [...scalesComposable.scales.value]
      .filter(s => !s.isError)
      .sort((a, b) => getScaleCapacity(a) - getScaleCapacity(b))
  const best = sorted.find(s => getScaleCapacity(s) >= target) || sorted[sorted.length - 1]
  setupSelectedScale.value = best?.id || scalesComposable.scales.value[0]?.id || 0
  showContainerSetupDialog.value = true
}


/**
 * Step 7: After label print → reopen scan dialog for next batch
 * Called from onPrintLabel after a successful save
 */
const reopenScanDialogAfterPrint = () => {
  setTimeout(() => {
    if (selectedReCode.value) {
      openScanDialog()
    }
  }, 500)
}

const refreshPlanData = async () => {
    if (selectedProductionPlan.value) {
        $q.notify({ type: 'info', message: 'Refreshing data...', position: 'top', timeout: 500 })
        await fetchPrebatchItems(selectedProductionPlan.value)
        if (selectedReCode.value) {
            await fetchIngredientBatchDetail(selectedReCode.value)
        }
        await fetchPreBatchRecords()
    }
}
</script>
<template>
  <q-page class="q-pa-md bg-white">
    <!-- Page Header -->
    <div class="bg-blue-9 text-white q-pa-md rounded-borders q-mb-sm shadow-2">
      <div class="row justify-between items-center">
        <div class="row items-center q-gutter-md">
          <div class="row items-center q-gutter-sm">
            <q-icon name="science" size="sm" />
            <div class="text-h6 text-weight-bolder">{{ t('preBatch.title') }}</div>
          </div>
          <div class="row items-center no-wrap bg-blue-10 q-px-md q-py-xs rounded-borders shadow-1">
            <div class="text-subtitle2 text-weight-bold q-mr-md">Select Production Plan:</div>
            <q-select
              v-model="planFilter"
              :options="productionPlanOptions"
              dense
              filled
              square
              emit-value
              map-options
              bg-color="blue-1"
              label-color="blue-9"
              style="min-width: 250px;"
              popup-content-class="bg-blue-1"
            >
              <template v-slot:prepend>
                <q-icon name="filter_alt" size="xs" color="blue-9" />
              </template>
            </q-select>
          </div>
          <!-- Department Filter -->
          <div class="row items-center no-wrap bg-blue-10 q-px-sm q-py-xs rounded-borders shadow-1">
            <q-icon name="warehouse" size="xs" class="q-mr-xs" />
            <q-btn-toggle
              v-model="selectedWarehouse"
              toggle-color="white"
              toggle-text-color="blue-9"
              text-color="blue-2"
              color="blue-10"
              dense
              no-caps
              unelevated
              :options="[
                { label: 'ALL', value: 'All' },
                { label: 'FH', value: 'FH' },
                { label: 'SPP', value: 'SPP' },
              ]"
              class="text-weight-bold"
              style="font-size: 0.8rem;"
            />
          </div>
        </div>
        <div class="row items-center q-gutter-sm">
          <q-btn flat round dense icon="assessment" text-color="white" @click="showPreBatchReportDialog = true">
            <q-tooltip>Pre-Batch Summary Report</q-tooltip>
          </q-btn>
          <div class="text-caption text-blue-2">{{ t('prodPlan.version') }} 0.2</div>
        </div>
      </div>
    </div>

    <div class="row q-col-gutter-lg">
      <!-- LEFT SIDEBAR -->
      <div class="col-12 col-md-4 column q-gutter-y-sm" style="height: calc(100vh - 140px);">

        <!-- CARD 1: Production Plans with expandable Batches -->
        <q-card class="bg-white shadow-2 column" style="flex-shrink: 0;">
          <q-card-section class="bg-blue-9 text-white q-py-xs">
            <div class="row items-center justify-between no-wrap q-gutter-x-sm">
              <div class="row items-center no-wrap">
                <q-icon name="assignment" size="sm" class="q-mr-xs" />
                <div class="text-subtitle2 text-weight-bold">{{ t('prodPlan.productionPlan') }}</div>
              </div>
              <q-badge color="white" text-color="blue-9" class="text-weight-bold">
                {{ filteredProductionPlans.length }} Plans Found
              </q-badge>
            </div>
          </q-card-section>

          <!-- Search Filters -->
          <q-card-section class="q-py-xs bg-grey-2 border-bottom">
            <div class="row q-col-gutter-xs">
              <div class="col-6">
                <q-input 
                  v-model="searchPlanId" 
                  dense 
                  outlined 
                  square
                  bg-color="white"
                  placeholder="Filter Plan ID..."
                >
                  <template v-slot:prepend>
                    <q-icon name="search" size="xs" color="grey-6" />
                  </template>
                </q-input>
              </div>
              <div class="col-6">
                <q-input 
                  v-model="searchSkuName" 
                  dense 
                  outlined 
                  square
                  bg-color="white"
                  placeholder="Filter Name/SKU..."
                >
                   <template v-slot:prepend>
                    <q-icon name="search" size="xs" color="grey-6" />
                  </template>
                </q-input>
              </div>
            </div>
          </q-card-section>
          <div class="relative-position">
              <template v-if="plansWithBatches.length > 0">
                <q-list dense separator class="text-caption">
                  <template v-for="plan in paginatedPlans" :key="plan.plan_id">
                    <q-item
                      clickable
                      v-ripple
                      :active="selectedProductionPlan === plan.plan_id"
                      active-class="bg-blue-1 text-blue-9 text-weight-bold"
                      :class="selectedProductionPlan !== plan.plan_id ? 'text-weight-bold bg-blue-grey-1 text-blue-grey-9' : ''"
                      @click="onPlanShow(plan)"
                    >
                      <q-item-section avatar style="min-width: 24px;">
                        <q-icon 
                          :name="selectedProductionPlan === plan.plan_id ? 'radio_button_checked' : 'radio_button_unchecked'" 
                          :color="selectedProductionPlan === plan.plan_id ? 'blue-9' : 'grey-5'"
                          size="xs" 
                        />
                      </q-item-section>
                      <q-item-section>
                        <q-item-label>{{ plan.sku_id }} - {{ plan.sku_name || 'No Name' }}</q-item-label>
                        <q-item-label caption>Plan: {{ plan.plan_id }} ({{ plan.batches.length }} batches)</q-item-label>
                      </q-item-section>
                      <q-item-section side>
                        <q-btn 
                          flat dense 
                          icon="play_circle" 
                          label="Start" 
                          size="xs" 
                          color="green-9" 
                          class="text-weight-bold"
                          @click.stop="startPreBatch(plan)"
                        >
                          <q-tooltip>Start Pre-Batch for this plan</q-tooltip>
                        </q-btn>
                      </q-item-section>
                    </q-item>
                  </template>
                </q-list>
                <!-- Pagination controls -->
                <div v-if="planTotalPages > 1" class="row items-center justify-center q-py-xs q-gutter-x-xs bg-grey-1" style="border-top: 1px solid #e0e0e0;">
                  <q-btn flat dense round icon="chevron_left" size="xs" color="blue-9" :disable="planPage <= 1" @click="planPage--" />
                  <span class="text-caption text-grey-8">{{ planPage }} / {{ planTotalPages }}</span>
                  <q-btn flat dense round icon="chevron_right" size="xs" color="blue-9" :disable="planPage >= planTotalPages" @click="planPage++" />
                </div>
              </template>
              <div v-else class="text-center q-pa-md text-grey">
                <q-icon name="inbox" size="lg" class="q-mb-sm" /><br>
                No active production plans matching selection
              </div>
          </div>
        </q-card>


        <!-- CARD 2: Ingredients for Selected Plan -->
        <q-card class="col bg-white shadow-2 column" style="min-height: 0;">
            <q-card-section class="bg-blue-grey-2 q-py-xs">
                <div class="row items-center justify-between no-wrap">
                    <div class="text-subtitle2 text-weight-bold text-blue-grey-8 row items-center no-wrap">
                        {{ t('preBatch.requireIngredient') }}
                        <!-- Warehouse filter hidden for SPP -->
                        <!--
                        <q-select
                            v-model="selectedWarehouse"
                            :options="warehouses"
                            dense
                            filled
                            square
                            emit-value
                            map-options
                            option-value="warehouse_id"
                            option-label="name"
                            bg-color="white"
                            label-color="blue-grey-8"
                            class="q-ml-md"
                            style="min-width: 120px;"
                        >
                            <template v-slot:prepend>
                                <q-icon name="filter_list" size="xs" color="blue-grey-6" />
                            </template>
                        </q-select>
                        -->
                    </div>
                    <div class="row items-center no-wrap">
                        <q-badge color="blue-grey-6" text-color="white" class="text-weight-bold">
                            {{ selectableIngredients.length }} {{ t('preBatch.items') }}
                        </q-badge>
                        <q-btn 
                            v-if="selectableIngredients.length > 0" 
                            flat round dense 
                            icon="refresh" 
                            size="sm" 
                            color="blue-grey-8" 
                            class="q-ml-xs" 
                            @click="refreshPlanData"
                        >
                            <q-tooltip>Refresh Data</q-tooltip>
                        </q-btn>
                        <q-btn 
                            v-if="selectableIngredients.length > 0" 
                            flat round dense 
                            icon="print" 
                            size="sm" 
                            color="blue-grey-8" 
                            class="q-ml-sm" 
                            @click="printGlobalPlanLabels"
                        >
                            <q-tooltip>Print All Labels for this Plan</q-tooltip>
                        </q-btn>
                    </div>
                </div>
            </q-card-section>
            <div class="col relative-position" style="overflow-y: auto;">
                <q-markup-table dense flat square separator="cell" sticky-header>
                    <thead class="bg-orange-1 text-orange-10">
                        <tr>
                            <th class="text-center" style="width: 30px"></th>
                            <th class="text-left" style="font-size: 0.7rem;">RE-Code</th>
                            <th class="text-center" style="font-size: 0.7rem;">Container</th>
                            <th class="text-right" style="font-size: 0.7rem;">Require</th>
                            <th class="text-right" style="font-size: 0.7rem;">Packaged</th>
                            <th class="text-center" style="font-size: 0.7rem;">{{ t('common.status') }}</th>
                            <th class="text-center" style="font-size: 0.7rem; width: 50px;">Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        <template v-for="ing in paginatedIngredients" :key="ing.re_code">
                            <tr 
                                class="transition-all"
                                :class="getIngredientRowClass(ing)"
                            >
                                <td class="text-center" style="padding: 0;">
                                    <q-btn
                                        flat round dense
                                        :icon="isExpanded(ing.re_code) ? 'expand_more' : 'chevron_right'"
                                        color="orange-9"
                                        size="xs"
                                        @click.stop="toggleIngredientExpand(ing.re_code)"
                                    />
                                </td>
                                <td class="text-weight-bold transition-all" style="font-size: 0.75rem;">
                                    <div class="text-blue-9">
                                        {{ ing.re_code }}
                                    </div>
                                    <q-tooltip>{{ ing.ingredient_name }}</q-tooltip>
                                </td>
                                <td class="text-center text-caption" style="font-size: 0.7rem;">{{ ing.package_container_type }}</td>
                                <td class="text-right text-weight-bold text-orange-9" style="font-size: 0.75rem;">{{ ing.batch_require ? ing.batch_require.toFixed(5) : '0' }}</td>
                                <td class="text-right text-weight-bold text-green-9" style="font-size: 0.75rem;">{{ ing.total_packaged ? ing.total_packaged.toFixed(5) : '0' }}</td>
                                <td class="text-center">
                                    <q-badge v-if="ing.status === 2" color="green" :label="t('preBatch.complete')" size="sm" />
                                    <q-badge v-else-if="ing.status === 1" color="orange" :label="t('preBatch.onBatch')" size="sm" />
                                    <q-badge v-else color="grey-6" label="Wait" size="sm" />
                                </td>
                                <td class="text-center">
                                    <q-btn
                                        v-if="ing.status < 2"
                                        flat dense
                                        icon="play_circle"
                                        label="Start"
                                        size="xs"
                                        color="green-9"
                                        class="text-weight-bold"
                                        @click.stop="openScanDialog(ing)"
                                    >
                                        <q-tooltip>Start Pre-Batch Weighing</q-tooltip>
                                    </q-btn>
                                    <q-btn v-if="ing.status >= 1" flat round dense icon="print" size="xs" color="blue-9" @click.stop="printAllPlanLabels(ing)">
                                        <q-tooltip>Print All Labels for this Ingredient</q-tooltip>
                                    </q-btn>
                                </td>
                            </tr>
                            
                            <!-- Per-batch breakdown table -->
                            <tr v-if="isExpanded(ing.re_code)" class="bg-blue-grey-1">
                                <td colspan="7" class="q-pa-none">
                                    <div class="q-pl-lg q-pr-sm q-py-xs" style="max-width: 100%; overflow-x: auto;">
                                        <q-markup-table dense flat square separator="cell" class="bg-white rounded-borders shadow-1" style="font-size: 0.65rem;">
                                            <thead class="bg-blue-grey-2">
                                                <tr>
                                                    <th style="width: 20px;"></th>
                                                    <th class="text-left" style="font-size: 0.65rem;">Batch ID</th>
                                                    <th class="text-right" style="font-size: 0.65rem;">Require</th>
                                                    <th class="text-right" style="font-size: 0.65rem;">Packaged</th>
                                                    <th class="text-center" style="font-size: 0.65rem;">Status</th>
                                                    <th class="text-center" style="font-size: 0.65rem; width: 40px;">Action</th>
                                                </tr>
                                            </thead>
                                            <tbody>
                                                <template v-for="bd in (ingredientBatchDetail[ing.re_code] || [])" :key="bd.batch_id">
                                                    <tr 
                                                        :class="bd.status === 2 ? 'bg-green-1 text-grey-6' : 'cursor-pointer'"
                                                        @click="bd.status !== 2 && onBatchIngredientClick({ batch_id: bd.batch_id }, { re_code: ing.re_code, id: bd.req_id, required_volume: bd.required_volume, status: bd.status }, selectedPlanDetails)"
                                                    >
                                                        <td style="padding: 0; width: 20px;">
                                                            <q-btn flat round dense size="xs"
                                                                :icon="isBatchRowExpanded(bd.batch_id + '-' + ing.re_code) ? 'expand_more' : 'chevron_right'"
                                                                color="blue-grey-6"
                                                                @click.stop="toggleBatchRow(bd.batch_id + '-' + ing.re_code)"
                                                            />
                                                        </td>
                                                        <td class="text-left">{{ bd.batch_id }}</td>
                                                        <td class="text-right">{{ bd.required_volume.toFixed(5) }}</td>
                                                        <td class="text-right" :class="bd.actual_volume > 0 ? 'text-blue-9 text-weight-bold' : ''">{{ bd.actual_volume.toFixed(5) }}</td>
                                                        <td class="text-center">
                                                            <q-badge v-if="bd.status === 2" color="green" label="preBatch_ok" size="sm" />
                                                            <q-badge v-else-if="bd.status === 1" color="orange" label="Prepare" size="sm" />
                                                            <q-badge v-else color="grey-5" label="Wait" size="sm" />
                                                        </td>
                                                        <td class="text-center">
                                                            <div class="row no-wrap justify-center q-gutter-x-xs">
                                                                <q-btn 
                                                                    v-if="bd.status >= 1" 
                                                                    flat round dense 
                                                                    icon="print" 
                                                                    size="xs" 
                                                                    color="blue-9" 
                                                                    @click.stop="printAllBatchLabels(bd.batch_id, ing.re_code, bd.required_volume)"
                                                                >
                                                                    <q-tooltip>Reprint Batch Labels</q-tooltip>
                                                                </q-btn>
                                                                <q-btn 
                                                                    v-if="bd.status === 2" 
                                                                    flat round dense 
                                                                    icon="edit" 
                                                                    size="xs" 
                                                                    color="orange-9" 
                                                                    @click.stop="onRebatchClick(bd, ing)"
                                                                >
                                                                    <q-tooltip>Rebatch — cancel and re-weigh</q-tooltip>
                                                                </q-btn>
                                                            </div>
                                                        </td>
                                                    </tr>
                                                    <!-- Expanded package plan -->
                                                    <tr v-if="isBatchRowExpanded(bd.batch_id + '-' + ing.re_code)" class="bg-blue-grey-1">
                                                        <td :colspan="6" class="q-pa-none q-pl-lg">
                                                            <q-markup-table dense flat square separator="cell" class="bg-white" style="font-size: 0.6rem;">
                                                                <thead class="bg-grey-2">
                                                                    <tr>
                                                                        <th style="font-size: 0.6rem; width: 30px;">Pkg#</th>
                                                                        <th class="text-right" style="font-size: 0.6rem;">Target</th>
                                                                        <th class="text-right" style="font-size: 0.6rem;">Packaged</th>
                                                                        <th class="text-center" style="font-size: 0.6rem; width: 40px;"></th>
                                                                    </tr>
                                                                </thead>
                                                                <tbody>
                                                                    <tr v-for="pkg in getPackagePlan(bd.batch_id, ing.re_code, bd.required_volume)" :key="pkg.pkg_no"
                                                                        :class="pkg.status === 'done' ? 'bg-green-1' : ''">
                                                                        <td class="text-center">#{{ pkg.pkg_no }}</td>
                                                                        <td class="text-right">{{ pkg.target.toFixed(3) }}</td>
                                                                        <td class="text-right" :class="pkg.status === 'done' ? 'text-blue-9 text-weight-bold' : 'text-grey-5'">
                                                                            {{ pkg.actual !== null ? pkg.actual.toFixed(4) : '-' }}
                                                                        </td>
                                                                        <td class="text-center">
                                                                            <q-icon v-if="pkg.status === 'done'" name="check_circle" color="green" size="xs" />
                                                                            <q-btn 
                                                                                v-if="pkg.log && pkg.log.id" 
                                                                                flat round dense 
                                                                                icon="delete_outline" 
                                                                                size="xs" 
                                                                                color="red-7" 
                                                                                @click.stop="onDeleteRecord(pkg.log)"
                                                                            >
                                                                                <q-tooltip>Delete this package record</q-tooltip>
                                                                            </q-btn>
                                                                        </td>
                                                                    </tr>
                                                                </tbody>
                                                            </q-markup-table>
                                                        </td>
                                                    </tr>
                                                </template>
                                                <tr v-if="!ingredientBatchDetail[ing.re_code]">
                                                    <td colspan="5" class="text-center text-grey text-italic">Loading...</td>
                                                </tr>
                                                <tr v-else-if="ingredientBatchDetail[ing.re_code]?.length === 0">
                                                    <td colspan="5" class="text-center text-grey text-italic">No batch data</td>
                                                </tr>
                                            </tbody>
                                        </q-markup-table>
                                    </div>
                                </td>
                            </tr>
                        </template>
                        <tr v-if="selectableIngredients.length === 0">
                            <td colspan="7" class="text-center text-grey q-pa-md">
                                <template v-if="selectedProductionPlan">
                                    <div v-if="prebatchItems.length > 0">
                                        {{ t('preBatch.noMatchingIngredients') }}
                                    </div>
                                    <div v-else-if="isBatchSelected">
                                        {{ t('preBatch.noIngredientsForBatch') }}
                                    </div>
                                    <div v-else>
                                        {{ t('preBatch.selectBatchToViewDetailed') }}
                                    </div>
                                </template>
                                <div v-else>{{ t('preBatch.selectPlanToView') }}</div>
                            </td>
                        </tr>
                    </tbody>
                </q-markup-table>
                <!-- Ingredient pagination -->
                <div v-if="selectableIngredients.length > ingredientPerPage" class="row items-center justify-end q-px-sm q-py-xs bg-grey-2" style="font-size: 0.75rem;">
                    <span class="text-grey-7 q-mr-sm">
                        {{ (ingredientPage - 1) * ingredientPerPage + 1 }}-{{ Math.min(ingredientPage * ingredientPerPage, selectableIngredients.length) }} of {{ selectableIngredients.length }}
                    </span>
                    <q-btn flat round dense icon="chevron_left" size="xs" :disable="ingredientPage <= 1" @click="ingredientPage--" />
                    <q-btn flat round dense icon="chevron_right" size="xs" :disable="ingredientPage >= ingredientTotalPages" @click="ingredientPage++" />
                </div>
            </div>
        </q-card>
      </div>

      <!-- RIGHT MAIN CONTENT -->
      <div class="col-12 col-md-8">

        <!-- SCALES SECTION -->
        <q-card bordered flat class="q-mb-md">
          <q-card-section class="q-py-xs row items-center bg-blue-grey-1">
            <div class="text-subtitle1 text-weight-bold">{{ t('preBatch.weightingScale') }}</div>
            <q-space />
            <div class="row items-center q-gutter-x-sm">
                <q-chip :color="workflowStatus.color" text-color="white" square size="md" class="text-weight-bold shadow-1">
                    STEP {{ workflowStatus.id }}
                </q-chip>
                <div class="text-h6 text-weight-bolder" :class="`text-${workflowStatus.color}`">
                    {{ workflowStatus.msg.toUpperCase() }}
                </div>
            </div>
          </q-card-section>

          <q-card-section class="q-py-sm">
            <div class="row q-col-gutter-sm">
              <div v-for="scale in scales" :key="scale.id" class="col">
                <q-card flat :bordered="selectedScale !== scale.id" class="q-pa-xs column cursor-pointer" :class="getScaleClass(scale)" @click="onScaleSelect(scale)">
                  <div class="row justify-between items-center q-mb-xs">
                    <div class="text-caption text-weight-bold">{{ scale.label }}</div>
                    <div 
                      class="status-indicator shadow-2"
                      :class="scale.connected ? 'bg-green-14' : 'bg-red-14'"
                    >
                      <q-tooltip>{{ scale.connected ? 'Connected' : 'Disconnected' }}</q-tooltip>
                    </div>
                  </div>
                  <!-- Digital Display (read-only monitor) -->
                    <div
                      class="relative-position text-right q-pa-xs text-h4 text-weight-bold rounded-borders flex items-center justify-end"
                      :class="getDisplayClass(scale)"
                      style="min-height: 80px;"
                    >

                      <div class="scale-value text-right" style="width: 100%; padding-right: 4px;">
                        {{ scale.displayValue }}
                      </div>
                      <div class="text-caption text-weight-bolder q-ml-xs" style="font-size: 0.8rem; margin-top: 15px;">{{ scale.unit || 'kg' }}</div>
                    </div>
                </q-card>
              </div>
            </div>
          </q-card-section>
        </q-card>


        <!-- Package Batching Prepare Section -->
        <q-card bordered flat class="q-mb-md">
            <q-card-section class="q-py-xs row items-center no-wrap q-gutter-x-md">
                <!-- Part 1: Batch ID -->
                <div class="row items-center no-wrap col-auto">
                    <div class="text-subtitle1 text-weight-bold q-mr-sm text-no-wrap">{{ t('preBatch.packagePrepareFor') }}</div>
                    <q-input
                        outlined
                        :model-value="selectedBatch ? selectedBatch.batch_id : ''"
                        dense
                        bg-color="grey-2"
                        readonly
                        style="width: 250px"
                    />
                    <q-btn
                        v-if="selectedBatch && filteredPreBatchLogs.length > 0"
                        flat round dense
                        icon="delete_sweep"
                        color="red-8"
                        size="sm"
                        @click="$q.dialog({
                            title: 'Clear All Records',
                            message: `Delete all ${filteredPreBatchLogs.length} records for batch ${selectedBatch.batch_id}? This will restore inventory.`,
                            cancel: true,
                            persistent: true,
                            color: 'red'
                        }).onOk(() => clearAllBatchRecords(selectedBatch.batch_id))"
                    >
                        <q-tooltip>Clear all preBatch records for this batch</q-tooltip>
                    </q-btn>
                </div>

                <q-space />

                <!-- Part 2: Auto Print -->
                <q-toggle 
                    v-model="autoPrint" 
                    :label="t('common.autoPrint') || 'Auto Print'" 
                    color="green" 
                    dense 
                    class="text-weight-bold text-no-wrap"
                />

                <q-separator vertical inset class="q-mx-sm" />

                <!-- Part 3: Intake Lot ID & Silent Scan -->
                <div class="row items-center no-wrap col-auto q-gutter-x-sm">
                    <div class="text-subtitle1 text-weight-bold text-no-wrap">{{ t('preBatch.fromIntakeLotId') }}</div>
                    <div style="width: 280px; position: relative;">
                        <!-- FIFO Recommendation Hint -->
                        <div v-if="workflowStep === 2 && fifoRecommendedLot" class="absolute-top-right text-caption text-green-9 text-weight-bold" style="top: -18px; right: 4px;">
                            <q-icon name="info" size="xs" color="green" /> Use: {{ fifoRecommendedLot.intake_lot_id }}
                        </div>
                        <q-input
                            v-if="workflowStep === 2"
                            ref="mainLotInputRef"
                            v-model="scanLotInput"
                            outlined
                            dense
                            autofocus
                            bg-color="orange-1"
                            placeholder="ZAP BARCODE HERE"
                            @keyup.enter="onScanLotEnter"
                            :error="!!scanLotError"
                            :error-message="scanLotError"
                            input-class="text-weight-bold text-center"
                        >
                             <template v-slot:prepend>
                                 <q-icon name="qr_code_scanner" color="orange-9" size="xs" />
                             </template>
                        </q-input>
                        <q-input
                            v-else
                            outlined
                            :model-value="currentPackageOrigins.length > 0 ? currentPackageOrigins.map((o: any) => o.intake_lot_id).join(' + ') : (selectedIntakeLotId || '—')"
                            dense
                            :bg-color="selectedIntakeLotId ? 'green-1' : 'grey-2'"
                            readonly
                            input-class="text-weight-bold text-center"
                        >
                            <template v-slot:append>
                                <q-btn icon="qr_code_scanner" flat round dense size="sm" @click="showScanDialog = true" color="grey-6" />
                            </template>
                        </q-input>
                    </div>
                </div>
            </q-card-section>

            <!-- Lot Origin Chips (multi-lot tracking) -->
            <q-card-section v-if="currentPackageOrigins.length > 0" class="q-py-xs">
                <div class="row items-center q-gutter-xs">
                    <q-icon name="inventory_2" color="blue-9" size="xs" />
                    <span class="text-caption text-weight-bold text-blue-9">Lot Origins:</span>
                    <q-chip
                        v-for="(o, i) in currentPackageOrigins"
                        :key="i"
                        removable
                        @remove="onRemoveLot(i)"
                        color="blue-1"
                        text-color="blue-9"
                        dense
                        class="q-ma-xs"
                    >
                        {{ o.intake_lot_id }} ({{ o.take_volume.toFixed(4) }} kg)
                    </q-chip>
                    <q-badge color="blue-9" class="q-ml-sm">
                        Total: {{ currentPackageOrigins.reduce((s: number, o: any) => s + o.take_volume, 0).toFixed(4) }} kg
                    </q-badge>
                </div>
            </q-card-section>

            <q-card-section>
                <!-- ROW 1: Volumes and Scale -->
                <div class="row q-col-gutter-md q-mb-md">
                    <!-- Batch Request volume -->
                    <div class="col">
                        <div class="text-subtitle2 q-mb-xs text-no-wrap">{{ t('preBatch.requestVolume') }}</div>
                        <q-input
                            outlined
                            :model-value="requireVolume.toFixed(5)"
                            dense
                            bg-color="grey-2"
                            readonly
                            input-class="text-right"
                        />
                    </div>

                    <!-- Packaged Volume -->
                    <div class="col">
                        <div class="text-subtitle2 q-mb-xs text-no-wrap">{{ t('preBatch.packagedVolume') }}</div>
                        <q-input
                            outlined
                            :model-value="(workflowStep === 7 ? lastCapturedWeight : batchedVolume).toFixed(5)"
                            dense
                            :bg-color="packagedVolumeBgColor"
                            readonly
                            input-class="text-right text-weight-bold"
                        />
                    </div>

                    <!-- Remain Volume -->
                    <div class="col">
                        <div class="text-subtitle2 q-mb-xs text-no-wrap">{{ t('preBatch.remainVolume') }}</div>
                        <q-input
                            outlined
                            :model-value="remainVolume.toFixed(5)"
                            dense
                            bg-color="grey-2"
                            readonly
                            input-class="text-right"
                        />
                    </div>

                    <!-- Package Request Volume -->
                    <div class="col">
                        <div class="text-subtitle2 q-mb-xs text-no-wrap text-blue-9 text-weight-bold">{{ t('preBatch.reqForPackage') }}</div>
                        <q-input
                            outlined
                            :model-value="targetWeight.toFixed(5)"
                            dense
                            bg-color="blue-1"
                            readonly
                            input-class="text-right text-weight-bold"
                        />
                    </div>

                    <!-- Weight scale Value -->
                    <div class="col">
                        <div class="text-subtitle2 q-mb-xs text-no-wrap">{{ t('preBatch.weightingScale') }}</div>
                        <q-input
                            outlined
                            :model-value="activeScale?.displayValue || '0'"
                            dense
                            :bg-color="activeScale?.isError ? 'red-8' : (isToleranceExceeded ? 'yellow-4' : 'green-1')"
                            readonly
                            :input-class="(activeScale?.isError ? 'text-white' : 'text-black') + ' text-right text-weight-bold'"
                        >
                            <template v-slot:append>
                                <div class="text-caption text-weight-bolder">{{ activeScale?.unit || 'kg' }}</div>
                            </template>
                        </q-input>
                    </div>
                </div>

                <!-- ROW 2: Package Info and Container -->
                <div class="row q-col-gutter-md">
                    <!-- This Package ID -->
                    <div class="col-12 col-md-4">
                        <div class="text-subtitle2 q-mb-xs text-no-wrap">This Package ID</div>
                        <q-input
                            outlined
                            :model-value="currentPackageId"
                            dense
                            bg-color="grey-2"
                            readonly
                            input-class="text-weight-bold"
                        />
                    </div>

                    <!-- Container Type -->
                    <div class="col-12 col-md-3">
                        <div class="text-subtitle2 q-mb-xs text-no-wrap">{{ t('ingConfig.containerType') }}</div>
                        <q-input
                            outlined
                            :model-value="selectableIngredients.find(i => i.re_code === selectedReCode)?.package_container_type || 'Bag'"
                            dense
                            bg-color="grey-2"
                            readonly
                            input-class="text-center"
                        />
                    </div>

                    <!-- Container Size -->
                    <div class="col-12 col-md-3">
                        <div class="text-subtitle2 q-mb-xs text-no-wrap">
                            Container Size (kg)
                            <q-btn flat dense round icon="settings" size="xs" color="grey-6" style="margin-top: -4px" @click="showContainerSizeDialog = true">
                                <q-tooltip>Manage Sizes</q-tooltip>
                            </q-btn>
                        </div>
                        <q-select
                            outlined
                            v-model="containerSize"
                            :options="containerSizeOptions"
                            dense
                            bg-color="white"
                            input-class="text-right"
                            use-input
                            fill-input
                            hide-selected
                            @filter="(val, update) => update(() => {})"
                            @new-value="(val, done) => { const n = Number(val); if (!isNaN(n) && n > 0) done(n, 'add-unique'); else done() }"
                        >
                        </q-select>
                    </div>

                    <!-- Package No / Total -->
                    <div class="col-12 col-md-2">
                        <div class="text-subtitle2 q-mb-xs text-no-wrap">{{ t('preBatch.nextPkgNo') }}</div>
                        <q-input
                            outlined
                            :model-value="`${nextPackageNo} / ${requestBatch}`"
                            dense
                            bg-color="yellow-1"
                            readonly
                            input-class="text-center text-weight-bold"
                        >
                            <q-tooltip>Package {{ nextPackageNo }} of {{ requestBatch }} ({{ packageSize }} kg each)</q-tooltip>
                        </q-input>
                    </div>
                </div>

                <!-- Static Control Row: ALWAYS SHOW ACTIVE OR INACTIVE -->
                <div class="row q-col-gutter-md items-center justify-end q-pt-md">
                    
                    <!-- Stop Button -->
                    <div class="col-6 col-md-3">
                        <q-btn
                            label="STOP"
                            color="red-10"
                            icon="stop"
                            class="full-width"
                            style="height: 44px"
                            unelevated
                            @click="handleStopPreBatch"
                            :disable="workflowStep === 1 && !selectedReCode"
                            flat
                            outline
                        />
                    </div>

                    <!-- SCAN FULL LOT Button (Step 3+) -->
                    <div class="col-6 col-md-3">
                        <q-btn
                            label="SCAN FULL LOT"
                            color="purple-9"
                            text-color="white"
                            icon="qr_code_scanner"
                            class="full-width"
                            style="height: 44px"
                            unelevated
                            @click="openScanFullLotDialog"
                            :disable="workflowStep < 3 || !selectedReCode || !selectedBatch"
                        >
                            <q-tooltip>Scan full intake lots without weighing — uses exact package volume</q-tooltip>
                        </q-btn>
                    </div>

                    <!-- Step 3: Start PreBatch / Step 4: Next Lot -->
                    <div class="col-6 col-md-3">                        <!-- NEXT LOT button (during weighing, has weight, not yet done) -->
                        <q-btn
                            v-if="workflowStep === 4 && batchedVolume > 0.001 && !isPackagedVolumeInTol"
                            label="NEXT LOT"
                            color="orange-9"
                            text-color="white"
                            icon="swap_horiz"
                            class="full-width"
                            style="height: 44px"
                            unelevated
                            @click="handleNextLot"
                        >
                            <q-tooltip>Capture weight from current lot and scan next intake lot</q-tooltip>
                        </q-btn>
                        <!-- START button (Step 3) -->
                        <q-btn
                            v-else
                            :label="workflowStep === 3 && !isScaleAtZero ? 'CLEAR SCALE' : 'START'"
                            :color="workflowStep === 3 && isScaleAtZero ? 'blue-10' : 'grey-4'"
                            :text-color="workflowStep === 3 && isScaleAtZero ? 'white' : 'grey-7'"
                            :icon="workflowStep === 3 && !isScaleAtZero ? 'warning' : 'play_arrow'"
                            class="full-width"
                            style="height: 44px"
                            unelevated
                            @click="handleStartWeighting"
                            :disable="workflowStep !== 3 || !isScaleAtZero"
                            :pulse="workflowStep === 3 && isScaleAtZero"
                        >
                            <q-tooltip v-if="workflowStep === 3 && !isScaleAtZero">
                                Scale must read 0.00 before starting — clear and tare the scale first
                            </q-tooltip>
                        </q-btn>
                    </div>

                    <!-- Step 4 & 7: Done / Next Prep -->
                    <div class="col-12 col-md-3">
                        <q-btn
                            :label="workflowStep === 7 ? 'NEXT PREP' : t('prodPlan.done')"
                            :color="(workflowStep === 7 || (workflowStep === 4 && isPackagedVolumeInTol)) ? 'green-9' : 'grey-4'"
                            :text-color="(workflowStep === 7 || (workflowStep === 4 && isPackagedVolumeInTol)) ? 'white' : 'grey-7'"
                            :icon="workflowStep === 7 ? 'forward' : 'check_circle'"
                            class="full-width"
                            style="height: 44px"
                            unelevated
                            @click="workflowStep === 7 ? handleStep7Confirm(true) : handleDoneClick()"
                            :disable="(workflowStep !== 4 && workflowStep !== 7) || (workflowStep === 4 && !isPackagedVolumeInTol)"
                        />
                    </div>

                </div>
            </q-card-section>
        </q-card>

        <!-- INVENTORY SECTION (compact) -->
        <q-card bordered flat class="q-mb-md">
            <q-card-section class="q-py-xs row items-center">
              <div class="text-subtitle1 text-weight-bold">{{ t('preBatch.onHandInventory') }}</div>
              <q-space />
              <q-btn flat round dense icon="refresh" color="primary" @click="fetchInventory" size="sm" class="q-mr-xs">
                  <q-tooltip>{{ t('preBatch.refreshInventory') }}</q-tooltip>
              </q-btn>
              <q-checkbox v-model="showAllInventory" :label="t('preBatch.showAllInv')" dense class="text-caption" />
            </q-card-section>
           <q-card-section class="q-py-sm">
              <q-table
                 flat
                 bordered
                 dense
                 :rows="filteredInventory"
                 :columns="inventoryColumns"
                 row-key="id"
                 :loading="inventoryLoading"
                 separator="cell"
                 :pagination="{ rowsPerPage: 5 }"
              >
                <!-- Expire Date Highlight -->
                <template v-slot:body-cell-expire_date="props">
                    <q-td :props="props" class="text-center">
                        <template v-if="filteredInventory.length > 0 && props.row.id === filteredInventory[0]?.id">
                            <q-badge color="green" text-color="white">{{ formatDate(props.value) }}</q-badge>
                        </template>
                        <template v-else>{{ formatDate(props.value) }}</template>
                    </q-td>
                </template>
                <!-- Status Slot -->
                 <template v-slot:body-cell-status="props">
                    <q-td :props="props" class="text-center">
                        <q-badge :color="props.value === 'Active' ? 'green' : (props.value === 'Hold' ? 'orange' : 'red')">
                            {{ props.value }}
                        </q-badge>
                    </q-td>
                </template>

                <!-- Actions Slot -->
                <template v-slot:body-cell-actions="props">
                    <q-td :props="props" class="text-center">
                        <div class="row no-wrap q-gutter-xs justify-center">
                            <q-btn 
                                round dense flat size="sm" 
                                color="blue" icon="print" 
                                @click.stop="openIntakeLabelDialog(props.row)"
                            >
                                <q-tooltip>{{ t('preBatch.printIntakeLabel') }}</q-tooltip>
                            </q-btn>
                            <q-btn 
                                round dense flat size="sm" 
                                color="blue" icon="history" 
                                @click.stop="onViewHistory(props.row)"
                            >
                                <q-tooltip>{{ t('preBatch.viewHistoryMonitor') }}</q-tooltip>
                            </q-btn>
                        </div>
                    </q-td>
                </template>

                <!-- Summary Row -->
                <template v-slot:bottom-row>
                    <q-tr class="bg-grey-2 text-weight-bold">
                        <q-td colspan="9" class="text-right">{{ t('preBatch.total') }}</q-td>
                        <q-td class="text-right">{{ inventorySummary.remain_vol.toFixed(3) }}</q-td>
                        <q-td></q-td>
                        <q-td class="text-center">{{ inventorySummary.pkgs }}</q-td>
                        <q-td colspan="5"></q-td>
                    </q-tr>
                </template>
                
                <template v-slot:no-data>
                   <div class="full-width row flex-center q-pa-md text-grey">
                      <span v-if="!selectedReCode">Select an ingredient to view inventory</span>
                      <span v-else>No inventory found for {{ selectedReCode }}</span>
                   </div>
                </template>
             </q-table>
           </q-card-section>
        </q-card>


      </div>
    </div>

    <!-- Cancel & Repack Confirmation Dialog -->
    <q-dialog v-model="showDeleteDialog" persistent>
        <q-card style="min-width: 400px; max-width: 500px">
            <q-card-section class="bg-negative text-white row items-center">
                <div class="text-h6">{{ t('preBatch.confirmRepackCancel') }}</div>
                <q-space />
                <q-btn icon="close" flat round dense v-close-popup />
            </q-card-section>

            <q-card-section class="q-pa-md">
                <div v-if="recordToDelete">
                    <p class="text-subtitle1 q-mb-sm">
                        Cancel Package <b>#{{ recordToDelete.package_no }}</b> — {{ recordToDelete.re_code }}
                    </p>
                    <p class="text-caption text-grey-7 q-mb-md">
                        {{ recordToDelete.batch_record_id }}
                    </p>
                    <q-select
                        v-model="deleteInput"
                        :options="['Weight Error', 'Wrong Ingredient', 'Label Damaged', 'Contamination', 'Operator Mistake', 'Other']"
                        outlined
                        dense
                        label="Reason for cancellation"
                        emit-value
                        map-options
                    >
                        <template v-slot:prepend>
                            <q-icon name="report_problem" color="orange" />
                        </template>
                    </q-select>
                </div>
            </q-card-section>

            <q-card-actions align="right" class="q-pa-md bg-grey-1">
                <q-btn :label="t('preBatch.goBack')" flat color="grey-7" v-close-popup />
                <q-btn 
                    :label="t('preBatch.confirmDeletion')" 
                    color="negative" 
                    unelevated 
                    :disable="!deleteInput"
                    @click="onConfirmDeleteManual" 
                />
            </q-card-actions>
        </q-card>
    </q-dialog>

    <!-- Container Setup Dialog (after scan, before weighing) -->
    <q-dialog v-model="showContainerSetupDialog" persistent>
        <q-card style="min-width: 440px; max-width: 540px;">
            <q-card-section class="bg-indigo-9 text-white">
                <div class="row items-center no-wrap">
                    <q-icon name="inventory_2" size="md" class="q-mr-sm" />
                    <div>
                        <div class="text-h6" style="line-height: 1.2;">Container Setup</div>
                        <div v-if="selectedPlanDetails" class="text-caption" style="opacity: 0.85;">
                            {{ selectedPlanDetails.sku_id }} — {{ selectedPlanDetails.sku_name || '' }}
                        </div>
                    </div>
                    <q-space />
                    <q-btn flat round dense icon="close" color="white" @click="showContainerSetupDialog = false" />
                </div>
            </q-card-section>

            <q-card-section class="q-pa-lg">
                <!-- Scanned Info -->
                <div class="q-pa-sm bg-green-1 rounded-borders q-mb-md" style="border-left: 4px solid #4caf50;">
                    <div class="row items-center q-mb-xs">
                        <q-icon name="check_circle" color="green" size="xs" class="q-mr-xs" />
                        <span class="text-caption text-weight-bold text-green-9">Scan Validated (FIFO OK)</span>
                    </div>
                    <div class="text-body2 text-weight-bold">{{ setupMatchedIngredient }}</div>
                    <div class="text-caption text-grey-7">
                        Lot: {{ setupMatchedLot }} | Batch: {{ setupPendingItem?.batch_id || '-' }}
                    </div>
                </div>

                <!-- Request Volume -->
                <div class="row items-center q-mb-md">
                    <div class="col-5 text-subtitle2 text-grey-8">Request Volume:</div>
                    <div class="col-7">
                        <q-input outlined dense readonly :model-value="requireVolume.toFixed(4)" bg-color="grey-2" input-class="text-right text-weight-bold" suffix="kg" />
                    </div>
                </div>

                <!-- Container Size Select -->
                <div class="row items-center q-mb-md">
                    <div class="col-5 text-subtitle2 text-grey-8">Container Size:</div>
                    <div class="col-7">
                        <q-select
                            outlined
                            v-model="setupContainerSize"
                            :options="containerSizeOptions"
                            dense
                            bg-color="white"
                            input-class="text-right text-weight-bold"
                            use-input
                            fill-input
                            hide-selected
                            suffix="kg"
                            @filter="(val, update) => update(() => {})"
                            @new-value="(val, done) => { const n = Number(val); if (!isNaN(n) && n > 0) done(n, 'add-unique'); else done() }"
                        />
                    </div>
                </div>

                <q-separator class="q-my-md" />

                <!-- Calculated Packages -->
                <div class="row items-center q-mb-sm">
                    <div class="col-5 text-subtitle2 text-grey-8">Number of Packages:</div>
                    <div class="col-7">
                        <div class="text-h4 text-weight-bolder text-center" :class="setupCalcPackages > 0 ? 'text-indigo-9' : 'text-grey-5'">
                            {{ setupCalcPackages || '-' }}
                        </div>
                    </div>
                </div>
                <div v-if="setupCalcPackages > 0" class="text-caption text-grey-6 text-center q-mt-xs">
                    {{ setupCalcPackages }} × {{ setupContainerSize }} kg
                    <span v-if="requireVolume % setupContainerSize !== 0">
                        (last pkg: {{ (requireVolume % setupContainerSize).toFixed(4) }} kg)
                    </span>
                </div>

                <q-separator class="q-my-md" />

                <!-- Scale Selector -->
                <div class="text-subtitle2 text-weight-bold text-grey-8 q-mb-sm">Select Scale:</div>
                <div class="row q-gutter-sm q-mb-sm">
                    <q-btn
                        v-for="scale in scales" :key="scale.id"
                        :outline="setupSelectedScale !== scale.id"
                        :unelevated="setupSelectedScale === scale.id"
                        :color="setupSelectedScale === scale.id ? 'indigo-9' : 'grey-5'"
                        :text-color="setupSelectedScale === scale.id ? 'white' : 'grey-8'"
                        :label="scale.label.split('(')[0].trim()"
                        :disable="scale.isError"
                        class="col text-weight-bold"
                        style="font-size: 0.75rem;"
                        @click="setupSelectedScale = scale.id"
                    >
                        <q-tooltip>{{ scale.label }}</q-tooltip>
                    </q-btn>
                </div>
                <div class="text-caption text-green-9 text-weight-bold text-center">
                    ✅ Auto-selected for {{ setupContainerSize }} kg
                </div>
            </q-card-section>

            <q-card-actions class="q-px-lg q-pb-lg" align="right">
                <q-btn flat label="Cancel" color="grey-7" @click="showContainerSetupDialog = false" />
                <q-btn 
                    unelevated 
                    label="Confirm & Start Weighing" 
                    icon="scale" 
                    color="indigo-9" 
                    :disable="setupCalcPackages <= 0"
                    @click="confirmContainerSetup"
                />
            </q-card-actions>
        </q-card>
    </q-dialog>

    <!-- Tare Popup (Step 3, scale NOT at zero) -->
    <q-dialog v-model="showTarePopup" persistent>
        <q-card style="min-width: 420px; max-width: 500px;">
            <q-card-section class="bg-amber-9 text-white">
                <div class="row items-center no-wrap">
                    <q-icon name="scale" size="md" class="q-mr-sm" />
                    <div>
                        <div class="text-h6" style="line-height: 1.2;">⚖️ Tare Scale</div>
                        <div class="text-caption" style="opacity: 0.85;">Place container on scale and tare before weighing</div>
                    </div>
                </div>
            </q-card-section>

            <q-card-section class="q-py-md">
                <!-- Scale selector -->
                <div class="text-subtitle2 text-weight-bold text-grey-8 q-mb-sm">Select Scale:</div>
                <div class="row q-gutter-sm">
                    <q-btn
                        v-for="scale in scales" :key="scale.id"
                        :outline="selectedTareScale !== scale.id"
                        :unelevated="selectedTareScale === scale.id"
                        :color="selectedTareScale === scale.id ? 'amber-9' : 'grey-5'"
                        :text-color="selectedTareScale === scale.id ? 'white' : 'grey-8'"
                        :label="scale.label.split('(')[0].trim()"
                        :disable="scale.isError"
                        class="col text-weight-bold"
                        style="font-size: 0.8rem;"
                        @click="selectedTareScale = scale.id"
                    >
                        <q-tooltip>{{ scale.label }}</q-tooltip>
                    </q-btn>
                </div>
                <div class="text-caption text-green-9 text-weight-bold q-mt-sm text-center">
                    ✅ Recommended for {{ packageSize.toFixed(1) }} kg package
                </div>
            </q-card-section>

            <q-card-section class="text-center q-pt-none q-pb-md">
                <div class="text-h5 text-weight-bolder text-amber-10 q-mb-sm">
                    ⚖️ Press TARE on Scale
                </div>
                <div class="text-body2 text-grey-7">
                    Place your container on the scale, then press the <b>TARE</b> button on the scale to zero it out.
                </div>
                <div class="text-caption text-red-5 q-mt-xs text-weight-bold">⚠️ Scale is NOT zero — tare before weighing</div>
            </q-card-section>

            <q-card-actions class="q-px-lg q-pb-lg row q-gutter-sm" align="center">
                <q-btn
                    unelevated
                    label="TARE"
                    icon="restart_alt"
                    color="amber-9"
                    class="col text-weight-bold"
                    style="font-size: 1rem;"
                    @click="handleTareAndAdvance"
                />
                <q-btn
                    outline
                    label="SKIP"
                    icon="skip_next"
                    color="grey-7"
                    class="col text-weight-bold"
                    style="font-size: 1rem;"
                    @click="closeTarePopupAndAdvance"
                />
            </q-card-actions>
        </q-card>
    </q-dialog>

    <!-- Confirm Start Weighing Popup (Step 3, scale IS zero) -->
    <q-dialog v-model="showConfirmStartPopup" persistent>
        <q-card style="min-width: 400px; max-width: 480px;">
            <q-card-section class="bg-green-8 text-white">
                <div class="row items-center no-wrap">
                    <q-icon name="check_circle" size="md" class="q-mr-sm" />
                    <div>
                        <div class="text-h6" style="line-height: 1.2;">✅ Scale Ready</div>
                        <div class="text-caption" style="opacity: 0.85;">Scale reads 0.00 — ready to start weighing</div>
                    </div>
                </div>
            </q-card-section>

            <q-card-section class="text-center q-py-lg">
                <div class="text-h5 text-weight-bolder text-green-9 q-mb-sm">
                    Start Weighing?
                </div>
                <div class="text-body2 text-grey-7">
                    Ingredient: <b>{{ selectedReCode }}</b><br/>
                    Package: <b>{{ packageSize }} kg</b> — Remain: <b>{{ remainVolume.toFixed(2) }} kg</b>
                </div>
            </q-card-section>

            <q-card-actions class="q-px-lg q-pb-lg row q-gutter-sm" align="center">
                <q-btn
                    unelevated
                    label="START WEIGHING"
                    icon="play_arrow"
                    color="green-8"
                    class="col text-weight-bold"
                    style="font-size: 1.1rem;"
                    @click="confirmStartWeighing"
                />
                <q-btn
                    outline
                    label="CANCEL"
                    color="grey-7"
                    class="col-4 text-weight-bold"
                    @click="showConfirmStartPopup = false; workflowStep = 1"
                />
            </q-card-actions>
        </q-card>
    </q-dialog>
    <!-- FIFO Violation Dialog -->
    <q-dialog v-model="showFifoViolationDialog" persistent>
        <q-card style="min-width: 420px; max-width: 500px;">
            <q-card-section class="bg-red-9 text-white">
                <div class="row items-center no-wrap">
                    <q-icon name="warning" size="lg" class="q-mr-sm" />
                    <div>
                        <div class="text-h6 text-weight-bolder" style="line-height: 1.2;">FIFO Violation!</div>
                        <div class="text-caption" style="opacity: 0.85;">Wrong lot scanned — must use earliest expire date first</div>
                    </div>
                </div>
            </q-card-section>

            <q-card-section class="q-pa-lg">
                <!-- Scanned (Wrong) -->
                <div class="q-pa-sm bg-red-1 rounded-borders q-mb-md" style="border-left: 4px solid #f44336;">
                    <div class="text-caption text-weight-bold text-red-9 q-mb-xs">❌ You Scanned:</div>
                    <div class="text-body1 text-weight-bold">{{ fifoViolationScannedLot }}</div>
                    <div class="text-caption text-grey-7">Expire: {{ fifoViolationScannedExpiry }}</div>
                </div>

                <!-- Expected (Correct) -->
                <div class="q-pa-sm bg-green-1 rounded-borders" style="border-left: 4px solid #4caf50;">
                    <div class="text-caption text-weight-bold text-green-9 q-mb-xs">✅ Please Use This Lot Instead:</div>
                    <div class="text-body1 text-weight-bold text-green-10">{{ fifoViolationExpectedLot }}</div>
                    <div class="text-caption text-grey-7">Expire: {{ fifoViolationExpectedExpiry }}</div>
                </div>
            </q-card-section>

            <q-card-actions class="q-px-lg q-pb-lg" align="center">
                <q-btn 
                    unelevated 
                    label="OK, Scan Again" 
                    icon="qr_code_scanner" 
                    color="red-9" 
                    class="full-width text-weight-bold"
                    style="font-size: 1rem;"
                    @click="showFifoViolationDialog = false"
                />
            </q-card-actions>
        </q-card>
    </q-dialog>

    <!-- Scan Prebatch Dialog (Workflow Controller) -->
    <q-dialog v-model="showScanDialog">
        <q-card style="min-width: 580px; max-width: 720px;">
            <!-- Header with progress -->
            <q-card-section class="bg-blue-9 text-white q-pb-xs">
                <div class="row items-center no-wrap">
                    <q-icon name="qr_code_scanner" size="sm" class="q-mr-sm" />
                    <div>
                        <div class="text-h6" style="line-height: 1.2;">Prebatch Workflow</div>
                        <div v-if="selectedPlanDetails" class="text-caption" style="opacity: 0.85;">
                            {{ selectedPlanDetails.sku_id }} — {{ selectedPlanDetails.sku_name || '' }} | Plan: {{ selectedProductionPlan }}
                        </div>
                    </div>
                    <q-space />
                    <q-badge v-if="scanProgress.total > 0" color="white" text-color="blue-9" class="text-weight-bold q-mr-sm">
                        {{ scanProgress.done }} / {{ scanProgress.total }}
                    </q-badge>
                    <q-btn icon="close" flat round dense v-close-popup />
                </div>
            </q-card-section>
            <q-linear-progress v-if="scanProgress.total > 0" :value="scanProgress.done / scanProgress.total" color="green" track-color="blue-7" size="4px" />

            <!-- Ingredient Info Header -->
            <q-card-section v-if="scanDialogIngInfo" class="bg-blue-1 q-py-sm">
                <div class="row items-center q-gutter-md">
                    <div>
                        <div class="text-caption text-grey-7">Ingredient</div>
                        <div class="text-subtitle1 text-weight-bold text-blue-9">{{ scanDialogIngInfo.ingredient_name }}</div>
                    </div>
                    <div>
                        <div class="text-caption text-grey-7">MAT SAP Code</div>
                        <div class="text-subtitle2 text-weight-bold">{{ scanDialogIngInfo.mat_sap_code }}</div>
                    </div>
                    <div>
                        <div class="text-caption text-grey-7">Total Require</div>
                        <div class="text-subtitle2 text-weight-bold text-orange-9">{{ scanDialogIngInfo.total_require.toFixed(4) }} kg</div>
                    </div>
                </div>
            </q-card-section>
            <q-card-section v-else class="bg-green-1 q-py-sm">
                <div class="row items-center q-gutter-sm">
                    <q-icon name="qr_code_scanner" color="green-9" size="md" />
                    <div>
                        <div class="text-subtitle1 text-weight-bold text-green-9">Scan intake lot to identify ingredient</div>
                        <div class="text-caption text-grey-7">System will validate ingredient is in this plan and FIFO is correct</div>
                    </div>
                </div>
            </q-card-section>

            <!-- Step 3: Scan Intake Lot Label -->
            <q-card-section class="q-py-sm">
                <!-- FIFO Recommended Lot -->
                <div v-if="fifoRecommendedLot" class="q-mb-sm q-pa-sm rounded-borders" style="background: #e8f5e9; border-left: 4px solid #4caf50;">
                    <div class="row items-center q-gutter-sm">
                        <q-icon name="inventory_2" color="green-9" size="sm" />
                        <div class="col">
                            <div class="text-caption text-grey-7">Use this Intake Lot (FIFO)</div>
                            <div class="text-subtitle2 text-weight-bold text-green-9">
                                {{ fifoRecommendedLot.intake_lot_id }}
                            </div>
                        </div>
                        <div class="text-right">
                            <div class="text-caption text-grey-7">Exp: {{ formatDate(fifoRecommendedLot.expire_date) }}</div>
                            <div class="text-caption text-weight-bold">Remain: {{ fifoRecommendedLot.remain_vol?.toFixed(2) }} kg</div>
                        </div>
                    </div>
                </div>
                <div v-else class="q-mb-sm q-pa-xs rounded-borders bg-orange-1 text-center">
                    <q-icon name="warning" color="orange-9" size="xs" class="q-mr-xs" />
                    <span class="text-caption text-orange-9 text-weight-bold">No active inventory found for this ingredient</span>
                </div>
                <div class="text-caption text-weight-bold text-grey-7 q-mb-xs">
                    <q-icon name="arrow_right" size="xs" /> {{ currentPackageOrigins.length > 0 ? 'Scan Next Lot (multi-lot)' : 'Scan Intake Lot Label' }}
                </div>
                <q-input
                    ref="dialogScanInputRef"
                    v-model="scanLotInput"
                    outlined
                    dense
                    autofocus
                    placeholder="Scan intake lot label (e.g. LB-26-004205)"
                    @keyup.enter="onScanLotEnter"
                    bg-color="white"
                    :error="!!scanLotError"
                    :error-message="scanLotError"
                >
                    <template v-slot:prepend>
                        <q-icon name="qr_code_scanner" color="blue-9" />
                    </template>
                    <template v-slot:append>
                        <q-icon v-if="scanLotValidated" name="check_circle" color="green" />
                    </template>
                </q-input>
                <div v-if="selectedIntakeLotId && scanLotValidated" class="q-mt-xs">
                    <q-chip color="green-1" text-color="green-9" icon="check_circle" dense>
                        {{ selectedIntakeLotId }} — Ready
                    </q-chip>
                </div>
            </q-card-section>

            <!-- Loading -->
            <q-card-section v-if="scanDialogLoading" class="text-center q-py-lg">
                <q-spinner-dots size="40px" color="blue-9" />
                <div class="text-caption q-mt-sm">Loading prebatch items...</div>
            </q-card-section>

            <!-- Tree of items grouped by Plan -->
            <q-card-section v-else class="q-pa-sm" style="max-height: 350px; overflow-y: auto;">
                <div v-if="scanDialogTree.length === 0" class="text-center text-grey-6 q-py-md">
                    No items found. Select an ingredient first.
                </div>
                <div v-for="group in scanDialogTree" :key="group.plan_id" class="q-mb-sm">
                    <div class="text-caption text-weight-bold text-blue-grey-7 q-px-xs q-py-xs bg-grey-2 rounded-borders">
                        <q-icon name="folder" size="xs" class="q-mr-xs" />
                        {{ group.plan_id }}
                    </div>
                    <q-list dense separator>
                        <q-item
                            v-for="(item, idx) in getPaginatedScanItems(group.plan_id, group.items)"
                            :key="item.batch_id"
                            :clickable="item.status !== 2 && scanLotValidated"
                            :class="[
                                item.status === 2 ? 'bg-green-1 text-grey-6' : '',
                                item === nextPendingItem && scanLotValidated ? 'bg-amber-1' : '',
                                item.status !== 2 && scanLotValidated ? 'cursor-pointer' : ''
                            ]"
                            @click="scanLotValidated && onScanItemSelect(item)"
                            class="q-pl-lg"
                        >
                            <q-item-section avatar>
                                <q-icon
                                    :name="item.status === 2 ? 'check_circle' : (item === nextPendingItem ? 'arrow_right' : 'radio_button_unchecked')"
                                    :color="item.status === 2 ? 'green' : (item === nextPendingItem ? 'orange-9' : 'grey-5')"
                                    size="xs"
                                />
                            </q-item-section>
                            <q-item-section>
                                <q-item-label class="text-weight-medium" style="font-size: 0.8rem;">
                                    {{ item.batch_id }}
                                </q-item-label>
                                <q-item-label caption>
                                    Require: {{ item.required_volume.toFixed(4) }} kg
                                    <span v-if="item.actual_volume > 0" class="text-blue-9 text-weight-bold q-ml-sm">
                                        Packed: {{ item.actual_volume.toFixed(4) }} kg
                                    </span>
                                </q-item-label>
                            </q-item-section>
                            <q-item-section side>
                                <q-badge
                                    :color="item.status === 2 ? 'green' : (item.status === 1 ? 'orange' : 'grey-5')"
                                    :label="item.status === 2 ? 'preBatch_ok' : (item.status === 1 ? 'Prepare' : 'Wait')"
                                    size="sm"
                                />
                            </q-item-section>
                        </q-item>
                    </q-list>
                    <!-- Batch pagination controls -->
                    <div v-if="getScanDialogTotalPages(group.items) > 1" class="row items-center justify-center q-py-xs q-gutter-x-xs bg-grey-1" style="border-top: 1px solid #e0e0e0;">
                      <q-btn flat dense round icon="chevron_left" size="xs" color="blue-9" :disable="getScanDialogPage(group.plan_id) <= 1" @click="setScanDialogPage(group.plan_id, getScanDialogPage(group.plan_id) - 1)" />
                      <span class="text-caption text-grey-8">{{ getScanDialogPage(group.plan_id) }} / {{ getScanDialogTotalPages(group.items) }}</span>
                      <q-btn flat dense round icon="chevron_right" size="xs" color="blue-9" :disable="getScanDialogPage(group.plan_id) >= getScanDialogTotalPages(group.items)" @click="setScanDialogPage(group.plan_id, getScanDialogPage(group.plan_id) + 1)" />
                    </div>
                </div>
            </q-card-section>

            <!-- All done message -->
            <q-card-section v-if="scanProgress.total > 0 && scanProgress.done === scanProgress.total" class="bg-green-1 text-center q-py-sm">
                <q-icon name="celebration" color="green" size="md" />
                <div class="text-weight-bold text-green-9">All batches completed!</div>
            </q-card-section>
        </q-card>
    </q-dialog>

    <!-- Rebatch Confirmation Dialog -->
    <q-dialog v-model="showRebatchDialog" persistent>
        <q-card style="min-width: 420px; max-width: 520px">
            <q-card-section class="bg-orange-9 text-white row items-center">
                <q-icon name="edit" size="sm" class="q-mr-sm" />
                <div class="text-h6">Rebatch Confirmation</div>
                <q-space />
                <q-btn icon="close" flat round dense v-close-popup />
            </q-card-section>

            <q-card-section class="q-pa-md">
                <div v-if="rebatchTarget" class="q-mb-md">
                    <div class="text-subtitle2 text-grey-8 q-mb-xs">
                        Cancel and re-weigh this item:
                    </div>
                    <div class="text-body1 text-weight-bold text-blue-9">
                        {{ rebatchTarget.batch_id }} — {{ rebatchIng?.re_code }}
                    </div>
                    <div class="text-caption text-grey-6 q-mt-xs">
                        Current weight: {{ rebatchTarget.actual_volume?.toFixed(4) }} kg
                    </div>
                </div>
                <q-select
                    v-model="rebatchReason"
                    :options="rebatchReasonOptions"
                    outlined
                    dense
                    label="Select reason *"
                    emit-value
                    map-options
                >
                    <template v-slot:prepend>
                        <q-icon name="warning_amber" color="orange-9" />
                    </template>
                </q-select>
                <q-input
                    v-if="rebatchReason === 'Other'"
                    v-model="rebatchRemark"
                    outlined
                    dense
                    type="textarea"
                    rows="2"
                    label="Please specify *"
                    placeholder="Enter the reason..."
                    class="q-mt-sm"
                    :rules="[(val: string) => !!val.trim() || 'Please specify the reason']"
                />
            </q-card-section>

            <q-card-actions align="right" class="q-pa-md bg-grey-1">
                <q-btn label="Cancel" flat color="grey-7" v-close-popup />
                <q-btn
                    label="Confirm Rebatch"
                    color="orange-9"
                    unelevated
                    icon="edit"
                    :disable="!rebatchFinalRemark"
                    @click="confirmRebatch"
                />
            </q-card-actions>
        </q-card>
    </q-dialog>

    <!-- Package Label Dialog -->
    <q-dialog v-model="showLabelDialog" persistent>
      <q-card style="min-width: 650px; max-width: 800px">
        <!-- Dialog Header -->
        <q-card-section class="row items-center q-pb-none bg-grey-3">
          <div class="text-h6 text-weight-bold text-grey-8">{{ t('preBatch.packageLabelPrint') }}</div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup class="bg-grey-5 text-white" />
        </q-card-section>

        <q-separator />

        <q-card-section class="q-pt-md">
          <!-- ID Input Row -->
          <div class="row q-col-gutter-md q-mb-md items-end">
            <div class="col-8">
              <div class="text-subtitle2 q-mb-xs">{{ t('preBatch.packageLabelId') }}</div>
              <div class="row no-wrap">
                <q-input v-model="packageLabelId" outlined dense class="full-width bg-white" />
                <q-btn icon="arrow_drop_down" outline color="grey-7" class="q-ml-sm" />
              </div>
            </div>
            <div class="col-4">
              <!-- Reprint uses onReprintLabel from history table -->
            </div>
          </div>

          <!-- Label Preview Container (Enforced 6x6 Square Ratio) -->
          <div class="row justify-center q-mb-md">
            <div class="label-preview-container q-pa-md shadow-2">
            <!-- Main Label Area -->
            <!-- SVG Production Label Render -->
            <div 
              v-if="labelDataMapping" 
              class="label-svg-preview bg-white q-pa-md shadow-2 flex flex-center"
              v-html="renderedLabel"
            ></div>
            </div>
          </div>

          <!-- Main Print Button -->
          <div class="row justify-end">
            <q-btn
              :label="t('common.print')"
              color="primary"
              class="q-px-xl q-py-sm"
              size="lg"
              unelevated
              @click="onPrintLabel"
              no-caps
            />
          </div>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- History Monitor Dialog -->
    <q-dialog v-model="showHistoryDialog">
      <q-card style="min-width: 700px">
        <q-card-section class="row items-center q-pb-none bg-blue-1">
          <div class="text-h6 text-blue-9">
            <q-icon name="history" class="q-mr-sm" />
            Inventory History Monitor - {{ selectedHistoryItem?.intake_lot_id }}
          </div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>

        <q-separator />

        <q-card-section class="q-pa-none">
          <q-markup-table flat bordered square dense separator="cell">
            <thead class="bg-grey-2">
              <tr>
                <th class="text-left">Timestamp</th>
                <th class="text-left">Action</th>
                <th class="text-center">Old Status</th>
                <th class="text-center">New Status</th>
                <th class="text-left">By</th>
                <th class="text-left">Remarks</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(h, idx) in selectedHistoryItem?.history || []" :key="idx">
                <td class="text-caption">{{ h.changed_at ? h.changed_at.replace('T', ' ').split('.')[0] : '-' }}</td>
                <td class="text-weight-bold">{{ h.action }}</td>
                <td class="text-center">
                   <q-badge :color="h.old_status === 'Active' ? 'green' : 'orange'" dense>
                     {{ h.old_status || '-' }}
                   </q-badge>
                </td>
                <td class="text-center">
                   <q-badge :color="h.new_status === 'Active' ? 'green' : 'orange'" dense>
                     {{ h.new_status || '-' }}
                   </q-badge>
                </td>
                <td class="text-caption">{{ h.changed_by }}</td>
                <td class="text-caption">{{ h.remarks || '-' }}</td>
              </tr>
              <tr v-if="!selectedHistoryItem?.history || selectedHistoryItem.history.length === 0">
                <td colspan="6" class="text-center text-grey q-pa-md italic">{{ t('preBatch.noHistoryRecords') }}</td>
              </tr>
            </tbody>
          </q-markup-table>
        </q-card-section>

        <q-card-section class="q-pt-md">
           <div class="row q-col-gutter-sm">
              <div class="col-12 col-md-6">
                 <div class="text-caption text-grey">{{ t('preBatch.targetInfo') }}</div>
                 <div class="text-subtitle2">Lot: {{ selectedHistoryItem?.intake_lot_id }}</div>
                 <div class="text-subtitle2">MAT: {{ selectedHistoryItem?.mat_sap_code }}</div>
              </div>
              <div class="col-12 col-md-6">
                 <div class="text-caption text-grey">{{ t('preBatch.currentStatus') }}</div>
                 <q-badge :color="selectedHistoryItem?.status === 'Active' ? 'green' : (selectedHistoryItem?.status === 'Hold' ? 'orange' : 'red')" size="md">
                    {{ selectedHistoryItem?.status }}
                 </q-badge>
              </div>
           </div>
        </q-card-section>

        <q-separator />

        <q-card-actions align="right">
          <q-btn flat :label="t('common.close')" color="primary" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Ingredient Intake Label Dialog (6x6) -->
    <q-dialog v-model="showIntakeLabelDialog">
      <q-card style="min-width: 650px">
        <q-card-section class="row items-center q-pb-none bg-grey-3 text-black">
          <div class="text-h6 text-weight-bold">{{ t('preBatch.intakeLabelPrint') }}</div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>

        <q-card-section class="q-pa-md">
            <!-- Label Selection / Printer Settings -->
            <div class="row q-col-gutter-sm q-mb-md">
                <div class="col-8">
                    <q-select
                        outlined
                        dense
                        :label="t('preBatch.defaultPrinter')"
                        v-model="selectedPrinter"
                        :options="['TSC_MB241', 'Zebra-Label-Printer', 'Brother-QL-800', 'Microsoft Print to PDF']"
                        bg-color="white"
                    />
                </div>
                <div class="col-4">
                    <q-btn color="primary" icon="print" :label="t('preBatch.directPrint')" class="full-width" @click="printIntakeLabel" />
                </div>
            </div>

            <!-- 6x6 Preview Area -->
            <div class="row justify-center">
                <div id="intake-label-printable" class="intake-label-6x6 shadow-3">
                    <!-- Top Part -->
                    <div class="intake-header q-pa-sm text-center">
                        <div class="text-h5 text-weight-bolder letter-spacing-2">INGREDIENT INTAKE</div>
                    </div>
                    
                    <div class="q-pa-md col-grow column">
                        <!-- Lot ID Row -->
                        <div class="row items-start q-mb-md">
                            <div class="col">
                                <div class="text-caption text-weight-bold text-grey-7">INTAKE LOT ID</div>
                                <div class="text-h6 text-weight-bolder text-mono line-height-1">{{ intakeLabelData?.intake_lot_id }}</div>
                            </div>
                            <div class="col-auto">
                                <q-icon name="qr_code_2" size="80px" />
                            </div>
                        </div>

                        <!-- Ingredient Code Row -->
                        <div class="q-mb-md">
                            <div class="text-caption text-weight-bold text-grey-7">INGREDIENT CODE</div>
                            <div class="text-h3 text-weight-bolder">{{ intakeLabelData?.re_code }}</div>
                            <div class="text-subtitle1 text-grey-8">{{ intakeLabelData?.mat_sap_code }}</div>
                        </div>

                        <!-- Volume and Package Row -->
                        <div class="row q-col-gutter-lg q-mb-md">
                            <div class="col">
                                <div class="text-caption text-weight-bold text-grey-7">INTAKE VOL</div>
                                <div class="text-h4 text-weight-bolder">{{ (intakeLabelData?.intake_vol ?? 0).toFixed(4) }} <span class="text-h6">kg</span></div>
                            </div>
                            <div class="col-auto text-right">
                                <div class="text-caption text-weight-bold text-grey-7">PACKAGE</div>
                                <div class="text-h4 text-weight-bolder">1 / {{ intakeLabelData?.package_intake }}</div>
                            </div>
                        </div>

                        <!-- Dates Row -->
                        <div class="row q-col-gutter-md">
                            <div class="col-6">
                                <div class="text-caption text-weight-bold text-grey-7 uppercase">Expire Date</div>
                                <div class="text-h6 text-weight-bold">{{ formatDate(intakeLabelData?.expire_date) }}</div>
                            </div>
                            <div class="col-6">
                                <div class="text-caption text-weight-bold text-grey-7 uppercase">Mfg Date</div>
                                <div class="text-subtitle1 text-weight-bold word-break-all">{{ formatDate(intakeLabelData?.manufacturing_date) }}</div>
                            </div>
                        </div>
                    </div>

                    <!-- Dashed Line -->
                    <div class="q-px-md">
                        <div style="border-top: 2px dashed #333; height: 1px; width: 100%;"></div>
                    </div>

                    <!-- Sub Label (Bottom) -->
                    <div class="q-pa-md row items-center">
                        <div class="col-8">
                             <div class="text-caption text-weight-bold text-grey-7 uppercase" style="font-size: 0.6rem;">INTAKE LOT ID</div>
                             <div class="text-subtitle2 text-weight-bold q-mb-xs">{{ intakeLabelData?.intake_lot_id }}</div>
                             
                             <div class="row">
                                <div class="col-6">
                                    <div class="text-caption uppercase text-grey-8" style="font-size: 0.65rem;">Material</div>
                                    <div class="text-subtitle2 text-weight-bold">{{ intakeLabelData?.re_code }}</div>
                                    <div class="text-caption text-grey-7" style="font-size: 0.6rem;">{{ intakeLabelData?.mat_sap_code }}</div>
                                </div>
                                <div class="col-6">
                                    <div class="text-caption uppercase text-grey-8" style="font-size: 0.65rem;">Weight</div>
                                    <div class="text-subtitle2 text-weight-bold">{{ (intakeLabelData?.intake_vol ?? 0).toFixed(4) }} kg</div>
                                    <div class="text-caption text-grey-7" style="font-size: 0.6rem;">1 / {{ intakeLabelData?.package_intake }}</div>
                                </div>
                             </div>
                        </div>
                        <div class="col-4 flex flex-center">
                            <q-icon name="qr_code_2" size="60px" />
                        </div>
                    </div>
                </div>
            </div>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- Packing Box Label Dialog -->
    <q-dialog v-model="showPackingBoxLabelDialog" persistent>
      <q-card style="min-width: 650px; max-width: 800px">
        <q-card-section class="row items-center q-pb-none bg-green-1 text-green-9">
          <div class="text-h6 text-weight-bold">{{ t('preBatch.packingBoxPreview') }}</div>
          <q-space />
          <q-btn icon="close" flat round dense v-close-popup />
        </q-card-section>

        <q-card-section class="q-pa-md">
          <div class="row justify-center q-mb-md">
            <div class="label-preview-container q-pa-md shadow-2">
              <div 
                v-if="packingBoxLabelDataMapping" 
                class="label-svg-preview bg-white q-pa-md flex flex-center"
                v-html="renderedPackingBoxLabel"
              ></div>
            </div>
          </div>

          <div class="row justify-end q-gutter-sm">
            <q-btn :label="t('common.cancel')" flat color="grey-7" v-close-popup />
            <q-btn
              :label="t('preBatch.printPackingBoxLabel')"
              color="green-7"
              class="q-px-xl"
              size="lg"
              unelevated
              @click="onPrintPackingBoxLabel"
              no-caps
            />
          </div>
        </q-card-section>
      </q-card>
    </q-dialog>

    <!-- Pre-Batch Report Dialog -->
    <q-dialog v-model="showPreBatchReportDialog">
      <q-card style="min-width: 400px;">
        <q-card-section class="bg-primary text-white">
          <div class="text-h6"><q-icon name="assessment" class="q-mr-sm" />Pre-Batch Summary Report</div>
          <div class="text-caption">Select date range for the report</div>
        </q-card-section>
        <q-card-section class="q-gutter-md">
          <q-input v-model="prebatchReportFromDate" label="From Date" filled mask="##/##/####" fill-mask>
            <template #append><q-icon name="event" class="cursor-pointer"><q-popup-proxy cover><q-date v-model="prebatchReportFromDate" mask="DD/MM/YYYY" /></q-popup-proxy></q-icon></template>
          </q-input>
          <q-input v-model="prebatchReportToDate" label="To Date" filled mask="##/##/####" fill-mask>
            <template #append><q-icon name="event" class="cursor-pointer"><q-popup-proxy cover><q-date v-model="prebatchReportToDate" mask="DD/MM/YYYY" /></q-popup-proxy></q-icon></template>
          </q-input>
        </q-card-section>
        <q-card-actions align="right">
          <q-btn flat label="Cancel" v-close-popup />
          <q-btn color="primary" icon="print" label="Generate Report" :loading="prebatchReportLoading" @click="printPreBatchReport" />
        </q-card-actions>
      </q-card>
    </q-dialog>

    <!-- Container Size Mgmt Dialog -->
    <q-dialog v-model="showContainerSizeDialog">
      <q-card style="min-width: 350px;">
        <q-card-section class="bg-blue-grey-1 text-weight-bold">
          <div class="text-h6">Manage Sizes for {{ currentContainerType }}</div>
        </q-card-section>
        
        <q-card-section class="q-pt-md">
            <div class="row q-gutter-x-sm q-mb-md">
                <q-input v-model.number="newContainerSize" type="number" step="0.01" outlined dense label="New Size (kg)" style="flex: 1;" @keyup.enter="addContainerSize" />
                <q-btn color="primary" icon="add" label="Add" @click="addContainerSize" :disable="!newContainerSize" />
            </div>
            
            <q-list bordered separator>
                <q-item v-for="s in fetchedContainerSizes.filter(s => s.container_type === currentContainerType).sort((a,b) => a.size - b.size)" :key="s.id">
                    <q-item-section>{{ s.size.toFixed(2) }} kg</q-item-section>
                    <q-item-section side>
                        <q-btn flat round dense color="negative" icon="delete" @click="deleteContainerSize(s.id)" />
                    </q-item-section>
                </q-item>
                <q-item v-if="fetchedContainerSizes.filter(s => s.container_type === currentContainerType).length === 0">
                    <q-item-section class="text-grey text-italic" style="font-size: 0.8rem;">No custom sizes configured.</q-item-section>
                </q-item>
            </q-list>
        </q-card-section>
        
        <q-card-actions align="right">
          <q-btn flat label="Close" color="primary" v-close-popup />
        </q-card-actions>
      </q-card>
    </q-dialog>
    <!-- Scan Full Lot Dialog -->
    <q-dialog v-model="showScanFullLotDialog" persistent>
      <q-card style="min-width: 520px; max-width: 650px;">
        <q-card-section class="bg-purple-9 text-white">
          <div class="row items-center no-wrap">
            <q-icon name="qr_code_scanner" size="md" class="q-mr-sm" />
            <div>
              <div class="text-h6 text-weight-bold">SCAN FULL LOT</div>
              <div class="text-caption">Scan full intake lots — use exact package volume without weighing</div>
            </div>
            <q-space />
            <q-btn flat round icon="close" color="white" @click="showScanFullLotDialog = false" />
          </div>
        </q-card-section>

        <q-card-section>
          <!-- Ingredient & Batch Info -->
          <div class="row q-col-gutter-sm q-mb-md">
            <div class="col-6">
              <q-input outlined dense readonly :model-value="selectedBatch?.batch_id || ''" label="Batch ID" />
            </div>
            <div class="col-6">
              <q-input outlined dense readonly :model-value="selectedReCode || ''" label="Ingredient" />
            </div>
          </div>

          <!-- Package Volume Input -->
          <div class="row q-col-gutter-sm q-mb-md items-end">
            <div class="col-4">
              <q-input
                outlined dense
                v-model.number="scanFullLotPackageVol"
                label="Package Volume (kg)"
                type="number"
                step="0.1"
                min="0"
                input-class="text-weight-bold text-center"
                bg-color="purple-1"
              />
            </div>
            <div class="col-8">
              <div class="row q-col-gutter-xs">
                <div class="col-4">
                  <q-field outlined dense label="Remain (kg)" stack-label>
                    <template v-slot:control>
                      <div class="text-weight-bold text-h6 full-width text-center">{{ remainVolume.toFixed(2) }}</div>
                    </template>
                  </q-field>
                </div>
                <div class="col-4">
                  <q-field outlined dense label="Full Packs" stack-label>
                    <template v-slot:control>
                      <div class="text-weight-bold text-h6 full-width text-center text-purple-9">{{ scanFullLotCalc.fullPacks }}</div>
                    </template>
                  </q-field>
                </div>
                <div class="col-4">
                  <q-field outlined dense label="Weigh (kg)" stack-label>
                    <template v-slot:control>
                      <div class="text-weight-bold text-h6 full-width text-center" :class="scanFullLotCalc.remainder > 0 ? 'text-orange-9' : 'text-green-9'">
                        {{ scanFullLotCalc.remainder.toFixed(4) }}
                      </div>
                    </template>
                  </q-field>
                </div>
              </div>
            </div>
          </div>

          <!-- Scan Input -->
          <q-input
            v-if="scanFullLotScanned.length < scanFullLotCalc.fullPacks"
            outlined dense autofocus
            v-model="scanFullLotInput"
            :label="`Scan Lot ${scanFullLotScanned.length + 1} / ${scanFullLotCalc.fullPacks}`"
            placeholder="ZAP INTAKE LOT BARCODE"
            @keyup.enter="onScanFullLotEnter"
            :loading="scanFullLotProcessing"
            bg-color="purple-1"
            input-class="text-weight-bold text-center"
            class="q-mb-md"
          >
            <template v-slot:prepend>
              <q-icon name="qr_code_scanner" color="purple-9" />
            </template>
          </q-input>

          <q-banner v-else class="bg-green-1 text-green-9 q-mb-md" rounded>
            <template v-slot:avatar><q-icon name="check_circle" color="green" /></template>
            All {{ scanFullLotCalc.fullPacks }} full lots scanned!
            <span v-if="scanFullLotCalc.remainder > 0" class="text-orange-9"> — Remaining {{ scanFullLotCalc.remainder.toFixed(4) }} kg → weigh on scale</span>
          </q-banner>

          <!-- Scanned Lots List -->
          <q-list v-if="scanFullLotScanned.length > 0" bordered separator class="rounded-borders">
            <q-item v-for="(item, idx) in scanFullLotScanned" :key="idx">
              <q-item-section avatar>
                <q-icon name="check_circle" color="green" />
              </q-item-section>
              <q-item-section>
                <q-item-label class="text-weight-bold">Pkg #{{ item.pkg_no }} — {{ item.lot_id }}</q-item-label>
                <q-item-label caption>{{ item.volume }} kg (full lot)</q-item-label>
              </q-item-section>
              <q-item-section side>
                <q-badge color="green" :label="`${item.volume} kg`" />
              </q-item-section>
            </q-item>
          </q-list>

          <!-- Summary Bar -->
          <div v-if="scanFullLotScanned.length > 0" class="q-mt-sm row justify-between items-center text-weight-bold">
            <div>Scanned: {{ scanFullLotScanned.length }} / {{ scanFullLotCalc.fullPacks }}</div>
            <div>Total: {{ scanFullLotScanned.reduce((s, o) => s + o.volume, 0).toFixed(2) }} kg</div>
          </div>
        </q-card-section>

        <q-card-actions align="right" class="q-px-md q-pb-md">
          <q-btn flat label="Close" color="grey-7" @click="showScanFullLotDialog = false" />
        </q-card-actions>
      </q-card>
    </q-dialog>

  </q-page>
</template>

<style scoped>
.scale-value,
:deep(.scale-value) {
  font-weight: bold !important;
  font-size: 48px !important;
  line-height: 1.1 !important;
}

.batch-list-container {
  border: 1px solid #ccc;
  border-radius: 4px;
  height: 400px; /* Example height to make it look like a panel */
  overflow-y: auto;
  background: #f8f9fa;
}

.ingredient-list-container {
  border: 1px solid #ccc;
  border-radius: 4px;
  height: 300px; /* Slightly shorter than batch list or adjust as needed */
  overflow-y: auto;
  background: #f8f9fa;
}

.scale-card-border {
  border: 1px solid #000;
  border-radius: 8px;
}

.status-indicator {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  cursor: pointer;
  border: 2px solid white;
}

.status-indicator:hover {
  transform: scale(1.1);
}

.prebatch-list-container {
  border: 1px solid #777;
  border-radius: 4px;
  height: 250px;
  overflow-y: auto;
  background: #fff;
  font-family: monospace; /* Log style font */
  font-size: 13px;
}

/* Custom styling to match radio button size in image roughly (if needed) */
:deep(.q-radio__inner) {
  font-size: 24px;
}

/* Override input styles to match specific visual cues from image */
:deep(.focused-border-blue .q-field__control) {
  border-color: #1976d2 !important;
  border-width: 2px;
}

/* Label Dialog Styles */
.label-preview-container {
  border: 4px solid #1d3557; /* Dark border */
  border-radius: 8px;
  background-color: #ffffff;
  width: 550px;
  height: 550px;
  display: flex;
  flex-direction: column;
}
.main-label-area {
  flex-grow: 1;
}
/* Active Scale Highlighting */
.active-scale-border {
  border: 5px solid #4caf50 !important; /* Green */
  border-radius: 8px;
}
.border-left {
  border-left: 1px solid #e0e0e0;
}
.text-mono {
  font-family: 'Courier New', Courier, monospace;
}
.letter-spacing-2 {
  letter-spacing: 2px;
}
.line-height-1 {
  line-height: 1;
}
.word-break-all {
  word-break: break-all;
}

.label-svg-preview {
  width: 100%;
  max-width: 400px;
  min-height: 400px;
  border-radius: 8px;
  overflow: hidden;
}

.label-svg-preview :deep(svg) {
  width: 100%;
  height: auto;
}

@media print {
  body * {
    visibility: hidden;
  }
  #intake-label-printable, #intake-label-printable * {
    visibility: visible;
  }
  #intake-label-printable {
    position: fixed;
    left: 0;
    top: 0;
    width: 4in;
    height: 3in;
    border: none;
    margin: 0;
    padding-left: 2.5mm; /* Safety offset */
    padding-top: 1.5mm;
    box-sizing: border-box;
    background: white;
  }
  @page {
    size: auto;
    margin: 0 !important;
  }
}

/* Sticky Header Table */
.sticky-header-table {
  height: 250px;
}
.sticky-header-table thead tr th {
  position: sticky;
  z-index: 1;
}
.sticky-header-table thead tr:first-child th {
  top: 0;
  background-color: #f5f5f5;
}

@keyframes pulse-orange {
  0% { transform: scale(1); box-shadow: 0 0 0 0 rgba(230, 81, 0, 0.4); }
  70% { transform: scale(1.05); box-shadow: 0 0 0 10px rgba(230, 81, 0, 0); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 rgba(230, 81, 0, 0); }
}
.anim-pulse {
  animation: pulse-orange 1.5s infinite;
}
@keyframes blink-red {
  0% { background-color: #ef5350; }
  50% { background-color: #b71c1c; }
  100% { background-color: #ef5350; }
}
.bg-red-blink {
  animation: blink-red 1s infinite;
}


</style>

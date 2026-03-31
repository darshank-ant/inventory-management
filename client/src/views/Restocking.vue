<template>
  <div class="restocking">
    <div class="page-header">
      <h2>{{ t('restocking.title') }}</h2>
      <p>{{ t('restocking.description') }}</p>
    </div>

    <div v-if="loading" class="loading">{{ t('common.loading') }}</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div v-if="successMessage" class="success-banner">
        {{ successMessage }}
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.budgetSlider') }}</h3>
        </div>
        <div class="budget-section">
          <input
            type="range"
            class="budget-slider"
            :min="1000"
            :max="100000"
            :step="1000"
            v-model.number="budget"
          />
          <div class="budget-stats">
            <div class="budget-stat">
              <div class="budget-stat-label">{{ t('restocking.budgetSlider') }}</div>
              <div class="budget-stat-value">{{ currencySymbol }}{{ budget.toLocaleString() }}</div>
            </div>
            <div class="budget-stat allocated">
              <div class="budget-stat-label">{{ t('restocking.allocated') }}</div>
              <div class="budget-stat-value allocated-value">{{ currencySymbol }}{{ (recommendations ? recommendations.total_allocated : 0).toLocaleString() }}</div>
            </div>
            <div class="budget-stat remaining">
              <div class="budget-stat-label">{{ t('restocking.remaining') }}</div>
              <div class="budget-stat-value remaining-value">{{ currencySymbol }}{{ (recommendations ? recommendations.remaining_budget : budget).toLocaleString() }}</div>
            </div>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-header">
          <h3 class="card-title">{{ t('restocking.recommendations') }}</h3>
          <p class="priority-note">{{ t('restocking.priorityNote') }}</p>
        </div>
        <div v-if="recLoading" class="loading">{{ t('common.loading') }}</div>
        <div v-else-if="recError" class="error">{{ recError }}</div>
        <div v-else>
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>{{ t('restocking.table.sku') }}</th>
                  <th>{{ t('restocking.table.item') }}</th>
                  <th>{{ t('restocking.table.trend') }}</th>
                  <th>{{ t('restocking.table.quantity') }}</th>
                  <th>{{ t('restocking.table.unitCost') }}</th>
                  <th>{{ t('restocking.table.lineCost') }}</th>
                  <th>{{ t('restocking.table.status') }}</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in recommendationItems"
                  :key="item.item_sku"
                  :class="{ 'over-budget': !item.fits_budget }"
                >
                  <td><strong>{{ item.item_sku }}</strong></td>
                  <td>{{ item.item_name }}</td>
                  <td>
                    <span :class="['badge', item.trend]">{{ t('trends.' + item.trend) }}</span>
                  </td>
                  <td>{{ item.recommended_quantity }}</td>
                  <td>{{ currencySymbol }}{{ item.unit_cost.toLocaleString() }}</td>
                  <td :class="{ 'strikethrough': !item.fits_budget }">{{ currencySymbol }}{{ item.line_cost.toLocaleString() }}</td>
                  <td>
                    <span v-if="item.fits_budget" class="badge success">{{ t('restocking.fitsInBudget') }}</span>
                    <span v-else class="badge danger">{{ t('restocking.overBudget') }}</span>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="order-action">
            <button
              class="place-order-btn"
              :disabled="!hasAffordableItems || submitting"
              @click="placeOrder"
            >
              {{ t('restocking.placeOrder') }}
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, watch, onMounted } from 'vue'
import { api } from '../api'
import { useI18n } from '../composables/useI18n'

export default {
  name: 'Restocking',
  setup() {
    const { t, currentCurrency } = useI18n()

    const currencySymbol = computed(() => {
      return currentCurrency.value === 'JPY' ? '¥' : '$'
    })

    const loading = ref(false)
    const error = ref(null)
    const recLoading = ref(false)
    const recError = ref(null)
    const budget = ref(25000)
    const recommendations = ref(null)
    const submitting = ref(false)
    const successMessage = ref('')

    const recommendationItems = computed(() => {
      if (!recommendations.value) return []
      return recommendations.value.recommendations || []
    })

    const hasAffordableItems = computed(() => {
      return recommendationItems.value.some(item => item.fits_budget)
    })

    const loadRecommendations = async () => {
      recLoading.value = true
      recError.value = null
      try {
        recommendations.value = await api.getRestockingRecommendations(budget.value)
      } catch (err) {
        recError.value = 'Failed to load recommendations: ' + err.message
        console.error(err)
      } finally {
        recLoading.value = false
      }
    }

    let debounceTimer = null
    watch(budget, () => {
      clearTimeout(debounceTimer)
      debounceTimer = setTimeout(() => loadRecommendations(), 300)
    })

    const placeOrder = async () => {
      if (!hasAffordableItems.value || submitting.value) return
      submitting.value = true
      try {
        const items = recommendationItems.value
          .filter(item => item.fits_budget)
          .map(item => ({
            item_sku: item.item_sku,
            item_name: item.item_name,
            quantity: item.recommended_quantity,
            unit_cost: item.unit_cost
          }))
        const order = await api.createRestockingOrder(items)
        successMessage.value = t('restocking.orderPlaced', { orderNumber: order.order_number })
        setTimeout(() => { successMessage.value = '' }, 4000)
        await loadRecommendations()
      } catch (err) {
        error.value = 'Failed to place order: ' + err.message
        console.error(err)
      } finally {
        submitting.value = false
      }
    }

    onMounted(() => loadRecommendations())

    return {
      t,
      currencySymbol,
      loading,
      error,
      recLoading,
      recError,
      budget,
      recommendations,
      recommendationItems,
      hasAffordableItems,
      submitting,
      successMessage,
      placeOrder
    }
  }
}
</script>

<style scoped>
.budget-section {
  padding: 1.5rem;
}

.budget-slider {
  width: 100%;
  height: 6px;
  background: #e2e8f0;
  border-radius: 3px;
  accent-color: #2563eb;
  cursor: pointer;
  margin-bottom: 1.5rem;
}

.budget-stats {
  display: flex;
  gap: 1.5rem;
}

.budget-stat {
  flex: 1;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 1rem;
}

.budget-stat-label {
  font-size: 0.813rem;
  color: #64748b;
  margin-bottom: 0.25rem;
}

.budget-stat-value {
  font-size: 1.25rem;
  font-weight: 600;
  color: #0f172a;
}

.allocated-value {
  color: #059669;
}

.remaining-value {
  color: #2563eb;
}

.priority-note {
  font-size: 0.875rem;
  color: #64748b;
  margin: 0;
}

.over-budget {
  opacity: 0.5;
}

.strikethrough {
  text-decoration: line-through;
}

.order-action {
  padding: 1rem 1.5rem;
  border-top: 1px solid #e2e8f0;
  display: flex;
  justify-content: flex-end;
}

.place-order-btn {
  background: #2563eb;
  color: white;
  padding: 0.75rem 1.5rem;
  border-radius: 6px;
  font-weight: 600;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  transition: background 0.15s;
}

.place-order-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.place-order-btn:hover:not(:disabled) {
  background: #1d4ed8;
}

.success-banner {
  background: #d1fae5;
  color: #065f46;
  padding: 1rem;
  border-radius: 8px;
  margin-bottom: 1rem;
  font-weight: 500;
}
</style>

import { defineStore } from 'pinia'

export const useNavigationStore = defineStore('navigation', {
  state: () => ({ mobileOpen: false }),
  actions: { closeMobile() { this.mobileOpen = false }, toggleMobile() { this.mobileOpen = !this.mobileOpen } },
})

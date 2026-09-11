import { defineStore } from 'pinia'

export interface AuthenticatedUserSummary { fullName: string; username: string }

export const useUserStore = defineStore('user', {
  state: (): { summary: AuthenticatedUserSummary | null } => ({ summary: null }),
  actions: { setSummary(summary: AuthenticatedUserSummary | null) { this.summary = summary } },
})

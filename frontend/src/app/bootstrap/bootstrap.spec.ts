import { mount } from '@vue/test-utils'
import { createTestingPinia } from '@/app/bootstrap/testing'
import App from '@/App.vue'
import { router } from '@/app/router'

describe('application bootstrap', () => {
  it('mounts an RTL operational shell at the home route', async () => {
    await router.push('/')
    await router.isReady()

    const wrapper = mount(App, {
      global: { plugins: [router, createTestingPinia()] },
    })

    expect(wrapper.find('[data-testid="app-root"]').attributes('dir')).toBe('rtl')
    expect(wrapper.find('[data-testid="app-shell"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('الرئيسية')
  })
})

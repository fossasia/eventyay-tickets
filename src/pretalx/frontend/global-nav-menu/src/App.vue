<script setup lang="ts">
import { ref, useTemplateRef, onMounted, onBeforeUnmount } from 'vue'

const ENTRY_CLASSES = 'text-[#1a69a4] hover:text-white hover:bg-[#1a69a4] px-4 py-2 block no-underline'
const WITH_ICON_CLASSES = 'flex flex-row items-center space-x-2'
const WITH_BORDER_CLASSES = 'border-t border-s-0 border-e-0 border-b-0 border-solid border-gray-300'
const open = ref(false)
const subOpen = ref(false)
const container = useTemplateRef('container')

function showMenu() {
  open.value = true
}

function closeMenu() {
  open.value = false
}

function handleClickOutside(event: MouseEvent) {
  const target = event.target as HTMLElement
  if (container.value && !container.value.contains(target)) {
    closeMenu()
  }
}

function handleKeyDown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    closeMenu()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeyDown)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeyDown)
})
</script>

<template>
  <div class='relative font-sans text-sm' ref='container'>
    <button class='text-xl cursor-pointer' @click='showMenu'><div class='i-fa-caret-down h-4 w-4' /></button>
    <div v-if='open' ref='main-menu' class='absolute z-1 end-1 grid grid-cols-1 shadow shadow-lg min-w-48 bg-white'>
      <div class='relative cursor-pointer' @mouseover='subOpen = true' @mouseleave='subOpen = false'>
        <div class='flex flex-row items-center space-x-2' :class='ENTRY_CLASSES' >
          <div class='i-fa-tachometer h-3 w-3'></div>
          <div class=''>Dashboard</div>
        </div>
        <ul v-if='subOpen' class='absolute z-2 top-0 -translate-x-full list-none m-0 p-s-0 bg-white shadow-lg min-w-56'>
          <li>
            <a href='/common/' :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' class='block'>
              <div class='i-fa-tachometer h-3 w-3'></div>
              <div>Main dashboard</div>
            </a>
          </li>
          <li>
            <a href='/tickets/control/' :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' class='block'>
              <div class='i-fa-ticket h-3 w-3'></div>
              <div>Tickets</div>
            </a>
          </li>
          <li>
            <a href='/talk/orga/event/' :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' class='block'>
              <div class='i-fa-microphone h-3 w-3'></div>
              <div>Talks</div>
            </a>
          </li>
        </ul>
      </div>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' href='/tickets/common/orders/'>
        <div class='i-fa-shopping-cart h-3 w-3'></div>
        <div>My orders</div>
      </a>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' href='/tickets/common/events/'>
        <div class='i-fa-calendar h-3 w-3'></div>
        <div>My events</div>
      </a>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES]' href='/tickets/common/organizers/'>
        <div class='i-fa-users h-3 w-3'></div>
        <div>Organizers</div>
      </a>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES, WITH_BORDER_CLASSES]' href='/tickets/common/account/'>
        <div class='i-fa-user h-3 w-3'></div>
        <div>Accounts</div>
      </a>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES, WITH_BORDER_CLASSES]' href='/tickets/control/admin/'>
        <div class='i-fa-cog h-3 w-3'></div>
        <div>Admin</div>
      </a>
      <a :class='[ENTRY_CLASSES, WITH_ICON_CLASSES, WITH_BORDER_CLASSES]' href='/tickets/control/logout'>
        <div class='i-fa-sign-out h-3 w-3'></div>
        <div>Logout</div>
      </a>
    </div>
  </div>
</template>

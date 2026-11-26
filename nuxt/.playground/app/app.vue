<template>
  <div class="shell">
    <header class="bar">
      <NuxtLink to="/admin/dev-tickets" class="brand">Playground</NuxtLink>
      <span class="grow" />
      <DevTicketBell />
    </header>
    <main class="main">
      <NuxtPage />
    </main>
    <DevTicketWidget />
  </div>
</template>

<style>
body {
  background: var(--p-surface-50);
  color: var(--p-text-color);
  font-family: system-ui, sans-serif;
  margin: 0;
}
.bar {
  align-items: center;
  background: var(--p-content-background);
  border-bottom: 1px solid var(--p-content-border-color);
  display: flex;
  padding: 0.5rem 1.5rem;
}
.brand {
  color: inherit;
  font-weight: 700;
  text-decoration: none;
}
.grow {
  flex: 1;
}
.main {
  padding: 1.5rem;
}
</style>

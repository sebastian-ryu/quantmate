<script lang="ts">
  import { page } from '$app/stores';
  import '../app.css';

  const navItems = [
    { href: '/', label: '대시보드' },
    { href: '/universe', label: '데이터' },
    { href: '/recommendations', label: '추천' },
    { href: '/screener', label: '검색기' },
    { href: '/strategies', label: '전략/백테스트' },
    { href: '/paper', label: '모의 투자' },
    { href: '/settings', label: '설정' }
  ];

  $: currentPath = $page.url.pathname;
</script>

<main class="app-shell">
  <aside class="sidebar" aria-label="주요 메뉴">
    <div class="brand">
      <strong>QuantMate</strong>
      <span>Local Research</span>
    </div>
    <nav>
      {#each navItems as item}
        <a class:active={currentPath === item.href} href={item.href}>{item.label}</a>
      {/each}
    </nav>
  </aside>

  <section class="workspace">
    <slot />
  </section>
</main>

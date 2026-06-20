<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  onMount(() => {
    void goto('/screener', { replaceState: true });
  });
</script>

<svelte:head>
  <title>QuantMate</title>
</svelte:head>

<section class="state-panel">검색기로 이동합니다.</section>

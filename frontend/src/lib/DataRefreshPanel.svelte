<script lang="ts">
  import {
    fetchManualDataRefreshJob,
    startManualDataRefresh,
    type DataFreshness,
    type ManualDataRefreshJob
  } from './api';

  export let freshness: DataFreshness | null = null;
  export let source = '';
  export let onCompleted: (() => void | Promise<void>) | null = null;

  let job: ManualDataRefreshJob | null = null;
  let error = '';
  let pollTimer: ReturnType<typeof setTimeout> | null = null;

  $: running = job?.status === 'queued' || job?.status === 'running';

  function clearPollTimer() {
    if (pollTimer) {
      clearTimeout(pollTimer);
      pollTimer = null;
    }
  }

  async function refreshData() {
    clearPollTimer();
    error = '';
    try {
      job = await startManualDataRefresh({
        refresh_instruments: true,
        refresh_daily_prices: true,
        markets: ['KOSPI', 'KOSDAQ'],
        lookback_days: 10
      });
      pollJob();
    } catch (err) {
      error = err instanceof Error ? err.message : '최신 데이터 갱신을 시작하지 못했습니다.';
    }
  }

  async function pollJob() {
    if (!job) return;
    try {
      job = await fetchManualDataRefreshJob(job.job_id);
      if (job.status === 'queued' || job.status === 'running') {
        pollTimer = setTimeout(pollJob, 1500);
        return;
      }
      clearPollTimer();
      if (job.status === 'completed' && onCompleted) {
        await onCompleted();
      }
    } catch (err) {
      clearPollTimer();
      error = err instanceof Error ? err.message : '최신 데이터 갱신 상태를 확인하지 못했습니다.';
    }
  }

  function formatSeconds(value: number | null) {
    if (value === null || value < 0) return '계산 중';
    const minutes = Math.floor(value / 60);
    const seconds = value % 60;
    if (minutes <= 0) return `${seconds}초`;
    return `${minutes}분 ${seconds}초`;
  }

  function freshnessTone(value: DataFreshness | null) {
    if (!value) return '확인 중';
    if (value.daily_price_status === 'current') return '최신';
    if (value.daily_price_status === 'stale') return '지연';
    if (value.daily_price_status === 'missing') return '없음';
    return value.daily_price_status;
  }
</script>

<section class="data-refresh-panel">
  <div class="data-refresh-summary">
    <div>
      <span>데이터 기준</span>
      <strong>
        {freshness?.latest_daily_price_date ?? job?.latest_daily_price_date ?? '확인 중'}
        <small>{freshnessTone(freshness)}</small>
      </strong>
      <p>
        기대 기준일 {freshness?.expected_daily_price_date ?? job?.expected_daily_price_date ?? '-'}
        {#if source} · {source}{/if}
      </p>
    </div>
    <button type="button" class="secondary" disabled={running} onclick={refreshData}>
      {running ? '갱신 중' : '최신 데이터 갱신'}
    </button>
  </div>

  {#if job}
    <div class="refresh-progress">
      <div class="progress-track" aria-label="데이터 갱신 진행률">
        <span style={`width: ${Math.max(3, Math.min(job.progress_pct, 100))}%`}></span>
      </div>
      <div class="refresh-progress-meta">
        <span>{job.stage} · {job.progress_pct}%</span>
        <span>
          {job.current_step}/{job.total_steps || '-'} 단계 · 저장 {job.saved_count.toLocaleString('ko-KR')}건
          · 경과 {formatSeconds(job.elapsed_seconds)}
          {#if running} · 예상 남은 시간 {formatSeconds(job.estimated_remaining_seconds)}{/if}
        </span>
      </div>
      <p>{job.message}</p>
      {#if job.warnings.length}
        <p class="refresh-warning">{job.warnings.join(' · ')}</p>
      {/if}
    </div>
  {/if}

  {#if freshness?.warnings?.length}
    <p class="refresh-warning">{freshness.warnings.join(' · ')}</p>
  {/if}

  {#if error}
    <p class="refresh-error">{error}</p>
  {/if}
</section>

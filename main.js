// main.js

let chart, lineSeries, chartData = [];

async function initChart() {
  chart = LightweightCharts.createChart(document.getElementById('chart-container'), {
    layout: { background: { color: '#0A0A0A' }, textColor: '#ffffff' },
    grid: { vertLines: { color: 'rgba(255,255,255,0.03)' }, horzLines: { color: 'rgba(255,255,255,0.03)' } },
    timeScale: { borderColor: '#1a1a1a', textColor: '#666666' },
    rightPriceScale: { borderColor: '#1a1a1a', textColor: '#666666', minValue: 0 },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal }
  });

  lineSeries = chart.addAreaSeries({
    lineColor: '#00E5FF',
    topColor: 'rgba(0,229,255,0.4)',
    bottomColor: 'rgba(0,229,255,0.0)',
    lineWidth: 2,
    crosshairMarkerVisible: true,
    crosshairMarkerRadius: 4,
    priceFormat: { type: 'price', precision: 2, minMove: 0.01 }
  });

  const response = await fetch('data/daily_scores.json');
  const rawData = await response.json();

  chartData = rawData.map(item => {
    const timeUnix = Math.floor(new Date(item.time + 'T00:00:00Z').getTime() / 1000);
    return { time: timeUnix, value: Number(item.value), ...(item.events ? { events: item.events } : {}) };
  });

  lineSeries.setData(chartData);
  lineSeries.setMarkers(chartData.filter(d => d.events).map(d => ({
    time: d.time, position: 'aboveBar', color: '#fff', shape: 'circle', text: ''
  })));

  chart.timeScale().fitContent();
  setupTimeControls();
  setupEventPopup();
  updateTimeRange('3M');
  setupLegend();
  loadTopMovers();
}

function setupLegend() {
  const container = document.getElementById('chart-container');
  const legend = document.querySelector('.chart-legend');
  const symbolName = 'Avg. Daily % Change – Top 10 on Polymarket';
  let latestValue = chartData.length ? chartData[chartData.length - 1].value.toFixed(2) + '%' : '';
  legend.innerHTML = `${symbolName} <strong>${latestValue}</strong>`;
  chart.subscribeCrosshairMove(param => {
    let priceFormatted = latestValue;
    if (param.time) {
      const data = param.seriesData.get(lineSeries);
      if (data && (data.value !== undefined || data.close !== undefined)) {
        const price = data.value !== undefined ? data.value : data.close;
        priceFormatted = price.toFixed(2) + '%';
      }
    }
    legend.innerHTML = `${symbolName} <strong>${priceFormatted}</strong>`;
  });
  window.addEventListener('resize', () => {
    chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
  });
}

function setupTimeControls() {
  const buttons = document.querySelectorAll('.time-controls button');
  buttons.forEach(button => {
    button.addEventListener('click', () => {
      buttons.forEach(b => b.classList.remove('active'));
      button.classList.add('active');
      updateTimeRange(button.dataset.range);
    });
  });
  document.querySelector('button[data-range="3M"]').classList.add('active');
}

function updateTimeRange(range) {
  if (!chartData.length) return;
  const last = new Date(chartData[chartData.length - 1].time * 1000);
  let start = new Date(last);
  if (range === '1M') start.setMonth(last.getMonth() - 1);
  else if (range === '3M') start.setMonth(last.getMonth() - 3);
  else if (range === '1Y') start.setFullYear(last.getFullYear() - 1);
  else if (range === 'ALL') { chart.timeScale().fitContent(); return; }
  chart.timeScale().setVisibleRange({
    from: Math.floor(start.getTime() / 1000),
    to: Math.floor(last.getTime() / 1000),
  });
}

async function loadTopMovers() {
  try {
    const todayStr = new Date().toISOString().split('T')[0];
    const top10Response = await fetch(`data/top10/${todayStr}.json`);
    if (top10Response.ok) {
      let top10Data = await top10Response.json();
      const originalOrder = top10Data.filter(m => m.priceChange !== undefined);
      const sortedMovers = [...originalOrder].sort((a, b) => Math.abs(b.priceChange) - Math.abs(a.priceChange));
      const moversList = document.getElementById('top-movers-list');
      moversList.innerHTML = '';
      sortedMovers.forEach((m) => {
        const origIndex = originalOrder.findIndex(x => x.question === m.question) + 1;
        let direction, arrowSvg = '';
        if (m.priceChange > 0) {
          direction = 'up';
          arrowSvg = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 4l6 8h-4v8h-4v-8h-4z"/></svg>';
        } else if (m.priceChange < 0) {
          direction = 'down';
          arrowSvg = '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 20l-6-8h4v-8h4v8h4z"/></svg>';
        } else {
          direction = 'neutral';
          arrowSvg = '';
        }
        moversList.innerHTML += `
          <div class="mover-item">
            <div class="mover-rank">#${origIndex}</div>
            <div class="mover-title">${m.question}</div>
            <div class="mover-change ${direction}">
              ${arrowSvg}<span>${m.priceChange.toFixed(2)}%</span>
            </div>
          </div>
        `;
      });
    } else {
      console.warn('No top10 data found for today.');
    }
  } catch (err) {
    console.error('Error loading top10 data:', err);
  }
}

function setupEventPopup() {
  const popup = document.getElementById('event-popup');
  const container = document.getElementById('chart-container');

  function showPopupAtPoint(point, time) {
    const eventData = chartData.find(d => d.time === time && d.events);
    if (eventData) {
      popup.innerHTML =
        eventData.events.map(e => {
          let arrowSvg, percentClass;
          if (e.value > 0) {
            arrowSvg = '<span class="arrow" style="color:#00FFA3;">' +
              '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 4l6 8h-4v8h-4v-8h-4z"/></svg></span>';
            percentClass = 'up';
          } else if (e.value < 0) {
            arrowSvg = '<span class="arrow" style="color:#FF4C4C;">' +
              '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 20l-6-8h4v-8h4v8h4z"/></svg></span>';
            percentClass = 'down';
          } else {
            arrowSvg = '<span class="arrow" style="color:#cccccc;">–</span>';
            percentClass = 'neutral';
          }
          return `
            <div class="event-card">
              <div class="event-title">${e.title}</div>
              <div class="event-value">
                <span class="percent-container">${arrowSvg}<span class="percent ${percentClass}">${e.value > 0 ? '+' : ''}${e.value}%</span></span>
                <div class="percent-bar-bg">
                  <div class="percent-bar-fill" style="width:${Math.abs(e.value)}%;"></div>
                </div>
              </div>
            </div>
          `;
        }).join('');
      const containerRect = container.getBoundingClientRect();
      const popupWidth = window.innerWidth < 600 ? 130 : 200;
      const margin = 10;
      let leftPos = point.x + popupWidth + margin > containerRect.width
        ? point.x - popupWidth - margin
        : point.x + margin;
      popup.style.left = `${leftPos}px`;
      popup.style.top = `${point.y}px`;
      popup.style.display = 'block';
    } else {
      popup.style.display = 'none';
    }
  }

  chart.subscribeCrosshairMove(param => {
    if ('ontouchstart' in window) return;
    if (!param.time || !param.point) {
      popup.style.display = 'none';
      return;
    }
    const paramTime = (typeof param.time === 'object')
      ? Math.floor(Date.UTC(param.time.year, param.time.month - 1, param.time.day) / 1000)
      : Math.floor(param.time);
    showPopupAtPoint(param.point, paramTime);
  });

  if ('ontouchstart' in window) {
    function updateMarkerHitboxes() {
      const timeScale = chart.timeScale();
      markerHitboxes = chartData.filter(d => d.events).map(d => {
        const px = timeScale.timeToCoordinate(d.time);
        return { time: d.time, x: px };
      });
    }
    chart.timeScale().subscribeVisibleLogicalRangeChange(updateMarkerHitboxes);
    updateMarkerHitboxes();
    container.addEventListener('touchstart', function(e) {
      if (!chartData.length) return;
      const rect = container.getBoundingClientRect();
      const x = e.touches[0].clientX - rect.left;
      const y = e.touches[0].clientY - rect.top;
      let nearest = null;
      let minDist = 9999;
      for (const m of markerHitboxes) {
        if (m.x == null) continue;
        const dist = Math.abs(m.x - x);
        if (dist < minDist && dist < 24) {
          minDist = dist;
          nearest = m;
        }
      }
      if (nearest) {
        showPopupAtPoint({ x: nearest.x, y: y }, nearest.time);
      } else {
        popup.style.display = 'none';
      }
    });
    document.body.addEventListener('touchstart', function(e) {
      if (!container.contains(e.target) && !popup.contains(e.target)) {
        popup.style.display = 'none';
      }
    }, { passive: true });
  }

  document.body.addEventListener('mousedown', function(e) {
    if (!container.contains(e.target) && !popup.contains(e.target)) {
      popup.style.display = 'none';
    }
  });
}

document.addEventListener('DOMContentLoaded', initChart);

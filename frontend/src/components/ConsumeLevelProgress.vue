&lt;!-- frontend/src/components/ConsumeLevelProgress.vue --&gt; &lt;template&gt; &lt;div
class="consume-level-progress"&gt; &lt;div class="level-labels"&gt; &lt;div v-for="(level, index) in
levels" :key="level.value" class="level-label" :class="{ active: currentLevelIndex &gt;= index,
current: currentLevel === level.value }" &gt; &lt;span class="level-badge"
:class="level.value.toLowerCase()"&gt;
{{ level.label }}
&lt;/span&gt; &lt;/div&gt; &lt;/div&gt; &lt;div class="progress-bar-container"&gt; &lt;div
class="progress-segments"&gt; &lt;div v-for="(segment, index) in segments" :key="index"
class="progress-segment" :class="segment.level.toLowerCase()" /&gt; &lt;/div&gt; &lt;div
class="progress-fill" :style="{ width: `${progress}%` }" /&gt; &lt;div class="progress-marker"
:style="{ left: `${progress}%` }"&gt; &lt;div class="marker-dot"
:class="currentLevel.toLowerCase()"&gt;&lt;/div&gt; &lt;/div&gt; &lt;/div&gt; &lt;div
class="level-info"&gt; &lt;div class="current-level"&gt; &lt;span
class="info-label"&gt;当前等级&lt;/span&gt; &lt;span class="level-value"
:class="currentLevel.toLowerCase()"&gt;
{{ getLevelLabel(currentLevel) }}
&lt;/span&gt; &lt;/div&gt; &lt;div v-if="nextLevel" class="next-level"&gt; &lt;span
class="info-label"&gt;下一等级&lt;/span&gt; &lt;span class="level-value"
:class="nextLevel.toLowerCase()"&gt;
{{ getLevelLabel(nextLevel) }}
&lt;/span&gt; &lt;/div&gt; &lt;div class="progress-percentage"&gt; &lt;span
class="percentage-value"&gt;{{ progress }}%&lt;/span&gt; &lt;/div&gt; &lt;/div&gt; &lt;/div&gt;
&lt;/template&gt; &lt;script setup lang="ts"&gt; import { computed } from 'vue' withDefaults(
defineProps&lt;{ currentLevel: string progress: number }&gt;(), {} ) const levels = [ { value: 'C',
label: 'C级' }, { value: 'B', label: 'B级' }, { value: 'A', label: 'A级' }, { value: 'KA', label:
'KA级' }, ] const segments = [ { level: 'C' }, { level: 'B' }, { level: 'A' }, { level: 'KA' }, ]
const currentLevelIndex = computed(() =&gt; levels.findIndex((l) =&gt; l.value === currentLevel) )
const nextLevel = computed(() =&gt; { const index = currentLevelIndex.value return index &lt;
levels.length - 1 ? levels[index + 1].value : null }) const getLevelLabel = (level: string) =&gt; {
return levels.find((l) =&gt; l.value === level)?.label || level } &lt;/script&gt; &lt;style
scoped&gt; .consume-level-progress { background: white; border-radius: 16px; padding: 24px; border:
1px solid var(--neutral-2, #eef0f3); } .level-labels { display: flex; justify-content:
space-between; align-items: center; margin-bottom: 16px; } .level-label { opacity: 0.4; transition:
opacity 200ms ease; } .level-label.active { opacity: 1; } .level-label.current .level-badge {
transform: scale(1.1); box-shadow: 0 0 0 3px rgba(3, 105, 161, 0.1); } .level-badge { display:
inline-flex; align-items: center; justify-content: center; width: 48px; height: 48px; border-radius:
50%; font-size: 14px; font-weight: 700; transition: all 200ms ease; } .level-badge.c { background:
#fff7e8; color: #f59e0b; } .level-badge.b { background: #e8f3ff; color: #3296f7; } .level-badge.a {
background: #e8ffea; color: #22c55e; } .level-badge.ka { background: #f3e8ff; color: #a855f7; }
.progress-bar-container { position: relative; height: 12px; border-radius: 6px; overflow: hidden;
background: var(--neutral-2, #eef0f3); } .progress-segments { position: absolute; top: 0; left: 0;
right: 0; bottom: 0; display: flex; } .progress-segment { flex: 1; opacity: 0.3; }
.progress-segment.c { background: #f59e0b; } .progress-segment.b { background: #3296f7; }
.progress-segment.a { background: #22c55e; } .progress-segment.ka { background: #a855f7; }
.progress-fill { position: absolute; top: 0; left: 0; height: 100%; background:
linear-gradient(90deg, #f59e0b 0%, #3296f7 33%, #22c55e 66%, #a855f7 100%); transition: width 300ms
cubic-bezier(0.4, 0, 0.2, 1); border-radius: 6px; } .progress-marker { position: absolute; top: 50%;
transform: translate(-50%, -50%); transition: left 300ms cubic-bezier(0.4, 0, 0.2, 1); } .marker-dot
{ width: 20px; height: 20px; border-radius: 50%; border: 3px solid white; box-shadow: 0 2px 8px
rgba(0, 0, 0, 0.15); transition: all 200ms ease; } .marker-dot.c { background: #f59e0b; }
.marker-dot.b { background: #3296f7; } .marker-dot.a { background: #22c55e; } .marker-dot.ka {
background: #a855f7; } .level-info { display: flex; justify-content: space-between; align-items:
center; margin-top: 20px; } .current-level, .next-level { display: flex; flex-direction: column;
gap: 4px; } .info-label { font-size: 12px; font-weight: 500; color: var(--neutral-5, #8f959e); }
.level-value { font-size: 18px; font-weight: 700; } .level-value.c { color: #f59e0b; }
.level-value.b { color: #3296f7; } .level-value.a { color: #22c55e; } .level-value.ka { color:
#a855f7; } .progress-percentage { text-align: right; } .percentage-value { font-size: 24px;
font-weight: 700; color: var(--neutral-10, #1d2330); } &lt;/style&gt;

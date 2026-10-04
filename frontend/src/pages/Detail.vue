<template>
  <div class="wall">
    <h1 class="serif">{{ w.title }}</h1>
    <p :class="{ sealed: noteMasked(w) }">{{ noteText(w) }}</p>
    <p v-if="w.note_revealed" class="tag">🎉 惊喜附言已揭晓</p>
    <p class="tag">状态 {{ w.status }} · 认领人 {{ w.claimer || '—' }}</p>
    <p v-if="err" class="err">{{ err }}</p>
    <input v-model="claimer" placeholder="你的名字" />
    <div style="display:flex;gap:8px;flex-wrap:wrap">
      <button @click="claim">认领锁定</button>
      <button class="ghost" @click="release">释放</button>
      <button class="ghost" @click="fulfill">核销完成</button>
    </div>

    <h2 class="serif">发布者改附言</h2>
    <p v-if="editFrozen" class="tag">{{ w.status === 'fulfilled' ? '已核销,附言已成最终历史,不可再改。' : '已认领未核销,封存附言冻结,核销成功后随揭晓放出。' }}</p>
    <p v-else-if="noteMasked(w)" class="tag">封存中,保存将整体替换附言;新句仍只显示封条,核销成功后才揭晓。</p>
    <textarea v-model="editNote" rows="3" placeholder="新附言" :disabled="editFrozen" />
    <label class="seal-opt">
      <input type="checkbox" v-model="editSeal" :disabled="editFrozen" />
      惊喜附言封存
    </label>
    <button class="ghost" @click="saveNote" :disabled="editFrozen">保存附言</button>
  </div>
</template>
<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../api'
import { noteMasked, noteText } from '../seal'
const props = defineProps({ id: String })
const w = ref({})
const claimer = ref('访客')
const err = ref('')
const editNote = ref('')
const editSeal = ref(false)
// 与后端 note_edit_allowed 同口径:fulfilled 一律冻结;封存行 claimed 期间冻结。
const editFrozen = computed(() => {
  const s = w.value.status
  return s === 'fulfilled' || (!!w.value.seal_note && s === 'claimed')
})
async function load() {
  w.value = await api('/wishes/' + props.id)
  // 封存未揭晓时后端不下发明文,编辑框留空即整体替换
  editNote.value = noteMasked(w.value) ? '' : (w.value.note || '')
  editSeal.value = !!w.value.seal_note
}
async function claim() {
  err.value=''; try { await api('/wishes/'+props.id+'/claim',{method:'POST',body:JSON.stringify({claimer:claimer.value})}); await load() } catch(e){ err.value=e.message }
}
async function release() {
  err.value=''; try { await api('/wishes/'+props.id+'/release',{method:'POST',body:'{}'}); await load() } catch(e){ err.value=e.message }
}
async function fulfill() {
  err.value=''; try { await api('/wishes/'+props.id+'/fulfill',{method:'POST',body:'{}'}); await load() } catch(e){ err.value=e.message }
}
async function saveNote() {
  err.value=''
  try {
    await api('/wishes/'+props.id+'/note',{method:'PATCH',body:JSON.stringify({note:editNote.value,seal_note:editSeal.value})})
    await load()
  } catch(e){ err.value=e.message }
}
onMounted(load)
</script>

<template>
  <div class="wall">
    <h1 class="serif">发愿望</h1>
    <input v-model="title" placeholder="标题" />
    <textarea v-model="note" rows="4" placeholder="备注" />
    <label class="seal-opt">
      <input type="checkbox" v-model="seal" />
      惊喜附言封存(核销后再揭晓,认领人提前也看不到)
    </label>
    <button @click="submit">发布</button>
  </div>
</template>
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
const router = useRouter()
const title = ref('')
const note = ref('')
const seal = ref(false)
async function submit() {
  const r = await api('/wishes', { method: 'POST', body: JSON.stringify({ title: title.value, note: note.value, seal_note: seal.value }) })
  router.push('/wishes/' + r.id)
}
</script>

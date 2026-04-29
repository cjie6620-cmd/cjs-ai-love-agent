<template>
  <div class="admin-page">
    <section class="admin-card">
      <div class="admin-card-header">
        <h2>知识库管理</h2>
        <div class="admin-toolbar">
          <input v-model="keyword" class="admin-input" placeholder="搜索标题或文件名" />
          <button class="admin-button" type="button" @click="load">查询</button>
          <button class="admin-button secondary" type="button" @click="reindexAll">全量重建</button>
        </div>
      </div>
      <div class="admin-card-body">
        <div class="admin-toolbar">
          <input class="admin-input" type="file" @change="handleFileChange" />
          <input v-model="category" class="admin-input" placeholder="分类" />
          <input v-model="source" class="admin-input" placeholder="来源" />
          <button class="admin-button" type="button" @click="uploadFile">上传文件</button>
        </div>
        <div class="text-index-box">
          <input v-model="textForm.title" class="admin-input" placeholder="文本标题" />
          <input v-model="textForm.source" class="admin-input" placeholder="文本来源" />
          <textarea v-model="textForm.text" class="admin-textarea" placeholder="粘贴要写入知识库的文本" />
          <button class="admin-button" type="button" @click="submitText">新增文本知识</button>
        </div>
        <div class="text-index-box">
          <input v-model="searchQuery" class="admin-input" placeholder="调试检索 query" />
          <button class="admin-button secondary" type="button" @click="runSearch">搜索知识</button>
        </div>
      </div>
    </section>

    <section v-if="searchResults.length" class="admin-card">
      <div class="admin-card-header"><h2>检索结果</h2></div>
      <div class="admin-card-body">
        <article v-for="item in searchResults" :key="item.chunk_id" class="search-result">
          <strong>{{ item.title || item.source }}</strong>
          <span>{{ item.score.toFixed(4) }}</span>
          <p>{{ item.content }}</p>
        </article>
      </div>
    </section>

    <section class="admin-card">
      <div class="admin-card-header"><h2>文档列表</h2></div>
      <div class="admin-table-wrap">
        <table class="admin-table">
          <thead>
            <tr>
              <th>标题</th>
              <th>分类</th>
              <th>状态</th>
              <th>Chunk</th>
              <th>来源</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="document in documents" :key="document.id">
              <td>{{ document.title || document.filename }}</td>
              <td>{{ document.category }}</td>
              <td><span :class="['status-pill', document.status]">{{ document.status }}</span></td>
              <td>{{ document.chunk_count }}</td>
              <td class="text-cell">{{ document.source }}</td>
              <td>
                <div class="admin-actions">
                  <button class="admin-button secondary" type="button" @click="reindexDocument(document.id)">重建</button>
                  <button class="admin-button danger" type="button" @click="deleteDocument(document.id)">删除</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import {
  deleteKnowledgeDocument,
  fetchKnowledgeDocuments,
  indexKnowledgeText,
  reindexAllKnowledge,
  reindexKnowledgeDocument,
  searchKnowledge,
  uploadKnowledgeFile,
} from '@/api/admin'
import type { KnowledgeDocument, KnowledgeSearchResult } from '@/types/admin'

const documents = ref<KnowledgeDocument[]>([])
const searchResults = ref<KnowledgeSearchResult[]>([])
const keyword = ref('')
const category = ref('relationship_knowledge')
const source = ref('')
const selectedFile = ref<File | null>(null)
const searchQuery = ref('')
const textForm = reactive({
  title: '',
  source: 'admin:text',
  text: '',
})

const load = async () => {
  documents.value = await fetchKnowledgeDocuments({ keyword: keyword.value })
}

const handleFileChange = (event: Event) => {
  selectedFile.value = (event.target as HTMLInputElement).files?.[0] ?? null
}

const uploadFile = async () => {
  if (!selectedFile.value) {
    return
  }
  await uploadKnowledgeFile({
    file: selectedFile.value,
    category: category.value,
    source: source.value,
  })
  selectedFile.value = null
  await load()
}

const submitText = async () => {
  if (!textForm.title.trim() || !textForm.text.trim()) {
    return
  }
  await indexKnowledgeText({
    title: textForm.title,
    text: textForm.text,
    category: category.value,
    source: textForm.source,
  })
  textForm.title = ''
  textForm.text = ''
  await load()
}

const reindexDocument = async (documentId: string) => {
  await reindexKnowledgeDocument(documentId)
  await load()
}

const reindexAll = async () => {
  await reindexAllKnowledge()
  await load()
}

const deleteDocument = async (documentId: string) => {
  await deleteKnowledgeDocument(documentId)
  await load()
}

const runSearch = async () => {
  if (!searchQuery.value.trim()) {
    return
  }
  const result = await searchKnowledge({
    query: searchQuery.value,
    category: category.value,
    top_k: 5,
  })
  searchResults.value = result.results
}

onMounted(() => {
  void load()
})
</script>

<style scoped>
.text-index-box {
  display: grid;
  gap: 8px;
  margin-top: 12px;
}

.search-result {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  padding: 12px 0;
  border-bottom: 1px solid #e7ecf1;
}

.search-result p {
  grid-column: 1 / -1;
  margin: 0;
  color: #526273;
}
</style>
